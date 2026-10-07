# OpenAI workspace panel

The panel uses the official MCP Apps `App` and OpenAI `OpenAIExtensions` SDKs. Python registers the bundled HTML with `Apps`, a global/thread entrypoint and the `office_workspace` tool. A host with MCP Apps support displays it.

```bash
cd ui
npm ci
npm run build
npx playwright install chromium
npm test
```

The generated HTML is committed and packaged, so Python installation needs no Node.js or CDN access. Dependencies are pinned and the lockfile is included. `npm run build` also collects licenses for the client libraries included in the bundle.

Browser tests use a simulated host bridge and tool results to verify creation, text editing, saves, closure, formula edits and protection against applying a stale range. They do not prove compatibility with every native OpenAI host; real document operations have separate UNO integration tests.

The panel shows up to 400 cells and reads Writer body text in a bounded slice. Formatting, rich structures, database queries and other advanced tasks are performed through the assistant's tools. It is not a full LibreOffice WYSIWYG application.
