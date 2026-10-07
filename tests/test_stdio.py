"""Exercise actual MCP JSON-RPC framing through the installed server entrypoint."""
import importlib.util
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest


class StdioTests(unittest.TestCase):
    def exercise(self, openai=False):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, "RAJ_WORKSPACE": directory, "RAJ_UNO_PYTHON": sys.executable}
            command = [sys.executable, "-m", "raj_libreoffice.cli", "serve"]
            if openai:
                command.append("--openai")
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, env=env)
            responses = queue.Queue()

            def reader():
                for line in process.stdout:
                    responses.put(line)
                responses.put(None)

            threading.Thread(target=reader, daemon=True).start()

            def send(method, params, id=None):
                request = {"jsonrpc": "2.0", "method": method, "params": params}
                if id is not None:
                    request["id"] = id
                process.stdin.write(json.dumps(request) + "\n")
                process.stdin.flush()

            def receive(id):
                while True:
                    line = responses.get(timeout=15)
                    self.assertIsNotNone(line, "MCP process exited unexpectedly")
                    response = json.loads(line)
                    if response.get("id") == id:
                        self.assertNotIn("error", response, str(response))
                        return response["result"]

            try:
                send("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                    "clientInfo": {"name": "raj-integration", "version": "1"}}, 1)
                self.assertEqual(receive(1)["serverInfo"]["name"], "RAJ LibreOffice")
                send("notifications/initialized", {})
                send("tools/list", {}, 2)
                names = {x["name"] for x in receive(2)["tools"]}
                self.assertIn("document_create", names)
                self.assertNotIn("python_run", names)
                if openai:
                    self.assertIn("settings.read", names)
                send("tools/call", {"name": "status", "arguments": {}}, 3)
                result = receive(3)
                self.assertFalse(result.get("isError", False))
                self.assertFalse(result["structuredContent"]["result"]["connected"])
                send("resources/read", {"uri": "libreoffice://coverage"}, 4)
                self.assertIn("areas", json.loads(receive(4)["contents"][0]["text"]))
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                stderr = process.stderr.read()
                process.stdout.close()
                process.stderr.close()
                self.assertEqual(process.returncode, 0, stderr)

    def test_standard_stdio(self):
        self.exercise()

    @unittest.skipUnless(importlib.util.find_spec("openai_mcp_extensions"), "optional OpenAI SDK")
    def test_openai_stdio(self):
        self.exercise(openai=True)


if __name__ == "__main__":
    unittest.main()
