import argparse, json, os, secrets, sys
from datetime import datetime, timezone
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent

MAX_DAYS = 14
VALID = ("onayla", "ek_inceleme", "reddet")


class Pending(Exception):
    def __init__(self, question):
        self.question = question


def analyze(body):
    try:
        s, e = pd.Timestamp(body["start"]), pd.Timestamp(body["end"])
        if pd.isna(s) or pd.isna(e):
            raise ValueError("bos zaman")
    except Exception:
        return 400, {"hata": "start ve end 'YYYY-MM-DD HH:MM' biçiminde olmalı"}
    if e < s:
        return 400, {"hata": "end, start'tan önce olamaz"}
    if (e - s) > pd.Timedelta(days=MAX_DAYS):
        return 400, {"hata": f"pencere en fazla {MAX_DAYS} gün olabilir"}
    answers = [x for x in (body.get("karar"), body.get("karar2")) if x is not None]
    if any(str(x).strip().lower() not in VALID for x in answers):
        return 400, {"hata": "karar şu değerlerden biri olmalı: " + ", ".join(VALID)}
    it = iter(str(x).strip().lower() for x in answers)

    def answer_fn(q):
        try:
            return next(it)
        except StopIteration:
            raise Pending(q)

    start, end = s.strftime("%Y-%m-%d %H:%M"), e.strftime("%Y-%m-%d %H:%M")
    try:
        rep, _ = agent.run(start, end, answer_fn=answer_fn)
    except Pending as p:
        agent._log("api_pending", "INFO", start=start, end=end)
        return 200, {"durum": "insan_onayi_bekleniyor", "soru": p.question}
    agent._log("api_done", "INFO", start=start, end=end, nihai_durum=rep["nihai_durum"])
    out = {"durum": "tamamlandi", "rapor": rep}
    if rep["nihai_durum"] == "reddedildi":
        import feedback
        out["ret_nedeni_istendi"] = {"uc": "POST /feedback", "alanlar": ["start", "end", "iddia", "aciklama", "kaynak"],
                                     "iddia_secenekleri": list(feedback.CLAIMS)}
    return 200, out


def ask(body):
    soru = str(body.get("soru", "")).strip()
    if not soru or len(soru) > 500:
        return 400, {"hata": "soru 1-500 karakter olmalı"}
    kar = [str(x).strip().lower() for x in (body.get("karar"), body.get("karar2")) if x is not None]
    if any(k not in VALID for k in kar):
        return 400, {"hata": "karar şu değerlerden biri olmalı: " + ", ".join(VALID)}
    from router_graph import app as router_app  # gec yukleme: /analyze yolunu etkilemez
    o = router_app.invoke({"soru": soru, "istek_tipi": "", "start": None, "end": None,
                           "plan": [], "sonuc": {}, "kararlar": kar})
    return 200, {"yol": o["istek_tipi"], "plan": o["plan"], "pencere": {"start": o.get("start"), "end": o.get("end")}, "sonuc": o["sonuc"]}


def feedback_ep(body):
    import feedback
    try:
        s, e = pd.Timestamp(body["start"]), pd.Timestamp(body["end"])
        if pd.isna(s) or pd.isna(e):
            raise ValueError("bos zaman")
        start, end = s.strftime("%Y-%m-%d %H:%M"), e.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return 400, {"hata": "start ve end 'YYYY-MM-DD HH:MM' biçiminde olmalı"}
    if e < s:
        return 400, {"hata": "end, start'tan önce olamaz"}
    if (e - s) > pd.Timedelta(days=MAX_DAYS):
        return 400, {"hata": f"pencere en fazla {MAX_DAYS} gün olabilir"}
    iddia = str(body.get("iddia", "")).strip().lower()
    if iddia not in feedback.CLAIMS:
        return 400, {"hata": "iddia şu değerlerden biri olmalı: " + ", ".join(feedback.CLAIMS)}
    r = feedback.review(start, end, iddia, body.get("aciklama", ""), body.get("kaynak", ""))
    agent._log("api_feedback", "INFO", id=r["id"], iddia=iddia, kanit_durumu=r["kanit_durumu"], sonuc=r["sonuc"])
    return 200, r


def scan_ep(body):
    import scan
    try:
        r = scan.scan(body["start"], body["end"])
    except KeyError:
        return 400, {"hata": "start ve end 'YYYY-MM-DD' biçiminde olmalı"}
    except ValueError as ex:
        return 400, {"hata": str(ex)[:200]}
    agent._log("api_scan", "INFO", aralik=r["aralik"], aday=len(r["adaylar"]), taranamayan=len(r["taranamayan"]))
    return 200, r


def series_ep(body):
    import series
    try:
        r = series.series(body.get("mod", "gunluk"), body["start"], body["end"])
    except KeyError:
        return 400, {"hata": "mod ('saatlik'|'gunluk'), start ve end gerekli"}
    except ValueError as ex:
        return 400, {"hata": str(ex)[:200]}
    agent._log("api_series", "INFO", mod=r["mod"], aralik=r["aralik"], bolge=len(r.get("bolgeler", [])))
    return 200, r

def hava_saatlik_ep(body):
    """Gosterim: saatlik trafik orani ile NO2/PM10 orani ust uste. Karar kuralina girmez."""
    import series
    import air_quality
    try:
        st, en = body["start"], body["end"]
        tr = series.series("saatlik", st, en)
    except KeyError:
        return 400, {"hata": "start ve end gerekli"}
    except ValueError as ex:
        return 400, {"hata": str(ex)[:200]}
    hv = air_quality.saatlik_oranlar(st, en)
    if hv is None:
        return 200, {"var": False, "noktalar": []}
    hmap = {p["ts"]: p for p in hv}
    pts = [{"ts": p["ts"], "trafik": p.get("oran"), "no2": hmap.get(p["ts"], {}).get("no2"), "pm10": hmap.get(p["ts"], {}).get("pm10")} for p in tr["noktalar"]]
    agent._log("api_hava_saatlik", "INFO", aralik=tr["aralik"], nokta=len(pts))
    return 200, {"var": True, "aralik": tr["aralik"], "noktalar": pts}

ROUTES = {"/hava_saatlik": hava_saatlik_ep, "/analyze": analyze, "/ask": ask, "/scan": scan_ep, "/series": series_ep, "/feedback": feedback_ep}
UI_FILE = Path(__file__).resolve().parent / "ui" / "index.html"


# Analiz istekleri (POST) tek kilitle siralanir: sqlite, chroma ve tools._c onbellegi eskisi gibi tek is parcacigi
# altinda calisir. Yalniz GET /health ve arayuz (GET /) kilitsizdir; ikisi de bu paylasimli duruma dokunmaz.
_POST_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"durum": "ok"})
        if self.path == "/ornekler":  # veri kapsamindan uretilen ornek sorular (arayuz dugmeleri)
            try:
                with _POST_LOCK:
                    from router_graph import ornek_sorular
                    return self._send(200, {"ornekler": ornek_sorular()})
            except Exception:
                return self._send(200, {"ornekler": []})
        if self.path in ("/", "/index.html") and UI_FILE.exists():
            data = UI_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return
        self._send(404, {"hata": "bulunamadı"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n > 10000:
            self.close_connection = True
            return self._send(413, {"hata": "gövde çok büyük"})
        raw = self.rfile.read(n) if n > 0 else b""
        if self.path not in ROUTES:
            return self._send(404, {"hata": "bulunamadı"})
        key = os.environ.get("TIMERCA_API_KEY")
        if key and not secrets.compare_digest(self.headers.get("X-API-Key", ""), key):
            return self._send(401, {"hata": "yetkisiz"})
        try:
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except Exception:
            return self._send(400, {"hata": "geçersiz JSON"})
        try:
            with _POST_LOCK:
                code, obj = ROUTES[self.path](body)
        except Exception as ex:
            agent._log("api_error", "ERROR", error=f"{type(ex).__name__}: {ex}"[:200])
            code, obj = 500, {"hata": "iç hata", "tur": type(ex).__name__}
        self._send(code, obj)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    os.environ.setdefault("TIMERCA_ACIKLAMA_LLM", "1")  # sunucuda tek gun analizine LLM aciklamasi; kapatmak icin 0. Testler (import) etkilenmez
    print(f"dinleniyor: http://{a.host}:{a.port}  (arayuz: GET /  |  POST /scan, /analyze, /ask, /feedback  |  GET /health)")
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    srv.serve_forever()
