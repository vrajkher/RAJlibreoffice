# Authenticated single-user HTTP

Both standard MCP and native OpenAI modes support Streamable HTTP at `/mcp`. Stdio needs no HTTP configuration.

```bash
export RAJ_HTTP_HOST=127.0.0.1
export RAJ_HTTP_PORT=8000
export RAJ_BEARER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
.venv-openai/bin/raj-libreoffice serve --openai --transport streamable-http
```

The client must send `Authorization: Bearer <token>` on every MCP request. Tokens must be at least 32 characters. A non-loopback bind requires a token; unauthenticated loopback remains available for existing local clients. Tokens are excluded from worker configuration and diagnostic representations.

`GET /health` returns a public, minimal `{"ok":true}` readiness response. It does not start LibreOffice or expose workspace information. The token protects all other HTTP requests.

For containers, bind `RAJ_HTTP_HOST=0.0.0.0` internally and publish only the intended host interface. The included Compose file publishes loopback. Public hosting requires a TLS reverse proxy, a persistent workspace and a client that supports explicit bearer headers. The token grants access to the single server workspace; this is not an OAuth server or a multi-user service. Native OpenAI extension metadata is available over this transport, but registration requirements depend on the client host.

One process owns one LibreOffice worker/profile. Do not route a stateful MCP session to different replicas: object handles and open documents exist in that process. Use one instance per isolated workspace/user. Restarting discards unsaved in-memory edits; saved files persist on the mounted volume.

No hosted URL is provisioned by this repository. Use the supplied Docker image and Compose service on your chosen host, configure TLS, then connect the client. Actual printer jobs, certificates, GUI slideshow playback and external database drivers also depend on that host.
