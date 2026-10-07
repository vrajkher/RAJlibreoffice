# Portable setup with Docker

Docker bundles compatible LibreOffice, PyUNO, Python, the SDK, embedded Firebird, fonts and English dictionaries. Install Docker Engine or Docker Desktop first.

## 1. Build

```bash
git clone https://github.com/vrajkher/RAJlibreoffice
cd RAJlibreoffice
docker build --build-arg OPENAI=1 -t raj-libreoffice:openai .
```

The image uses Debian trixie's LibreOffice. Its MCP interpreter is Python 3.12; the UNO worker uses `/usr/bin/python3`, which matches the distribution's PyUNO. This avoids Python ABI mismatches.

## 2. Check

```bash
docker run --rm raj-libreoffice:openai doctor
```

## 3. Connect

On Linux/macOS or Windows with WSL/Git Bash, use `.mcp.docker.json` as the MCP configuration, with its `cwd` set to your absolute repository checkout. Its launcher runs an interactive stdio container and mounts the checkout's `workspace` directory. Do not add `-t`: MCP uses plain JSON lines, not a terminal.

The launcher matches your UID/GID so output files belong to you. If your platform cannot map users, run Docker as its default `raj` user and grant that user access to the mounted directory, or use a Docker named volume. Avoid changing ownership of unrelated host files.

A direct native command for clients that do not support shell launchers:

```bash
docker run --rm -i --init -v /absolute/path/documents:/workspace \
  raj-libreoffice:openai serve --openai
```

For standard MCP clients, build without `OPENAI=1` and use `serve` without `--openai`.

## HTTP and persistent documents

Generate a private token file, then start the included Compose service:

```bash
python3 -c 'import secrets; print("RAJ_BEARER_TOKEN=" + secrets.token_urlsafe(48))' > .env
chmod 600 .env
docker compose up --build -d
```

The port is published only on `127.0.0.1:8000`. Documents and preferences persist in the `documents` volume. Configure your client with `http://127.0.0.1:8000/mcp` and an `Authorization: Bearer <your token>` header. See [HTTP details](HTTP.md) for remote hosting requirements.

## Reproduce integration tests

From a Unix shell, after building the native image:

```bash
docker run --rm --user 0 -v "$PWD:/app:ro" -e PYTHONPATH=/app/src \
  --entrypoint python raj-libreoffice:openai -m unittest discover -s tests -v
```

The test command uses root to read a potentially restrictive source mount; the production image runs as UID 10001. Tests create temporary documents and a private LibreOffice profile.

Managed environments with custom HTTPS CAs can supply a combined trusted CA bundle without storing it in image layers:

```bash
docker build --secret id=ca_bundle,src=/etc/ssl/certs/ca-certificates.crt \
  --build-arg OPENAI=1 -t raj-libreoffice:openai .
```
