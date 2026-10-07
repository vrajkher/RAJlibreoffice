from __future__ import annotations

from .bridge import Bridge
from .config import Config
from .tools import register_tools


def create_server(config: Config | None = None, *, openai: bool = False):
    config = config or Config.from_env()
    config.workspace.mkdir(parents=True, exist_ok=True)
    bridge = Bridge(config)
    if openai:
        from .openai import make_openai_server
        server, annotation_class = make_openai_server(bridge)
    else:
        try:
            from mcp.server.fastmcp import FastMCP
            from mcp.types import ToolAnnotations
        except ImportError as error:
            raise RuntimeError("Standard mode requires MCP 1.x; use the standard installation") from error
        server = FastMCP("RAJ LibreOffice", host="127.0.0.1", instructions=(
            "Use document_create/open → read/edit → document_save → document_close. "
            "Read libreoffice://guide for typed UNO values and workflow references. "
            "Do not claim universal tested coverage: consult libreoffice://coverage."
        ))
        annotation_class = ToolAnnotations
    register_tools(server, bridge, annotation_class)
    return server, bridge

