"""Ajan -> MCP sunucusu (stdio). Bir oturumda birden fazla arac cagirir."""
import json, sys
from pathlib import Path
import anyio
from mcp import Client, StdioServerParameters

SERVER = str(Path(__file__).resolve().parent / "mcp_server.py")


def _payload(r):
    sc = r.structured_content
    if sc is None:
        return json.loads(r.content[0].text)
    return sc["result"] if set(sc) == {"result"} else sc


async def _run(calls):
    params = StdioServerParameters(command=sys.executable, args=[SERVER])
    out = []
    async with Client(params) as client:
        for name, s, e in calls:
            try:
                r = await client.call_tool(name, {"start": s, "end": e})
                if r.is_error:
                    out.append({"tool": name, "error": "MCP arac hatasi"})
                else:
                    out.append(_payload(r))
            except Exception as ex:
                out.append({"tool": name, "error": f"{type(ex).__name__}: {ex}"[:200]})
    return out


def call_many(calls):
    """calls: [(arac_adi, start, end), ...] -> ayni sirada sonuc listesi."""
    return anyio.run(_run, calls)
