"""Soru kapsam kontrolu: kural tabanli, LLM ve embedding kullanmaz.

check_scope(soru) -> {"status": "in" | "out", "reasons": [...], "notes": [...]}
Yalnizca veri kapsamini (tarih, sehir, olay turu) denetler. Konu disi sorulari (Bitcoin gibi) elemez.
"""
import re
from datetime import date

import holidays

MONTHS = {"ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
          "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12}

# Yuklu veri kapsami (gun dahil): parquet, ETL logu ve tools.QUAKE_COVER'dan turetilir, elle yazilmaz.
import json
import sys
from pathlib import Path

import pandas as pd

_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
import tools


def _ranges(periods):
    out = []
    for p in sorted(set(periods)):
        if out and p == out[-1][1] + 1:
            out[-1][1] = p
        else:
            out.append([p, p])
    return [(x.start_time.date(), y.end_time.date()) for x, y in out]


def _derive_cover():
    proc = _ROOT / "data" / "processed"
    traffic = {pd.Period(p.stem.replace("hourly_", "")) for p in proc.glob("hourly_*.parquet")}
    weather = set()
    for f in proc.glob("weather_*.parquet"):
        weather |= set(pd.to_datetime(pd.read_parquet(f).index).to_period("M"))
    etl = set()
    for line in (_ROOT / "logs" / "etl_log.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["stage"] == "run_started":
            etl.add(pd.Period(r["details"]["month"]))
    quake = [(date.fromisoformat(x), date.fromordinal(date.fromisoformat(y).toordinal() - 1))
             for x, y in tools.QUAKE_COVER]
    cover = {"traffic": _ranges(traffic), "weather": _ranges(weather),
             "quake": quake, "etl": _ranges(etl)}
    return cover, traffic


COVER, _TRAFFIC_MONTHS = _derive_cover()
ASSUMED_YEARS = tuple(sorted({p.year for p in _TRAFFIC_MONTHS}))  # yil yazilmamissa degerlendirilen yillar

SOURCE_WORDS = {
    "weather": ("hava", "yağış", "yağmur", "rüzgâr", "rüzgar", "sıcaklık"),
    "quake": ("deprem",),
    "etl": ("eksik", "etl", "log", "boşluk", "veri hatası"),
    "traffic": ("trafik", "hacim", "yoğunluk", "araç", "sapma", "anomali", "düş", "art", "azal"),
}
HOLIDAY_KEYS = ("kurban bayramı", "ramazan bayramı")

PROVINCES = """adana adıyaman afyonkarahisar ağrı aksaray amasya ankara antalya ardahan artvin aydın balıkesir
bartın batman bayburt bilecik bingöl bitlis bolu burdur bursa çanakkale çankırı çorum denizli diyarbakır düzce
edirne elazığ erzincan erzurum eskişehir gaziantep giresun gümüşhane hakkari hatay iğdır isparta kahramanmaraş
karabük karaman kars kastamonu kayseri kırıkkale kırklareli kırşehir kilis kocaeli konya kütahya malatya manisa
mardin mersin muğla muş nevşehir niğde osmaniye rize sakarya samsun siirt sinop sivas şanlıurfa şırnak tekirdağ
tokat trabzon tunceli uşak yalova yozgat zonguldak izmir""".split()
# "van" ve "ordu" gunluk dilde de gectigi icin listede yok: bu bilinen bir bosluktur.

EVENT_RE = re.compile(r"\b(grev|yangın|maç|konser|miting|protesto)\w*|\bsel(?:i|in|de|den|ler|lere)?\b|\bseçim\s+gün\w*|\b(?:genel|yerel|cumhurbaşkanlığı|milletvekili)\s+seçim\w*")


def tr_lower(s):
    return s.replace("İ", "i").replace("I", "ı").lower()


def _overlap(rng, a, b):
    return any(a <= e and b >= s for s, e in rng)


def _periods(text):
    """Metindeki acik tarih donemleri: [(baslangic, bitis, etiket, yil_yazili_mi, span)]"""
    out = []
    mon = "|".join(MONTHS)
    pat = re.compile(rf"(?:(\d{{1,2}})\s+)?\b({mon})\b(?:['’]\w+)?(?:\s+(\d{{4}}))?")
    spans = []
    for m in pat.finditer(text):
        d, mo, y = m.group(1), MONTHS[m.group(2)], m.group(3)
        years = [int(y)] if y else list(ASSUMED_YEARS)
        for yr in years:
            try:
                if d:
                    a = b = date(yr, mo, int(d))
                else:
                    a = date(yr, mo, 1)
                    b = date(yr + (mo == 12), (mo % 12) + 1, 1)
                    b = date.fromordinal(b.toordinal() - 1)
            except ValueError:
                continue
            out.append((a, b, m.group(0).strip(), bool(y), m.span()))
        spans.append(m.span())
    for m in re.finditer(r"(\d{4})-(\d{2})(?:-(\d{2}))?", text):
        yr, mo = int(m.group(1)), int(m.group(2))
        if not 1 <= mo <= 12:
            continue
        if m.group(3):
            a = b = date(yr, mo, int(m.group(3)))
        else:
            a = date(yr, mo, 1)
            b = date.fromordinal(date(yr + (mo == 12), (mo % 12) + 1, 1).toordinal() - 1)
        out.append((a, b, m.group(0), True, m.span()))
        spans.append(m.span())
    for m in re.finditer(r"\b(20\d{2})\b", text):
        if any(s <= m.start() < e for s, e in spans):
            continue
        yr = int(m.group(1))
        out.append((date(yr, 1, 1), date(yr, 12, 31), m.group(0), True, m.span()))
    return out


def _holiday_instances(text):
    tr = holidays.Turkey(years=list(ASSUMED_YEARS))
    years_in_text = {int(y) for y in re.findall(r"\b(20\d{2})\b", text)}
    res = []
    for key in HOLIDAY_KEYS:
        if key not in text:
            continue
        ds = sorted(d for d, n in tr.items() if tr_lower(key) in tr_lower(n))
        if years_in_text:
            ds = [d for d in ds if d.year in years_in_text] or ds
        res.append((key, ds))
    return res


def _sources(text, has_holiday):
    found = [s for s, ws in SOURCE_WORDS.items() if any(re.search(r"\b" + re.escape(w), text) for w in ws)]
    if found:
        return found, False
    if has_holiday:
        return [], True  # yalnizca takvim sorusu
    return list(COVER), False


def check_scope(question):
    text = tr_lower(question.replace("’", "'"))
    reasons, notes = [], []
    hols = _holiday_instances(text)
    sources, calendar_only = _sources(text, bool(hols))

    if not calendar_only:
        grouped = {}
        for a, b, label, explicit, span in _periods(text):
            grouped.setdefault((label, span), []).append((a, b, explicit))
        for (label, _), insts in grouped.items():
            ok = [i for i in insts if any(_overlap(COVER[s], i[0], i[1]) for s in sources)]
            if not ok:
                reasons.append(f"tarih kapsam dışı: '{label}' ({', '.join(sources)} verisi yok)")
                continue
            if not insts[0][2]:
                notes.append(f"yıl yazılmamış: '{label}' için {ASSUMED_YEARS} değerlendirildi")
            miss = [s for s in sources if not any(_overlap(COVER[s], i[0], i[1]) for i in ok)]
            if miss:
                notes.append(f"'{label}' için eksik kaynaklar: {', '.join(miss)}")
        for key, ds in hols:
            ok = [d for d in ds if any(_overlap(COVER[s], d, d) for s in sources)]
            if not ok:
                span = f"{ds[0]} - {ds[-1]}" if ds else "tarih bulunamadı"
                reasons.append(f"bayram kapsam dışı: '{key}' ({span}), {', '.join(sources)} verisi yok")

    tokens = set(re.findall(r"[a-zçğıöşü]+", text))
    others = sorted(p for p in PROVINCES if p in tokens)
    if others:
        if "istanbul" in tokens or "deprem" in tokens:
            notes.append(f"başka il geçiyor ({', '.join(others)}), İstanbul veya deprem bağlamında olduğu için engellenmedi")
        else:
            reasons.append(f"İstanbul dışı il: {', '.join(others)}")
    ev = EVENT_RE.search(text)
    if ev:
        reasons.append(f"olay türü için veri kaynağı yok: '{ev.group(0)}'")

    return {"status": "out" if reasons else "in", "reasons": reasons, "notes": notes}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = " ".join(sys.argv[1:]) or "Kurban Bayramı'nda trafik nasıl değişti?"
    print(check_scope(q))
