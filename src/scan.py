"""Anomali taramasi: tarih araligini gun gun gecmis baseline ile karsilastirir, aday pencere listesi uretir.
Esikler evidence.py ile ayni (LOW, HIGH, GAP_SHARE); tarama yalniz aday bulur, neden aramaz (neden icin ajan: /analyze)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence

MAX_SCAN_DAYS = 62


def _compare(s, e):
    import tools  # tarama on eleme adimidir: dogrudan arac, gun basina ayri MCP sureci acilmaz
    return tools.compare_same_weekday_history(s, e)


def classify(cmp_):
    total, missing = cmp_.get("hours_in_window", 0), cmp_.get("hours_missing", 0)
    ratio = cmp_.get("median_ratio_excl_etl_flagged")
    if ratio is None:
        ratio = cmp_.get("median_ratio_all")
    if total > 0 and missing == total:
        return "veri_yok", None
    if ratio is None:
        return "degerlendirilemedi", None
    dev = ratio < evidence.LOW or ratio > evidence.HIGH
    gap = total > 0 and round(missing / total, 2) >= evidence.GAP_SHARE
    if dev and gap:
        return "eksik_veri_ve_sapma", ratio
    if gap:
        return "eksik_veri", ratio
    if dev:
        return ("dusus" if ratio < evidence.LOW else "artis"), ratio
    return "normal", ratio


def scan(start_day, end_day):
    s, e = pd.Timestamp(start_day).normalize(), pd.Timestamp(end_day).normalize()
    if e < s:
        raise ValueError("bitis, baslangictan once olamaz")
    n = (e - s).days + 1
    if n > MAX_SCAN_DAYS:
        raise ValueError(f"en fazla {MAX_SCAN_DAYS} gun taranabilir")
    rows, errors = [], []
    for d in pd.date_range(s, e, freq="D"):
        ws, we = d.strftime("%Y-%m-%d 00:00"), d.strftime("%Y-%m-%d 23:00")
        try:
            c = _compare(ws, we)
        except Exception as ex:
            errors.append({"gun": d.strftime("%Y-%m-%d"), "hata": f"{type(ex).__name__}: {ex}"[:120]})
            continue
        if isinstance(c, dict) and "error" in c:
            errors.append({"gun": d.strftime("%Y-%m-%d"), "hata": str(c["error"])[:120]})
            continue
        durum, ratio = classify(c)
        rows.append({"gun": d.strftime("%Y-%m-%d"), "baslangic": ws, "bitis": we, "durum": durum,
                     "medyan_oran": ratio, "eksik_saat": c.get("hours_missing", 0), "toplam_saat": c.get("hours_in_window", 0)})
    cand = [r for r in rows if r["durum"] != "normal"]
    return {"aralik": [s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")], "gun_sayisi": n, "taranan": len(rows),
            "normal_sayisi": len(rows) - len(cand), "adaylar": cand, "taranamayan": errors,
            "sinirlar": ["Gun duzeyi medyan: saatlik/yerel etkiler (kar firtinasi gibi) seyrelir, tarama bunlari kacirabilir.",
                         "Tarama yalniz aday listesi uretir; nedeni ajan arastirir. Aday olmayan gun 'sorunsuz' demek degildir, 'esigi asmadi' demektir.",
                         f"Esikler: oran < {evidence.LOW} veya > {evidence.HIGH}; eksik saat orani >= {evidence.GAP_SHARE}."]}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = scan(sys.argv[1], sys.argv[2])
    print(f"{r['aralik'][0]} - {r['aralik'][1]}: {r['taranan']} gun tarandi, {len(r['adaylar'])} aday, {r['normal_sayisi']} gun esigi asmadi, {len(r['taranamayan'])} taranamadi")
    for a in r["adaylar"]:
        print(f"  {a['gun']}  {a['durum']:20}  oran={a['medyan_oran']}  eksik={a['eksik_saat']}/{a['toplam_saat']}")
    for x in r["taranamayan"]:
        print("  taranamadi:", x["gun"], x["hata"])
