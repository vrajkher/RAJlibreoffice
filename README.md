# LibreOffice MCP

Let an AI assistant (Claude, ChatGPT, any MCP client) **create, read, edit and export LibreOffice documents**: Word-style text, spreadsheets, slides, drawings, databases and formulas.

```
 You ──ask──▶ AI assistant ──MCP──▶ libreoffice_mcp ──UNO──▶ LibreOffice (headless) ──▶ .docx .xlsx .pptx .pdf …
```

108 tools. Anything without a dedicated tool is reachable through the generic UNO tools.

## 1. Install (once)

```bash
sudo apt install libreoffice python3-uno     # LibreOffice + Python bindings
pip install "mcp>=2"
git clone https://github.com/vrajkher/RAJlibreoffice && cd RAJlibreoffice
```

Use the system `python3` (the one that can `import uno`).

## 2. Connect your AI client (once)

Add this to Claude Desktop's config or your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "libreoffice": {
      "command": "python3",
      "args": ["-m", "libreoffice_mcp"],
      "cwd": "/path/to/RAJlibreoffice"
    }
  }
}
```

Restart the client. LibreOffice starts by itself in the background when first needed.

## 3. Use it: the same 5 steps every time

```
 1 OPEN ─▶ 2 LOOK ─▶ 3 EDIT ─▶ 4 VERIFY ─▶ 5 SAVE
```

| Step | What happens | Tools |
|---|---|---|
| 1 Open | Create a blank file or open one; you get a `doc_id` | `create_document`, `open_document` |
| 2 Look | Read what is in it | `document_info`, `writer_get_text`, `calc_get_range`, `impress_list_slides` |
| 3 Edit | Change it | `writer_*`, `calc_*`, `impress_*` |
| 4 Verify | Read it back or render it | same read tools, `export_pdf`, `impress_export_slide` |
| 5 Save | Format comes from the extension | `save_document_as`, `close_document` |

Just talk to the assistant, for example:

> "Create a Word document with a title, three paragraphs about our Q3 results, and a table of regional sales. Save it as `~/q3.docx` and a PDF."

> "Open `~/budget.xlsx`, add a Total row with SUM formulas, bold the header, and add a column chart."

> "Make a 5-slide deck on our roadmap with speaker notes and save it as `~/roadmap.pptx`."

Not sure where to start? Ask it to call `lo_guide`. Full walkthrough with examples: **[docs/HOW_TO_USE.md](docs/HOW_TO_USE.md)**.

## What it covers

| Area | Highlights |
|---|---|
| Documents | open, create, save-as odt/docx/rtf/html/epub/ods/xlsx/csv/odp/pptx/png/svg, PDF export (page range, password), metadata, undo |
| Writer (31) | text, styles, find/replace, formatting, tables, lists, images, headers/footers, page setup, TOC, bookmarks, comments, footnotes, track changes |
| Calc (22) | sheets, ranges, formulas, number formats, borders, sort, filters, validation, conditional formats, charts, pivot tables, named ranges |
| Impress / Draw (21) | slides, layouts, shapes, text, images, tables, notes, transitions, backgrounds, export |
| Base / Math (7) | SQL on databases; formulas, also embedded in Writer |
| Generic UNO (13) | call/get/set any property or method, run `.uno:` commands, macros, Python snippets |

## ChatGPT features (optional)

`pip install openai-mcp-extensions` adds [OpenAI MCP Extensions](https://github.com/openai/mcp-extensions): `@`-mention open documents in the composer and open office files directly from ChatGPT.

## Check it works

```bash
python3 tests/run.py test_stage1 test_writer test_calc test_impress   # live LibreOffice tests
python3 tests/e2e_stdio.py                                            # full MCP round trip
```

## Good to know

- Math and Base are untested here (their LibreOffice packages were not installed): `apt install libreoffice-math libreoffice-base`.
- `run_python` / `run_macro` run code with your user's rights. Only connect clients you trust.
- Settings via environment: `LO_MCP_PORT` (default 2002), `LO_MCP_SOFFICE`, `LO_MCP_PROFILE`. Remote use: `python3 -m libreoffice_mcp --transport streamable-http`.

MIT licensed.
