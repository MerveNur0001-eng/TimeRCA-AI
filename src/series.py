"""Grafik verisi: saatlik/gunluk seri, ayni gun-saati baseline'i (onceki 4 hafta medyani, en az 3 gecerli hafta) ve oran.
ETL'nin isaretledigi saatler (dusuk hucre kapsami, yogunluk supheli) ajanla ayni sekilde ele alinir: bolge ve gun orani hesabina girmez.
Bolge isaretleme yalniz GOSTERIM icindir: ardisik MIN_RUN saat bant disinda ise bolge cizilir. Karar kurali degildir;
nedeni ajan arastirir (/analyze). Esikler evidence.py ile ayni (LOW, HIGH)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence

MAX_HOURLY_DAYS = 14
MAX_DAILY_DAYS = 62
MIN_RUN = 3
DOT_MIN_SAAT = 6   # YALNIZ GOSTERIM: gunluk grafikteki mavi nokta icin en kisa bolge suresi (karar kurali degildir)
_cache = {}


def etl_flagged(start, end):
    """tools.compare_same_weekday_history ile ayni kaynak: check_etl_log'un isaretledigi saatler."""
    import tools
    log = tools.check_etl_log(str(start), str(end))
    if not isinstance(log, dict) or "error" in log:
        return set()
    return {pd.Timestamp(x["ts"]) for x in log.get("low_cell_coverage_hours", []) + log.get("density_suspect_hours", [])}


def baseline_frame(h, start, end, flagged=None):
    """h: saatlik duzenli indeksli Series. Doner: value, baseline, ratio, ratio_temiz (ETL isaretli saatler NaN), etl, n_weeks."""
    idx = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="h")
    prev = pd.concat([h.reindex(idx - pd.Timedelta(weeks=k)).set_axis(idx) for k in range(1, 5)], axis=1)
    n = prev.notna().sum(axis=1)
    base = prev.median(axis=1).where(n >= 3)
    cur = h.reindex(idx)
    ratio = (cur / base).round(3)
    etl = pd.Series(idx.isin(list(flagged)) if flagged else False, index=idx)
    return pd.DataFrame({"value": cur, "baseline": base, "ratio": ratio, "ratio_temiz": ratio.where(~etl),
                         "etl": etl, "n_weeks": n})


def _num(x):
    return None if pd.isna(x) else round(float(x), 3)


def segments(df, low=None, high=None, min_run=MIN_RUN):
    low = evidence.LOW if low is None else low
    high = evidence.HIGH if high is None else high
    col = "ratio_temiz" if "ratio_temiz" in df else "ratio"
    out, run = [], []

    def flush():
        if len(run) >= min_run:
            r = df.loc[run, col]
            med = round(float(r.median()), 2)
            out.append({"baslangic": run[0].strftime("%Y-%m-%d %H:%M"), "bitis": run[-1].strftime("%Y-%m-%d %H:%M"),
                        "saat": len(run), "yon": "dusus" if r.iloc[0] < low else "artis", "medyan_oran": med,
                        "siddet": round(len(run) * abs(1 - med), 2)})
    cur_dir = None
    for t, r in df[col].items():
        d = None if pd.isna(r) else ("dusus" if r < low else ("artis" if r > high else None))
        if d is not None and d == cur_dir:
            run.append(t)
            continue
        flush()
        run.clear()
        cur_dir = d
        if d is not None:
            run.append(t)
    flush()
    return out


def hourly(h, start, end, flagged=None):
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if e < s:
        raise ValueError("bitis, baslangictan once olamaz")
    if (e - s) > pd.Timedelta(days=MAX_HOURLY_DAYS):
        raise ValueError(f"saatlik gorunum en fazla {MAX_HOURLY_DAYS} gun")
    df = baseline_frame(h, s, e, flagged)
    pts = [{"ts": t.strftime("%Y-%m-%d %H:%M"), "deger": _num(r.value), "baseline": _num(r.baseline), "oran": _num(r.ratio),
            "etl": bool(r.etl)} for t, r in df.iterrows()]
    return {"mod": "saatlik", "aralik": [s.strftime("%Y-%m-%d %H:%M"), e.strftime("%Y-%m-%d %H:%M")], "noktalar": pts,
            "bolgeler": segments(df), "esikler": [evidence.LOW, evidence.HIGH], "min_ardisik_saat": MIN_RUN,
            "not": limits()}


def _durum(vals, med):
    """scan.classify ile ayni kural: saatlerin >=GAP_SHARE'i eksikse sapma guvenilir sayilmaz."""
    if vals.isna().all():
        return "veri_yok"
    if med is None:
        return "baseline_yok"
    dev = med < evidence.LOW or med > evidence.HIGH
    gap = bool(vals.isna().mean() >= evidence.GAP_SHARE)
    if dev and gap:
        return "eksik_veri_ve_sapma"
    if gap:
        return "eksik_veri"
    return ("dusus" if med < evidence.LOW else "artis") if dev else "normal"


def daily(h, start_day, end_day, flagged=None):
    s, e = pd.Timestamp(start_day).normalize(), pd.Timestamp(end_day).normalize()
    if e < s:
        raise ValueError("bitis, baslangictan once olamaz")
    if (e - s).days + 1 > MAX_DAILY_DAYS:
        raise ValueError(f"gunluk gorunum en fazla {MAX_DAILY_DAYS} gun")
    df = baseline_frame(h, s, e + pd.Timedelta(hours=23), flagged)
    segs = segments(df)
    per_day, per_long = {}, {}
    for sg in segs:
        k = sg["baslangic"][:10]
        per_day[k] = per_day.get(k, 0) + 1
        if sg["saat"] >= DOT_MIN_SAAT:
            per_long[k] = per_long.get(k, 0) + 1
    pts = []
    for d, g in df.groupby(df.index.normalize()):
        clean, allr = g["ratio_temiz"].dropna(), g["ratio"].dropna()
        r = clean if len(clean) else allr          # scan.classify ile ayni: temiz saat yoksa tum saatler
        med = float(r.median()) if len(r) else None
        pts.append({"gun": d.strftime("%Y-%m-%d"), "baslangic": d.strftime("%Y-%m-%d 00:00"), "bitis": d.strftime("%Y-%m-%d 23:00"),
                    "oran": None if med is None else round(med, 2), "eksik_saat": int(g["value"].isna().sum()), "saat": int(len(g)),
                    "etl_isaretli": int(g["etl"].sum()), "etl_pay_yuksek": bool(len(g) and g["etl"].sum() / len(g) >= evidence.GAP_SHARE), "saatlik_bolge": per_day.get(d.strftime("%Y-%m-%d"), 0),
                    "saatlik_bolge_uzun": per_long.get(d.strftime("%Y-%m-%d"), 0),
                    "durum": _durum(g["value"], None if med is None else round(med, 2))})
    return {"mod": "gunluk", "aralik": [s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")], "noktalar": pts, "bolgeler": segs,
            "esikler": [evidence.LOW, evidence.HIGH], "not": limits()}


def limits():
    return ["Çizgi: gerçek trafik. Kesikli çizgi: önceki 4 haftanın aynı gün ve saatindeki tipik değer. Bant: "
            f"{evidence.LOW}-{evidence.HIGH} oran.",
            f"İşaretli bölge = en az {MIN_RUN} ardışık saat bant dışında. Bu yalnızca gösterimdir, neden değildir ve karar kuralı değildir.",
            "Veri sorunu kaydedilen saatler bölge ve gün oranı hesabına girmez; gri şeritle gösterilir.",
            f"Günlük görünümde günün genel oranı kısa süreli düşüşleri seyreltir; mavi nokta en az {DOT_MIN_SAAT} saatlik bölgeleri gösterir (daha kısa bölgeler saatlik görünümde görülür).",
            "Karşılaştırma yapılan önceki haftalar tatil ya da hava olaylarından etkilenmiş olabilir; bu yüzden normal düzey her zaman kusursuz değildir."]


def base_rates(h):
    """Yuklu tum veride bolge sikligi: kisa bolgelerin ne kadar siradan oldugunu gostermek icin (bir kez hesaplanir)."""
    if "taban" not in _cache:
        v = h.dropna()
        df = baseline_frame(h, v.index.min(), v.index.max(), etl_flagged(v.index.min(), v.index.max()))
        segs = segments(df)
        valid = df["ratio_temiz"].dropna()
        per = valid.groupby(valid.index.normalize()).size()
        n = int((per >= 12).sum())
        days_with = len({s["baslangic"][:10] for s in segs})
        n12 = sum(1 for s in segs if s["saat"] >= 12)
        days_long = len({s["baslangic"][:10] for s in segs if s["saat"] >= DOT_MIN_SAAT})
        _cache["taban"] = {"gun": n, "bolgeli_gun_orani": round(days_with / n, 2) if n else None,
                           "bolge_gun_basina": round(len(segs) / n, 2) if n else None,
                           "bolge_12h_gun_basina": round(n12 / n, 3) if n else None,
                           "bolgeli_gun_orani_uzun": round(days_long / n, 2) if n else None,
                           "nokta_min_saat": DOT_MIN_SAAT}
    return _cache["taban"]


def series(mode, start, end):
    import tools
    h = tools._hourly()["total_vehicles"]
    if mode == "saatlik":
        r = hourly(h, start, end, etl_flagged(start, end))
    else:
        s, e = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
        r = daily(h, start, end, etl_flagged(s, e + pd.Timedelta(hours=23)))
    r["taban"] = base_rates(h)
    return r