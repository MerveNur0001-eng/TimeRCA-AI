# -*- coding: utf-8 -*-
"""Hava kalitesi (IBB saatlik, istasyon medyani) EK SINYAL: trafikle capraz kontrol. KANIT, karar kurali degil.
Ana gosterge NO2 (kentte agirlikla tasit kaynakli); PM10 yan bilgi. Veri yoksa (data/processed/aqi_hourly.csv,
scripts/veri/fetch_hava_kalitesi.py ile indirilir) hicbir sey yapmaz.
Baseline trafikle ayni: onceki 4 haftanin ayni gun/saat medyani, en az 3 gecerli hafta; esikler 0.85 / 1.15."""
from pathlib import Path

import numpy as np
import pandas as pd

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"
FILE = PROC / "aqi_hourly.csv"
try:
    import evidence
    LOW, HIGH = evidence.LOW, evidence.HIGH
except Exception:  # pragma: no cover
    LOW, HIGH = 0.85, 1.15
MIN_SAAT = 12  # pencerede en az bu kadar saat degerlendirilebilmeli
MADDELER = ("no2", "pm10", "o3")
_c = {}


def _load():
    if "d" not in _c:
        if not FILE.exists():
            _c["d"] = None
        else:
            d = pd.read_csv(FILE, parse_dates=["ts"], index_col="ts").sort_index()
            d = d[~d.index.duplicated()]
            _c["d"] = d.reindex(pd.date_range(d.index.min(), d.index.max(), freq="h"))
    return _c["d"]


def available():
    return _load() is not None


def _ratio(s, start, end):
    vals = []
    for t in pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="h"):
        cur = s.get(t, np.nan)
        prev = [s.get(t - pd.Timedelta(weeks=k), np.nan) for k in range(1, 5)]
        prev = [float(x) for x in prev if pd.notna(x)]
        if pd.isna(cur) or len(prev) < 3:
            continue
        med = float(np.median(prev))
        if med > 0:
            vals.append(float(cur) / med)
    if len(vals) < MIN_SAAT:
        return None, len(vals)
    return round(float(np.median(vals)), 2), len(vals)


def compare(start, end):
    d = _load()
    if d is None:
        return {"error": "hava kalitesi verisi yuklu degil"}
    out = {"hours_in_window": len(pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="h"))}
    for k in MADDELER:
        if k not in d.columns:
            out["ratio_" + k], n = None, 0
        else:
            out["ratio_" + k], n = _ratio(d[k], start, end)
        if k == "no2":
            out["n_valid"] = n
    return out


def saatlik_oranlar(start, end):
    """GOSTERIM: saat saat NO2 ve PM10 orani (o saat / onceki 4 haftanin ayni gun-saati medyani, en az 3 hafta).
    Karar kurali degildir. Doner: [{'ts','no2','pm10'}]; hesaplanamayan saat None. Veri yoksa None."""
    d = _load()
    if d is None:
        return None
    out = []
    for t in pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="h"):
        p = {"ts": t.strftime("%Y-%m-%d %H:%M")}
        for k in ("no2", "pm10"):
            r = None
            if k in d.columns:
                cur = d[k].get(t, np.nan)
                prev = [float(x) for x in (d[k].get(t - pd.Timedelta(weeks=w), np.nan) for w in range(1, 5)) if pd.notna(x)]
                if pd.notna(cur) and len(prev) >= 3:
                    med = float(np.median(prev))
                    if med > 0:
                        r = round(float(cur) / med, 3)
            p[k] = r
        out.append(p)
    return out


def oran_serisi(k="no2"):
    """GOSTERIM: tum saatlik seri icin o saat / onceki 4 haftanin ayni gun-saati medyani (en az 3 hafta). Vektorel. Veri yoksa None."""
    d = _load()
    if d is None or k not in d.columns:
        return None
    s = d[k]
    prev = pd.concat([s.shift(168 * w) for w in range(1, 5)], axis=1)
    med = prev.median(axis=1).where(prev.notna().sum(axis=1) >= 3)
    return (s / med).where(med > 0).replace([np.inf, -np.inf], np.nan)


def _d(r):
    if r is None:
        return None
    return "dusuk" if r < LOW else ("yuksek" if r > HIGH else "normal")


_METIN = {
    ("dusuk", "dusuk"): ("birlikte_dusus", "Trafik düşük ve araç kaynaklı NO2 de normalin altında: gerçek bir araç azalmasıyla uyumlu; rüzgâr ve yağış da kirliliği düşürebilir, kesin değildir."),
    ("dusuk", "normal"): ("trafik_dususu_no2_normal", "Trafik düşük ama NO2 normal: hava kalitesi bu düşüşü desteklemiyor; veri hatası ya da yerel sorun olasılığı artar, ancak NO2'nin başka kaynakları da vardır; kesin değildir."),
    ("dusuk", "yuksek"): ("trafik_dususu_no2_artis", "Trafik düşük ama NO2 yüksek: hava koşulları (durgun hava gibi) ya da trafik dışı kaynaklar olabilir; trafik düşüşünü desteklemez; kesin değildir."),
    ("yuksek", "yuksek"): ("birlikte_artis", "Trafik ve NO2 birlikte yüksek: gerçek bir araç artışıyla uyumlu; kesin değildir."),
    ("yuksek", "normal"): ("trafik_artisi_no2_normal", "Trafik yüksek ama NO2 normal: hava kalitesi bu artışı desteklemiyor; veri hatası ya da yerel yoğunluk olasılığı artar; kesin değildir."),
    ("yuksek", "dusuk"): ("trafik_artisi_no2_dusus", "Trafik yüksek ama NO2 düşük: rüzgâr/yağış kirliliği temizlemiş olabilir ya da trafik artışı veri kaynaklı olabilir; kesin değildir."),
}


_HAVA_ETKISI = ("birlikte_dusus_hava_olabilir", "Trafik düşük, NO2 ve PM10 da normalin altında: PM10'un birlikte düşmesi yağış ya da rüzgâr gibi hava etkisini de akla getirir; araç azalmasıyla tek başına açıklanamaz; kesin değildir.")


def signal(trafik_orani, no2_orani, pm10_orani=None):
    """None: sinyal yok (trafik normal ya da trafik orani yok). Yoksa {'kod','metin'}. Karar kuraline girmez.
    NO2 ile birlikte PM10 da dusukse (hava temizlemesi olasiligi) metin buna gore temkinli olur."""
    t, a = _d(trafik_orani), _d(no2_orani)
    if t == "dusuk" and a == "dusuk" and _d(pm10_orani) == "dusuk":
        return {"kod": _HAVA_ETKISI[0], "metin": _HAVA_ETKISI[1]}
    if t is None or t == "normal":
        return None
    if a is None:
        return {"kod": "hava_verisi_yetersiz", "metin": "Hava kalitesi verisi bu aralık için yetersiz; çapraz kontrol yapılamadı."}
    if a == "normal" or (t, a) in _METIN:
        kod, metin = _METIN[(t, a)]
        return {"kod": kod, "metin": metin}
    return None  # pragma: no cover
