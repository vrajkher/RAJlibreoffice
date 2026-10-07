---
name: libreoffice
description: Read, create, modify and export LibreOffice documents through structured MCP tools and installed UNO APIs.
---

Read `libreoffice://guide` and `libreoffice://coverage` once. Follow files_list/document_create/document_open → inspect/read → edit → read back → document_save → document_close. Use returned document handles rather than guessing them. Relative files resolve inside RAJ_WORKSPACE. Save output explicitly and report its path.

For advanced operations, inspect UNO properties and signatures before invoking methods. Use typed JSON for structs, enums, references, PropertyValue sequences and Any. Read docs/UNO.md for recipes. Keep caller authorization and file-overwrite intent in context; do not repeatedly ask permission for an already requested operation.

Workflow steps execute sequentially and are not atomic. On failure, report completed steps and remaining work. After timeout/restart reopen documents and inspect output before retrying a write. Report unavailable services and unverified features accurately.

