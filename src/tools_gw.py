"""Arac agi gecidi: evidence/report araclari buradan cagirir.
TIMERCA_TOOLS=mcp (varsayilan): MCP sunucusu uzerinden. direct: dogrudan tools.py.
MCP hata verirse logs/agent_log.jsonl'a mcp_fallback yazilir ve dogrudan cagriya dusulur."""
import copy, json, os
from datetime import datetime, timezone
from pathlib import Path
import tools as _direct

LOGF = Path(__file__).resolve().parents[1] / "logs" / "agent_log.jsonl"


def _mode():
    return os.environ.get("TIMERCA_TOOLS", "mcp").strip().lower()


def _log(**d):
    try:
        LOGF.parent.mkdir(exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "stage": "mcp_fallback", "level": "WARN", "details": d}
        with LOGF.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


_NAMES = ["check_etl_log", "compare_same_weekday_history", "get_weather", "get_calendar", "get_earthquakes"]
_STAGES = [_NAMES[:2], _NAMES[2:]]  # 1: ETL + gecmis karsilastirmasi, 2: hava + takvim + deprem
_CACHE = {}


def _is_err(r):
    return isinstance(r, dict) and set(r) == {"tool", "error"}


def _call(name, s, e):
    if _mode() == "mcp":
        key = (name, s, e)
        if key in _CACHE:
            return copy.deepcopy(_CACHE[key])
        try:
            import mcp_client
            group = next(g for g in _STAGES if name in g)
            res = mcp_client.call_many([(n, s, e) for n in group])
            if len(_CACHE) > 400:
                _CACHE.clear()
            for n, r in zip(group, res):
                if not _is_err(r):
                    _CACHE[(n, s, e)] = r
            r = res[group.index(name)]
            if _is_err(r):
                raise RuntimeError(r["error"])
            return copy.deepcopy(r)
        except Exception as ex:
            _log(stage="gateway", tool=name, error=f"{type(ex).__name__}: {ex}"[:200])
    return getattr(_direct, name)(s, e)


def check_etl_log(s, e): return _call("check_etl_log", s, e)
def compare_same_weekday_history(s, e): return _call("compare_same_weekday_history", s, e)
def get_weather(s, e): return _call("get_weather", s, e)
def get_calendar(s, e): return _call("get_calendar", s, e)
def get_earthquakes(s, e): return _call("get_earthquakes", s, e)
