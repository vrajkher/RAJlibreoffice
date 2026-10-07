---
name: onboarding
description: Set up RAJ LibreOffice MCP using a compatible PyUNO interpreter and a local document workspace.
---

Read README.md and docs/INSTALL.md. Check `raj-libreoffice doctor` before attempting document work. If missing, install LibreOffice and its matching Python UNO bindings using the host's supported installation procedure. Install the OpenAI extra into `.venv-openai` using `python -m pip install --pre -e '.[openai]'`. Configure RAJ_WORKSPACE to the user's document folder. Customize `.mcp.json` paths for the platform.

Do not claim the plugin is connected until the host has actually loaded the MCP server. Do not enable advanced, installed scripts or Python unless requested by the user. For already authorized setup and document tasks, proceed without an extra confirmation.

