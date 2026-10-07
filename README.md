# RAJ LibreOffice MCP

[![LibreOffice MCP tests](https://github.com/vrajkher/RAJlibreoffice/actions/workflows/test.yml/badge.svg)](https://github.com/vrajkher/RAJlibreoffice/actions/workflows/test.yml)

A Python MCP server that reads, creates, edits and exports LibreOffice documents through **UNO**. It includes simple tools for Writer, Calc, Impress, Draw, Math and Base, a reusable workflow runner, and an advanced bridge to LibreOffice's installed UNO API and SDK type information.

OpenAI integration uses the official [`openai/mcp-extensions`](https://github.com/openai/mcp-extensions) Python package for composer mentions and native settings. It is an optional MCP 2 mode; standard MCP supports MCP 1 and MCP 2.

**Scope:** this is a broad automation foundation, not a claim that every LibreOffice feature is implemented and tested. Dedicated tools cover common workflows. The generic UNO bridge reaches additional APIs supported by the installed LibreOffice, extensions and drivers. GUI dialogs, signatures, accessibility, rendering fidelity, some presentation commands and operating-system integrations require further validation. See [coverage](docs/COVERAGE.md).

## Start in three steps

Ubuntu/Debian:

```bash
# 1. Install LibreOffice and its matching Python UNO bindings.
sudo apt-get update
sudo apt-get install libreoffice libreoffice-dev python3-uno libreoffice-sdbc-firebird python3-venv

# 2. Install this MCP server in a separate Python environment.
git clone https://github.com/vrajkher/RAJlibreoffice.git
cd RAJlibreoffice
python3 -m venv .venv
.venv/bin/python -m pip install -e . 'mcp>=1.30,<2'

# 3. Choose a document folder, check setup, then connect your MCP client.
export RAJ_WORKSPACE="$PWD/workspace"
.venv/bin/raj-libreoffice doctor
.venv/bin/raj-libreoffice serve
```

`serve` is a stdio MCP process; it waits for an MCP client rather than showing a terminal chat. LibreOffice starts automatically on the first document operation, using a private profile and a local UNO pipe. No manually exposed UNO socket is required.

Add this to your MCP client configuration, replacing both absolute paths:

```json
{
  "mcpServers": {
    "libreoffice": {
      "command": "/absolute/path/RAJlibreoffice/.venv/bin/raj-libreoffice",
      "args": ["serve"],
      "env": {
        "RAJ_WORKSPACE": "/absolute/path/my-documents",
        "RAJ_UNO_PYTHON": "/usr/bin/python3"
      }
    }
  }
}
```

The MCP environment and PyUNO environment are intentionally separate. Installing a PyPI package named `uno` does **not** install LibreOffice's UNO bindings. See [installation](docs/INSTALL.md) for macOS, Windows, SDK and external-session details.

## The simple document flow

1. Find a file with `files_list`, or create one with `document_create`.
2. Open an existing file with `document_open`.
3. Read and edit using its returned `document` handle.
4. Save or export with `document_save`.
5. Close with `document_close`.

Ask your MCP client: “Create a Writer document, add a title and a small table, save it as `report.odt`, and export `report.pdf`.”

Every ordinary tool response has an outer `result` key. New documents return `result.document`. Object-producing tools return `result.$ref`; pass that string as the next tool's `object`. Handles belong to one server process, and expire on close or worker restart.

Indexes and body-text offsets start at zero. Calc ranges use A1 notation. Shape and image dimensions use hundredths of a millimetre: `10000` means 10 cm.

## One-call workflows

`workflow_run` executes an ordered sequence and lets later steps reference earlier results:

```json
{
  "steps": [
    {"id": "new", "tool": "document_create", "arguments": {"kind": "writer"}},
    {"id": "text", "tool": "writer_insert", "arguments": {
      "document": {"$step": "new", "path": ["document"]},
      "text": "Quarterly report\nPrepared with LibreOffice UNO."
    }},
    {"id": "save", "tool": "document_save", "arguments": {
      "document": {"$step": "new", "path": ["document"]},
      "path": "report.odt"
    }},
    {"id": "pdf", "tool": "document_save", "arguments": {
      "document": {"$step": "new", "path": ["document"]},
      "path": "report.pdf", "export": true
    }}
  ]
}
```

Workflows contain at most 50 steps, stop on the first error by default, and report completed operations. They are **not transactions**: changes already applied remain applied. A timed-out write is never automatically replayed.

The [examples folder](examples/README.md) contains complete Writer, Calc and Impress workflow arguments.

## Tool families

| Area | Dedicated tools |
|---|---|
| Files and documents | list files, create/open/list/inspect documents, save/export, close, metadata, undo/redo, installed filters |
| Writer | read/insert/replace text, formatting, tables, bookmarks, fields, embedded images, style families and style editing |
| Calc | sheet management, values/formulas, range formatting, number formats, merge/clear, recalculation, charts, named ranges, sorting |
| Impress and Draw | list/add/remove pages, text and geometric shapes, images, page inspection, slide notes |
| Math | read/write StarMath formulas; native save and PDF export |
| Base | SDBC connections, table discovery, parameterized queries and updates, explicit transactions |
| UNO / SDK | object introspection, installed services, runtime type descriptions, arbitrary property access, methods, service creation and dispatch |
| Trusted automation | installed Basic/Python scripts and Python snippets with UNO context |
| MCP guidance | guide, tool catalog and coverage resources; editing prompt; ordered workflows |

Default mode advertises **79 tools**. Enabling all advanced/script/Python settings advertises **87 tools**. OpenAI mode adds native settings, mentions, preference-aware saving and a workspace panel (84 tools by default, 92 with all trusted tools).

## Advanced features

Enable advanced UNO automation before starting the server:

```bash
export RAJ_ALLOW_ADVANCED=1
# Optional, for trusted automation code:
export RAJ_ALLOW_SCRIPTS=1
export RAJ_ALLOW_PYTHON=1
```

Use `uno_inspect` to discover the actual installed API, then `uno_get`, `uno_call`, `uno_set` or `uno_service`. This covers APIs that do not have a dedicated convenience tool: headers/footers, sections, comments, footnotes, indexes, mail merge, conditional formatting, validation, pivots, chart types, master pages, connectors, forms and extensions. Detailed [UNO recipes](docs/UNO.md) explain typed values and object traversal.

Advanced UNO, installed scripts and Python are trusted automation capabilities. They can access files, databases, external services and process functionality beyond `RAJ_WORKSPACE`; the workspace boundary applies to dedicated file tools, not unrestricted UNO. Python execution is not sandboxed. Default mode omits these tools. Automatic document macros and external-link updates are disabled when opening documents.

## OpenAI plugin mode

```bash
python3 -m venv .venv-openai
.venv-openai/bin/python -m pip install -e '.[openai]'
RAJ_WORKSPACE="$PWD/workspace" .venv-openai/bin/raj-libreoffice serve --openai
```

This uses `openai-mcp-extensions==0.1.0`, whose declared dependency is MCP `>=2.0.0b2`; this repository requires the verified MCP 2.3 API. Use a separate environment from the standard MCP 1 install. Included plugin metadata lives in `.codex-plugin/plugin.json` and `.mcp.json`.

Composer mentions search immediate workspace files. Native settings store a preferred format and optional PDF export in `.raj-preferences.json`. The default format is `native`, which chooses ODT/ODS/ODP/ODG/ODF/ODB for the document type. `document_save_preferred` applies those preferences; `document_save` always follows explicit arguments. The plugin does not install itself into your ChatGPT account or expose your desktop to a cloud client. A basic MCP Apps workspace panel and authenticated single-user HTTP transport are included. A hosted deployment and a full LibreOffice graphical editor require additional host work.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Unit tests verify tool schemas, path containment, capability gates, workflow references and worker errors. Integration tests exercise real Writer/Calc/Impress/Draw/Math documents, PDF output, typed UNO values and Base with embedded Firebird. They skip when PyUNO is unavailable. GitHub Actions installs LibreOffice and runs them in a standard-mode job; a second job validates native OpenAI extension registration and both jobs exercise the actual stdio protocol.

Real LibreOffice, native SDK, HTTP and browser panel checks run locally in a container and in GitHub Actions; consult the linked test status and [coverage map](docs/COVERAGE.md) for what is exercised. The native OpenAI host interface and macOS/Windows behavior still require their own validation.


## Version 0.2: wider workflows and a simple panel

New convenience tools cover Writer page headers/footers, sections, frames, footnotes/endnotes, TOC refresh, comments, tracked-change inspection, style creation, database fields and file mail merge. Calc adds filters, pivots, validation, conditional formatting, comments, protection, function evaluation, matrix formulas, goal seek, solver, subtotals and chart configuration. Impress/Draw adds masters, backgrounds/transitions, shape edits/groups, layers, custom shows and page graphics exports. Base adds connection configuration and stored query definitions. Forms, dictionaries, installed extensions, configuration, templates and any installed export filter also have convenience tools.

In native OpenAI mode, call `office_workspace` to open the panel. Its three steps are choose a document, read/edit, then save. It supports text insertion, Calc value/formula editing, shapes, Math formulas and PDF export. Rich formatting and advanced operations remain available through the assistant's tools. The panel uses the official MCP Apps and OpenAI extension SDKs, bundled locally with no external scripts. It needs a host with MCP Apps support.

Run `bash scripts/setup.sh standard` or `bash scripts/setup.sh openai` after installing LibreOffice/PyUNO. For a container that bundles LibreOffice, PyUNO, SDK, Firebird and dictionaries, follow [Docker setup](docs/DOCKER.md). This is also the simplest portable setup for macOS/Windows with Docker Desktop.

Native and standard modes support authenticated Streamable HTTP. See [HTTP setup](docs/HTTP.md) and [workflow recipes](docs/WORKFLOWS.md). Coverage and host-dependent features are tracked in [the coverage map](docs/COVERAGE.md).

For the complete trusted tool set, use `.mcp.full.json` after running `bash scripts/setup.sh openai`, with absolute paths for your checkout. It enables generic UNO, installed scripts and unsandboxed Python (92 native tools). Use it only for a workspace and clients you trust. `.mcp.json` keeps these execution tools disabled by default.
