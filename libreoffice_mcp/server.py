"""MCP server entry point: registers every tool module."""
import argparse
import functools
import sys
import importlib

from mcp.server.mcpserver import MCPServer

from .bridge import LOError

def _safe(fn):
    """Surface UNO and Python errors to the client as readable tool errors."""
    @functools.wraps(fn)
    def run(*a, **kw):
        try:
            return fn(*a, **kw)
        except LOError:
            raise
        except Exception as e:
            raise LOError(f"{fn.__name__} failed: {type(e).__name__}: {str(e)[:600]}")
    return run


MODULES = ["guide", "documents", "generic", "writer", "calc", "impress", "base_math"]


def build():
    extensions = []
    try:
        from .openai_ext import extensions as ext
        extensions = ext()
    except Exception as e:
        print(f"[libreoffice-mcp] OpenAI extensions disabled: {e}", file=sys.stderr)
    server = MCPServer("libreoffice", instructions="Call lo_guide first. Open or create a document, edit it with the writer_/calc_/impress_ tools, then save it.", extensions=extensions)
    for name in MODULES:
        try:
            mod = importlib.import_module(f".tools.{name}", __package__)
        except ModuleNotFoundError as e:
            if e.name and e.name.endswith(f"tools.{name}"):
                continue
            raise
        for fn in mod.TOOLS:
            server.add_tool(_safe(fn))
    try:
        from .openai_ext import extra_tools
        for fn, kw in extra_tools():
            server.add_tool(_safe(fn), **kw)
    except Exception as e:
        print(f"[libreoffice-mcp] OpenAI file entrypoint disabled: {e}", file=sys.stderr)
    return server


def main():
    ap = argparse.ArgumentParser(description="LibreOffice MCP server")
    ap.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    args = ap.parse_args()
    build().run(args.transport)


if __name__ == "__main__":
    main()
