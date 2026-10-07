"""Optional OpenAI MCP Extensions integration (https://github.com/openai/mcp-extensions).

Adds ChatGPT-native behaviour when `openai-mcp-extensions` is installed:
  * composer @mentions: type @ in ChatGPT to pick an open LibreOffice document
  * file entrypoint: opening an office file in ChatGPT routes it to `open_chatgpt_file`
The server runs unchanged without the package; install with `pip install openai-mcp-extensions`.
"""
from typing import Any

from . import bridge as b
from .tools import documents as docs

FILE_TYPES = [".odt", ".ods", ".odp", ".odg", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".rtf"]


def _build():
    from mcp.server.mcpserver.context import Context
    from mcp_types import ResourceLink
    from openai_mcp_extensions import (OpenAIExtensions, OpenAIFileEntrypoint, OpenAIMentionSearchParams,
                                       OpenAIMentionSearchResult, OpenAIUiToolMetadata, get_resource_path)

    ext = OpenAIExtensions()

    @ext.mentions.search
    async def search_mentions(params: OpenAIMentionSearchParams, context: Context[Any, Any]) -> OpenAIMentionSearchResult:
        q = params.query.lower()
        items = [ResourceLink(uri=f"libreoffice://{d['doc_id']}", name=d["title"] or d["doc_id"], description=f"{d['kind']} document ({d['doc_id']})")
                 for d in docs.list_documents() if q in (d["title"] or "").lower() or q in d["doc_id"]]
        return OpenAIMentionSearchResult(items=items[:20])

    def open_chatgpt_file(context: Context[Any, Any]) -> dict:
        """Open the file the user selected in ChatGPT and return its doc_id."""
        path = get_resource_path(context.request_context.meta)
        if not path:
            raise b.LOError("No file was provided by the host. Use open_document(path) instead.")
        return docs.open_document(path)

    meta = {"openai/ui": OpenAIUiToolMetadata(entrypoints=[OpenAIFileEntrypoint(extensions=FILE_TYPES)]).model_dump(by_alias=True, exclude_none=True)}
    return ext, [(open_chatgpt_file, {"meta": meta})]


_cache = None


def load():
    """Return (extensions, extra_tools) or ([], []) when the SDK is unavailable."""
    global _cache
    if _cache is None:
        try:
            ext, tools = _build()
            _cache = ([ext], tools)
        except ImportError:
            _cache = ([], [])  # SDK not installed: optional layer stays off
    return _cache


def extensions():
    return load()[0]


def extra_tools():
    return load()[1]
