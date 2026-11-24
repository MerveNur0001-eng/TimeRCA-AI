import argparse, json, os, sys
from pathlib import Path
import time
from datetime import datetime, timezone
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence
import rag
import report
import tools
import tools_gw

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

ROOT = Path(__file__).resolve().parents[1]
TOOL_NAMES = ["check_etl_log", "compare_same_weekday_history", "get_weather", "get_calendar", "get_earthquakes"]
OPTIONS = {"onayla": "onaylandi", "ek_inceleme": "ek_inceleme_gerekli", "reddet": "reddedildi"}


LOGF = ROOT / "logs" / "agent_log.jsonl"


def _mode():
    return os.environ.get("TIMERCA_TOOLS", "mcp").strip().lower()


def _log(stage, level, **d):
    LOGF.parent.mkdir(exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage": stage, "level": level, "details": d}
    with LOGF.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def _retry(fn, label, *args, attempts=3):
    last = None
    for i in range(1, attempts + 1):
        try:
            res = fn(*args)
            if i > 1:
                _log("retry_ok", "WARN", label=label, attempt=i)
            return res
        except Exception as e:
            last = e
            _log("tool_error", "WARN", label=label, attempt=i, error=f"{type(e).__name__}: {e}"[:200])
            time.sleep(0.5 * i)
    _log("tool_failed", "ERROR", label=label, attempts=attempts)
    raise last



class State(TypedDict, total=False):
    start: str
    end: str
    tool_outputs: dict
    tool_plan: dict
    judgment: dict
    notes: list
    human: dict
    human2: dict
    extra: dict
    report: dict


def _clean(x):
    return json.loads(json.dumps(x, ensure_ascii=False, default=str))


def collect(state):
    """Asama 1: ETL logu + gecmis karsilastirmasi. Asama 2 (hava, takvim, deprem) yalniz sapma varsa."""
    s, e = state["start"], state["end"]

    def call(name):
        try:
            return _clean(_retry(getattr(tools_gw, name), name, s, e))
        except Exception as ex:
            return {"tool": name, "error": f"{type(ex).__name__}: {ex}"[:200]}

    stage1 = [n for n in TOOL_NAMES if n not in evidence.CONTEXT_TOOLS]
    out = {n: call(n) for n in stage1}
    cmp_ = out.get("compare_same_weekday_history", {})
    if "error" in cmp_:
        plan = {"gerekli": True, "neden": "karsilastirma araci hata verdi, guvenli tarafta kalinip tum araclar cagrildi"}
    else:
        plan = evidence.context_plan(cmp_)
    for n in evidence.CONTEXT_TOOLS:
        out[n] = call(n) if plan["gerekli"] else {"tool": n, "atlandi": plan["neden"]}
    called = [n for n in TOOL_NAMES if "atlandi" not in out[n]]
    skipped = [n for n in TOOL_NAMES if "atlandi" in out[n]]
    _log("tool_plan", "INFO", mode=_mode(), cagrilan=called, atlanan=skipped, neden=plan["neden"])
    return {"tool_outputs": {n: out[n] for n in TOOL_NAMES},
            "tool_plan": {"cagrilan": called, "atlanan": skipped, "neden": plan["neden"]}}


def judge(state):
    return {"judgment": _clean(_retry(evidence.judge, "judge", state["start"], state["end"]))}


def fetch_notes(state):
    used = []
    for h, status in state["judgment"]["hipotezler"].items():
        if status != "desteklemiyor":
            for t in rag.HYP_TOOLS[h]:
                if t not in used:
                    used.append(t)
    notes = rag.notes_for_tools(used) if used else []
    return {"notes": [{"id": n["id"], "file": n["file"], "tool": n["arac"], "text": n["text"]} for n in notes]}


def route(state):
    return "ask_human" if state["judgment"]["needs_human"] else "make_report"


def ask_human(state):
    j = state["judgment"]
    question = {
        "soru": "Kanıtlar kesin bir neden vermiyor. Nasıl devam edelim?",
        "pencere": j["pencere"],
        "guven": j["guven"],
        "destekleyen": [k for k, v in j["hipotezler"].items() if v == "destekliyor"],
        "belirsiz": [k for k, v in j["hipotezler"].items() if v == "belirsiz"],
        "notlar": j["notlar"],
        "secenekler": {"onayla": "kodun sonucunu kabul et",
                       "ek_inceleme": "ek inceleme iste",
                       "reddet": "sonucu reddet"},
    }
    answer = interrupt(question)
    raw = answer.get("karar") if isinstance(answer, dict) else answer
    karar = str(raw).strip().lower()
    if karar not in OPTIONS:
        return {"human": {"karar": "gecersiz", "ham_yanit": str(raw)}}
    return {"human": {"karar": karar, "ham_yanit": str(raw)}}


def _compare_day(s, e):
    if _mode() == "mcp":
        try:
            import mcp_client
            r = mcp_client.call_many([("compare_same_weekday_history", s, e)])[0]
            if "error" not in r:
                return _clean(r)
            _log("mcp_fallback", "WARN", stage="extra_review", error=str(r["error"])[:200])
        except Exception as ex:
            _log("mcp_fallback", "WARN", stage="extra_review", error=f"{type(ex).__name__}: {ex}"[:200])
    return _clean(_retry(tools.compare_same_weekday_history, "compare_day", s, e))


def extra_review(state):
    day = state["start"][:10]
    s, e = f"{day} 00:00", f"{day} 23:00"
    ext = _compare_day(s, e)
    brief = {k: ext.get(k) for k in ("hours_in_window", "hours_missing", "hours_etl_flagged",
                                     "median_ratio_excl_etl_flagged", "n_clean_hours",
                                     "n_clean_below_0.7", "n_clean_above_1.3")}
    question = {
        "soru": "Ek inceleme sonucu (tum gun). Nasil devam edelim?",
        "gun": day,
        "gun_bulgulari": brief,
        "secenekler": {"onayla": "ek incelemeyi de gordum, sonucu kabul et",
                       "reddet": "sonucu reddet"},
    }
    answer = interrupt(question)
    raw = answer.get("karar") if isinstance(answer, dict) else answer
    karar = str(raw).strip().lower()
    if karar not in ("onayla", "reddet"):
        karar = "gecersiz"
    return {"human2": {"karar": karar, "ham_yanit": str(raw)}, "extra": brief}


def route_after_human(state):
    h = state.get("human") or {}
    return "extra_review" if h.get("karar") == "ek_inceleme" else "make_report"


RANK_STATUS = {"destekliyor": 0, "belirsiz": 1}
# Esit kanit durumunda sabit oncelik: veri hatasi olcumun kendisini etkiledigi icin once gelir.
RANK_ORDER = ["veri_hatasi", "tatil", "hava", "deprem", "aciklanamayan"]


# Hava, tatil ve deprem bulgulari zamansal cakismadir; nedensellik kaniti degildir (proje kapsam kurali).
KANIT_TURU = {"veri_hatasi": "dogrudan_olcum", "hava": "zamansal_cakisma", "tatil": "zamansal_cakisma",
              "deprem": "zamansal_cakisma", "aciklanamayan": "dislama"}
NEDENSELLIK = {k: "Zamansal çakışma; nedensellik kanıtı değildir." for k in ("hava", "tatil", "deprem")}
NEDENSELLIK["aciklanamayan"] = "Diğer hipotezler sapmayı açıklamadığı için işaretlenir; bir neden iddiası değildir."

# Raporda kullanilan her aracin kaynak turu, kapsami ve siniri (guncellik ve guvenilirlik bilgisi).
KAYNAK_BILGISI = {
    "check_etl_log": {"kaynak": "Kendi ETL logumuz (logs/etl_log.jsonl)", "guncellik": "Yalnızca yüklediğimiz aylar",
                      "sinir": "Boşluğun nedenini söylemez; yalnızca bizim yüklememizde görülenleri kaydeder."},
    "compare_same_weekday_history": {"kaynak": "İBB saatlik trafik verisi, önceki 4 haftanın aynı gün-saati medyanı",
                                     "guncellik": "Yüklü aylar", "sinir": "Tatil veya yağışlı haftalar baseline'ı kirletebilir; gün düzeyi medyan yerel etkileri seyreltir."},
    "get_weather": {"kaynak": "Open-Meteo reanalysis", "guncellik": "Yüklü aylar", "sinir": "Tek nokta, istasyon ölçümü değil; zayıf kanıt."},
    "get_calendar": {"kaynak": "holidays Python paketi", "guncellik": "Paket sürümüne bağlı", "sinir": "Yalnızca resmî tatil ve bayram; okul tatili ve etkinlik yok."},
    "get_earthquakes": {"kaynak": "USGS FDSN, yerel katalog", "guncellik": "Yalnızca indirilen dönemler",
                        "sinir": "M4,5 üstü için tam kabul edilir; büyüklük ve mesafe tek başına nedensellik göstermez."},
}


KAPSAM_SINIRI = ("Değerlendirme yalnızca araçların bildiği etkenleri kapsar (veri kalitesi, hava, resmî tatil, deprem). "
                 "Etkinlik, yol çalışması, okul tatili gibi etkenler için veri yoktur; bunlar dışlanmış sayılmaz.")


def _overall(olasi, deviation, degerlendirilemedi=False, karisik=False):
    """Genel degerlendirme: coklu nedeni acikca soyler. Karari DEGISTIRMEZ, yalniz raporu aciklar.
    Etkilerin payi hesaplanmaz (ayristirma icin veri yok); olasilik verilmez."""
    ad = {"veri_hatasi": "veri hatası", "hava": "hava", "tatil": "tatil/bayram", "deprem": "deprem", "aciklanamayan": "açıklanamayan"}
    des = [x["neden"] for x in olasi if x["durum"] == "destekliyor" and x["neden"] != "aciklanamayan"]
    bel = [x["neden"] for x in olasi if x["durum"] == "belirsiz"]
    acik = any(x["neden"] == "aciklanamayan" and x["durum"] == "destekliyor" for x in olasi)
    names = lambda l: ", ".join(ad[k] for k in l)
    if degerlendirilemedi:
        m = "Baseline için yeterli geçerli hafta yok; neden değerlendirilemedi."
    elif not deviation:
        if "veri_hatasi" in des:
            m = ("Temiz saatlerde belirgin trafik sapması yok, ancak veri kalitesi sorunu var (veri hatası destekleniyor); "
                 "sapma yok sonucu günün tamamı için güvenilir değil.")
        else:
            m = "Belirgin trafik sapması yok; neden araştırması gerekmedi."
    elif len(des) >= 2:
        m = (f"Birden fazla etken aynı anda destekleniyor ({names(des)}). Her birinin sapmadaki payı ayrıştırılamaz; "
             "bunlar zamansal çakışmadır, nedensellik kanıtı değildir.")
    elif len(des) == 1 and bel:
        m = f"Bir etken destekleniyor ({names(des)}); ayrıca belirsiz: {names(bel)}. Belirsiz etkenlerin payı dışlanamaz."
    elif len(des) == 1:
        m = f"Tek etken destekleniyor ({names(des)}); araçların bildiği diğer etkenler desteklenmiyor."
    elif bel:
        m = f"Kesin neden belirlenemedi; belirsiz: {names(bel)}."
    elif acik:
        m = "Kesin neden belirlenemedi (açıklanamayan); araçların bildiği hiçbir etken sapmayı açıklamıyor."
    else:
        m = "Sapma var, ancak desteklenen veya belirsiz bir etken yok."
    if karisik:
        m += " Eksik veri ve sapma birlikte olduğu için gerçek trafik değişimi dışlanamaz."
    return {"coklu_neden": len(des) >= 2, "desteklenen": des, "belirsiz": bel, "metin": m, "kapsam_siniri": KAPSAM_SINIRI}


def _kaynak_bilgisi(cagrilan):
    return {t: KAYNAK_BILGISI[t] for t in (cagrilan or []) if t in KAYNAK_BILGISI}


def _rank(hyps):
    """Desteklenen ve belirsiz nedenler, kanit durumuna gore sirali. Desteklenmeyenler listeye girmez."""
    keep = [h for h in hyps if h["status"] in RANK_STATUS]
    keep.sort(key=lambda h: (RANK_STATUS[h["status"]], RANK_ORDER.index(h["name"]) if h["name"] in RANK_ORDER else 99))
    return [{"sira": i, "neden": h["name"], "durum": h["status"], "kanit": h["detail"], "kaynak_araclar": h["sources"],
             "kanit_turu": KANIT_TURU.get(h["name"], ""), "nedensellik_notu": NEDENSELLIK.get(h["name"], "")}
            for i, h in enumerate(keep, 1)]


def make_report(state):
    rep = report.build(state["start"], state["end"]).model_dump()
    human = state.get("human")
    human2 = state.get("human2")
    last = human2 or human
    final = "otomatik" if last is None else OPTIONS.get(last["karar"], "ek_inceleme_gerekli")
    rep["insan_karari_2"] = human2
    rep["ek_inceleme"] = state.get("extra")
    rep["kaynakli_notlar"] = state.get("notes", [])
    rep["insan_karari"] = human
    rep["nihai_durum"] = final
    rep["arac_ciktilari"] = state.get("tool_outputs", {})
    rep["arac_plani"] = state.get("tool_plan")
    _j = state.get("judgment", {})
    rep["veri_kalitesi_uyarisi"] = _j.get("veri_kalitesi_uyarisi")
    rep["degerlendirilemedi"] = _j.get("degerlendirilemedi", False)
    rep["karisik_durum"] = _j.get("karisik_durum", False)
    rep["olasi_nedenler"] = _rank(rep["hypotheses"])
    rep["saatlik_bilgi"] = _j.get("saatlik_bilgi")
    rep["genel_degerlendirme"] = _overall(rep["olasi_nedenler"], rep["deviation"], rep["degerlendirilemedi"], rep["karisik_durum"])
    rep["kaynak_bilgisi"] = _kaynak_bilgisi((state.get("tool_plan") or {}).get("cagrilan"))
    return {"report": _clean(rep)}


def build_graph():
    g = StateGraph(State)
    g.add_node("collect", collect)
    g.add_node("judge", judge)
    g.add_node("fetch_notes", fetch_notes)
    g.add_node("ask_human", ask_human)
    g.add_node("make_report", make_report)
    g.add_edge(START, "collect")
    g.add_edge("collect", "judge")
    g.add_edge("judge", "fetch_notes")
    g.add_conditional_edges("fetch_notes", route, {"ask_human": "ask_human", "make_report": "make_report"})
    g.add_node("extra_review", extra_review)
    g.add_conditional_edges("ask_human", route_after_human, {"extra_review": "extra_review", "make_report": "make_report"})
    g.add_edge("extra_review", "make_report")
    g.add_edge("make_report", END)
    return g.compile(checkpointer=InMemorySaver())


def run(start, end, answer_fn=None):
    graph = build_graph()
    cfg = {"configurable": {"thread_id": f"{start}|{end}"}}
    res = graph.invoke({"start": start, "end": end}, cfg)
    asked = None
    for _ in range(3):
        if not res.get("__interrupt__"):
            break
        asked = res["__interrupt__"][0].value
        if answer_fn is not None:
            ans = answer_fn(asked)
        else:
            print("\nINSAN ONAYI GEREKLI:", json.dumps(asked, ensure_ascii=False, indent=2))
            ans = input("Karar (onayla / ek_inceleme / reddet): ")
        res = graph.invoke(Command(resume=ans), cfg)
    return res["report"], asked


def show(rep):
    print(rep["summary_tr"])
    g = rep.get("genel_degerlendirme")
    if g:
        print("  genel degerlendirme:", g["metin"])
    p = rep.get("arac_plani") or {}
    print("  araclar: cagrilan", len(p.get("cagrilan", [])), "| atlanan", len(p.get("atlanan", [])), "|", p.get("neden"))
    for x in rep.get("olasi_nedenler") or []:
        print(f"  {x['sira']}. olasi neden: {x['neden']} ({x['durum']}) | {x['kanit']}")
    for h in rep["hypotheses"]:
        print(f"  [{h['status']}] {report.NAMES[h['name']]}: {h['detail']}")
    print("güven:", rep["confidence"], "| insan gerekti:", rep["needs_human"],
          "| nihai durum:", rep["nihai_durum"], "| insan kararı:", rep["insan_karari"])
    print(f"kaynaklı notlar ({len(rep['kaynakli_notlar'])}):")
    for n in rep["kaynakli_notlar"]:
        print(f"  [{n['id']}] {n['text'][:90]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--answer", choices=list(OPTIONS), help="insan sorusuna otomatik yanıt (demo/test)")
    ap.add_argument("--json", help="raporu bu dosyaya yaz")
    ap.add_argument("--llm", action="store_true", help="LLM ile Turkce aciklama ekle (karar degismez)")
    a = ap.parse_args()
    fn = (lambda q: a.answer) if a.answer else None
    try:
        rep, asked = run(a.start, a.end, fn)
    except rag.RagError as e:
        print("HATA:", e)
        sys.exit(1)
    if a.llm:
        import llm_explain
        rep["llm_aciklama"] = llm_explain.explain(rep)
    show(rep)
    if rep["nihai_durum"] == "reddedildi" and not a.answer:
        import feedback
        iddia = input("Ret nedeni (" + " / ".join(feedback.CLAIMS) + "): ").strip().lower()
        if iddia in feedback.CLAIMS:
            rep["ret_incelemesi"] = feedback.review(a.start, a.end, iddia, input("Aciklama: "), input("Kaynak (yoksa bos): "))
            print(json.dumps(rep["ret_incelemesi"], ensure_ascii=False, indent=2))
    if a.llm:
        x = rep["llm_aciklama"]
        print(f"\nAciklama ({x['source']}" + (f", {x['reason']}" if x["reason"] else "") + "):", x["text"])
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print("kaydedildi:", a.json)
