import json
import numpy as np
import pandas as pd
import holidays
import calendar_ctx
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
LOG = ROOT / "logs" / "etl_log.jsonl"
MONTHS = ['2021-12', '2022-01', '2022-10', '2022-11', '2023-01', '2023-02', '2023-03', '2023-04', '2023-05', '2023-06', '2023-07', '2023-08', '2023-09', '2023-11', '2023-12', '2024-01', '2024-03', '2024-04']
_c = {}

def _hourly():
    if "h" not in _c:
        h = pd.concat([pd.read_parquet(PROC / f"hourly_{m}.parquet") for m in MONTHS]).sort_index()
        h = h[~h.index.duplicated()]
        _c["h"] = h.reindex(pd.date_range(h.index.min(), h.index.max(), freq="h"))
    return _c["h"]

def _weather():
    if "w" not in _c:
        _c["w"] = pd.concat([pd.read_parquet(p) for p in sorted(PROC.glob("weather_*.parquet"))]).sort_index()
    return _c["w"]

def _ts(x):
    return pd.Timestamp(x)

def check_etl_log(start, end):
    s, e = _ts(start), _ts(end)
    pad = pd.Timedelta(hours=1)
    runs = {}
    for line in LOG.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        runs.setdefault(r["run_id"], {"ts": r["ts"], "st": {}})["st"][r["stage"]] = r["details"]
    latest = {}
    for run in runs.values():
        m = run["st"]["run_started"]["month"]
        if m not in latest or run["ts"] > latest[m]["ts"]:
            latest[m] = run
    months = [str(p) for p in pd.period_range(s - pad, e + pad, freq="M")]
    have = [m for m in months if m in latest]
    missing_months = [m for m in months if m not in latest]
    if not have:
        return {"tool": "check_etl_log", "error": "bu donem icin log yok: " + ", ".join(months)}
    gaps, cov, dens = [], [], []
    for m in have:
        st = latest[m]["st"]
        for blk in st["missing_hours"]["blocks"]:
            bs, be = _ts(blk["start"]), _ts(blk["end"])
            if bs <= e + pad and be >= s - pad:
                gaps.append({**blk, "overlaps_window": bool(bs <= e and be >= s)})
        cov += [x for x in st["cell_coverage"]["low_coverage_hours"] if s <= _ts(x["ts"]) <= e]
        dens += [x for x in st["density_suspect"]["hours"] if s <= _ts(x["ts"]) <= e]
    return {"tool": "check_etl_log", "months_checked": have, "months_without_log": missing_months,
            "gaps_near_window": gaps, "low_cell_coverage_hours": cov, "density_suspect_hours": dens,
            "limits": "Log yalniz yuklemede gorulenleri kaydeder, bosluk nedenini soylemez. Logu olmayan aylar icin bilgi yok (months_without_log)."}

def compare_same_weekday_history(start, end):
    h = _hourly()["total_vehicles"]
    log = check_etl_log(start, end)
    flagged = {_ts(x["ts"]) for x in log.get("low_cell_coverage_hours", []) + log.get("density_suspect_hours", [])}
    rows = []
    for t in pd.date_range(_ts(start), _ts(end), freq="h"):
        cur = h.get(t, np.nan)
        prev = [h.get(t - pd.Timedelta(weeks=k), np.nan) for k in range(1, 5)]
        prev = [float(x) for x in prev if pd.notna(x)]
        if pd.isna(cur) or len(prev) < 3:
            rows.append({"ts": str(t), "status": "veri_yok" if pd.isna(cur) else "baseline_yok"})
            continue
        b = float(np.median(prev))
        rows.append({"ts": str(t), "value": float(cur), "baseline": b, "ratio": round(float(cur) / b, 2),
                     "n_weeks": len(prev), "etl_flagged": t in flagged})
    ok = [r for r in rows if "ratio" in r]
    clean = [r for r in ok if not r["etl_flagged"]]
    med = lambda xs: round(float(np.median([r["ratio"] for r in xs])), 2) if xs else None
    s0 = _ts(start)
    return {"tool": "compare_same_weekday_history",
            "hours_in_window": len(rows),
            "hours_missing": sum(r.get("status") == "veri_yok" for r in rows),
            "hours_no_baseline": sum(r.get("status") == "baseline_yok" for r in rows),
            "hours_etl_flagged": sum(r["etl_flagged"] for r in ok),
            "median_ratio_all": med(ok),
            "median_ratio_excl_etl_flagged": med(clean),
            "n_clean_hours": len(clean),
            "n_clean_below_0.7": sum(r["ratio"] < 0.7 for r in clean),
            "n_clean_above_1.3": sum(r["ratio"] > 1.3 for r in clean),
            "most_deviant_clean_hours": sorted(clean, key=lambda r: abs(r["ratio"] - 1), reverse=True)[:3],
            "baseline_days_of_first_hour": [str((s0 - pd.Timedelta(weeks=k)).date()) for k in range(1, 5)],
            "limits": "Baseline = onceki 4 haftanin ayni gun-saati medyani, en az 3 gecerli hafta gerekir. baseline_days_of_first_hour icin get_calendar ve get_weather ile baseline kirliligini kontrol et."}

def get_weather(start, end):
    w = _weather()
    win = w.loc[_ts(start):_ts(end)]
    if len(win) == 0:
        return {"tool": "get_weather", "error": "bu donem icin hava verisi indirilmedi"}
    daily = w["precipitation"].groupby(w.index.normalize()).sum()
    return {"tool": "get_weather", "hours": len(win),
            "precip_total_mm": round(float(win["precipitation"].sum()), 1),
            "precip_max_day_mm": round(float(win["precipitation"].sum() if win.index.normalize().nunique() == 1 else win["precipitation"].groupby(win.index.normalize()).sum().max()), 1),
            "precip_max_hour_mm": round(float(win["precipitation"].max()), 1),
            "wind_max_kmh": round(float(win["wind_speed_10m"].max()), 1),
            "temp_mean_c": round(float(win["temperature_2m"].mean()), 1),
            "period_daily_precip_median_mm": round(float(daily.median()), 1),
            "period_daily_precip_p90_mm": round(float(daily.quantile(0.9)), 1),
            "limits": "Open-Meteo reanalysis, tek nokta (41.01, 28.98), istasyon olcumu degil, tum Istanbul'u temsil etmez."}

def get_calendar(start, end):
    s, e = _ts(start).normalize(), _ts(end).normalize()
    tr = holidays.Turkey(years=sorted({s.year, e.year}))
    days = []
    for d in pd.date_range(s, e, freq="D"):
        hol = tr.get(d.date())
        row = {"date": str(d.date()), "weekday": d.day_name(), "holiday": hol,
               "day_before_holiday": bool(tr.get((d + pd.Timedelta(days=1)).date()))}
        row.update(calendar_ctx.day_context(str(d.date()), d.weekday(), bool(hol)))
        days.append(row)
    return {"tool": "get_calendar", "days": days, "limits": calendar_ctx.LIMITS}
QUAKE_COVER = [('2021-11-01', '2022-02-01'), ('2022-09-01', '2022-12-01'), ('2023-02-01', '2024-02-01'), ('2024-03-01', '2024-05-01')]

def get_earthquakes(start, end, min_mag=4.5, max_km=500, big_mag=6.5, lookback_h=12):
    s, e = _ts(start), _ts(end)
    if not any(_ts(a) <= s and e < _ts(b) for a, b in QUAKE_COVER):
        return {"tool": "get_earthquakes", "error": "bu donem icin deprem katalogu indirilmedi", "covered_ranges": QUAKE_COVER}
    if "q" not in _c:
        q = pd.read_csv(ROOT / "data" / "raw" / "usgs_quakes.csv", parse_dates=["time_utc"])
        q["t_local"] = q["time_utc"] + pd.Timedelta(hours=3)
        la1, lo1 = np.radians(41.01), np.radians(28.98)
        la2, lo2 = np.radians(q["lat"]), np.radians(q["lon"])
        x = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
        q["dist_km"] = 6371 * 2 * np.arcsin(np.sqrt(x))
        _c["q"] = q
    q = _c["q"]
    near = (q["mag"] >= min_mag) & (q["dist_km"] <= max_km)
    sel = q[(q["t_local"] >= s - pd.Timedelta(hours=lookback_h)) & (q["t_local"] <= e) & (near | (q["mag"] >= big_mag))]
    sel = sel.sort_values("mag", ascending=False)
    top = [{"time_local": str(r.t_local), "mag": float(r.mag), "place": r.place,
            "dist_km_to_istanbul": int(round(r.dist_km)), "inside_window": bool(s <= r.t_local <= e)}
           for r in sel.head(5).itertuples()]
    return {"tool": "get_earthquakes", "source": "USGS FDSN, onceden indirilmis katalog (indirilen M>=4, tam olan M>=4,5)",
            "n_relevant": int(len(sel)), "top_events": top,
            "limits": "Katalog yaklasik M4,5 ustu icin tam (USGS ComCat dunya geneli tamlik M4,5), M4-4,5 arasi eksik olabilir. Alaka kurali: M>=4.5 ve <=500 km, veya M>=6.5 her mesafe; bu esikler secimdir, trafik etkisi icin bilinen bir esik degil. Buyukluk ve mesafe tek basina nedensellik gostermez, zaman sirasina bak."}

def get_air_quality_signal(start, end):
    """Hava kalitesi (IBB saatlik, istasyon medyani) ile trafik oranini yan yana okur. EK KANIT: karar kuralinda kullanilmaz."""
    try:
        import air_quality
        import scan
    except Exception as ex:
        return {"tool": "get_air_quality_signal", "error": f"modul yuklenemedi: {type(ex).__name__}"}
    if not air_quality.available():
        return {"tool": "get_air_quality_signal", "error": "hava kalitesi verisi yok (python scripts\\veri\\fetch_hava_kalitesi.py ile indirilir)"}
    try:
        tr = scan.classify(scan._compare(start, end))[1]
        c = air_quality.compare(start, end)
    except Exception as ex:
        return {"tool": "get_air_quality_signal", "error": f"hesaplanamadi: {type(ex).__name__}"}
    if "error" in c:
        return {"tool": "get_air_quality_signal", "error": c["error"]}
    sig = air_quality.signal(tr, c.get("ratio_no2"), c.get("ratio_pm10"))
    return {"tool": "get_air_quality_signal", "kaynak": "IBB hava kalitesi (saatlik, istasyon medyani)", "trafik_orani": tr,
            "no2_orani": c.get("ratio_no2"), "pm10_orani": c.get("ratio_pm10"), "o3_orani": c.get("ratio_o3"),
            "sinyal": sig, "limits": "Ek kanit; nedensellik kaniti degil, hipotez puanina girmez. Ruzgar/yagis kirliligi degistirir; NO2'nin tasit disi kaynaklari vardir."}


if __name__ == "__main__":
    cases = [("2023-04-22 02:00", "2023-04-22 09:00"),
             ("2023-04-08 00:00", "2023-04-08 23:00"),
             ("2023-05-04 00:00", "2023-05-04 23:00"),
             ("2023-04-26 07:00", "2023-04-26 11:00")]
    for s, e in cases:
        print("=" * 60, s, "->", e)
        for fn in (check_etl_log, compare_same_weekday_history, get_weather, get_calendar):
            print(json.dumps(fn(s, e), ensure_ascii=False, default=str)[:700])
