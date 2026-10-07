# LibreOffice MCP

An MCP server that lets Claude, ChatGPT or any MCP client read, write and modify LibreOffice documents (Writer, Calc, Impress, Draw, plus Base and Math) through the UNO API. 106 tools; everything else is reachable through the generic UNO tools.

## Quick start

```bash
sudo apt install libreoffice python3-uno        # LibreOffice + UNO bindings (use the system python3)
pip install "mcp>=2"
python3 -m libreoffice_mcp                      # stdio server; soffice is started headless on demand
```

Claude Desktop / Claude Code (`.mcp.json`):

```json
{ "mcpServers": { "libreoffice": { "command": "python3", "args": ["-m", "libreoffice_mcp"], "cwd": "/path/to/RAJlibreoffice" } } }
```

`python3` must be the interpreter that can `import uno` (on Debian/Ubuntu: `/usr/bin/python3`). Options: `--transport streamable-http|sse`; env `LO_MCP_PORT` (2002), `LO_MCP_SOFFICE`, `LO_MCP_PROFILE`.

## How to use it: always the same 5 steps

1. **OPEN** `create_document(kind)` or `open_document(path)` returns a `doc_id`
2. **LOOK** `document_info`, `writer_get_text`, `calc_get_range`, `impress_list_slides`
3. **EDIT** the `writer_*`, `calc_*`, `impress_*` tools
4. **VERIFY** read back, or `export_pdf`
5. **SAVE** `save_document_as(doc_id, "out.docx")` (format from the extension), then `close_document`

Call `lo_guide()` first; `lo_guide("writer" | "calc" | "impress" | "uno" | "tips")` lists the tools for each area.

## What is covered

| Area | Tools |
|---|---|
| Documents | open/create/save/save-as (odt, docx, doc, rtf, txt, html, epub, ods, xlsx, xls, csv, odp, pptx, ppt, odg, png, jpg, svg), PDF export (page range, password), metadata, undo/redo |
| Writer (31) | text, paragraphs, styles (create/apply), find/replace (regex), char+paragraph formatting, tables, lists, images, page setup, headers/footers/page numbers, page breaks, TOC, bookmarks, comments, footnotes/endnotes, track changes, fields, outline |
| Calc (22) | sheets, read/write ranges and formulas, formatting + number formats + borders, merge, sort, autofilter, validation, conditional formats, charts, pivot tables, named ranges, freeze, sizes, find/replace, protect, hyperlinks |
| Impress / Draw (21) | slides, layouts, shapes (incl. star, arrow, callout…), text, images, tables, z-order, notes, transitions, backgrounds, masters, slide export |
| Base / Math (7) | create/open databases, list tables, SQL query/execute; Math formulas and embedding into Writer |
| Generic UNO (13) | `uno_root/create/call/get/set/inspect/enumerate`, `dispatch_command('.uno:…')`, `run_macro`, `run_python`: the escape hatch for the rest of the SDK |

Colours: `#RRGGBB`, names, or ints. Lengths are mm in the friendly tools and 1/100 mm in raw UNO. Indices are 0-based.

## OpenAI MCP Extensions (optional)

With `pip install openai-mcp-extensions` ([openai/mcp-extensions](https://github.com/openai/mcp-extensions)) the server also registers ChatGPT composer **@mentions** for open documents and a **file entrypoint** (`open_chatgpt_file`) for office file types. Without the package it runs unchanged.

## Testing and known limits

```bash
python3 tests/run.py            # live tests against headless LibreOffice (Writer, Calc, Impress/Draw)
python3 tests/e2e_stdio.py      # spawns the server and drives it with an MCP client
```

- **Math and Base are untested**: the machine used for development had no `libreoffice-math` or full Base package. The tools skip with a clear error when a module is missing.
- **The OpenAI extension layer is untested**: its package could not be installed in the development sandbox; it was written against the SDK source and README.
- `run_python` and `run_macro` execute arbitrary code with your user's rights; expose this server only to clients you trust.
- Tools target headless operation; slideshow start and other UI actions may need a visible window.
