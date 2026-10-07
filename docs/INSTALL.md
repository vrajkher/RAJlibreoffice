# Installation and operating modes

## Linux (primary supported setup)

Use the installation commands in the README. LibreOffice and `python3-uno` must come from compatible packages. `/usr/bin/python3 -c 'import uno'` must succeed. The MCP process may use a different Python version because it communicates with the UNO worker using JSON rather than importing PyUNO itself.

The optional `libreoffice-dev` package installs SDK/IDL resources. Runtime UNO reflection works without the SDK development files. Native C++/Java extension compilation and custom UNO component registration are external development tasks; this MCP server can instantiate components after they are installed.

The worker locates LibreOffice using `RAJ_SOFFICE`. Some distributions call the executable `soffice`; set this explicitly if needed.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `RAJ_WORKSPACE` | `./workspace` | Local folder used by dedicated document/file tools |
| `RAJ_UNO_PYTHON` | `/usr/bin/python3` | Python executable with compatible PyUNO |
| `RAJ_SOFFICE` | `libreoffice` | LibreOffice launcher path |
| `RAJ_UNO_CONNECTION` | empty | Attach to an existing UNO resolver URL rather than launch a private office |
| `RAJ_TIMEOUT` | `120` seconds | Per-operation limit; timed-out workers stop and lose handles |
| `RAJ_ALLOW_ADVANCED` | `0` | Advertise generic UNO property, invocation, creation and dispatch tools |
| `RAJ_ALLOW_SCRIPTS` | `0` | With advanced mode, advertise installed script invocation |
| `RAJ_ALLOW_PYTHON` | `0` | With advanced mode, advertise unrestricted Python execution |

Read `libreoffice://guide`, `libreoffice://tools` and `libreoffice://coverage` in your MCP client for available capabilities.

## Existing LibreOffice session

For a visible desktop session, launch LibreOffice with a local pipe:

```bash
libreoffice --accept='pipe,name=raj_desktop;urp;StarOffice.ServiceManager'
export RAJ_UNO_CONNECTION='uno:pipe,name=raj_desktop;urp;StarOffice.ComponentContext'
```

Do not already have an unrelated LibreOffice process using the same profile: launcher arguments can be forwarded to it rather than creating the intended listener. A private `-env:UserInstallation=file:///...` profile avoids that ambiguity. The default server-managed mode already does this.

The server never terminates an externally attached office. `document_list` reports only documents it has opened or created; it does not silently adopt every document from the user's desktop. Advanced Python can enumerate `desktop.getComponents()` and return object references; dedicated document wrappers still require registered document handles.

## macOS

Install LibreOffice. Set `RAJ_SOFFICE` to `/Applications/LibreOffice.app/Contents/MacOS/soffice`. Locate the Python runtime supplied by that LibreOffice release, or install PyUNO bindings built for an exactly compatible Python/architecture. Set `RAJ_UNO_PYTHON` to the executable that passes `import uno`.

Distribution layouts differ; do not assume that a Homebrew Python can import LibreOffice's bundled PyUNO binary. This repository does not yet have macOS integration CI.

## Windows

Install LibreOffice and a matching PyUNO-capable Python. Set `RAJ_SOFFICE` to the full `soffice.exe` path and `RAJ_UNO_PYTHON` to the compatible `python.exe`. MCP virtualenv entrypoints are under `Scripts`, for example `.venv\Scripts\raj-libreoffice.exe`.

```powershell
$env:RAJ_WORKSPACE = 'C:\Documents\OfficeMCP'
$env:RAJ_SOFFICE = 'C:\Program Files\LibreOffice\program\soffice.exe'
$env:RAJ_UNO_PYTHON = 'C:\path\to\compatible\python.exe'
.venv\Scripts\raj-libreoffice.exe doctor
```

Windows distribution/ABI discovery and child-process cleanup have not been integration-tested. The default plugin `.mcp.json` uses Linux/macOS virtualenv paths; customize it for Windows.

## Transport and deployment

Stdio is the default local transport. Both modes support `--transport streamable-http` at `/mcp`, with explicit bearer authentication. See [HTTP setup](HTTP.md). Containers and Compose bundle the office runtime and persistent storage; public hosting still needs TLS and a suitable client.

One server process owns one UNO worker and serializes calls. It is suitable for one trusted user. It does not provide separate sessions for different remote users or parallel manipulation of the same office process.

## Diagnostics

- `doctor` fails: confirm the selected UNO Python runs `import uno`, then check the LibreOffice launcher path.
- “Cannot connect”: confirm that LibreOffice can launch and that the private profile folder is writable. For attachments, verify the exact listener pipe/socket and resolver URL.
- “Unknown handle”: reopen the document after worker restart; handles cannot survive restart.
- Timeout: inspect the output files before retrying a write. The operation may already have completed. On POSIX the worker process group is killed to clean up its spawned office.
- Missing service/driver: install the relevant LibreOffice component, database driver or extension, then restart the office worker.
- Wrong import in OpenAI mode: use its separate virtualenv and install `.[openai]`. OpenAI mode requires MCP 2; standard mode supports either MCP SDK generation.
- Layout or fonts differ: install the original fonts and compare exported files in a viewer. Document generation cannot guarantee pixel-identical Microsoft Office conversion.

