import json, sys
from pathlib import Path
from typing import Literal
from pydantic import BaseModel

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence
import tools_gw as tools

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"veri_hatasi": "veri hatası", "hava": "hava", "tatil": "tatil/bayram",
         "deprem": "deprem", "aciklanamayan": "açıklanamayan"}
SOURCES = {"veri_hatasi": ["check_etl_log", "compare_same_weekday_history"],
           "hava": ["get_weather"], "tatil": ["get_calendar"],
           "deprem": ["get_earthquakes"], "aciklanamayan": []}
CAVEATS = [
    "Normal düzey: önceki 4 haftanın aynı gün ve saatlerinin ortancası; tatil haftaları bu normal düzeyi bozabilir.",
    "Hava: Open-Meteo reanalysis, tek nokta; istasyon ölçümü değil.",
    "ETL logu yalnızca bizim yüklememizde görülenleri kaydeder, boşluğun nedenini söylemez.",
    "Eşikler Nisan 2023 üzerinde ayarlandı; dış etiketli bağımsız ilk ölçüm (v3, 13 pencere) küçük örneklemlidir, ayrıntı docs/07-degerlendirme.md.",
]

class Hyp(BaseModel):
    name: str
    status: Literal["destekliyor", "desteklemiyor", "belirsiz"]
    detail: str
    sources: list[str]

class Report(BaseModel):
    window: str
    deviation: bool
    median_ratio: float | None
    hypotheses: list[Hyp]
    confidence: Literal["dusuk", "orta", "yuksek"]
    needs_human: bool
    summary_tr: str
    caveats: list[str]
    notes: list[str] = []

def details(s, e):
    etl = tools.check_etl_log(s, e)
    cmp_ = tools.compare_same_weekday_history(s, e)
    plan = evidence.context_plan(cmp_)
    if plan["gerekli"]:
        wx = tools.get_weather(s, e)
        cal = tools.get_calendar(s, e)
        eq = tools.get_earthquakes(s, e)
    else:
        wx, cal, eq = {"error": "atlandi"}, {"days": []}, {"n_relevant": 0}
    gaps = sum(1 for g in etl.get("gaps_near_window", []) if g.get("overlaps_window"))
    d = {}
    d["veri_hatasi"] = (f"Veri yükleme kaydında (ETL) işaretli saat: {cmp_.get('hours_etl_flagged', 0)}; "
                        f"incelenen aralıkla kesişen veri boşluğu: {gaps}; veri sorunu olmayan saat: {cmp_.get('n_clean_hours', 0)}.")
    if "error" in wx:
        d["hava"] = "Hava verisi bu dönem için yok."
    else:
        d["hava"] = (f"Yağış {wx['precip_total_mm']} mm"
                     + (f", en yağışlı gün {wx['precip_max_day_mm']} mm" if wx.get("precip_max_day_mm", wx["precip_total_mm"]) != wx["precip_total_mm"] else "")
                     + f" (dönem günlük p90: {wx['period_daily_precip_p90_mm']} mm); "
                     f"azami rüzgâr {wx['wind_max_kmh']} km/sa.")
    hol = sorted({x["holiday"] for x in cal.get("days", []) if x.get("holiday")})
    adm = sorted({x["date"] for x in cal.get("days", []) if x.get("admin_leave") and not x.get("half_day")})
    d["tatil"] = ("Resmî tatil: " + ", ".join(hol) + ".") if hol else (
        ("Pencerede resm\u00ee tatil yok; kamu idari izni var (yaln\u0131z devlet memurlar\u0131 i\u00e7in): " + ", ".join(adm) + ".") if adm
        else "Pencerede resm\u00ee tatil yok.")
    if "error" in eq:
        d["deprem"] = "Deprem kataloğu bu dönemi kapsamıyor."
    elif eq["n_relevant"] == 0:
        d["deprem"] = "İlgili deprem kaydı yok."
    else:
        top = eq["top_events"][0]
        ek = []
        tl = str(top.get("time_local") or "")
        if len(tl) >= 16 and tl[4] == "-":
            ek.append(f"{tl[8:10]}.{tl[5:7]}.{tl[0:4]} {tl[11:16]}")
        if top.get("place"):
            ek.append(_yer_tr(top["place"]) + ", kaynak USGS")
        if "inside_window" in top:
            ek.append("incelenen aralıkta gerçekleşti" if top["inside_window"] else "incelenen aralığın dışında")
        d["deprem"] = (f"{eq['n_relevant']} ilgili olay; en büyüğü M{top['mag']}, "
                       f"İstanbul'a {top['dist_km_to_istanbul']} km"
                       + (" (" + ", ".join(ek) + ")" if ek else "") + ". Zaman çakışması nedensellik göstermez.")
    d["aciklanamayan"] = "Diğer hipotezlerin hiçbiri sapmayı açıklamıyorsa desteklenir."
    if not plan["gerekli"]:
        for k in ("hava", "tatil", "deprem"):
            d[k] = "Ara\u00e7 \u00e7a\u011fr\u0131lmad\u0131: " + plan["neden"] + "."
    return d

_YON_TR = {"N": "kuzey", "NNE": "kuzey-kuzeydoğu", "NE": "kuzeydoğu", "ENE": "doğu-kuzeydoğu",
           "E": "doğu", "ESE": "doğu-güneydoğu", "SE": "güneydoğu", "SSE": "güney-güneydoğu",
           "S": "güney", "SSW": "güney-güneybatı", "SW": "güneybatı", "WSW": "batı-güneybatı",
           "W": "batı", "WNW": "batı-kuzeybatı", "NW": "kuzeybatı", "NNW": "kuzey-kuzeybatı"}
_ULKE_TR = {"Turkey": "Türkiye", "Greece": "Yunanistan", "Bulgaria": "Bulgaristan", "Syria": "Suriye",
            "Iran": "İran", "Iraq": "Irak", "Georgia": "Gürcistan", "Armenia": "Ermenistan",
            "Sea of Marmara": "Marmara Denizi", "Aegean Sea": "Ege Denizi", "Black Sea": "Karadeniz"}


def _yer_tr(place):
    """USGS yer metnini ('15 km W of Düzce, Turkey') Türkçe yazar; biçim tanınmazsa metni olduğu gibi bırakır."""
    import re
    p = str(place).strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*km\s+([NSEW]{1,3})\s+of\s+(.+)$", p)
    km = yon = None
    if m and m.group(2) in _YON_TR:
        km, yon, p = m.group(1), _YON_TR[m.group(2)], m.group(3).strip()
    parcalar = [x.strip() for x in p.split(",")]
    parcalar = [_ULKE_TR.get(x, x) for x in parcalar]
    if km is not None and len(parcalar) >= 1:
        parcalar.insert(1, km + " km " + yon)
    return ", ".join(parcalar)


def summarize(r, ratio_txt):
    if r.get("veri_yok"):
        s = f"{r['pencere']} aralığındaki saatlerin hiçbiri kaynak dosyada yok: veri hatası destekleniyor."
        if r.get("etl_log_yok"):
            s += " ETL logu bu dönemi kapsamıyor, dönem yüklü verinin dışında olabilir."
        return s
    if r.get("degerlendirilemedi"):
        return f"{r['pencere']} aralığı için karşılaştırılacak yeterli geçmiş veri yok; değerlendirme yapılamadı. İnsan incelemesi gerekli."
    if not r["sapma_var"]:
        if r.get("hipotezler", {}).get("veri_hatasi") == "destekliyor":
            return (f"{r['pencere']} aralığında veri sorunu olmayan saatlerde belirgin sapma yok (normale göre oran {ratio_txt}), "
                    "ancak veri kalitesi sorunu var: bu sonuç günün tamamı için güvenilir değil.")
        return f"{r['pencere']} aralığında belirgin bir sapma yok (normale göre oran {ratio_txt})."
    sup = [NAMES[k] for k, v in r["hipotezler"].items() if v == "destekliyor"]
    unc = [NAMES[k] for k, v in r["hipotezler"].items() if v == "belirsiz"]
    parts = [f"{r['pencere']} aralığında normale göre oran {ratio_txt}."]
    parts.append(("Desteklenen: " + ", ".join(sup) + ".") if sup else ("Kesin neden belirlenemedi (açıklanamayan)." if r["needs_human"] else "Desteklenen neden yok."))
    if unc:
        parts.append("Belirsiz: " + ", ".join(unc) + ".")
    if r["needs_human"]:
        parts.append("İnsan incelemesi gerekli.")
    return " ".join(parts)

def build(s, e):
    r = evidence.judge(s, e)
    d = details(s, e)
    hyps = [Hyp(name=k, status=v, detail=d[k], sources=SOURCES[k]) for k, v in r["hipotezler"].items()]
    ratio = r["medyan_oran"]
    ratio_txt = "hesaplanamadı" if ratio is None else f"{ratio:.2f}"
    return Report(window=r["pencere"], deviation=r["sapma_var"], median_ratio=ratio,
                  hypotheses=hyps, confidence=r["guven"], needs_human=r["needs_human"],
                  summary_tr=summarize(r, ratio_txt), caveats=CAVEATS, notes=r["notlar"])

if __name__ == "__main__":
    CASES = [("A_bayram", "2023-04-22 02:00", "2023-04-22 09:00"),
             ("B_etl_tek_saat", "2023-04-08 10:00", "2023-04-08 10:00"),
             ("C_aciklanamayan", "2023-05-04 00:00", "2023-05-04 23:00"),
             ("D_subat6", "2023-02-06 00:00", "2023-02-06 23:00"),
             ("E_pencere_tamamen_bos", "2023-04-19 02:00", "2023-04-19 09:00"),
             ("F_baseline_yok", "2023-01-03 08:00", "2023-01-03 12:00"),
             ("G_yari_eksik", "2023-04-19 10:00", "2023-04-19 15:00")]
    out = {}
    for label, s, e in CASES:
        rep = build(s, e)
        out[label] = rep.model_dump()
        print("\n" + label)
        print(" ", rep.summary_tr)
        for n in rep.notes:
            print("   not:", n)
        for h in rep.hypotheses:
            print(f"   [{h.status}] {NAMES[h.name]}: {h.detail}")
        print("   güven:", rep.confidence, "| insan:", rep.needs_human)
    (ROOT / "logs" / "report_demo.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nKaydedildi: logs/report_demo.json")
