"""E2E for the OpenAI extensions layer over stdio."""
import asyncio, json, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command="python3", args=["-m", "libreoffice_mcp"], env={**os.environ, "LO_MCP_PORT": "2012", "LO_MCP_PROFILE": "/tmp/lo_mcp_e2e2"})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            print("capabilities:", json.dumps(init.capabilities.model_dump(by_alias=True, exclude_none=True))[:400])
            tools = (await s.list_tools()).tools
            names = [t.name for t in tools]
            print("tools:", len(names), [n for n in names if "mention" in n or "chatgpt" in n])
            f = next(t for t in tools if t.name == "open_chatgpt_file")
            print("file meta:", f.meta)
            did = json.loads((await s.call_tool("create_document", {"kind": "calc"})).content[0].text)["doc_id"]
            mt = next((n for n in names if "mention" in n), None)
            if mt:
                res = await s.call_tool(mt, {"query": ""})
                print("mention result:", res.is_error, res.structured_content or res.content)
            import tempfile
            src = os.path.join(tempfile.mkdtemp(), "host.csv")
            open(src, "w").write("a,b\n1,2\n")
            ok = await s.call_tool("open_chatgpt_file", {}, meta={"openai/resource": {"path": src}})
            print("host file opened:", ok.is_error, ok.structured_content or ok.content)
            bad = await s.call_tool("open_chatgpt_file", {})
            print("no-host-file:", bad.is_error, bad.content[0].text[:120])

asyncio.run(main())
