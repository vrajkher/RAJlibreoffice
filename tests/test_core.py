import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from raj_libreoffice.bridge import Bridge, OfficeError
from raj_libreoffice.config import Config, workspace_path
from raj_libreoffice.tools import DESCRIPTIONS, Step, register_tools, resolve_steps, tool_signature
from raj_libreoffice.worker import OPERATIONS, Office


class Recorder:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **kwargs):
        def add(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return add

    def resource(self, *args, **kwargs):
        return lambda fn: fn

    def prompt(self, *args, **kwargs):
        return lambda fn: fn


class FakeBridge:
    def __init__(self, root, **options):
        self.config = Config(Path(root), **options)
        self.lock = threading.RLock()
        self.calls = []

    def call(self, operation, **arguments):
        self.calls.append((operation, arguments))
        if operation == "document_create":
            return {"document": "doc_one"}
        if operation == "writer_insert" and arguments.get("text") == "fail":
            raise OfficeError("Simulated write failure")
        return arguments


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_paths_block_traversal_urls_and_symlinks(self):
        for path in ["../escape", "https://example.com/doc.odt", "file:///tmp/a"]:
            with self.assertRaises(ValueError):
                workspace_path(self.root, path)
        (self.root / "escape").symlink_to("/tmp")
        with self.assertRaises(ValueError):
            workspace_path(self.root, "escape/out.odt")
        self.assertEqual(workspace_path(self.root, "new.odt"), self.root / "new.odt")

    def test_all_worker_operations_have_tool_schemas(self):
        self.assertEqual(OPERATIONS, set(DESCRIPTIONS))
        for operation in OPERATIONS:
            signature = tool_signature(getattr(Office, operation))
            self.assertNotIn("self", signature.parameters)
            self.assertTrue(all(p.annotation is not p.empty for p in signature.parameters.values()))

    def register(self, **options):
        recorder = Recorder()
        bridge = FakeBridge(self.root, **options)
        enabled = register_tools(recorder, bridge, lambda **kwargs: kwargs)
        return recorder, bridge, enabled

    def test_advanced_tools_are_absent_by_default(self):
        recorder, _, enabled = self.register()
        for tool in ["python_run", "script_run", "uno_call", "uno_dispatch"]:
            self.assertNotIn(tool, enabled)
            self.assertNotIn(tool, recorder.tools)
        _, _, enabled = self.register(advanced=True, scripts=True, python_execution=True)
        self.assertEqual(enabled, OPERATIONS)

    def test_workflow_resolves_results_and_stops_on_error(self):
        recorder, bridge, _ = self.register()
        steps = [Step(id="new", tool="document_create", arguments={"kind": "writer"}),
                 Step(id="edit", tool="writer_insert", arguments={
                     "document": {"$step": "new", "path": ["document"]}, "text": "fail"}),
                 Step(id="save", tool="document_save", arguments={"document": "doc_one"})]
        result = recorder.tools["workflow_run"](steps)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(len(result["steps"]), 2)
        self.assertEqual(bridge.calls[1][1]["document"], "doc_one")
        self.assertFalse(result["atomic"])

    def test_workflow_validates_all_steps_before_execution(self):
        recorder, bridge, _ = self.register()
        with self.assertRaises(ValueError):
            recorder.tools["workflow_run"]([
                Step(id="a", tool="document_create", arguments={"kind": "writer"}),
                Step(id="b", tool="uno_call", arguments={"object": "a", "method": "store"})])
        self.assertEqual(bridge.calls, [])
        with self.assertRaises(TypeError):
            recorder.tools["workflow_run"]([Step(id="a", tool="writer_insert", arguments={})])
        self.assertEqual(bridge.calls, [])

    def test_workspace_listing_omits_external_symlinks(self):
        recorder, _, _ = self.register()
        (self.root / "report.odt").write_text("fixture")
        (self.root / "outside").symlink_to("/etc/passwd")
        result = recorder.tools["files_list"]()
        self.assertEqual([x["path"] for x in result["files"]], ["report.odt"])

    def test_worker_status_and_missing_pyuno_are_structured(self):
        # The MCP interpreter intentionally need not contain PyUNO.
        bridge = Bridge(Config(self.root, uno_python=sys.executable))
        try:
            result = bridge.call("status")
            self.assertFalse(result["connected"])
            with self.assertRaisesRegex(OfficeError, "PyUNO unavailable|LibreOffice|No such file"):
                bridge.call("document_create", kind="writer")
            self.assertFalse(bridge.call("status")["connected"])
        finally:
            bridge.close()

    def test_nested_workflow_references(self):
        result = resolve_steps({"data": [{"$step": "first", "path": ["rows", 0]}]},
                               {"first": {"rows": [[1, 2]]}})
        self.assertEqual(result, {"data": [[1, 2]]})


class StandardMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_schemas_resources_and_structured_call(self):
        try:
            from mcp.server.fastmcp import FastMCP
        except ImportError:
            self.skipTest("MCP 1 standard mode is covered in its separate CI job")
        from raj_libreoffice.server import create_server
        with tempfile.TemporaryDirectory() as directory:
            server, bridge = create_server(Config(Path(directory), uno_python=sys.executable))
            try:
                tools = await server.list_tools()
                names = {t.name for t in tools}
                self.assertEqual(len(names), 45)
                calc = next(t for t in tools if t.name == "calc_write")
                self.assertEqual(set(calc.inputSchema["required"]), {"document", "sheet", "range", "data"})
                resources = await server.list_resources()
                self.assertEqual(len(resources), 3)
                result = await server.call_tool("status", {})
                # MCP 1 returns content blocks and structured output as a tuple.
                self.assertIn("connected", result[1]["result"])
                error = await server.call_tool("files_list", {"directory": "../escape"})
                self.fail(f"Expected a ToolError, got {error}")
            except Exception as error:
                if "Path is outside RAJ_WORKSPACE" not in str(error):
                    raise
            finally:
                bridge.close()


if __name__ == "__main__":
    unittest.main()

