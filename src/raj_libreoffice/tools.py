from __future__ import annotations

import inspect
import json
from functools import wraps
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .bridge import Bridge, OfficeError
from .config import workspace_path
from .worker import OPERATIONS, Office
from .features import FEATURES


DESCRIPTIONS = {
    "status": "Check connection, workspace, open documents and capability settings. Does not start Office.",
    "document_create": "Create a Writer, Calc, Impress, Draw, Math or Base document. Returns its document handle.",
    "document_open": "Open a workspace file. Automatic macros and link updates are disabled. Returns a document handle.",
    "document_list": "List documents opened by this server. Handles are valid until close or worker restart.",
    "document_info": "Inspect document type, location, modified status and UNO services.",
    "document_save": "Save or export a document. Supply a path on first save. Set overwrite explicitly to replace a file. Embedded Base writes require commit/rollback, then save before connection close.",
    "document_close": "Close a document. Unsaved changes require discard=true. Invalidates its object handles.",
    "document_metadata": "Read or update Title, Subject, Description, Author, Keywords and Language.",
    "document_undo": "Undo the last undoable operation, or redo. UNO operations do not all support undo.",
    "filter_list": "Discover installed import/export filter names, optionally filtered by query.",
    "writer_read": "Read a bounded slice of the Writer body text; offsets are zero-based.",
    "writer_insert": "Insert text at a zero-based character position, or append. Optional UNO character/paragraph properties.",
    "writer_replace": "Replace Writer body matches, with optional regular expressions and case sensitivity.",
    "writer_format": "Apply UNO character and paragraph properties to a Writer text selection.",
    "writer_table": "Insert a rectangular Writer table from data and return its UNO object handle.",
    "writer_bookmark": "Insert a named bookmark at a zero-based body-text position.",
    "writer_field": "Insert a com.sun.star.text.TextField.* field with typed UNO properties.",
    "writer_image": "Embed a workspace image in Writer. Size uses hundredths of a millimetre.",
    "style_list": "Discover document style families or styles in a named family.",
    "style_update": "Modify properties of an existing named style in a document style family.",
    "calc_sheets": "List, add, remove, rename, move or copy Calc sheets. Sheet indexes are zero-based.",
    "calc_read": "Read values or formulas from an A1 Calc range. Sheet may be name or zero-based index.",
    "calc_write": "Write a rectangular array matching an A1 range. Formula mode requires strings; values use strings/numbers.",
    "calc_format": "Apply cell properties and optional number-format code to an A1 range.",
    "calc_merge": "Merge or unmerge a rectangular Calc range.",
    "calc_clear": "Clear Calc range contents using CellFlags; default 1023 clears all supported content flags.",
    "calc_recalculate": "Recalculate all formulas in a Calc document.",
    "calc_chart": "Create an embedded chart from an A1 range. First row/column are labels. Returns chart handle.",
    "calc_named_range": "Define a Calc named range or expression with a zero-based reference address.",
    "calc_sort": "Sort a Calc range by a zero-based column offset within that range.",
    "presentation_pages": "List, insert or remove Impress slides or Draw pages using zero-based indexes.",
    "presentation_shape": "Add text, rectangle, ellipse, line, image, connector, polygon, polyline, Bezier, custom or OLE shape to an Impress/Draw page.",
    "presentation_read": "Read page shapes and their text; returns live UNO object handles for editing.",
    "presentation_notes": "Read or replace an Impress slide's notes text.",
    "math_formula": "Read or replace a Math formula using StarMath notation.",
    "base_connect": "Open an isolated Base/SDBC connection, optionally requesting read-only mode. Returns connection handle.",
    "base_tables": "List tables visible through a Base/SDBC connection.",
    "base_query": "Execute parameterized SQL with bounded results. write=true executes an update; connection state is preserved.",
    "base_transaction": "Begin, commit, rollback, restore autocommit, or close a Base connection. For embedded data: commit/rollback, document_save while connected, then close.",
    "uno_inspect": "Discover an object's UNO services, property types and method signatures without invoking methods.",
    "uno_get": "ADVANCED: read a UNO property or attribute and return typed values or a live object handle.",
    "uno_set": "ADVANCED: set UNO properties/struct fields using typed JSON values.",
    "uno_call": "ADVANCED: invoke any public UNO method. Encode structs, enums, sequences, Any and references as typed JSON.",
    "uno_service": "ADVANCED: instantiate a global or document-scoped UNO service, with optional constructor arguments.",
    "uno_services": "Discover available UNO services in the connected LibreOffice installation.",
    "uno_type": "Inspect SDK runtime type information, struct members and enum values by qualified UNO type name.",
    "uno_dispatch": "ADVANCED: run a .uno: command against a document frame. Some commands need a visible GUI.",
    "script_run": "TRUSTED CODE: invoke an installed Basic/Python script URI; requires advanced and script execution settings.",
    "python_run": "TRUSTED CODE: execute Python with uno, context, desktop and document; assign result. Not sandboxed.",
    "handles_release": "Release temporary UNO object handles; close documents with document_close instead.",
}

DESCRIPTIONS.update(FEATURES)

ADVANCED = {"uno_get", "uno_set", "uno_call", "uno_service", "uno_dispatch", "script_run", "python_run", "writer_mail_merge"}
READ_ONLY = {"status", "document_list", "document_info", "filter_list", "writer_read", "style_list",
             "calc_read", "presentation_read", "base_tables", "uno_inspect", "uno_services", "uno_type"}


def expected_errors(fn):
    """Expose actionable domain errors using the SDK's public ToolError seam."""
    @wraps(fn)
    def invoke(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (OfficeError, ValueError, TypeError, OSError) as error:
            try:
                from mcp.server.fastmcp.exceptions import ToolError
            except ImportError:
                from mcp.server.mcpserver.exceptions import ToolError
            raise ToolError(str(error)) from error
    return invoke

STRING_ARGS = {"document", "path", "kind", "search", "replacement", "family", "name", "range",
               "action", "new_name", "number_format", "content", "formula", "connection", "user",
               "password", "sql", "object", "method", "service", "command", "uri", "code", "query",
               "image_path", "format", "text", "style", "author", "parent", "cell", "output",
               "diagram", "title", "subtitle", "node", "word", "language", "country",
               "formula_cell", "variable_cell", "target", "header", "footer", "comment", "filter_name",
               "template", "database", "table", "output_directory", "prefix", "objective"}
DICT_ARGS = {"properties", "values", "options", "background", "printer"}


def tool_signature(method):
    parameters = []
    for name, param in inspect.signature(method).parameters.items():
        if name == "self":
            continue
        if name == "sheet":
            annotation = str | int
        elif name == "data":
            annotation = list[list[Any]]
        elif name in {"arguments", "parameters", "fields", "entries", "columns", "variables", "constraints"}:
            annotation = list[Any]
        elif name == "indexes":
            annotation = list[int]
        elif name in {"record", "visible", "legend"}:
            annotation = bool
        elif name == "handles":
            annotation = list[str]
        elif name in DICT_ARGS:
            annotation = dict[str, Any]
        elif isinstance(param.default, bool):
            annotation = bool
        elif name in STRING_ARGS or (name == "column" and method.__name__ == "writer_database_field"):
            annotation = str
        else:
            annotation = int
        if param.default is None:
            annotation = annotation | None
        parameters.append(param.replace(annotation=annotation))
    return inspect.Signature(parameters, return_annotation=dict[str, Any])


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


def resolve_steps(value, completed):
    if isinstance(value, dict):
        if "$step" in value:
            result = completed[value["$step"]]
            for part in value.get("path", []):
                result = result[part]
            return result
        return {k: resolve_steps(v, completed) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_steps(v, completed) for v in value]
    return value


def register_tools(server, bridge: Bridge, annotation_class):
    enabled = set(OPERATIONS)
    if not bridge.config.advanced:
        enabled -= ADVANCED
    if not bridge.config.scripts:
        enabled.discard("script_run")
    if not bridge.config.python_execution:
        enabled.discard("python_run")

    def create_tool(operation):
        signature = tool_signature(getattr(Office, operation))

        def tool(**kwargs):
            signature.bind(**kwargs)
            return {"result": bridge.call(operation, **kwargs)}

        tool.__name__ = operation
        tool.__doc__ = DESCRIPTIONS[operation]
        tool.__signature__ = signature
        tool.__annotations__ = {p.name: p.annotation for p in signature.parameters.values()}
        tool.__annotations__["return"] = dict[str, Any]
        return expected_errors(tool)

    for operation in sorted(enabled):
        annotations = annotation_class(**{
            "readOnlyHint": operation in READ_ONLY,
            "destructiveHint": operation not in READ_ONLY,
            "openWorldHint": operation in ADVANCED or operation.startswith("base_"),
        })
        server.tool(name=operation, annotations=annotations)(create_tool(operation))

    @server.tool()
    def workflow_run(steps: list[Step], stop_on_error: bool = True) -> dict[str, Any]:
        """Run up to 50 ordered steps. Reference prior result with {$step: id, path: [key]}.

        Runs sequentially, not atomically. Reports completed steps and errors; does
        not roll back changes. Step references point to each operation's result,
        without the MCP tool's outer result envelope.
        """
        if not 1 <= len(steps) <= 50:
            raise ValueError("Supply between 1 and 50 workflow steps")
        ids = set()
        for step in steps:
            if step.id in ids:
                raise ValueError("Step IDs must be unique")
            ids.add(step.id)
            if step.tool not in enabled:
                raise ValueError(f"Unavailable workflow tool: {step.tool}")
            tool_signature(getattr(Office, step.tool)).bind(**step.arguments)
        completed, results = {}, []
        with bridge.lock:
            for step in steps:
                try:
                    arguments = resolve_steps(step.arguments, completed)
                    result = bridge.call(step.tool, **arguments)
                    completed[step.id] = result
                    results.append({"id": step.id, "result": result})
                except Exception as error:
                    results.append({"id": step.id, "error": str(error)})
                    if stop_on_error:
                        break
        return {"steps": results, "atomic": False,
                "completed": len(completed), "requested": len(steps)}

    @server.tool(annotations=annotation_class(**{"readOnlyHint": True}))
    @expected_errors
    def files_list(directory: str = ".", query: str = "", limit: int = 100) -> dict[str, Any]:
        """List immediate workspace files and folders. Uses local filenames, not remote URLs."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        root = workspace_path(bridge.config.workspace, directory)
        if not root.is_dir():
            raise ValueError("Directory does not exist")
        files = []
        for file in sorted(root.iterdir()):
            if query.lower() not in file.name.lower():
                continue
            try:
                safe = workspace_path(bridge.config.workspace, str(file))
            except ValueError:
                continue
            files.append({"path": str(file.relative_to(bridge.config.workspace)),
                          "directory": safe.is_dir(), "bytes": safe.stat().st_size})
            if len(files) == limit:
                break
        return {"files": files}

    @server.resource("libreoffice://guide")
    def guide() -> str:
        return (
            "1. files_list or document_create. 2. document_open if needed. "
            "3. Read/modify using the returned document handle. 4. document_save. "
            "5. document_close. Tool responses wrap the operation in result. "
            "Offsets, sheet and page indexes are zero-based. Sizes use 1/100 mm. "
            "Advanced tools: uno_inspect → uno_get/uno_call → uno_set. "
            "Typed values: {$ref: handle}, {$enum: type, value: name}, "
            "{$struct: type, fields: {...}}, {$properties: {...}}, "
            "{$any: type, value: ...}, {$type: type}, {$bytes: base64}. "
            "workflow_run is ordered but not atomic. Save explicitly."
        )

    @server.resource("libreoffice://tools")
    def catalog() -> str:
        return json.dumps({k: DESCRIPTIONS[k] for k in sorted(enabled)}, indent=2)

    @server.resource("libreoffice://coverage")
    def coverage() -> str:
        return Path(__file__).with_name("coverage.json").read_text()

    @server.prompt()
    def edit_document(path: str, task: str) -> str:
        """A simple inspect → edit → verify → save document workflow."""
        return (
            f"Open {path!r} with document_open. Inspect its type and read relevant content. "
            f"Carry out this task: {task}. Read back changed content to verify it. "
            "Save to an appropriate workspace path. Report the output path and any failures. "
            "For advanced features inspect UNO signatures before calling methods."
        )

    return enabled

