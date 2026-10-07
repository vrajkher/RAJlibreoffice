"""Single-user HTTP transport with explicit bearer-header authentication.

This is not an OAuth authorization server. Put public deployments behind TLS.
"""
from __future__ import annotations

import secrets


class BearerGuard:
    def __init__(self, app, token):
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            if scope.get("path") == "/health" and scope.get("method") == "GET":
                await self.reply(send, 200, b'{"ok":true}')
                return
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"authorization", b"")
            if self.token and not secrets.compare_digest(supplied, b"Bearer " + self.token):
                await self.reply(send, 401, b'{"error":"Bearer token required"}',
                                 [(b"www-authenticate", b"Bearer")])
                return
        await self.app(scope, receive, send)

    @staticmethod
    async def reply(send, status, body, headers=()):
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), *headers]})
        await send({"type": "http.response.body", "body": body})


def run_http(server, config):
    if config.http_host not in {"127.0.0.1", "localhost", "::1"} and not config.bearer_token:
        raise ValueError("Non-loopback HTTP requires RAJ_BEARER_TOKEN (at least 32 characters)")
    if config.bearer_token and len(config.bearer_token) < 32:
        raise ValueError("RAJ_BEARER_TOKEN must contain at least 32 characters")
    import uvicorn
    uvicorn.run(BearerGuard(server.streamable_http_app(), config.bearer_token),
                host=config.http_host, port=config.http_port, log_level="info")
