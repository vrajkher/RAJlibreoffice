"""Native OpenAI extensions using openai/mcp-extensions' Python SDK.

Requires MCP 2 beta. Kept separate so standard MCP 1 clients remain supported.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_format: str = Field(title="Default output format", min_length=1, max_length=12)
    export_pdf_after_save: bool = Field(title="Export a PDF after saving")


def make_openai_server(bridge):
    try:
        from mcp.server.mcpserver import MCPServer
        from mcp.server.mcpserver.context import Context
        from mcp_types import ResourceLink, ToolAnnotations
        from openai_mcp_extensions import (
            OpenAIExtensions, OpenAIMentionSearchParams, OpenAIMentionSearchResult,
            OpenAISettings,
        )
    except ImportError as error:
        raise RuntimeError(
            "OpenAI mode needs pip install --pre '.[openai]' in a separate environment; "
            "the extensions SDK requires MCP 2 beta."
        ) from error

    import json
    import threading
    preferences_file = bridge.config.workspace / ".raj-preferences.json"
    settings_lock = threading.RLock()

    def load():
        if preferences_file.exists():
            return Preferences.model_validate_json(preferences_file.read_text())
        return Preferences(default_format="odt", export_pdf_after_save=False)

    extensions = OpenAIExtensions()
    settings = OpenAISettings(schema=Preferences)

    def read_settings(context):
        with settings_lock:
            return load()

    def update_settings(set, context):
        with settings_lock:
            values = Preferences.model_validate({**load().model_dump(), **set})
            temporary = preferences_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(values.model_dump()), encoding="utf-8")
            temporary.replace(preferences_file)
            return values

    settings.read(read_settings)
    settings.update(update_settings)

    def mentions(params, context):
        items = []
        root = bridge.config.workspace
        for path in sorted(root.iterdir()):
            resolved = path.resolve()
            if root not in resolved.parents or not resolved.is_file() or path.name.startswith("."):
                continue
            if params.query.lower() not in path.name.lower():
                continue
            items.append(ResourceLink(uri="libreoffice://file/" + quote(path.name, safe=""),
                                      name=path.name, title=path.name))
            if len(items) == 50:
                break
        return OpenAIMentionSearchResult(items=items)

    # Assign real runtime types: these are local imports and postponed
    # annotations cannot resolve them in the SDK's signature inspection.
    mentions.__annotations__ = {"params": OpenAIMentionSearchParams,
                                "context": Context[Any, Any],
                                "return": OpenAIMentionSearchResult}
    extensions.mentions.search(mentions)
    server = MCPServer("RAJ LibreOffice", extensions=[extensions, settings],
                       middleware=[settings.advertise_legacy_capability])

    @server.tool()
    def document_save_preferred(document: str, path: str, overwrite: bool = False) -> dict[str, Any]:
        """Save with native OpenAI preferences and optionally export a neighboring PDF.

        Standard document_save always uses its own explicit format arguments.
        """
        from pathlib import Path
        with settings_lock:
            preferences = load()
        output = str(Path(path).with_suffix("." + preferences.default_format))
        result = bridge.call("document_save", document=document, path=output,
                             format=preferences.default_format, overwrite=overwrite)
        if preferences.export_pdf_after_save:
            result["pdf"] = bridge.call("document_save", document=document,
                                        path=str(Path(path).with_suffix(".pdf")),
                                        format="pdf", overwrite=overwrite, export=True)
        return {"result": result}

    @server.resource("libreoffice://file/{name}")
    def mentioned_file(name: str) -> str:
        from urllib.parse import unquote
        from .config import workspace_path
        path = workspace_path(bridge.config.workspace, unquote(name), exists=True)
        return json.dumps({"path": str(path.relative_to(bridge.config.workspace)),
                           "bytes": path.stat().st_size,
                           "next_tool": "document_open"})

    return server, ToolAnnotations

