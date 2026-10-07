"""Exercise authenticated Streamable HTTP through the real CLI and SDK."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import http.client
import contextlib


class HttpTests(unittest.TestCase):
    def exercise(self, openai=False):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as port_socket:
                port_socket.bind(("127.0.0.1", 0))
                port = port_socket.getsockname()[1]
            token = secrets.token_hex(32)
            env = {**os.environ, "RAJ_WORKSPACE": directory, "RAJ_HTTP_HOST": "127.0.0.1",
                   "RAJ_HTTP_PORT": str(port), "RAJ_BEARER_TOKEN": token,
                   "RAJ_UNO_PYTHON": sys.executable, "RAJ_ALLOW_ADVANCED": "0",
                   "RAJ_ALLOW_PYTHON": "0", "RAJ_ALLOW_SCRIPTS": "0"}
            command = [sys.executable, "-m", "raj_libreoffice.cli", "serve", "--transport", "streamable-http"]
            if openai:
                command.append("--openai")
            with open(Path(directory, "server.log"), "w+") as log:
                process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
                try:
                    url = f"http://127.0.0.1:{port}"
                    class Response:
                        def __init__(self, response, connection):
                            self.response, self.connection = response, connection
                            self.status_code = response.status
                            self.headers = dict((k.lower(), v) for k, v in response.getheaders())
                        def __enter__(self):
                            return self
                        def __exit__(self, *args):
                            self.connection.close()
                        def read(self):
                            return self.response.read()
                        def iter_lines(self):
                            while line := self.response.readline():
                                yield line.decode().rstrip()
                    class Client:
                        def stream(self, method, url, headers=None, json=None):
                            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                            path = url.split(f":{port}", 1)[1]
                            connection.request(method, path, body=None if json is None else __import__("json").dumps(json),
                                               headers={"Content-Type": "application/json", **(headers or {})})
                            return Response(connection.getresponse(), connection)
                        def get(self, url):
                            with self.stream("GET", url) as response:
                                response.read()
                                return response
                        def post(self, url, **kwargs):
                            with self.stream("POST", url, **kwargs) as response:
                                response.read()
                                return response
                    with contextlib.nullcontext(Client()) as client:
                        deadline = time.monotonic() + 15
                        while True:
                            try:
                                if client.get(url + "/health").status_code == 200:
                                    break
                            except (OSError, http.client.HTTPException):
                                pass
                            if time.monotonic() > deadline or process.poll() is not None:
                                log.seek(0)
                                self.fail("HTTP server failed to start: " + log.read())
                            time.sleep(0.05)
                        self.assertEqual(client.post(url + "/mcp", json={}).status_code, 401)
                        self.assertEqual(client.post(url + "/mcp", headers={"Authorization": "Bearer wrong"}, json={}).status_code, 401)
                        headers = {"Authorization": "Bearer " + token,
                                   "Accept": "application/json, text/event-stream"}
                        def rpc(method, params, id):
                            with client.stream("POST", url + "/mcp", headers=headers,
                                               json={"jsonrpc": "2.0", "id": id, "method": method, "params": params}) as response:
                                self.assertEqual(response.status_code, 200)
                                if response.headers.get("mcp-session-id"):
                                    headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
                                if "application/json" in response.headers["content-type"]:
                                    result = json.loads(response.read())
                                else:
                                    result = next(json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: "))
                                self.assertNotIn("error", result)
                                return result["result"]
                        result = rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                    "clientInfo": {"name": "http-test", "version": "1"}}, 1)
                        self.assertEqual(result["serverInfo"]["name"], "RAJ LibreOffice")
                        headers["Mcp-Protocol-Version"] = result["protocolVersion"]
                        response = client.post(url + "/mcp", headers=headers, json={
                            "jsonrpc": "2.0", "method": "notifications/initialized"})
                        self.assertEqual(response.status_code, 202)
                        result = rpc("tools/call", {"name": "status", "arguments": {}}, 2)
                        self.assertFalse(result["structuredContent"]["result"]["connected"])
                        if openai:
                            result = rpc("tools/call", {"name": "office_workspace", "arguments": {}}, 3)
                            self.assertEqual(result["structuredContent"]["documents"], [])
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

    def test_standard_authenticated_http(self):
        self.exercise()

    @unittest.skipUnless(importlib.util.find_spec("openai_mcp_extensions"), "optional OpenAI SDK")
    def test_openai_authenticated_http(self):
        self.exercise(openai=True)

    def test_credentials_not_forwarded_to_worker_or_repr(self):
        from raj_libreoffice.config import Config
        config = Config(Path("."), bearer_token="private-test-value")
        self.assertNotIn("bearer_token", config.wire())
        self.assertNotIn("private-test-value", repr(config))
