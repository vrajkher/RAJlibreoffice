"""MCP server entry point: registers every tool module."""
import argparse
import importlib

from mcp.server.mcpserver import MCPServer

MODULES = ["guide", "documents", "generic", "writer", "calc", "impress", "base_math"]


def build():
    extensions = []
    try:
        from .openai_ext import extensions as ext
        extensions = ext()
    except Exception:
        pass
    server = MCPServer("libreoffice", instructions="Call lo_guide first. Open or create a document, edit it with the writer_/calc_/impress_ tools, then save it.", extensions=extensions)
    for name in MODULES:
        try:
            mod = importlib.import_module(f".tools.{name}", __package__)
        except ModuleNotFoundError as e:
            if e.name and e.name.endswith(f"tools.{name}"):
                continue
            raise
        for fn in mod.TOOLS:
            server.add_tool(fn)
    return server


def main():
    ap = argparse.ArgumentParser(description="LibreOffice MCP server")
    ap.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = ap.parse_args()
    build().run(args.transport)


if __name__ == "__main__":
    main()
