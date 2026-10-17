"""The MCP server exposes every API function as a tool, and tools are callable."""
import asyncio
from mtengine import api
from mtengine.mcp_server import server


def test_tools_registered():
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == set(api.FUNCTIONS)
    schema = next(t for t in tools if t.name == "hessenberg_betti").input_schema
    assert {"kbar", "h"} <= set(schema["properties"])


def test_tool_call():
    import json
    out = asyncio.run(server.call_tool("hessenberg_betti", {"kbar": [2, 2], "h": [2, 2]}))
    assert json.loads(out.content[0].text)["value"] == [1, 1, 2, 1, 1]


def test_stdio_transport():
    """A separate client process can initialise the server and call a tool over stdio."""
    import json, sys
    from pathlib import Path
    import mcp.client.stdio as cs
    from mcp import ClientSession, StdioServerParameters

    exe = Path(sys.executable).with_name("mtengine-mcp")

    async def run():
        async with cs.stdio_client(StdioServerParameters(command=str(exe), args=[])) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                out = await s.call_tool("hessenberg_betti", {"kbar": [1, 1, 1], "h": [3, 3, 3]})
                return names, json.loads(out.content[0].text)["value"]

    names, value = asyncio.run(run())
    assert names == set(api.FUNCTIONS) and value == [1, 2, 2, 1]
