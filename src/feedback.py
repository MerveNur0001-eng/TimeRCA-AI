"""Ret nedeni incelemesi ve geri bildirim kaydi (HITL).

Kullanicinin iddiasi otomatik dogru kabul edilmez:
1) review(): iddia arac kanitiyla sinanir; sonuc ve gerekce SQLite'a yazilir.
Bu modul hipotez durumlarini DEGISTIRMEZ; karar evidence.judge'da kalir."""
import argparse, json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "logs" / "feedback.sqlite"
CLAIMS = ("veri_hatasi", "tatil", "hava", "deprem", "sapma_yok", "diger")
NEAR = 0.05
OUTCOME = {"sonuc_ayni": "sonuc_ayni", "kismi": "ek_inceleme_gerekli",
           "kanit_yok": "sonuc_korundu", "dogrulanamadi": "ek_inceleme_gerekli"}
MESAJ = {
    "sonuc_ayni": "Iddia ajanin sonucuyla ayni yonde; degisiklik gerekmiyor.",
    "kismi": "Iddiayi kismen destekleyen kanit var ama karar esigini gecmiyor. Sonuc otomatik degistirilmedi; ek inceleme gerekli.",
    "kanit_yok": "Eldeki arac kaniti iddiayi desteklemiyor; ajan sonucunu koruyor. Gerekce asagida.",
    "dogrulanamadi": "Iddia eldeki araclarla sinanamadi; sonuc korunur, ek inceleme gerekli.",
}
SQL = """CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, bas TEXT, bit TEXT, iddia TEXT, aciklama TEXT, kaynak TEXT,
    ajan_sonucu TEXT, kanit_durumu TEXT, sonuc TEXT, gerekce TEXT,
    dogrulama TEXT DEFAULT 'bekliyor', onaylayan TEXT, dogrulama_ts TEXT)"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(x):
    return datetime.fromisoformat(str(x).strip().replace("T", " ")).strftime("%Y-%m-%d %H:%M")


def _conn():
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    c.execute(SQL)
    return c


def _row(r):
    d = dict(r)
    d["ajan_sonucu"] = json.loads(d["ajan_sonucu"])
    d["gerekce"] = json.loads(d["gerekce"])
    d["pencere"] = d.pop("bas") + " - " + d.pop("bit")
    return d


def _no_dev(what, ratio, lo, hi):
    g = [what,
         f"ancak pencere medyan oranı {ratio} (sapma eşiği: <{evidence.LOW} veya >{evidence.HIGH}); belirgin sapma yok",
         f"saat bazında {lo} saat 0.7 altında, {hi} saat 1.3 üstünde"]
    return ("kismi" if lo + hi > 0 else "kanit_yok"), g


def _baseline_holidays(cmp_):
    out = []
    for d in cmp_.get("baseline_days_of_first_hour") or []:
        try:
            cal = evidence.tools.get_calendar(f"{d} 00:00", f"{d} 23:00")
            out += [f"{x['date']}: {x['holiday']}" for x in cal.get("days", []) if x.get("holiday")]
        except Exception:
            pass
    return out


def _check(iddia, j, cmp_, wx, cal, eq):
    """(kanit_durumu, gerekce). kanit_durumu: sonuc_ayni | kismi | kanit_yok | dogrulanamadi"""
    hyp, dev, ratio = j["hipotezler"], j["sapma_var"], j.get("medyan_oran")
    lo = cmp_.get("n_clean_below_0.7") or 0
    hi = cmp_.get("n_clean_above_1.3") or 0
    if iddia == "diger":
        return "dogrulanamadi", ["serbest metin iddia araçlarla sınanamaz"]
    if j.get("degerlendirilemedi"):
        return "dogrulanamadi", ["baseline hesaplanamadı (en az 3 geçerli hafta yok); bu pencerede hiçbir iddia sınanamaz"]
    if j.get("veri_yok") and iddia != "veri_hatasi":
        return "dogrulanamadi", ["pencerenin tüm saatleri kaynak dosyada yok; trafik davranışı ölçülemedi"]

    if iddia == "veri_hatasi":
        u = j.get("veri_kalitesi_uyarisi") or {}
        if hyp["veri_hatasi"] == "destekliyor":
            return "sonuc_ayni", ["ajan da veri hatasını destekliyor: " + "; ".join(j["notlar"])]
        if u:
            g = [f"eksik saat {u.get('eksik_saat')}/{u.get('toplam_saat')}, ETL isaretli saat {u.get('isaretli_saat')}",
                 f"eksik oran {u.get('eksik_oran')}, veri hatası eşiği {evidence.GAP_SHARE}"]
            if u.get("etl_log_yok"):
                g.append("ETL logu bu dönem için yok: veri kalitesi doğrulanamadı")
            return "kismi", g
        return "kanit_yok", ["pencerede eksik saat yok, ETL isaretli saat yok, ETL logu mevcut"]

    if iddia == "tatil":
        days = cal.get("days", [])
        hol = sorted({d["holiday"] for d in days if d.get("holiday")})
        if hyp["tatil"] == "destekliyor":
            return "sonuc_ayni", ["ajan da tatili destekliyor: " + ", ".join(hol)]
        if hol and not dev:
            return _no_dev("takvimde tatil var: " + ", ".join(hol), ratio, lo, hi)
        if any(d.get("day_before_holiday") for d in days):
            return "kismi", ["pencere bir resmî tatilin arifesinde", "sınır: takvim aracı arife yarım gününü tatil saymaz"]
        bh = _baseline_holidays(cmp_)
        if bh:
            return "kismi", ["pencere tatil değil, ama karşılaştırma haftalarında tatil var: " + "; ".join(bh),
                             "baseline bu yüzden düşük, oran olduğundan yüksek görünebilir"]
        return "kanit_yok", ["takvimde bu pencere için resmî tatil veya bayram yok",
                             "sınır: okul tatili, idari izin ve etkinlikler takvimde yok"]

    if iddia == "hava":
        if "error" in wx:
            return "dogrulanamadi", ["hava verisi bu dönem için yok"]
        if hyp["hava"] == "destekliyor":
            return "sonuc_ayni", ["ajan da havayı destekliyor"]
        precip, p90, wind = wx.get("precip_total_mm", 0), wx.get("period_daily_precip_p90_mm"), wx.get("wind_max_kmh", 0)
        precip_day = wx.get("precip_max_day_mm", precip)
        yagis_txt = f"yağış {precip} mm" + (f" (en yağışlı gün {precip_day} mm)" if precip_day != precip else "")
        olcum = f"{yagis_txt} (eşik: dönem günlük p90 {p90} mm), rüzgâr {wind} km/sa (eşik 40)"
        if (p90 is not None and precip_day > p90) or wind > 40:
            return _no_dev("aşırı hava var: " + olcum, ratio, lo, hi)
        return "kanit_yok", [olcum + ": aşırı hava eşiği aşılmadı",
                             "sınır: tek nokta reanalysis; kar, buzlanma ve sis ölçülmez, tüm İstanbul'u temsil etmez"]

    if iddia == "deprem":
        if "error" in eq:
            return "dogrulanamadi", ["deprem kataloğu bu dönemi kapsamıyor"]
        n = eq.get("n_relevant", 0)
        if n > 0:
            top = (eq.get("top_events") or [{}])[0]
            what = f"ilgili deprem kaydı {n} adet" + (f" (en büyük: M{top.get('mag')} {top.get('place')}, {top.get('time_local')})" if top else "")
            if not dev:
                return _no_dev(what, ratio, lo, hi)
            return "kismi", [what, "büyüklük ve mesafe tek başına nedensellik göstermez; ajan da depremi 'belirsiz' bıraktı"]
        return "kanit_yok", ["katalogda pencere ve önceki 12 saat için ilgili deprem yok (M>=4.5 ve <=500 km, veya M>=6.5)",
                             "sınır: günler sonra gelen kurumsal etkiler (okul tatili gibi) bu araçla görülemez"]

    # sapma_yok
    if not dev:
        return "sonuc_ayni", ["ajan da belirgin sapma bulmadı (medyan oran %s)" % ratio]
    g = [f"pencere medyan oranı {ratio} (sapma eşiği: <{evidence.LOW} veya >{evidence.HIGH})",
         f"saat bazında {lo} saat 0.7 altında, {hi} saat 1.3 üstünde, temiz saat {cmp_.get('n_clean_hours')}"]
    if ratio is not None and (evidence.LOW - NEAR <= ratio < evidence.LOW or evidence.HIGH < ratio <= evidence.HIGH + NEAR):
        return "kismi", g + [f"oran eşiğe {NEAR} kadar yakın; sapma zayıf"]
    return "kanit_yok", g


def review(start, end, iddia, aciklama="", kaynak=""):
    """Ret nedenini kanitla sinar ve kaydeder. Hipotez durumlarini degistirmez."""
    iddia = str(iddia).strip().lower()
    if iddia not in CLAIMS:
        raise ValueError("iddia su degerlerden biri olmali: " + ", ".join(CLAIMS))
    s, e = _norm(start), _norm(end)
    if e < s:
        raise ValueError("end, start'tan once olamaz")
    T = evidence.tools
    j = evidence.judge(s, e)
    durum, gerekce = _check(iddia, j, T.compare_same_weekday_history(s, e), T.get_weather(s, e),
                            T.get_calendar(s, e), T.get_earthquakes(s, e))
    ajan = {"destekleyen": sorted(k for k, v in j["hipotezler"].items() if v == "destekliyor"),
            "belirsiz": sorted(k for k, v in j["hipotezler"].items() if v == "belirsiz"),
            "sapma_var": j["sapma_var"], "medyan_oran": j.get("medyan_oran"), "guven": j["guven"]}
    aciklama, kaynak = str(aciklama or "").strip()[:500], str(kaynak or "").strip()[:300]
    c = _conn()
    try:
        with c:
            cur = c.execute("INSERT INTO feedback (ts, bas, bit, iddia, aciklama, kaynak, ajan_sonucu, kanit_durumu, sonuc, gerekce) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (_now(), s, e, iddia, aciklama, kaynak, json.dumps(ajan, ensure_ascii=False), durum,
                             OUTCOME[durum], json.dumps(gerekce, ensure_ascii=False)))
            fid = cur.lastrowid
    finally:
        c.close()
    return {"id": fid, "pencere": f"{s} - {e}", "iddia": iddia, "aciklama": aciklama, "kaynak": kaynak,
            "ajan_sonucu": ajan, "kanit_durumu": durum, "sonuc": OUTCOME[durum], "mesaj": MESAJ[durum],
            "gerekce": gerekce}


def stats():
    c = _conn()
    try:
        g = lambda col: {r[0]: r[1] for r in c.execute(f"SELECT {col}, COUNT(*) FROM feedback GROUP BY {col}")}
        return {"toplam": c.execute("SELECT COUNT(*) FROM feedback").fetchone()[0],
                "sonuc": g("sonuc"), "kanit_durumu": g("kanit_durumu")}
    finally:
        c.close()


def listele(n=20):
    c = _conn()
    try:
        return [_row(r) for r in c.execute("SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (int(n),))]
    finally:
        c.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("review")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--iddia", required=True, choices=CLAIMS)
    p.add_argument("--aciklama", default="")
    p.add_argument("--kaynak", default="")
    sub.add_parser("stats")
    sub.add_parser("list")
    a = ap.parse_args()
    try:
        if a.cmd == "review":
            out = review(a.start, a.end, a.iddia, a.aciklama, a.kaynak)
        elif a.cmd == "stats":
            out = stats()
        else:
            out = listele()
    except ValueError as ex:
        print("HATA:", ex)
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False, indent=2))
