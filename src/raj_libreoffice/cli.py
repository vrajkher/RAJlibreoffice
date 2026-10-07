from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys

from .config import Config


def doctor(config):
    try:
        result = subprocess.run([config.uno_python, "-c", "import uno; print('PyUNO available')"],
                                capture_output=True, text=True, timeout=10)
        uno_ok = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        uno_ok = False
    report = {"uno_python": config.uno_python, "pyuno_available": uno_ok,
              "soffice": shutil.which(config.soffice), "workspace": str(config.workspace),
              "external_connection": bool(config.connection),
              "advanced": config.advanced, "scripts": config.scripts,
              "python_execution": config.python_execution}
    for package in ["mcp", "openai-mcp-extensions"]:
        try:
            report[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report[package] = None
    print(json.dumps(report, indent=2))
    return 0 if uno_ok and (report["soffice"] or config.connection) else 1


def main():
    parser = argparse.ArgumentParser(description="RAJ LibreOffice MCP server")
    parser.add_argument("command", choices=["serve", "doctor"], nargs="?", default="serve")
    parser.add_argument("--openai", action="store_true", help="Use native OpenAI extensions with MCP 2")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    args = parser.parse_args()
    config = Config.from_env()
    if args.command == "doctor":
        sys.exit(doctor(config))
    from .server import create_server
    server, bridge = create_server(config, openai=args.openai)
    try:
        if args.transport == "streamable-http":
            from .http import run_http
            run_http(server, config)
        else:
            server.run(transport="stdio")
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
