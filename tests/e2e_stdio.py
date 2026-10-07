"""End-to-end: spawn the server over stdio and drive it with the MCP client."""
import asyncio, json, tempfile, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command="python3", args=["-m", "libreoffice_mcp"], env={**os.environ, "LO_MCP_PORT": "2011", "LO_MCP_PROFILE": "/tmp/lo_mcp_e2e"})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            print("tools:", len(tools))
            call = lambda n, a: s.call_tool(n, a)
            print((await call("lo_guide", {})).content[0].text[:60].replace("\n", " "))
            did = json.loads((await call("create_document", {"kind": "writer"})).content[0].text)["doc_id"]
            await call("writer_append", {"doc_id": did, "text": "Hello from MCP", "style": "Heading 1"})
            out = os.path.join(tempfile.mkdtemp(), "e2e.pdf")
            await call("save_document_as", {"doc_id": did, "path": out})
            print("pdf bytes:", os.path.getsize(out))
            bad = await call("writer_get_text", {"doc_id": "nope"})
            print("error surfaced:", bad.is_error, bad.content[0].text[:60])

asyncio.run(main())
