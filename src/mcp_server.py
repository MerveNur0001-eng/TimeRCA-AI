import json, sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server import MCPServer

mcp = MCPServer("timerca-tools", version="0.1")


def _clean(x):
    return json.loads(json.dumps(x, ensure_ascii=False, default=str))


import functools, os, time
from datetime import datetime, timezone

# Cagri izi yalnizca dosyaya yazilir: stdio'da stdout protokol kanalidir, print edilmez.
MCP_LOG = Path(os.environ.get("TIMERCA_MCP_LOG", str(Path(__file__).resolve().parents[1] / "logs" / "mcp_calls.jsonl")))


def traced(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        t0 = time.perf_counter()
        ok, err = True, None
        try:
            return fn(*a, **k)
        except Exception as ex:
            ok, err = False, f"{type(ex).__name__}: {ex}"[:200]
            raise
        finally:
            try:
                MCP_LOG.parent.mkdir(parents=True, exist_ok=True)
                rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool": fn.__name__,
                       "args": k or list(a), "ok": ok, "ms": round((time.perf_counter() - t0) * 1000), "error": err}
                with MCP_LOG.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            except Exception:
                pass
    return wrapper


@mcp.tool()
@traced
def check_etl_log(start: str, end: str) -> dict[str, Any]:
    """ETL logundaki eksik saat bloklari, dusuk hucre kapsami ve yogunluk suphesi. Tarih: 'YYYY-MM-DD HH:MM'."""
    return _clean(tools.check_etl_log(start, end))


@mcp.tool()
@traced
def compare_same_weekday_history(start: str, end: str) -> dict[str, Any]:
    """Pencereyi onceki 4 haftanin ayni gun-saatinin medyaniyla karsilastirir. Tarih: 'YYYY-MM-DD HH:MM'."""
    return _clean(tools.compare_same_weekday_history(start, end))


@mcp.tool()
@traced
def get_weather(start: str, end: str) -> dict[str, Any]:
    """Open-Meteo reanalysis: yagis, ruzgar, sicaklik (tek nokta, istasyon olcumu degil)."""
    return _clean(tools.get_weather(start, end))


@mcp.tool()
@traced
def get_calendar(start: str, end: str) -> dict[str, Any]:
    """Resmi tatil ve bayramlar (holidays paketi). Etkinlik, mac, secim yok."""
    return _clean(tools.get_calendar(start, end))


@mcp.tool()
@traced
def get_earthquakes(start: str, end: str) -> dict[str, Any]:
    """USGS katalogundan ilgili depremler (yerel katalog, sinirli tarih araligi)."""
    return _clean(tools.get_earthquakes(start, end))


@mcp.tool()
@traced
def get_air_quality_signal(start: str, end: str) -> dict[str, Any]:
    """EK KANIT (hipotez puanina girmez): IBB hava kalitesi (NO2, PM10) orani ile trafik orani yan yana. Veri yoksa 'error' doner."""
    return _clean(tools.get_air_quality_signal(start, end))


if __name__ == "__main__":
    mcp.run(transport="stdio")
