# -*- coding: utf-8 -*-
"""Trafik ve hava kalitesi (NO2) YALNIZ GOSTERIM ozetleri: bayram gunleri tablosu ve gun gun iliski (dagilim) verisi.
Karar kurali degildir: gun durumlari series.daily'den (scan ile ayni esikler ve ayni temiz-saat kurali) aynen gelir;
NO2 orani air_quality ile hesaplanir. Birlikte hareket nedeni kanitlamaz."""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

GECERLI = ("normal", "dusus", "artis")     # eksik veri / veri yok gunleri oran hesabina girmez
MIN_NOKTA = 20
# YALNIZ GOSTERIM (karar kurali degil): 'hava benzer gun' suzgeci. NO2 yagis ve ruzgardan da etkilendigi icin, o gunun ve kiyas
# gunlerinin (onceki 4 hafta ayni gun) havasi benzerse trafik-NO2 iliskisi daha temiz okunur.
YAGIS_MM = 1.0            # gunluk yagis bunun altindaysa "yagissiz"
RUZGAR_ORAN = (0.75, 1.33)  # gunluk ortalama ruzgar / kiyas gunlerinin ortancasi bu aralikta ise "ruzgar benzer"                              # bunun altinda egim/korelasyon soylenmez
_cache = {}


def _gunluk_noktalar(a, b):
    """a..b (date) araligi icin gunluk trafik noktalari; 62'lik parcalarla (series.MAX_DAILY_DAYS)."""
    import series
    import tools
    h = tools._hourly()["total_vehicles"]
    out, s = [], a
    while s <= b:
        e = min(b, s + timedelta(days=series.MAX_DAILY_DAYS - 1))
        r = series.daily(h, str(s), str(e), series.etl_flagged(pd.Timestamp(s), pd.Timestamp(e) + pd.Timedelta(hours=23)))
        out += r["noktalar"]
        s = e + timedelta(days=1)
    return out


def _hava(gun):
    import air_quality
    c = air_quality.compare(f"{gun} 00:00", f"{gun} 23:00")
    if "error" in c:
        return None, None
    return c.get("ratio_no2"), c.get("ratio_pm10")


def _kapsam(cover):
    return [(s, e) for s, e in cover["traffic"]]


def tum_gunler(cover):
    """Yuklu tum trafik gunleri: [{gun, durum, trafik_orani, no2_orani, pm10_orani}] (yalniz GECERLI durumlar). Surec boyunca onbellek."""
    anahtar = tuple(cover["traffic"])
    if _cache.get("k") == anahtar:
        return _cache["v"]
    import air_quality
    var = air_quality.available()
    sonuc = []
    for s, e in _kapsam(cover):
        for p in _gunluk_noktalar(s, e):
            if p["durum"] not in GECERLI or p["oran"] is None:
                continue
            n, pm = _hava(p["gun"]) if var else (None, None)
            sonuc.append({"gun": p["gun"], "durum": p["durum"], "trafik_orani": p["oran"], "no2_orani": n, "pm10_orani": pm})
    _cache["k"], _cache["v"] = anahtar, sonuc
    return sonuc


def _d(r):
    import air_quality
    return None if r is None else air_quality._d(r)


def bayram_ozeti(cover):
    """Yuklu donemdeki tum resmi tatil gunlerinde trafik ve NO2 orani."""
    import tools
    tum = {g["gun"]: g for g in tum_gunler(cover)}
    gunler = []
    for s, e in _kapsam(cover):
        for d in tools.get_calendar(f"{s} 00:00", f"{e} 00:00")["days"]:
            if d.get("holiday") and d["date"] in tum:
                g = tum[d["date"]]
                gunler.append({"gun": d["date"], "ad": d["holiday"], "durum": g["durum"], "trafik_orani": g["trafik_orani"],
                               "no2_orani": g["no2_orani"], "no2_durum": _d(g["no2_orani"])})
    gunler.sort(key=lambda x: x["gun"])
    td = [g for g in gunler if g["durum"] == "dusus"]
    medyan = lambda xs: round(float(np.median(xs)), 2) if xs else None
    ozet = {"toplam": len(gunler), "trafik_dusen": len(td),
            "no2_de_dusen": sum(1 for g in td if g["no2_durum"] == "dusuk"),
            "no2_normal": sum(1 for g in td if g["no2_durum"] == "normal"),
            "no2_ters": sum(1 for g in td if g["no2_durum"] == "yuksek"),
            "no2_yok": sum(1 for g in td if g["no2_durum"] is None),
            "medyan_trafik_orani": medyan([g["trafik_orani"] for g in gunler]),
            "medyan_no2_orani": medyan([g["no2_orani"] for g in gunler if g["no2_orani"] is not None])}
    return {"gunler": gunler, "ozet": ozet}


def _hava_gunluk():
    """{gun: (gunluk_yagis_mm, ortalama_ruzgar_kmh)}; hava verisi yoksa {}."""
    try:
        import tools
        w = tools._weather()
        g = w.groupby(w.index.normalize())
        yagis, ruzgar = g["precipitation"].sum(), g["wind_speed_10m"].mean()
        return {str(d.date()): (float(yagis[d]), float(ruzgar[d])) for d in yagis.index}
    except Exception:
        return {}


def benzer_hava(gun, hv):
    """Gun ile onceki 4 hafta ayni gununun havasi benzer mi? Doner: True/False ya da None (hava verisi yetersiz)."""
    d = date.fromisoformat(gun)
    bu = hv.get(gun)
    onceki = [hv.get(str(d - timedelta(weeks=k))) for k in range(1, 5)]
    onceki = [x for x in onceki if x is not None]
    if bu is None or len(onceki) < 3:
        return None
    yagisli_onceki = sum(1 for x in onceki if x[0] >= YAGIS_MM)
    med = float(np.median([x[1] for x in onceki]))
    if bu[0] >= YAGIS_MM or yagisli_onceki > 1 or med <= 0:
        return False
    return RUZGAR_ORAN[0] <= bu[1] / med <= RUZGAR_ORAN[1]


def _esik():
    import air_quality
    return air_quality.LOW, air_quality.HIGH


def _dogru(nok):
    """(egim, korelasyon) ya da (None, None): en az MIN_NOKTA gun ve degisim yoksa hesaplanmaz."""
    if len(nok) < MIN_NOKTA:
        return None, None
    x = np.array([g["trafik_orani"] for g in nok], float)
    y = np.array([g["no2_orani"] for g in nok], float)
    if x.std() == 0 or y.std() == 0:
        return None, None
    return round(float(np.polyfit(x, y, 1)[0]), 2), round(float(np.corrcoef(x, y)[0, 1]), 2)


def iliski(cover):
    """Gun gun (trafik orani, NO2 orani) noktalari, dogrusal egim ve korelasyon. Nedensellik iddiasi yok."""
    nok = [g for g in tum_gunler(cover) if g["no2_orani"] is not None]
    r = {"noktalar": [{"gun": g["gun"], "trafik": g["trafik_orani"], "no2": g["no2_orani"], "durum": g["durum"]} for g in nok],
         "n": len(nok), "egim": None, "korelasyon": None}
    gr = {}
    for d in ("dusus", "normal", "artis"):
        v = [g["no2_orani"] for g in nok if g["durum"] == d]
        gr[d] = {"n": len(v), "medyan_no2": round(float(np.median(v)), 2) if v else None,
                 "no2_dusuk_pay": round(sum(1 for z in v if z < _esik()[0]) / len(v), 2) if v else None}
    r["gruplar"] = gr
    r["egim"], r["korelasyon"] = _dogru(nok)
    hv = _hava_gunluk()
    if hv:
        for p, g in zip(r["noktalar"], nok):
            p["benzer_hava"] = benzer_hava(g["gun"], hv)
        bz = [g for g, p in zip(nok, r["noktalar"]) if p["benzer_hava"]]
        e, k = _dogru(bz)
        gb = {}
        for d in ("dusus", "normal", "artis"):
            v = [g["no2_orani"] for g in bz if g["durum"] == d]
            gb[d] = {"n": len(v), "medyan_no2": round(float(np.median(v)), 2) if v else None,
                     "no2_dusuk_pay": round(sum(1 for z in v if z < _esik()[0]) / len(v), 2) if v else None}
        r["benzer_hava"] = {"n": len(bz), "egim": e, "korelasyon": k, "gruplar": gb,
                            "kriter": f"gün yağışsız (<{YAGIS_MM:g} mm), önceki 4 haftanın aynı günlerinin en fazla biri yağışlı, rüzgâr kıyas günlerinin {RUZGAR_ORAN[0]:g}-{RUZGAR_ORAN[1]:g} katı"}
    return r


KIRP = (0.2, 3.0)        # gosterim: uc saatlik oranlar (kucuk sayilarla bolum) ortalamayi bozmasin
MAX_GECIKME = 4          # saat


def _saatlik(cover):
    """(trafik_orani, no2_orani) saatlik seriler (ETL isaretli saatler trafikte NaN), KIRP ile kirpilmis. Onbellekli."""
    anahtar = ("saatlik", tuple(cover["traffic"]))
    if _cache.get("sk") == anahtar:
        return _cache["sv"]
    import air_quality
    import series
    import tools
    h = tools._hourly()["total_vehicles"]
    parcalar = []
    for s, e in _kapsam(cover):
        a, b = pd.Timestamp(s), pd.Timestamp(e) + pd.Timedelta(hours=23)
        parcalar.append(series.baseline_frame(h, a, b, series.etl_flagged(a, b))["ratio_temiz"])
    tr = pd.concat(parcalar).replace([np.inf, -np.inf], np.nan).clip(*KIRP)
    n2 = air_quality.oran_serisi("no2")
    n2 = None if n2 is None else n2.clip(*KIRP)
    _cache["sk"], _cache["sv"] = anahtar, (tr, n2)
    return tr, n2


def saatlik_gecikme(cover):
    """Saat saat trafik orani ile NO2 orani: 0..MAX_GECIKME saat gecikmeyle Spearman bagintisi. Nedensellik iddiasi yok."""
    tr, n2 = _saatlik(cover)
    if n2 is None:
        return None
    lagler = []
    for L in range(MAX_GECIKME + 1):
        df = pd.concat({"t": tr, "n": n2.shift(-L)}, axis=1).dropna()
        lagler.append({"gecikme": L, "n": int(len(df)), "korelasyon": round(float(df["t"].rank().corr(df["n"].rank())), 2) if len(df) >= 100 else None})
    gecerli = [x for x in lagler if x["korelasyon"] is not None]
    en = max(gecerli, key=lambda x: x["korelasyon"]) if gecerli else None
    return {"lagler": lagler, "en_iyi_gecikme": en["gecikme"] if en else None, "en_iyi_korelasyon": en["korelasyon"] if en else None,
            "saat_sayisi": lagler[0]["n"]}


def gun_profili(cover):
    """Resmi tatil gunleri ile diger gunlerin gun ici (saat 0-23) ortalama trafik ve NO2 orani."""
    import tools
    tr, n2 = _saatlik(cover)
    if n2 is None:
        return None
    tatil = set()
    for s, e in _kapsam(cover):
        tatil |= {d["date"] for d in tools.get_calendar(f"{s} 00:00", f"{e} 00:00")["days"] if d.get("holiday")}
    df = pd.concat({"t": tr, "n": n2}, axis=1)
    gun = pd.Series(df.index.strftime("%Y-%m-%d"), index=df.index)
    ist = gun.isin(tatil)
    out = {}
    for ad, m in (("tatil", ist), ("diger", ~ist)):
        g = df[m]
        ort = g.groupby(g.index.hour).mean()
        out[ad] = {"trafik": [None if pd.isna(ort["t"].get(h)) else round(float(ort["t"][h]), 2) for h in range(24)],
                   "no2": [None if pd.isna(ort["n"].get(h)) else round(float(ort["n"][h]), 2) for h in range(24)],
                   "gun_sayisi": int(gun[m].nunique())}
    return out


def tespit_ozeti(cover):
    """Resmi tatil gunlerinin kacinda trafik dusus olarak bulundu; tatil disi gunlerin kacinda olağandışı isaretlendi. YALNIZ GOSTERIM."""
    import tools
    tum = tum_gunler(cover)
    tatil = set()
    for s, e in _kapsam(cover):
        tatil |= {d["date"] for d in tools.get_calendar(f"{s} 00:00", f"{e} 00:00")["days"] if d.get("holiday")}
    t = [g for g in tum if g["gun"] in tatil]
    d = [g for g in tum if g["gun"] not in tatil]
    say = lambda xs, k: sum(1 for g in xs if g["durum"] == k)
    return {"tatil": {"toplam": len(t), "dusus": say(t, "dusus"), "normal": say(t, "normal"), "artis": say(t, "artis")},
            "diger": {"toplam": len(d), "dusus": say(d, "dusus"), "normal": say(d, "normal"), "artis": say(d, "artis")},
            "degerlendirilen_gun": len(tum)}
