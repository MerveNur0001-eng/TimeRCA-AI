"""Yönlendirme: sorunun metnine göre bilgi (RAG) veya pencere analizi (rapor).
Karar kuraldadır. LLM yalnız kural tarihi bulamayınca soruyu anlamak için denenir (soru_llm.py):
çıktı sorunun kendi metnine bağlanarak doğrulanır, geçmezse ya da Ollama yoksa kural cevabı kullanılır.
Kapatmak için: ortam değişkeni TIMERCA_SORU_LLM=0.
"Nisan 2024'te bir gün seç, trafik neden düştü" gibi sorularda gün kural ile seçilir (ay taranır, oranı 1'den en çok
sapan gün), LLM seçmez; seçilen gün normal ajan yoluyla incelenir. "Nisan 2024'te anomali var mıydı" ay boyunca taranır.
Ortam: TIMERCA_ACIKLAMA_LLM=1 ise tek gün analizine LLM açıklaması eklenir (sayı/tarih/hipotez doğrulamalı, olmazsa kural metni)."""
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rag
import report
from scope import tr_lower, MONTHS, COVER, _overlap

def fold(s):
    return tr_lower(s.replace("’", "'")).translate(str.maketrans("ığüşöç", "igusoc"))


ANALIZ_KEYS = ("analiz", "neden dus", "neden art", "neden azal", "neden yuksel",
               "nicin dus", "nicin art", "nicin azal", "nicin yuksel", "anomali",
               "sapma", "incele", "kok neden", "ne oldu", "niye")
_MONTHS_F = {fold(k): v for k, v in MONTHS.items()}
_NEDEN_RE = re.compile(r"\b(?:neden|nicin|niye)\s+(?:\w+\s+){0,2}(?:dus|art|azal|yuksel)\w*")
MAX_GUN = 7
_AYLAR = "|".join(_MONTHS_F)
DATE_RES = [
    (re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b"), lambda m: (m[1], m[2], m[3])),
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b"), lambda m: (m[3], m[2], m[1])),
    (re.compile(r"\b(\d{1,2})\s+(" + _AYLAR + r")\w*\s+(20\d{2})\b"), lambda m: (m[3], _MONTHS_F[m[2]], m[1])),
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b"), lambda m: (m[3], m[2], m[1])),
    (re.compile(r"\b(20\d{2})\s*(?:yili\w*\s*)?(" + _AYLAR + r")\w*\s+(\d{1,2})\b"), lambda m: (m[1], _MONTHS_F[m[2]], m[3])),
    (re.compile(r"\b(\d{1,2})\s*\.?\s*(?:inci|nci|uncu|ncu)?\s*ay\w*\s*(\d{1,2})\s*['\u2019\u2018`\u00b4]?\s*(?:inci|nci|uncu|ncu|si|su|i|u)?[\s,]+(?:yili\s+)?(20\d{2})\b"), lambda m: (m[3], m[1], m[2])),
    (re.compile(r"\b(20\d{2})\s*(?:yili\w*\s*)?(\d{1,2})\s*\.?\s*(?:inci|nci|uncu|ncu)?\s*ay\w*\s*(\d{1,2})\b"), lambda m: (m[1], m[2], m[3])),
]


class State(TypedDict):
    soru: str
    istek_tipi: str
    start: Optional[str]
    end: Optional[str]
    plan: list[str]
    sonuc: dict
    kararlar: list[str]
    mesaj: Optional[str]


def tarihleri_bul(metin):
    bulunan = []
    for rx, conv in DATE_RES:
        for m in rx.finditer(metin):
            y, mo, d = conv(m)
            try:
                bulunan.append((m.start(), date(int(y), int(mo), int(d))))
            except ValueError:
                pass
    return sorted({d for _, d in sorted(bulunan)})


_SIRA = {"birinci": 1, "ikinci": 2, "ucuncu": 3, "dorduncu": 4, "besinci": 5}
_ORD = r"(?:inci|nci|uncu|ncu)?"
_WEEK_RE = re.compile(r"(?<!\d)([1-5])\s*\.?\s*" + _ORD + r"\s*hafta|\b(birinci|ikinci|ucuncu|dorduncu|besinci)\s+hafta")
_AY_ADI_RE = re.compile(r"\b(" + _AYLAR + r")\w*")
_AY_NO_RE = re.compile(r"(?<!\d)(\d{1,2})\s*\.?\s*" + _ORD + r"\s*ay(?:in|inin|i)?\b")
_YIL_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_SEP = r"(?:-|\u2013|\u2014|ile|ila)"
RANGE_RES = [
    (re.compile(r"(?<!\d)(\d{1,2})\s*" + _SEP + r"\s*(\d{1,2})\s+(" + _AYLAR + r")\w*\s+(20\d{2})\b"), lambda m: (m[4], m[3], m[1], m[2])),
    (re.compile(r"\b(20\d{2})\s*(?:yili\w*\s*)?(" + _AYLAR + r")\w*\s+(\d{1,2})\s*" + _SEP + r"\s*(\d{1,2})(?!\d)"), lambda m: (m[1], m[2], m[3], m[4])),
]


def hafta_penceresi(metin):
    """'2024 yilinin 1. ayinin 2. haftasi' gibi ifadeler. Sozlesme: ayin N. haftasi = gun (N-1)*7+1 .. N*7
    (ay sonuna kirpilir). None: hafta ifadesi yok. ("hata", mesaj): ifade var ama anlasilamadi."""
    if "hafta" not in metin:
        return None
    w = _WEEK_RE.search(metin)
    y = _YIL_RE.search(metin)
    ma = _AY_ADI_RE.search(metin)
    if ma:
        ay = int(_MONTHS_F[ma.group(1)])
    else:
        mn = _AY_NO_RE.search(metin)
        ay = int(mn.group(1)) if mn else None
    if not (w and y and ay and 1 <= ay <= 12):
        return ("hata", "Hafta ifadesi için yıl, ay ve hafta numarası gerekli. Örnek: '2024 Ocak 2. hafta' (ayın 8-14. günleri). Ya da gün yaz: '8 Ocak 2024'.")
    n = int(w.group(1)) if w.group(1) else _SIRA[w.group(2)]
    yil = int(y.group(1))
    ay_son = (date(yil + (ay == 12), ay % 12 + 1, 1) - timedelta(days=1)).day
    bas, bit = (n - 1) * 7 + 1, min(n * 7, ay_son)
    if bas > ay_son:
        return ("hata", f"{yil}-{ay:02d} ayında {n}. hafta yok (ay {ay_son} gün). Hafta = ayın {7 * (n - 1) + 1}. gününden başlayan 7 gün.")
    return ("ok", date(yil, ay, bas), date(yil, ay, bit), n)


def aralik_bul(metin):
    for rx, conv in RANGE_RES:
        m = rx.search(metin)
        if not m:
            continue
        y, mo, d1, d2 = conv(m)
        try:
            a, b = date(int(y), int(_MONTHS_F[mo]) if not str(mo).isdigit() else int(mo), int(d1)), date(int(y), int(_MONTHS_F[mo]) if not str(mo).isdigit() else int(mo), int(d2))
        except (ValueError, KeyError):
            continue
        if b >= a:
            return a, b
    return None


_VAR_RE = re.compile(r"\bvar\s*mi(?:ydi)?\b|\boldu\s*mu\b|\bvar\s*midir\b")
_DURUM_TR = {"dusus": "düşüş", "artis": "artış", "eksik_veri": "eksik veri", "eksik_veri_ve_sapma": "eksik veri ve sapma",
             "veri_yok": "veri yok", "degerlendirilemedi": "değerlendirilemedi"}


def varlik_sorusu_mu(soru):
    """'anomali var miydi?' gibi: neden degil, var mi sorusu. Cok gunluk pencerede gun gun tarama ile cevaplanir."""
    return bool(_VAR_RE.search(fold(soru)))


def _gun(d):
    return f"{d[8:10]}.{d[5:7]}.{d[0:4]}"


def tarama_ozeti(r):
    n, k = r["taranan"], len(r["adaylar"])
    a, b = _gun(r["aralik"][0]), _gun(r["aralik"][1])
    if k == 0:
        m = (f"{a} - {b}: {n} gün tarandı, hiçbirinde sapma eşiği aşılmadı. "
             "Bu 'sorunsuz' demek değil, 'eşiği aşmadı' demektir (gün genelinde bakıldığı için kısa süreli sorunlar görünmeyebilir).")
    else:
        liste = "; ".join(f"{_gun(x['gun'])} {_DURUM_TR.get(x['durum'], x['durum'])}"
                          + (f" (oran {x['medyan_oran']:.2f})" if x.get("medyan_oran") is not None else "") for x in r["adaylar"])
        m = (f"{a} - {b}: {n} gün tarandı, {k} gün olağandışı: {liste}. "
             "Nedenini görmek için o günü tek gün olarak sor (örn. '22.04.2023 neden düştü').")
    if r.get("taranamayan"):
        m += f" {len(r['taranamayan'])} gün taranamadı."
    return m


_SEC_RE = re.compile(r"\b(?:sen|kendin)\s+(?:sec|bul|belirle)\w*|\b(?:gun|tarih)\w*\s+(?:sec|bul|belirle)\w*"
                     r"|\ben\s+(?:belirgin|buyuk|sapmali)\s+gun\b")
_NEDEN_YON_RE = re.compile(r"\b(?:neden|nicin|niye)\s+(?:\w+\s+){0,2}(dus|azal|art|yuksel)\w*")
_AY_TR = {v: k.capitalize() for k, v in MONTHS.items()}


_VERI_HATASIZ_RE = re.compile(r"veri\s+hata\w*\s+(?:olmayan|haric|disinda)|eksik\s+veri\s+(?:olmayan|haric)"
                              r"|gercek\s+(?:bir\s+)?(?:trafik\s+)?sapma")
_ILK_N_RE = re.compile(r"\b(?:ilk|en\s+(?:cok\s+(?:sapan|artan|azalan|dusen)|sapmali|belirgin))\s+(\d|iki|uc|dort|bes)\s+gun\w*")
_SAYI = {"iki": 2, "uc": 3, "dort": 4, "bes": 5}
MAX_SEC_GUN = 5   # 'ilk N gun' en cok bu kadar gun inceler
MAX_ELEME = 5     # 'veri hatasi olmayan' secimde en cok bu kadar aday ajanla denenir
_HIP_TR = {"veri_hatasi": "veri hatası", "hava": "hava", "tatil": "tatil/bayram", "deprem": "deprem",
           "aciklanamayan": "açıklanamayan"}


def secim_sorusu_mu(metin):
    """'tarihi sen sec' / 'ilk 3 gun' gibi: gunu kullanici vermiyor, ajan ayi tarayip secer. Metin fold edilmis olmali."""
    return bool(_SEC_RE.search(metin) or _ILK_N_RE.search(metin))


def secim_sayisi(metin):
    """'en cok sapan 3 gun' -> 3 (en az 1, en cok MAX_SEC_GUN); sayi yoksa 1."""
    m = _ILK_N_RE.search(metin)
    if not m:
        return 1
    g = m.group(1)
    return max(1, min(int(g) if g.isdigit() else _SAYI[g], MAX_SEC_GUN))


def secim_yonu(metin):
    """'neden dustu' -> 'dusus', 'neden artti' -> 'artis', yon yoksa None (en cok sapan gun)."""
    m = _NEDEN_YON_RE.search(metin)
    if not m:
        return None
    return "dusus" if m.group(1) in ("dus", "azal") else "artis"


def yuklu_yillar(ay):
    """Verilen ay icin trafik verisi yuklu yillar (veri kapsamindan turetilir, elle yazilmaz)."""
    out = []
    for y in range(2019, 2027):
        son = date(y + (ay == 12), ay % 12 + 1, 1) - timedelta(days=1)
        if _overlap(COVER["traffic"], date(y, ay, 1), son):
            out.append(y)
    return out


_ORNEK = {"sec": "Nisan 2024'te bir gün seç, trafik neden düştü", "tara": "Nisan 2024'te anomali var mıydı",
          "hafta": "Nisan 2024 haftalık özet", "hafta_tatil": "Nisan 2024'te hangi haftalar tatilden etkilendi",
          "siralama": "Nisan 2024'te hangi gün en çok düştü", "eksik": "Nisan 2024'te kaç gün eksik veri vardı",
          "hafta_ici": "Nisan 2024'te hafta içi ile hafta sonu karşılaştır"}


def ay_penceresi(metin, mod="sec"):
    """Yil + ay (ad ya da '4. ay') -> ('ok', ay_basi, ay_sonu) ; eksikse ('hata', mesaj). Yil yoksa yuklu yillari sayar, tahmin etmez."""
    y = _YIL_RE.search(metin)
    ma = _AY_ADI_RE.search(metin)
    if ma:
        ay = int(_MONTHS_F[ma.group(1)])
    else:
        mn = _AY_NO_RE.search(metin)
        ay = int(mn.group(1)) if mn else None
    ornek = _ORNEK[mod]
    if ay and 1 <= ay <= 12 and not y:
        ad, yl = _AY_TR[ay], yuklu_yillar(ay)
        if not yl:
            return ("hata", f"Yıl yazmadın ve {ad} ayı için yüklü trafik verisi yok.")
        return ("hata", f"Yıl yazmadın. {ad} için yüklü yıllar: {', '.join(map(str, yl))}. "
                        f"Yılı yazarak sor, örnek: '{ornek.replace('Nisan 2024', ad + ' ' + str(yl[-1]))}'. Yılı ben tahmin etmem.")
    if not (y and ay and 1 <= ay <= 12):
        on = "Günü ben seçeceksem yıl ve ay gerekli." if mod == "sec" else "Ay boyunca tarama için yıl ve ay gerekli."
        return ("hata", f"{on} Örnek: '{ornek}'. Yılı söylemezsen tahmin etmem.")
    yil = int(y.group(1))
    son = date(yil + (ay == 12), ay % 12 + 1, 1) - timedelta(days=1)
    return ("ok", date(yil, ay, 1), son)


def sirala_gunler(adaylar, yon):
    """Sabit kural: yone uyan adaylar, medyan oranin 1'den mutlak sapmasina gore buyukten kucuge (esitlikte erken tarih).
    Yalniz saatlik veri sapmasi olan gunler aday olur (salt eksik veri, veri yok, degerlendirilemedi degil)."""
    uygun = [x for x in adaylar
             if x["durum"] in ("dusus", "artis", "eksik_veri_ve_sapma") and x.get("medyan_oran") is not None]
    if yon == "dusus":
        uygun = [x for x in uygun if x["medyan_oran"] < 1]
    elif yon == "artis":
        uygun = [x for x in uygun if x["medyan_oran"] > 1]
    return sorted(uygun, key=lambda x: (-abs(1 - x["medyan_oran"]), x["gun"]))


def sec_gun(adaylar, yon):
    s = sirala_gunler(adaylar, yon)
    return s[0] if s else None


_GORELI_KESIN = re.compile(r"\b(?:dun|dunku|bugun|bugunku|yarin|yarinki|evvelki\s+gun|onceki\s+gun|haftaya|gecen\s+(?:hafta|ay|yil))\b")
_GORELI_BELIRSIZ = re.compile(r"\b(?:bu\s+(?:hafta|ay|yil)|gelecek\s+(?:hafta|ay|yil)|son\s+(?:\d+\s+)?(?:gun|hafta|ay))\b")


def yuklu_donemler():
    """Yuklu trafik donemleri (veri kapsamindan turetilir): '01.12.2021 - 31.01.2022; ...'."""
    return "; ".join(f"{s:%d.%m.%Y} - {e:%d.%m.%Y}" for s, e in COVER["traffic"])


def ornek_tarih():
    """Yuklu son donemin icinden gercek bir ornek gun ('10 Nisan 2024')."""
    s, e = COVER["traffic"][-1]
    d = min(e, s + timedelta(days=9))
    return f"{d.day} {_AY_TR[d.month]} {d.year}"


_EK = {3: "te", 4: "te", 5: "te", 6: "da", 9: "da"}


def ornek_sorular():
    """Yuklu verinin son doneminden uretilen ornek sorular (arayuz hizli ornek dugmeleri). Veri degisirse kendiliginden guncellenir."""
    s, e = COVER["traffic"][-1]
    ay = f"{_AY_TR[e.month]} {e.year}"
    d1 = max(s, min(s + timedelta(days=9), e - timedelta(days=7)))
    d2 = d1 + timedelta(days=7)
    out = [f"{d1.day} {_AY_TR[d1.month]} {d1.year} trafik neden düştü",
           f"{ay}'{_EK.get(e.year % 10, 'de')} anomali var mıydı",
           f"{ay}'{_EK.get(e.year % 10, 'de')} en çok sapan 3 günü bul, trafik neden düştü",
           f"{ay} haftalık özet"]
    if (s.year, s.month) != (e.year, e.month):
        out.append(f"{_AY_TR[s.month]} {s.year} ile {_AY_TR[e.month]} {e.year} karşılaştır")
    if d2 <= e:
        out.append(f"{d1.day} {_AY_TR[d1.month]} ile {d2.day} {_AY_TR[d2.month]} {d2.year} karşılaştır")
    return out


def goreli_mesaji(kelime):
    return (f"Göreli tarih ('{kelime}') anlaşılamaz: veri güncel değil, yalnız belirli dönemleri kapsar. "
            f"Yüklü trafik dönemleri: {yuklu_donemler()}. Bu aralıklardan bir tarih yaz, örnek: '{ornek_tarih()} trafik neden düştü' "
            f"ya da '{ornek_tarih().split()[1]} {ornek_tarih().split()[2]}'te anomali var mıydı'.")


def _trafik_orani(a, b):
    import scan
    return scan.classify(scan._compare(f"{a} 00:00", f"{b} 23:00"))[1]


def ek_sinyal(a, b):
    """Hava kalitesi (IBB saatlik NO2/PM10) ile trafik capraz kontrolu. KANIT, karar kurali degil. Veri yoksa ya da hata olursa None."""
    try:
        import air_quality
        if not air_quality.available():
            return None
        tr = _trafik_orani(a, b)
        c = air_quality.compare(f"{a} 00:00", f"{b} 23:00")
        if "error" in c:
            return None
        sig = air_quality.signal(tr, c.get("ratio_no2"), c.get("ratio_pm10"))
        if not sig:
            return None
        return {"kaynak": "İBB hava kalitesi (saatlik, istasyonların tipik değeri)", "trafik_orani": tr, "no2_orani": c.get("ratio_no2"),
                "pm10_orani": c.get("ratio_pm10"), "aralik": [str(a), str(b)], "kod": sig["kod"], "metin": sig["metin"]}
    except Exception:
        return None


def takvim_notu(a, b):
    """a..b (date) icin takvim bilgisi: resmi tatil, arife/yarim gun, idari izin, okul tatili. KANIT, karar kurali degil.
    Takvim araci hata verirse bos doner (analiz bozulmaz)."""
    try:
        import tools
        cal = tools.get_calendar(f"{a} 00:00", f"{b} 00:00")
    except Exception:
        return []
    out = []
    for d in cal.get("days", []):
        p = []
        if d.get("holiday"):
            p.append(f"resmî tatil ({d['holiday']})")
        if d.get("half_day"):
            p.append(f"{d['half_day']} (yarım gün)")
        elif d.get("day_before_holiday"):
            p.append("resmî tatil arifesi")
        if d.get("admin_leave") and d.get("admin_leave_note"):
            p.append(str(d["admin_leave_note"]).split(" | ")[0])
        if d.get("school") == "tatil" and d.get("school_note"):
            p.append("okul tatili: " + str(d["school_note"]).split(" | ")[0])
        if p:
            out.append({"gun": d["date"], "notlar": p})
    return out


_AY_YIL_RE = re.compile(r"\b(" + _AYLAR + r")\w*\s+(20\d{2})")
_AY_AY_YIL_RE = re.compile(r"\b(" + _AYLAR + r")\w*\s*(?:ile|ve|ila)\s*(" + _AYLAR + r")\w*\s+(20\d{2})")
_AYKARS_MSG = ("Ay karşılaştırması için iki ayın yılı da gerekli (en fazla üç ay karşılaştırılır). "
               "Örnek: 'Mart 2024 ile Nisan 2024 karşılaştır' ya da 'Şubat Mart Nisan 2024 karşılaştır'. Yılı tahmin etmem.")


def ay_karsilastirma(metin):
    """'Nisan 2023 ile Nisan 2024 karsilastir': None | ('ok', (y1,m1), (y2,m2)) | ('hata', mesaj). Gun tarihi varsa gun karsilastirmasi."""
    if not _KARS_RE.search(metin):
        return None
    if re.search(r"\d{1,2}\s+(?:" + _AYLAR + r")", metin) or tarihleri_bul(metin):
        return None
    m = _AY_AY_YIL_RE.search(metin)
    yillar = {int(y) for y in _YIL_RE.findall(metin)}
    adlar = []
    for x in _AY_ADI_RE.findall(metin):
        if x not in adlar:
            adlar.append(x)
    if m:
        cift = sorted({(int(m.group(3)), int(_MONTHS_F[m.group(1)])), (int(m.group(3)), int(_MONTHS_F[m.group(2)]))})
    elif len(yillar) == 1 and len(adlar) >= 2:  # 'Subat Mart Nisan 2024': tek yil, birden cok ay
        cift = sorted({(next(iter(yillar)), int(_MONTHS_F[a])) for a in adlar})
    else:
        cift = sorted({(int(y), int(_MONTHS_F[a])) for a, y in _AY_YIL_RE.findall(metin)})
    if len(cift) in (2, 3):
        return ("ok", *cift)
    if len(adlar) >= 2 or len(cift) > 3:
        return ("hata", _AYKARS_MSG)
    return None


_KARS_RE = re.compile(r"\bkarsilastir\w*|\bkiyasla\w*")
_KARS_TARIH_RE = re.compile(r"(?<!\d)(\d{1,2})\s*(?:\.?\s*(" + _AYLAR + r")\w*)?\s*(?:ile|ve|ila|-)\s*(\d{1,2})\s*\.?\s*(" + _AYLAR + r")\w*\s+(20\d{2})\b")
_HAFTALIK_RE = re.compile(r"haftalik\s+ozet|haftalar\w*\s+(?:ozetle|ozet|goster|incele)|hafta\s+hafta")
_HAVA_BIRLIKTE_RE = re.compile(r"\bno2\b|nitrojen|hava\s+kalite\w*|hava\s+kirlil\w*")
_BAYRAM_RE = re.compile(r"bayram|resmi\s+tatil|tatil\w*")
_ILISKI_RE = re.compile(r"iliski|korelasyon|dagilim|birlikte\s+hareket|ne\s+kadar\s+(?:azal|dus)\w*")
_PROFIL_RE = re.compile(r"gun\s+ici|profil\w*|saat\s+saat")
_SAATLIK_RE = re.compile(r"saatlik|gecikme\w*|kac\s+saat")
_TESPIT_RE = re.compile(r"tespit\w*|yakal\w*|basari\w*|dogruluk")
_KARS_MSG = "Karşılaştırma için iki günün tam tarihi (yıl dahil) gerekli. Örnek: '10 Nisan ile 17 Nisan 2024 karşılaştır'. Yılı tahmin etmem."


def karsilastirma_gunleri(metin):
    """'10 Nisan ile 17 Nisan 2024 karsilastir': None (karsilastirma sorusu degil) | ('ok', gun1, gun2) | ('hata', mesaj)."""
    if not _KARS_RE.search(metin):
        return None
    gunler = None
    m = _KARS_TARIH_RE.search(metin)
    if m:
        d1, a1, d2, a2, y = m.groups()
        try:
            gunler = [date(int(y), int(_MONTHS_F[a1 or a2]), int(d1)), date(int(y), int(_MONTHS_F[a2]), int(d2))]
        except ValueError:
            gunler = None
    if gunler is None:
        ds = tarihleri_bul(metin)
        if len(ds) > 2:
            return ("hata", "Karşılaştırma yalnız iki gün için yapılır. Örnek: '10 Nisan ile 17 Nisan 2024 karşılaştır'.")
        if len(ds) == 2:
            gunler = ds
        elif ds or re.search(r"\d{1,2}\s+(?:" + _AYLAR + r")", metin):
            return ("hata", _KARS_MSG)
        else:
            return None
    if gunler[0] == gunler[1]:
        return ("hata", "Karşılaştırma için iki farklı gün gerekli. " + _KARS_MSG)
    a, b = sorted(gunler)
    return ("ok", a, b)


_NORMAL_RE = re.compile(r"\bneden\s+(?:\w+\s+){0,2}normal(?:di)?\b|\bnormal\s*mi(?:ydi)?\b|\bnormal\s+(?:bir\s+)?gun\s*mu(?:ydu)?\b"
                        r"|\bneden\s+(?:\w+\s+){0,2}anomali\s+(?:degil|yok)\b|\banomali\s+degil\s*mi(?:ydi)?\b|\banormal\s+degil\s*mi(?:ydi)?\b")


def normal_gun_sorusu(metin):
    """'17 Nisan 2024 neden normal / normal mi' kalibi: TEK gunluk tam tarih varsa o gunu doner (date), yoksa None.
    Dusus/artis nedeni ya da karsilastirma sorulduysa, aralik varsa ya da tarih yoksa bu yol secilmez (genel bilgi sorulari etkilenmez)."""
    if not _NORMAL_RE.search(metin) or _NEDEN_RE.search(metin) or _KARS_RE.search(metin) or aralik_bul(metin):
        return None
    g = tarihleri_bul(metin)
    return g[0] if len(g) == 1 else None


_SIRALA_RE = re.compile(r"\bhangi\s+gun\w*\b.*\ben\s+cok\s+(dus|azal|art|yuksel|sap)\w*")
_SIRA_N_RE = re.compile(r"(?<!\d)(\d|iki|uc|dort|bes)\s+gun")
_EKSIK_SAY_RE = re.compile(r"\bkac\s+gun\w*\s+(?:\w+\s+){0,2}(?:eksik|veri\s+(?:yok|eksik))|\beksik\s+veri\w*\s+(?:olan\s+)?(?:kac\s+gun|gun\s+say)"
                           r"|\bhangi\s+gun\w*\s+(?:\w+\s+){0,2}eksik\s+veri")
_HICI_RE = re.compile(r"\bhafta\s*ici\b")
_HSONU_RE = re.compile(r"\bhafta\s*sonu\b")
_ONCE_SONRA_RE = re.compile(r"\boncesi\w*|\bsonrasi\w*|\bbayramdan\s+(?:once|sonra)\b")
MAX_NORMAL_HAFTA = 14


def siralama_sorusu(metin):
    """'Nisan 2024'te hangi gun en cok dustu / artti': neden sorusu degil (neden ve 'sen sec' yollari ayri kalir). Doner: yon ('dusus'/'artis'/None) ya da False."""
    if not _SIRALA_RE.search(metin) or re.search(r"\b(?:neden|nicin|niye)\b", metin) or _SEC_RE.search(metin):
        return False
    k = _SIRALA_RE.search(metin).group(1)
    return {"dus": "dusus", "azal": "dusus", "art": "artis", "yuksel": "artis"}.get(k, None) or ("sapma" if k == "sap" else False)


def siralama_sayisi(metin):
    m = _SIRA_N_RE.search(metin)
    if not m:
        return 3
    g = m.group(1)
    return max(1, min(int(g) if g.isdigit() else _SAYI[g], MAX_SEC_GUN))


def eksik_say_sorusu(metin):
    return bool(_EKSIK_SAY_RE.search(metin))


def hafta_ici_sonu_sorusu(metin):
    return bool(_HICI_RE.search(metin) and _HSONU_RE.search(metin))


def bayram_cevresi_sorusu(metin):
    return bool("bayram" in metin and "trafi" in metin and _ONCE_SONRA_RE.search(metin) and not _KARS_RE.search(metin))


def normal_hafta_sorusu(metin):
    """'Nisan 2024 2. hafta neden normaldi' / '8-14 Nisan 2024 normal miydi': (a, b) | ('hata', mesaj) | None. Tek gun tarihi varsa gun yolu, neden dustu/karsilastir ise ayri yol."""
    if not _NORMAL_RE.search(metin) or _NEDEN_RE.search(metin) or _KARS_RE.search(metin):
        return None
    ar = aralik_bul(metin)
    if ar:
        hedef = ar
    elif "hafta" in metin:
        hw = hafta_penceresi(metin)
        if hw is None:
            return None
        if hw[0] == "hata":
            return ("hata", hw[1])
        hedef = (hw[1], hw[2])
    else:
        return None
    if (hedef[1] - hedef[0]).days + 1 > MAX_NORMAL_HAFTA:
        return ("hata", f"Hafta için en fazla {MAX_NORMAL_HAFTA} günlük pencere sorulabilir. Örnek: '8-14 Nisan 2024 neden normaldi'.")
    return hedef


def _ay_yolu(metin, mod, adimlar):
    gor = _GORELI_KESIN.search(metin) or _GORELI_BELIRSIZ.search(metin)
    if gor and not (_AY_ADI_RE.search(metin) or _AY_NO_RE.search(metin)):
        return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": goreli_mesaji(gor.group(0))}
    ay = ay_penceresi(metin, mod)
    if ay[0] == "hata":
        return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": ay[1]}
    return {"istek_tipi": "analiz", "start": f"{ay[1]} 00:00", "end": f"{ay[2]} 23:00", "plan": adimlar}


def planla(state: State):
    metin = fold(state["soru"])
    if bayram_cevresi_sorusu(metin):
        bc = bayram_cevresi(metin)
        if bc[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": bc[1]}
        gun = bc[3]
        return {"istek_tipi": "analiz", "start": f"{gun[0] - timedelta(days=BAYRAM_PENCERE)} 00:00",
                "end": f"{gun[-1] + timedelta(days=BAYRAM_PENCERE)} 23:00", "plan": ["kapsam_kontrol", "takvim_kontrol", "bayram_oncesi_sonrasi"]}
    if hafta_ici_sonu_sorusu(metin):
        return _ay_yolu(metin, "hafta_ici", ["ay_coz", "kapsam_kontrol", "takvim_kontrol", "hafta_ici_sonu"])
    if eksik_say_sorusu(metin):
        return _ay_yolu(metin, "eksik", ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "eksik_veri_say"])
    if siralama_sorusu(metin):
        return _ay_yolu(metin, "siralama", ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "gun_siralama"])
    if _NORMAL_RE.search(metin) and "hafta" in metin and not _NEDEN_RE.search(metin):
        gor = _GORELI_KESIN.search(metin) or _GORELI_BELIRSIZ.search(metin)
        if gor and not (aralik_bul(metin) or tarihleri_bul(metin)):
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": goreli_mesaji(gor.group(0))}
    nh = normal_hafta_sorusu(metin)
    if nh and nh[0] == "hata":
        return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": nh[1]}
    if nh:
        return {"istek_tipi": "analiz", "start": f"{nh[0]} 00:00", "end": f"{nh[1]} 23:00", "plan": ["kapsam_kontrol", "hafta_normal_aciklama"]}
    bk = bayram_karsilastirma(metin)
    if bk:
        if bk[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": bk[1]}
        ilk = min(date(y, 1, 1) for _, y in bk[1])
        son = max(date(y, 12, 31) for _, y in bk[1])
        return {"istek_tipi": "analiz", "start": f"{ilk} 00:00", "end": f"{son} 23:00",
                "plan": ["kapsam_kontrol", "takvim_kontrol", "bayram_karsilastir"]}
    if hafta_tatil_sorusu(metin):
        gor = _GORELI_KESIN.search(metin) or _GORELI_BELIRSIZ.search(metin)
        if gor and not (_AY_ADI_RE.search(metin) or _AY_NO_RE.search(metin)):
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": goreli_mesaji(gor.group(0))}
        ay = ay_penceresi(metin, "hafta_tatil")
        if ay[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": ay[1]}
        return {"istek_tipi": "analiz", "start": f"{ay[1]} 00:00", "end": f"{ay[2]} 23:00",
                "plan": ["ay_coz", "kapsam_kontrol", "takvim_kontrol", "tatil_haftalari"]}
    analiz_mi = any(k in metin for k in ANALIZ_KEYS) or bool(_NEDEN_RE.search(metin))
    hafta = hafta_penceresi(metin) if analiz_mi else None
    _ar = aralik_bul(metin)
    _acik = bool(_ar or tarihleri_bul(metin))
    gor = _GORELI_KESIN.search(metin) or (_GORELI_BELIRSIZ.search(metin) if analiz_mi else None)
    if gor and not _acik and not (hafta and hafta[0] == "ok") and (analiz_mi or ("trafi" in metin and _GORELI_KESIN.search(metin))):
        return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": goreli_mesaji(gor.group(0))}
    ng = normal_gun_sorusu(metin)
    if ng:
        return {"istek_tipi": "analiz", "start": f"{ng} 00:00", "end": f"{ng} 23:00", "plan": ["kapsam_kontrol", "normal_gun_aciklama"]}
    akars = ay_karsilastirma(metin)
    if akars:
        if akars[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": akars[1]}
        (y1, m1), (y2, m2) = akars[1], akars[-1]
        son = date(y2 + (m2 == 12), m2 % 12 + 1, 1) - timedelta(days=1)
        return {"istek_tipi": "analiz", "start": f"{date(y1, m1, 1)} 00:00", "end": f"{son} 23:00",
                "plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "ay_karsilastir"]}
    kars = karsilastirma_gunleri(metin)
    if kars:
        if kars[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": kars[1]}
        return {"istek_tipi": "analiz", "start": f"{kars[1]} 00:00", "end": f"{kars[2]} 23:00",
                "plan": ["kapsam_kontrol", "gun_karsilastir", "araclari_cagir", "hipotezleri_puanla", "rapor"]}
    _serbest = not _AY_ADI_RE.search(metin) and not _AY_NO_RE.search(metin) and not aralik_bul(metin) and not tarihleri_bul(metin)
    if _serbest and (_TESPIT_RE.search(metin) and any(k in metin for k in ("sistem", "olay", "anomali", "bayram", "tatil"))) and not _HAVA_BIRLIKTE_RE.search(metin):
        ilk, son = min(x[0] for x in COVER["traffic"]), max(x[1] for x in COVER["traffic"])
        return {"istek_tipi": "analiz", "start": f"{ilk} 00:00", "end": f"{son} 23:00", "plan": ["kapsam_kontrol", "tespit_ozet"]}
    if _serbest and _HAVA_BIRLIKTE_RE.search(metin) and "trafi" in metin and (_PROFIL_RE.search(metin) or _SAATLIK_RE.search(metin)):
        ilk, son = min(x[0] for x in COVER["traffic"]), max(x[1] for x in COVER["traffic"])
        adim = "gun_profil_ozet" if _PROFIL_RE.search(metin) else "saatlik_iliski_ozet"
        return {"istek_tipi": "analiz", "start": f"{ilk} 00:00", "end": f"{son} 23:00", "plan": ["kapsam_kontrol", adim]}
    if (_HAVA_BIRLIKTE_RE.search(metin) and (_BAYRAM_RE.search(metin) or _ILISKI_RE.search(metin)) and "trafi" in metin
            and not _AY_ADI_RE.search(metin) and not _AY_NO_RE.search(metin) and not aralik_bul(metin) and not tarihleri_bul(metin)):
        ilk, son = min(x[0] for x in COVER["traffic"]), max(x[1] for x in COVER["traffic"])
        adim = "bayram_hava_ozet" if _BAYRAM_RE.search(metin) else "hava_iliski_ozet"
        return {"istek_tipi": "analiz", "start": f"{ilk} 00:00", "end": f"{son} 23:00", "plan": ["kapsam_kontrol", adim]}
    if _HAVA_BIRLIKTE_RE.search(metin) and "trafi" in metin and (_AY_ADI_RE.search(metin) or _AY_NO_RE.search(metin)) and not aralik_bul(metin) and not tarihleri_bul(metin):
        ay = ay_penceresi(metin, "tara")
        if ay[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": ay[1]}
        return {"istek_tipi": "analiz", "start": f"{ay[1]} 00:00", "end": f"{ay[2]} 23:00",
                "plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "hava_birlikte_ozet"]}
    if _HAFTALIK_RE.search(metin) and (_AY_ADI_RE.search(metin) or _AY_NO_RE.search(metin)):
        ay = ay_penceresi(metin, "hafta")
        if ay[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": ay[1]}
        return {"istek_tipi": "analiz", "start": f"{ay[1]} 00:00", "end": f"{ay[2]} 23:00",
                "plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "haftalik_ozet"]}
    if hafta and hafta[0] == "hata":
        return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": hafta[1]}
    if hafta:
        return {"istek_tipi": "analiz", "start": f"{hafta[1]} 00:00", "end": f"{hafta[2]} 23:00",
                "plan": ["hafta_coz", "kapsam_kontrol", "araclari_cagir", "hipotezleri_puanla", "rapor"]}
    ar = aralik_bul(metin)
    gunler = [ar[0], ar[1]] if ar else tarihleri_bul(metin)
    if analiz_mi and gunler:
        a, b = gunler[0], gunler[-1]
        return {"istek_tipi": "analiz", "start": f"{a} 00:00", "end": f"{b} 23:00",
                "plan": ["kapsam_kontrol", "araclari_cagir", "hipotezleri_puanla", "rapor"]}
    if analiz_mi and secim_sorusu_mu(metin):
        ay = ay_penceresi(metin, "sec")
        if ay[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": ay[1]}
        return {"istek_tipi": "analiz", "start": f"{ay[1]} 00:00", "end": f"{ay[2]} 23:00",
                "plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "en_sapmali_gun",
                         "araclari_cagir", "hipotezleri_puanla", "rapor"]}
    if analiz_mi and varlik_sorusu_mu(state["soru"]):
        ay = ay_penceresi(metin, "tara")
        if ay[0] == "hata":
            return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"], "mesaj": ay[1]}
        return {"istek_tipi": "analiz", "start": f"{ay[1]} 00:00", "end": f"{ay[2]} 23:00",
                "plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama"]}
    if analiz_mi:
        return {"istek_tipi": "eksik", "start": None, "end": None, "plan": ["tarih_iste"]}
    return {"istek_tipi": "bilgi", "start": None, "end": None,
            "plan": ["kapsam_kontrol", "kb_ara", "kaynakli_yanit"]}


_CALLER = None  # testte sahte LLM vermek icin; None ise gercek Ollama


def planla_ana(state: State):
    """Kural once. Kural cozemezse (eksik, ya da tarihli bilgi sorusu) LLM soru anlama denenir."""
    if os.environ.get("TIMERCA_SORU_LLM", "1") == "0":
        return planla(state)
    kural = planla(state)
    if kural["istek_tipi"] == "eksik" and str(kural.get("mesaj") or "").startswith(("Göreli tarih", "Karşılaştırma için", "Karşılaştırma yalnız", "Ay karşılaştırması için", "Bayram öncesi/sonrası için", "Hafta ifadesi için", "Hafta için")):
        return kural  # 'dun' gibi goreli tarih: LLM tarih uyduramaz (dogrulama gecmez), bekletmeden yuklu donemleri soyle
    try:
        import soru_llm
        kw = {"caller": _CALLER} if _CALLER else {}
        r = soru_llm.planla_llm(state, kural_planla=planla,
                                tarih_bul=lambda t: tarihleri_bul(fold(t)), **kw)
        return {k: r[k] for k in ("istek_tipi", "start", "end", "plan", "mesaj") if k in r}
    except Exception:
        return planla(state)


def yonlendir(state: State):
    return state["istek_tipi"]


def bilgi(state: State):
    r = rag.answer_context(state["soru"], k=3)
    return {"sonuc": {"tip": "bilgi", "durum": r["status"], "nedenler": r["reasons"],
                      "notlar": [{"id": h["id"], "metin": h["text"], "etiket": h["label"]}
                                 for h in r["hits"]]}}


def eksik(state: State):
    return {"sonuc": {"tip": "eksik",
                      "mesaj": state.get("mesaj") or "Analiz için tarih gerekli. Örnek: '10 Nisan 2024 trafik neden düştü?' "
                               "veya '2023-11-13 analiz et'. İki tarih verirsen aralık olur."}}


def _ay_tara(state):
    """Ay penceresinin yuklu gunlerini tarar. (None, {'sonuc':...}) kapsam disiysa; yoksa (tarama, ozet bilgileri)."""
    a, b = date.fromisoformat(state["start"][:10]), date.fromisoformat(state["end"][:10])
    n_gun = (b - a).days + 1
    kapsamli = [a + timedelta(days=i) for i in range(n_gun) if _overlap(COVER["traffic"], a + timedelta(days=i), a + timedelta(days=i))]
    if not kapsamli:
        return None, {"sonuc": {"tip": "kapsam_disi", "nedenler": [f"trafik verisi yüklü değil: {a} - {b}", f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    import scan
    r = scan.scan(str(kapsamli[0]), str(kapsamli[-1]))
    dv = sum(1 for x in r["adaylar"] if x["durum"] in ("veri_yok", "degerlendirilemedi"))
    return r, {"a": a, "kapsamli": kapsamli, "ay_ad": f"{_AY_TR[a.month]} {a.year}", "dv": dv,
               "sapma": sum(1 for x in r["adaylar"] if x["durum"] in ("dusus", "artis", "eksik_veri_ve_sapma")),
               "kapsam_txt": (f"{r['taranan']} gün tarandı, {r['taranan'] - dv} günü değerlendirilebildi"
                              + (f" ({dv} gün veri yok ya da karşılaştırma verisi yetersiz)" if dv else "")),
               "kismi": f" Ayın yalnız {len(kapsamli)} günü yüklü." if len(kapsamli) < n_gun else ""}


def _haftalar(r, c):
    """Ayin N. haftasi = gun (N-1)*7+1 .. N*7 (hafta_penceresi ile ayni sozlesme). Tarama sonucunu haftalara gruplar."""
    a = c["a"]
    ay_son = (date(a.year + (a.month == 12), a.month % 12 + 1, 1) - timedelta(days=1)).day
    kap = {str(d) for d in c["kapsamli"]}
    dv = {x["gun"] for x in r["adaylar"] if x["durum"] in ("veri_yok", "degerlendirilemedi")}
    out = []
    for n in range(1, 6):
        b1 = (n - 1) * 7 + 1
        if b1 > ay_son:
            break
        b2 = min(n * 7, ay_son)
        gunler = [f"{a.year}-{a.month:02d}-{d:02d}" for d in range(b1, b2 + 1)]
        yuklu = [g for g in gunler if g in kap]
        out.append({"hafta": n, "baslangic": gunler[0], "bitis": gunler[-1], "yuklu_gun": len(yuklu),
                    "degerlendirilebilen": len([g for g in yuklu if g not in dv]),
                    "adaylar": [{"gun": x["gun"], "durum": x["durum"], "oran": x.get("medyan_oran")} for x in r["adaylar"]
                                if x["gun"] in gunler and x["durum"] not in ("veri_yok", "degerlendirilemedi")]})
    return out


def _haftalik_ozet_metni(c, haftalar):
    p = []
    for w in haftalar:
        rng = f"{w['baslangic'][8:]}–{w['bitis'][8:]}.{w['baslangic'][5:7]}"
        if not w["yuklu_gun"]:
            p.append(f"{w['hafta']}. hafta ({rng}): yüklü gün yok")
            continue
        k = len(w["adaylar"])
        ad = ("; ".join(f"{_gun(x['gun'])} {_DURUM_TR.get(x['durum'], x['durum'])}"
                        + (f" (oran {x['oran']:.2f})" if x.get("oran") is not None else "") for x in w["adaylar"])) if k else ""
        p.append(f"{w['hafta']}. hafta ({rng}): " + (f"{k} olağandışı gün ({ad})" if k else "olağandışı gün yok")
                 + f", {w['degerlendirilebilen']}/{w['yuklu_gun']} gün değerlendirilebildi")
    return (f"{c['ay_ad']} haftalık özet: " + " | ".join(p) + ". 'Olağandışı gün yok' sorunsuz demek değil, eşiği aşmadı demektir; "
            "nedenini görmek için günü tek gün olarak sor.")


def _ay_var(state, haftalik=False):
    """'Nisan 2024'te anomali var miydi': ay boyunca gun gun tarama; neden aramaz, aday gunleri listeler."""
    r, c = _ay_tara(state)
    if r is None:
        return c
    if haftalik:
        hw = _haftalar(r, c)
        return {"plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "haftalik_ozet"],
                "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}",
                          "ozet": _haftalik_ozet_metni(c, hw) + c["kismi"], "hipotezler": {}, "insan_gerekli": False,
                          "nihai_durum": "otomatik", "haftalar": hw, "tarama": r}}
    return {"plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}",
                      "ozet": tarama_ozeti(r) + f" Değerlendirilebilen gün: {r['taranan'] - c['dv']}/{r['taranan']}." + c["kismi"],
                      "hipotezler": {}, "insan_gerekli": False, "nihai_durum": "otomatik", "tarama": r}}


def _ay_hava_birlikte(state):
    """'Nisan 2024'te trafik dusen kac gunde NO2 de dustu': ay taramasindaki dusus/artis gunlerini ayni gunun NO2 orani ile yan yana sayar.
    YALNIZ GOSTERIM: sayi ve gun listesi; neden iddiasi yok, karar kuralina girmez (gun durumlari scan.py'den aynen gelir)."""
    r, c = _ay_tara(state)
    if r is None:
        return c
    try:
        import air_quality
        var = air_quality.available()
    except Exception:
        air_quality, var = None, False
    cevap = {"dusus": [], "artis": []}
    for x in r["adaylar"]:
        if x["durum"] not in cevap:
            continue
        no2 = pm10 = None
        if var:
            try:
                cc = air_quality.compare(f"{x['gun']} 00:00", f"{x['gun']} 23:00")
                no2, pm10 = cc.get("ratio_no2"), cc.get("ratio_pm10")
            except Exception:
                no2 = pm10 = None
        cevap[x["durum"]].append({"gun": x["gun"], "trafik_orani": x["medyan_oran"], "no2_orani": no2,
                                  "no2_durum": air_quality._d(no2) if (var and no2 is not None) else None,
                                  "pm10_orani": pm10, "pm10_durum": air_quality._d(pm10) if (var and pm10 is not None) else None})
    ozet = {}
    for yon, liste in cevap.items():
        say = lambda d: sum(1 for g in liste if g["no2_durum"] == d)
        ozet[yon] = {"toplam": len(liste), "no2_ayni_yonde": say("dusuk" if yon == "dusus" else "yuksek"), "no2_normal": say("normal"),
                     "no2_ters_yonde": say("yuksek" if yon == "dusus" else "dusuk"), "no2_verisi_yok": sum(1 for g in liste if g["no2_durum"] is None),
                     "pm10_de_ayni_yonde": sum(1 for g in liste if g["no2_durum"] == ("dusuk" if yon == "dusus" else "yuksek")
                                               and g["pm10_durum"] == ("dusuk" if yon == "dusus" else "yuksek")),
                     "gunler": liste}
    def cumle(yon, ad, ayni):
        o = ozet[yon]
        if not o["toplam"]:
            return f"Trafiğin {ad} gün yok."
        return (f"Trafiğin {ad} {o['toplam']} günün {o['no2_ayni_yonde']} gününde NO2 de {ayni}; {o['no2_normal']} gününde NO2 normal, "
                f"{o['no2_ters_yonde']} gününde ters yönde, {o['no2_verisi_yok']} gününde NO2 verisi yok.")
    pm = ""
    if ozet["dusus"]["no2_ayni_yonde"]:
        pm = (f" NO2'nin de düştüğü {ozet['dusus']['no2_ayni_yonde']} günün {ozet['dusus']['pm10_de_ayni_yonde']} gününde PM10 da düşük"
              + (" (yağış ya da rüzgâr gibi bir hava temizlemesi etkisi olabilir)." if ozet["dusus"]["pm10_de_ayni_yonde"] else "."))
    metin = (f"{c['ay_ad']}: {c['kapsam_txt']}. " + cumle("dusus", "düştüğü", "düştü") + pm + " " + cumle("artis", "arttığı", "arttı")
             + " Bu bir sayımdır; birlikte hareket nedeni kanıtlamaz (rüzgâr, yağış gibi etkenler de NO2'yi değiştirir) ve hiçbir günün kararını değiştirmez.")
    if not var:
        metin += " Hava kalitesi verisi yüklü olmadığı için NO2 karşılaştırması yapılamadı."
    return {"plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "hava_birlikte_ozet"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": metin + c["kismi"], "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "hava_birlikte": ozet, "tarama": r}}


def _hava_hazir(state, adim):
    """Hava kalitesi verisi yoksa bilgi verir (uydurma yok). Doner: None ya da hazir sonuc."""
    try:
        import air_quality
        if air_quality.available():
            return None
    except Exception:
        pass
    return {"plan": ["kapsam_kontrol", adim], "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}",
            "ozet": "Hava kalitesi verisi yüklü değil, bu karşılaştırma yapılamadı.", "hipotezler": {}, "insan_gerekli": False, "nihai_durum": "otomatik"}}


def _bayram_hava(state):
    """'Bayramlarda NO2 ne kadar duser': yuklu donemdeki tum resmi tatil gunlerinde trafik ve NO2 orani. YALNIZ GOSTERIM."""
    hz = _hava_hazir(state, "bayram_hava_ozet")
    if hz:
        return hz
    import hava_ozet
    r = hava_ozet.bayram_ozeti(COVER)
    o = r["ozet"]
    if not o["toplam"]:
        ozet = "Yüklü dönemde değerlendirilebilen resmî tatil günü bulunamadı."
    else:
        ozet = (f"Yüklü dönemde değerlendirilebilen {o['toplam']} resmî tatil gününün {o['trafik_dusen']} gününde trafik normalin altında. "
                f"Bu {o['trafik_dusen']} günün {o['no2_de_dusen']} gününde NO2 de düşük; {o['no2_normal']} gününde NO2 normal, "
                f"{o['no2_ters']} gününde yüksek, {o['no2_yok']} gününde NO2 verisi yok. "
                f"Tüm tatil günlerinde ortanca trafik oranı {o['medyan_trafik_orani']:.2f}" + (f", NO2 oranı {o['medyan_no2_orani']:.2f}" if o["medyan_no2_orani"] is not None else "")
                + ". Bu bir sayımdır; birlikte hareket nedeni kanıtlamaz ve hiçbir günün kararını değiştirmez.")
    return {"plan": ["kapsam_kontrol", "bayram_hava_ozet"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "bayram_hava": r}}


def _hava_iliski(state):
    """'Trafik ile NO2 iliskisi': gun gun nokta, egim ve korelasyon. YALNIZ GOSTERIM; neden iddiasi yok."""
    hz = _hava_hazir(state, "hava_iliski_ozet")
    if hz:
        return hz
    import hava_ozet
    r = hava_ozet.iliski(COVER)
    if r["egim"] is None:
        ozet = f"Yeterli gün yok ({r['n']} gün); trafik ile NO2 arasındaki ilişki hesaplanmadı."
    else:
        k = abs(r["korelasyon"])
        guc = "zayıf" if k < 0.3 else ("orta" if k < 0.6 else "güçlü")
        ozet = (f"{r['n']} günde trafik oranı ile NO2 oranı birlikte incelendi. Gün gün bağıntı {r['korelasyon']:.2f}: ilişki {guc}"
                + (" (günlük NO2 rüzgâr ve yağış gibi hava koşullarından da güçlü etkilendiği için tek tek günlerde trafikle örtüşmeyebilir)." if guc == "zayıf" else "."))
        g = r.get("gruplar") or {}
        if g.get("dusus", {}).get("n") and g.get("normal", {}).get("n"):
            ozet += (f" Trafiğin normalin altında olduğu {g['dusus']['n']} günde NO2 oranının ortancası {g['dusus']['medyan_no2']:.2f} "
                     f"(günlerin %{round(g['dusus']['no2_dusuk_pay'] * 100)}'inde NO2 de düşük); normal trafikli {g['normal']['n']} günde ortanca {g['normal']['medyan_no2']:.2f} "
                     f"(%{round(g['normal']['no2_dusuk_pay'] * 100)}).")
        bz = r.get("benzer_hava")
        if bz:
            if bz["korelasyon"] is None:
                ozet += f" Hava koşulları benzer olan (yağışsız, rüzgâr normale yakın) yalnızca {bz['n']} gün var; bu günlerle ayrı bir bağıntı hesaplanmadı."
            else:
                kb = abs(bz["korelasyon"])
                gb = "zayıf" if kb < 0.3 else ("orta" if kb < 0.6 else "güçlü")
                ozet += (f" Yağış ve rüzgârın etkisini azaltmak için yalnızca hava koşulları benzer olan {bz['n']} gün ayrıca incelendi "
                         f"(yağışsız, rüzgâr kıyas günlerine yakın): bağıntı {bz['korelasyon']:.2f}, ilişki {gb}.")
                gg = bz["gruplar"]
                if gg["dusus"]["n"] and gg["normal"]["n"]:
                    ozet += (f" Bu günlerde trafiği normalin altında olan {gg['dusus']['n']} günde NO2 oranının ortancası {gg['dusus']['medyan_no2']:.2f}, "
                             f"normal trafikli {gg['normal']['n']} günde {gg['normal']['medyan_no2']:.2f}.")
        if k >= 0.3:
            ozet += f" Doğrusal eğim {r['egim']:.2f}: trafik oranı 0,10 düştüğünde NO2 oranı ortalama yaklaşık {abs(r['egim']) * 0.10:.2f} düşüyor."
        ozet += " Bu bir birlikte hareket ölçüsüdür; nedeni kanıtlamaz ve hiçbir günün kararını değiştirmez."
    return {"plan": ["kapsam_kontrol", "hava_iliski_ozet"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "hava_iliski": r}}


def _saatlik_iliski(state):
    """'Trafik ve NO2 saatlik gecikme': saat saat bagintilar. YALNIZ GOSTERIM; neden iddiasi yok."""
    hz = _hava_hazir(state, "saatlik_iliski_ozet")
    if hz:
        return hz
    import hava_ozet
    r = hava_ozet.saatlik_gecikme(COVER)
    if r is None or r["en_iyi_gecikme"] is None:
        ozet = "Saatlik karşılaştırma için yeterli veri yok."
    else:
        k = r["en_iyi_korelasyon"]
        guc = "zayıf" if abs(k) < 0.3 else ("orta" if abs(k) < 0.6 else "güçlü")
        g0 = r["lagler"][0]["korelasyon"]
        ks = [l["korelasyon"] for l in r["lagler"] if l["korelasyon"] is not None]
        if max(ks) - min(ks) <= 0.02:
            gec = f"0-{len(r['lagler']) - 1} saat gecikmelerinin hepsinde bağıntı aynı ({k:.2f}); belirgin bir gecikme görünmüyor (ilişki {guc}). "
        else:
            gec = f"NO2 trafikten {r['en_iyi_gecikme']} saat sonra ölçüldüğünde bağıntı en yüksek: {k:.2f} (ilişki {guc}). "
        ozet = (f"{r['saat_sayisi']} saatte trafik oranı ile NO2 oranı karşılaştırıldı (Spearman sıra bağıntısı). Aynı saatte bağıntı {g0:.2f}; " + gec
                + "Bu bir birlikte hareket ölçüsüdür; nedeni kanıtlamaz ve hiçbir günün kararını değiştirmez.")
    return {"plan": ["kapsam_kontrol", "saatlik_iliski_ozet"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "saatlik_iliski": r}}


def _gun_profil(state):
    """'Bayram gunlerinde gun ici trafik ve NO2 profili': tatil gunleri ile diger gunlerin saat saat ortalama orani. YALNIZ GOSTERIM."""
    hz = _hava_hazir(state, "gun_profil_ozet")
    if hz:
        return hz
    import hava_ozet
    r = hava_ozet.gun_profili(COVER)
    if r is None:
        ozet = "Gün içi profil için yeterli veri yok."
    else:
        t, d = r["tatil"], r["diger"]
        sab = [h for h in range(6, 11) if t["no2"][h] is not None and d["no2"][h] is not None]
        ozet = (f"Resmî tatil günlerinde ({t['gun_sayisi']} gün) ve diğer günlerde ({d['gun_sayisi']} gün) saat saat ortalama trafik ve NO2 oranı karşılaştırıldı. "
                + (f"Sabah 06:00-10:00 arasında ortalama trafik oranı tatilde {sum(t['trafik'][h] for h in sab) / len(sab):.2f}, diğer günlerde {sum(d['trafik'][h] for h in sab) / len(sab):.2f}; "
                   f"NO2 oranı tatilde {sum(t['no2'][h] for h in sab) / len(sab):.2f}, diğer günlerde {sum(d['no2'][h] for h in sab) / len(sab):.2f}. " if sab else "")
                + "Oranlar, her saatin önceki 4 haftanın aynı gün ve saatine göre değeridir. Bu bir gösterimdir; nedeni kanıtlamaz ve hiçbir günün kararını değiştirmez.")
    return {"plan": ["kapsam_kontrol", "gun_profil_ozet"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "gun_profili": r}}


def _tespit(state):
    """'Sistem bilinen olaylari ne kadar yakaliyor': tatil gunlerinin kacinda dusus bulundu, tatil disi gunlerin kacinda olagandisi isaretlendi."""
    import hava_ozet
    r = hava_ozet.tespit_ozeti(COVER)
    t, d = r["tatil"], r["diger"]
    pay = lambda a, b: f"%{round(100 * a / b)}" if b else "–"
    ozet = (f"Değerlendirilebilen {r['degerlendirilen_gun']} günün {t['toplam']} günü resmî tatil. Tatil günlerinin {t['dusus']} gününde trafik düşüş olarak bulundu "
            f"({pay(t['dusus'], t['toplam'])}), {t['normal']} gününde normal, {t['artis']} gününde artış göründü. Tatil olmayan {d['toplam']} günün "
            f"{d['dusus'] + d['artis']} günü olağandışı işaretlendi ({pay(d['dusus'] + d['artis'], d['toplam'])}: {d['dusus']} düşüş, {d['artis']} artış). "
            "Tatil dışı olağandışı günler yanlış alarm olmak zorunda değildir: okul tatili, idari izin, hava olayı ya da veri sorunu olabilir. "
            "Bu bir sayımdır; nedeni kanıtlamaz ve sistemin karar kurallarını değiştirmez.")
    return {"plan": ["kapsam_kontrol", "tespit_ozet"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "tespit": r}}


def _incele_gun(gun):
    import api  # mevcut ajan, /analyze ile ayni kod yolu
    return api.analyze({"start": f"{gun} 00:00", "end": f"{gun} 23:00"})


def _veri_hatasi_mi(code, obj):
    if code != 200:
        return False
    if "rapor" in obj:
        return any(h["name"] == "veri_hatasi" and h["status"] == "destekliyor" for h in obj["rapor"]["hypotheses"])
    return "veri_hatasi" in ((obj.get("soru") or {}).get("destekleyen") or [])


def _gun_satiri(g, code, obj):
    ad = f"{_gun(g['gun'])} (oran {g['medyan_oran']:.2f})"
    if code != 200:
        return f"{ad}: inceleme yapılamadı"
    if "rapor" in obj:
        d = [_HIP_TR.get(h["name"], h["name"]) for h in obj["rapor"]["hypotheses"] if h["status"] == "destekliyor"]
        return f"{ad}: " + ("destekleyen: " + ", ".join(d) if d else "destekleyen neden yok")
    return f"{ad}: kanıt yetersiz, insan onayı gerekir (bu günü tek gün olarak sor)"


def _ay_sec(state):
    """Ay penceresini tarar, sabit kuralla gun(ler) secer. {'sonuc':...} dondurursa orada biter; yoksa secilen gun bilgisi."""
    r, c = _ay_tara(state)
    if r is None:
        return c
    metin = fold(state["soru"])
    yon, n, hatasiz = secim_yonu(metin), secim_sayisi(metin), bool(_VERI_HATASIZ_RE.search(metin))
    sirali = sirala_gunler(r["adaylar"], yon)
    yon_tr = {"dusus": "düşüş", "artis": "artış", None: "sapma"}[yon]
    onbilgi = f"{c['ay_ad']}: {c['kapsam_txt']}; {c['sapma']} gün olağandışı."
    inc, secilen, elenen = {}, [], []
    if hatasiz:  # ajanla en cok MAX_ELEME aday denenir; 'veri hatasi destekliyor' olanlar elenir
        for g in sirali[:MAX_ELEME]:
            if len(secilen) >= n:
                break
            inc[g["gun"]] = _incele_gun(g["gun"])
            (elenen if _veri_hatasi_mi(*inc[g["gun"]]) else secilen).append(g)
    else:
        secilen = sirali[:n]
    if not secilen:
        if elenen:
            ozet = (f"{c['ay_ad']}: {c['kapsam_txt']}; {yon_tr} yönündeki ilk {len(elenen)} günün hepsinde veri hatası destekleniyor "
                    f"({', '.join(_gun(x['gun']) for x in elenen)}); veri hatası olmayan gün seçilmedi.{c['kismi']}")
        else:
            ozet = (f"{c['ay_ad']}: {c['kapsam_txt']}; {yon_tr} yönünde eşiği aşan gün yok, gün seçilmedi.{c['kismi']} "
                    "Bu 'sorunsuz' demek değil, 'eşiği aşmadı' demektir (gün genelinde bakıldığı için kısa süreli sorunlar görünmeyebilir).")
        return {"plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama"] + (["en_sapmali_gun"] if hatasiz else []),
                "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet,
                          "hipotezler": {}, "insan_gerekli": False, "nihai_durum": "otomatik", "tarama": r}}
    elenen_txt = (" Veri hatası destekleyen günler elendi: "
                  + ", ".join(f"{_gun(x['gun'])} (oran {x['medyan_oran']:.2f})" for x in elenen) + ".") if elenen else ""
    kural = (f"Seçim kuralı: {yon_tr} yönünde oranı 1'den en çok sapan gün"
             + (f" (veri hatası destekleyen günler elenir; en çok {MAX_ELEME} gün denenir)" if hatasiz else ""))
    if n == 1:
        g = secilen[0]
        onek = f"{onbilgi} {kural} → {_gun(g['gun'])} (oran {g['medyan_oran']:.2f}).{elenen_txt}{c['kismi']} "
        return {"start": f"{g['gun']} 00:00", "end": f"{g['gun']} 23:00", "onek": onek,
                "secim": {"gun": g["gun"], "oran": g["medyan_oran"], "yon": yon, "aday_sayisi": c["sapma"],
                          "taranan": r["taranan"], "degerlendirilemeyen": c["dv"],
                          "elenen": [x["gun"] for x in elenen]}}
    satirlar = [_gun_satiri(g, *(inc.get(g["gun"]) or _incele_gun(g["gun"]))) for g in secilen]
    ozet = f"{onbilgi} {kural}, ilk {len(secilen)}: " + "; ".join(satirlar) + "." + elenen_txt + c["kismi"]
    if len(secilen) < n:
        ozet += f" İstenen {n} günden yalnız {len(secilen)} uygun gün bulundu."
    return {"plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "en_sapmali_gun", "araclari_cagir", "hipotezleri_puanla", "rapor"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet,
                      "hipotezler": {}, "insan_gerekli": False, "nihai_durum": "otomatik",
                      "secim_listesi": [{"gun": g["gun"], "oran": g["medyan_oran"]} for g in secilen], "tarama": r}}


_ACIKLAMA = None  # testte sahte aciklama yazari vermek icin; None ise llm_explain (Ollama)


def _llm_aciklama(rep):
    """Tek gun analizine LLM aciklamasi (TIMERCA_ACIKLAMA_LLM=1). Karar degismez; dogrulama gecmezse kural metni doner."""
    if os.environ.get("TIMERCA_ACIKLAMA_LLM", "0") != "1":
        return None
    try:
        if _ACIKLAMA:
            x = _ACIKLAMA(rep)
        else:
            import llm_explain
            x = llm_explain.explain(rep)
        return {"text": x["text"], "source": x["source"], "model": x.get("model"), "reason": x.get("reason", "")}
    except Exception:
        return None


def _gun_orani(gun):
    import scan
    c = scan._compare(f"{gun} 00:00", f"{gun} 23:00")
    if isinstance(c, dict) and "error" in c:
        return None, None
    return scan.classify(c)


def _gun_karsilastir(state):
    """Iki gunu ayri ayri, ayni kurallarla degerlendirir; yan yana gosterir. Yeni karar kurali yoktur."""
    a, b = date.fromisoformat(state["start"][:10]), date.fromisoformat(state["end"][:10])
    gunler = [a, b]
    disi = [str(g) for g in gunler if not _overlap(COVER["traffic"], g, g)]
    if disi:
        return {"sonuc": {"tip": "kapsam_disi",
                          "nedenler": [f"trafik verisi yüklü değil: {', '.join(disi)}", f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    kayitlar, parcalar, bekleyen = [], [], False
    for g in gunler:
        gs = str(g)
        code, obj = _incele_gun(gs)
        try:
            durum, oran = _gun_orani(gs)
        except Exception:
            durum, oran = None, None
        ad = f"{_gun(gs)} ({'oran %.2f' % oran if oran is not None else 'oran hesaplanamadı'})"
        k = {"gun": gs, "oran": oran, "durum": durum, "destekleyen": [], "bekliyor": False,
             "takvim": [n for x in takvim_notu(g, g) for n in x["notlar"]]}
        if code != 200:
            parcalar.append(f"{ad}: inceleme yapılamadı")
        elif "rapor" in obj:
            k["destekleyen"] = [h["name"] for h in obj["rapor"]["hypotheses"] if h["status"] == "destekliyor"]
            d = [_HIP_TR.get(n, n) for n in k["destekleyen"]]
            parcalar.append(f"{ad}: " + ("destekleyen: " + ", ".join(d) if d else "destekleyen neden yok"))
        else:
            k["bekliyor"] = bekleyen = True
            parcalar.append(f"{ad}: kanıt yetersiz, insan onayı gerekir (bu günü tek gün olarak sor)")
        kayitlar.append(k)
    ozet = f"{_gun(str(a))} ile {_gun(str(b))} karşılaştırıldı. " + "; ".join(parcalar) + "."
    if all(k["oran"] is not None for k in kayitlar):
        o1, o2 = kayitlar[0]["oran"], kayitlar[1]["oran"]
        ozet += (f" Normale göre oran farkı: {abs(o1 - o2):.2f}. Her gün aynı kurallarla ayrı ayrı değerlendirildi; "
                 "karşılaştırma yeni bir karar kuralı değildir.")
    return {"plan": ["kapsam_kontrol", "gun_karsilastir", "araclari_cagir", "hipotezleri_puanla", "rapor"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": bekleyen, "nihai_durum": "ek_inceleme_gerekli" if bekleyen else "otomatik",
                      "karsilastirma": kayitlar}}


_HAFTA_RE = re.compile(r"\bhafta\w*")
_TATIL_RE = re.compile(r"\btatil\w*|\bbayram\w*")
_ETKI_RE = re.compile(r"\betkile\w*|\bhangi\b|\biceren\b|\bolan\b")
_RAMAZAN_RE = re.compile(r"\bramazan\b")
_KURBAN_RE = re.compile(r"\bkurban\b")
_BAYRAM_AD = {"ramazan": "Ramazan Bayramı", "kurban": "Kurban Bayramı"}


def hafta_tatil_sorusu(metin):
    """'Nisan 2024'te hangi haftalar tatilden etkilendi' kalibi: hafta + tatil/bayram + (etki / hangi / iceren / olan)."""
    return bool(_HAFTA_RE.search(metin) and _TATIL_RE.search(metin) and _ETKI_RE.search(metin)
                and not _KARS_RE.search(metin) and not _HAFTALIK_RE.search(metin))


def _tr_takvim(yillar):
    import holidays
    return holidays.Turkey(years=sorted(set(yillar)))


def _aralik_yaz(a, b):
    """date, date -> '8–14 Nisan 2024' ya da '28 Haziran 2023 – 1 Temmuz 2023'."""
    if a == b:
        return f"{a.day} {_AY_TR[a.month]} {a.year}"
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.day}–{b.day} {_AY_TR[a.month]} {a.year}"
    return f"{a.day} {_AY_TR[a.month]} {a.year} – {b.day} {_AY_TR[b.month]} {b.year}"


def _gun_listesi(gunler):
    """[date] -> '10, 11, 12 Nisan 2024' (ayni ay) ya da tam tarihler."""
    if not gunler:
        return ""
    if len({(g.year, g.month) for g in gunler}) == 1:
        return ", ".join(str(g.day) for g in gunler) + f" {_AY_TR[gunler[0].month]} {gunler[0].year}"
    return ", ".join(f"{g.day} {_AY_TR[g.month]} {g.year}" for g in gunler)


def _tatil_gunleri_ozeti(gunler):
    """Haftanin/bayramin tatil gunlerindeki trafik oranlarini tek cumlede ozetler: ortanca, esik alti gun sayisi, her gunun orani
    (hesaplanamayan gun acikca yazilir). Yeni karar kurali yoktur."""
    ol = [g for g in gunler if g.get("oran") is not None]
    gl = ", ".join(f"{_gun(g['gun'])[:5]} " + (f"{g['oran']:.2f}" if g.get("oran") is not None else "hesaplanamadı") for g in gunler)
    if not ol:
        return f"bu günlerin oranı hesaplanamadı ({gl})"
    import statistics
    med = statistics.median(g["oran"] for g in ol)
    dus = [g for g in ol if g["durum"] in ("dusus", "eksik_veri_ve_sapma") and g["oran"] < 1]
    return f"değerlendirilen {len(ol)}/{len(gunler)} günün ortanca oranı {med:.2f}; {len(dus)} gün düşüş eşiğinin altında; günler: {gl}"


def _gun_kaydi(g, ad, kap):
    gs = str(g)
    k = {"gun": gs, "ad": ad, "yuklu": bool(kap(g)), "durum": None, "oran": None}
    if k["yuklu"]:
        try:
            k["durum"], k["oran"] = _gun_orani(gs)
        except Exception:
            pass
    return k


def _tatil_haftalari(state, takvim=None):
    """'Nisan 2024'te hangi haftalar tatilden etkilendi': ayin haftalari (N. hafta = gun (N-1)*7+1 .. N*7, takvim haftasi degil).
    Etkilendi = o haftada takvimde resmi tatil gunu var. Tatil gunlerinin trafik orani ayni tarama kuraliyla (scan.classify) verilir.
    Yeni karar kurali yoktur; nedeni kanitlamaz."""
    a, b = date.fromisoformat(state["start"][:10]), date.fromisoformat(state["end"][:10])
    kap = lambda d: _overlap(COVER["traffic"], d, d)
    if not any(kap(a + timedelta(days=i)) for i in range((b - a).days + 1)):
        return {"sonuc": {"tip": "kapsam_disi", "nedenler": [f"trafik verisi yüklü değil: {a} - {b}", f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    tk = takvim if takvim is not None else _tr_takvim({a.year})
    try:
        ctx = {x["gun"]: [n for n in x["notlar"] if not n.startswith("resmî tatil (")
                          and not (n == "resmî tatil arifesi" and tk.get(date.fromisoformat(x["gun"])))] for x in takvim_notu(a, b)}
    except Exception:
        ctx = {}
    ay_ad = f"{_AY_TR[a.month]} {a.year}"
    haftalar = []
    for n in range(1, 6):
        b1 = (n - 1) * 7 + 1
        if b1 > b.day:
            break
        w1, w2 = date(a.year, a.month, b1), date(a.year, a.month, min(n * 7, b.day))
        gunler = [w1 + timedelta(days=i) for i in range((w2 - w1).days + 1)]
        tatil = [_gun_kaydi(g, tk.get(g), kap) for g in gunler if tk.get(g)]
        baglam = [{"gun": str(g), "notlar": ctx[str(g)]} for g in gunler if ctx.get(str(g))]
        haftalar.append({"hafta": n, "baslangic": str(w1), "bitis": str(w2), "etkilendi": bool(tatil),
                         "yuklu_gun": sum(1 for g in gunler if kap(g)), "tatil_gunleri": tatil, "baglam": baglam})
    etk = [w for w in haftalar if w["etkilendi"]]
    if not etk:
        ozet = (f"{ay_ad}: {len(haftalar)} haftanın hiçbirinde resmî tatil günü yok, hiçbir hafta tatilden etkilenmedi. ")
    else:
        parcalar = []
        for w in etk:
            d1, d2 = date.fromisoformat(w["baslangic"]), date.fromisoformat(w["bitis"])
            adlar = {}
            for g in w["tatil_gunleri"]:
                adlar.setdefault(g["ad"], []).append(date.fromisoformat(g["gun"]))
            tg = "; ".join(f"{ad} ({_gun_listesi(ds)})" for ad, ds in adlar.items())
            yuklu = [g for g in w["tatil_gunleri"] if g["yuklu"]]
            parca = f"{w['hafta']}. hafta ({_aralik_yaz(d1, d2)}): {tg}; " + (_tatil_gunleri_ozeti(yuklu) if yuklu else "tatil günleri için trafik verisi yüklü değil")
            if w["baglam"]:
                parca += " [takvim bağlamı: " + "; ".join(f"{_gun(x['gun'])[:5]} {', '.join(x['notlar'])}" for x in w["baglam"]) + "]"
            parcalar.append(parca)
        ek = {1: "i", 2: "si", 3: "ü", 4: "ü", 5: "i"}[len(etk)]
        ozet = f"{ay_ad}: {len(haftalar)} haftanın {len(etk)}'{ek} resmî tatilden etkilendi. " + " | ".join(parcalar) + ". "
        ets = [w for w in haftalar if not w["etkilendi"]]
        if ets:
            ozet += "Etkilenmeyen haftalar: " + ", ".join(f"{w['hafta']}. ({_aralik_yaz(date.fromisoformat(w['baslangic']), date.fromisoformat(w['bitis']))})" for w in ets) + ": resmî tatil günü yok. "
    ozet += ("Hafta = ayın 1–7, 8–14, … günleri (takvim haftası değildir). 'Etkilendi' yalnız o haftada takvimde resmî tatil günü olması demektir, "
             "trafiğin düştüğünü ya da nedenini kanıtlamaz; her gün kendi önceki 4 haftasıyla kıyaslanır. Nedeni için günü tek gün olarak sor. "
             "Bu bir sayımdır, yeni bir karar kuralı değildir.")
    return {"plan": ["ay_coz", "kapsam_kontrol", "takvim_kontrol", "tatil_haftalari"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "tatil_haftalari": haftalar}}


def _bayram_gunleri(takvim, anahtar, yil):
    """takvim (tarih->ad) icinde yil icin 'ramazan'/'kurban' bayraminin gunleri (sirali date listesi)."""
    ad = tr_lower(_BAYRAM_AD[anahtar])
    return sorted(d for d, n in takvim.items() if d.year == yil and ad in tr_lower(str(n)))


def _bayram_yillari(anahtar, takvim=None):
    """Bayramin gunlerinden en az biri yuklu trafik verisinde olan yillar (veri kapsamindan turetilir)."""
    yl = []
    for y in range(min(s.year for s, e in COVER["traffic"]), max(e.year for s, e in COVER["traffic"]) + 1):
        tk = takvim if takvim is not None else _tr_takvim({y})
        if any(_overlap(COVER["traffic"], d, d) for d in _bayram_gunleri(tk, anahtar, y)):
            yl.append(y)
    return yl


_BAYRAM_KARS_ORNEK = "'2023 Ramazan Bayramı ile Kurban Bayramı karşılaştır'"


def bayram_karsilastirma(metin, takvim=None):
    """'2023 Ramazan Bayrami ile Kurban Bayrami karsilastir' (iki bayram, tek yil) ya da 'Ramazan Bayrami 2023 ile 2024 karsilastir'
    (tek bayram, iki yil). None: bayram karsilastirmasi degil | ('ok', [(anahtar, yil), (anahtar, yil)]) | ('hata', mesaj). Yili tahmin etmez."""
    if not _KARS_RE.search(metin):
        return None
    var = [k for k, rx in (("ramazan", _RAMAZAN_RE), ("kurban", _KURBAN_RE)) if rx.search(metin)]
    if not var:
        return None
    yillar = sorted({int(y) for y in _YIL_RE.findall(metin)})
    if len(var) == 2:
        if len(yillar) == 1:
            return ("ok", [("ramazan", yillar[0]), ("kurban", yillar[0])])
        if not yillar:
            ys = {k: _bayram_yillari(k, takvim) for k in var}
            return ("hata", "Karşılaştırma için yıl gerekli. Yüklü yıllar: Ramazan Bayramı " + (", ".join(map(str, ys["ramazan"])) or "yok")
                    + "; Kurban Bayramı " + (", ".join(map(str, ys["kurban"])) or "yok") + f". Örnek: {_BAYRAM_KARS_ORNEK}. Yılı tahmin etmem.")
        return ("hata", f"Karşılaştırma için iki bayramın aynı yılı gerekli, tek yıl yaz. Örnek: {_BAYRAM_KARS_ORNEK}.")
    k = var[0]
    if len(yillar) == 2:
        return ("ok", [(k, yillar[0]), (k, yillar[1])])
    return ("hata", f"Karşılaştırma için iki bayram ya da aynı bayramın iki yılı gerekli. Örnek: {_BAYRAM_KARS_ORNEK} ya da "
                    f"'{_BAYRAM_AD[k]} 2023 ile 2024 karşılaştır'. Yılı tahmin etmem.")


def _bayram_donemi(takvim, anahtar, yil, kap):
    gunler = _bayram_gunleri(takvim, anahtar, yil)
    if not gunler:
        return None
    kayit = [_gun_kaydi(g, takvim.get(g), kap) for g in gunler]
    ol = [k["oran"] for k in kayit if k["oran"] is not None]
    import statistics
    return {"ad": _BAYRAM_AD[anahtar], "yil": yil, "baslangic": str(gunler[0]), "bitis": str(gunler[-1]),
            "aralik": _aralik_yaz(gunler[0], gunler[-1]), "gun_sayisi": len(gunler),
            "yuklu_gun": sum(1 for k in kayit if k["yuklu"]), "degerlendirilen": len(ol),
            "medyan_oran": round(statistics.median(ol), 2) if ol else None,
            "dusus_gun": sum(1 for k in kayit if k["durum"] == "dusus"), "gunler": kayit}


_BAYRAM_NO2 = None  # testte sahte NO2 vermek icin: {gun: oran}; None ise hava_ozet.bayram_ozeti


def _bayram_no2():
    """{gun: NO2 orani} (yalniz gosterim; veri/modul yoksa {})."""
    try:
        if _BAYRAM_NO2 is not None:
            return dict(_BAYRAM_NO2())
        import hava_ozet
        return {g["gun"]: g["no2_orani"] for g in hava_ozet.bayram_ozeti(COVER)["gunler"] if g.get("no2_orani") is not None}
    except Exception:
        return {}


def _bayram_karsilastir(state, takvim=None):
    """Iki bayrami (ya da ayni bayramin iki yilini) ayni tarama kuraliyla ayri ayri ozetler, tarih araliklariyla yan yana yazar.
    Yeni karar kurali yoktur."""
    kar = bayram_karsilastirma(fold(state["soru"]), takvim)
    if not kar or kar[0] != "ok":
        return {"sonuc": {"tip": "hata", "mesaj": kar[1] if kar else "bayram karşılaştırması anlaşılamadı"}}
    kap = lambda d: _overlap(COVER["traffic"], d, d)
    donemler, yok = [], []
    for anahtar, yil in kar[1]:
        tk = takvim if takvim is not None else _tr_takvim({yil})
        d = _bayram_donemi(tk, anahtar, yil, kap)
        if d is None:
            yok.append(f"{_BAYRAM_AD[anahtar]} {yil}: takvimde bulunamadı")
        elif not d["yuklu_gun"]:
            yok.append(f"{d['ad']} {yil} ({d['aralik']}): trafik verisi yüklü değil")
        else:
            donemler.append(d)
    if yok:
        return {"sonuc": {"tip": "kapsam_disi", "nedenler": yok + [f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    d1, d2 = donemler
    no2 = _bayram_no2()
    import statistics as _st
    for d in donemler:
        for k in d["gunler"]:
            k["no2_orani"] = no2.get(k["gun"])
        nv = [k["no2_orani"] for k in d["gunler"] if k["no2_orani"] is not None]
        d["no2_medyan"] = round(_st.median(nv), 2) if nv else None
        d["no2_gun"] = len(nv)
    ozet = (f"Karşılaştırılan dönemler: {d1['ad']} {d1['yil']} ({d1['aralik']}, {d1['gun_sayisi']} gün) ile "
            f"{d2['ad']} {d2['yil']} ({d2['aralik']}, {d2['gun_sayisi']} gün). ")
    for d in donemler:
        ozet += f"{d['ad']} {d['yil']} ({d['aralik']}): " + _tatil_gunleri_ozeti(d["gunler"]) + ". "
    if d1["medyan_oran"] is not None and d2["medyan_oran"] is not None:
        f = round(abs(d1["medyan_oran"] - d2["medyan_oran"]), 2)
        if f == 0:
            ozet += "İki dönemin ortanca oranı aynı. "
        else:
            dus = d1 if d1["medyan_oran"] < d2["medyan_oran"] else d2
            ozet += f"Ortanca oran farkı: {f:.2f} ({dus['ad']} {dus['yil']} daha düşük). "
    nd = [d for d in donemler if d["no2_medyan"] is not None]
    if nd:
        ozet += ("Hava kalitesi (NO2, normal düzeye göre oran, yalnız ek bilgi): "
                 + "; ".join(f"{d['ad']} {d['yil']} ortanca {d['no2_medyan']:.2f} ({d['no2_gun']}/{d['gun_sayisi']} gün verili)" for d in nd)
                 + ". NO2 sonucu ya da kararı değiştirmez. ")
    ozet += ("Yalnız resmî tatil günleri alındı (arife dahil değil). Her gün kendi önceki 4 haftasının aynı günleriyle kıyaslanır; "
             "iki dönem arasında mutlak trafik farkı ölçülmez. Karşılaştırma yeni bir karar kuralı değildir.")
    return {"plan": ["kapsam_kontrol", "takvim_kontrol", "bayram_karsilastir"],
            "sonuc": {"tip": "analiz", "pencere": f"{d1['baslangic']} 00:00 - {d2['bitis']} 23:00", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "bayram_karsilastirma": donemler}}


def _ay_no2(a, b):
    """Ayin tamaminda NO2'nin normal düzeye orani (air_quality.compare); veri ya da modul yoksa None. YALNIZ GOSTERIM."""
    try:
        import air_quality
        if not air_quality.available():
            return None
        return air_quality.compare(f"{a} 00:00", f"{b} 23:00").get("ratio_no2")
    except Exception:
        return None


def _ay_ozeti(y, m):
    a = date(y, m, 1)
    b = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    r, c = _ay_tara({"start": f"{a} 00:00", "end": f"{b} 23:00"})
    if r is None:
        return None, c
    sirali = sirala_gunler(r["adaylar"], None)
    en = sirali[0] if sirali else None
    return {"ay": c["ay_ad"], "taranan": r["taranan"], "degerlendirilebilen": r["taranan"] - c["dv"], "sapma": c["sapma"],
            "dusus": sum(1 for x in r["adaylar"] if x["durum"] == "dusus"),
            "artis": sum(1 for x in r["adaylar"] if x["durum"] == "artis"),
            "eksik_veri": sum(1 for x in r["adaylar"] if x["durum"] in ("eksik_veri", "eksik_veri_ve_sapma")),
            "en_sapan": {"gun": en["gun"], "oran": en["medyan_oran"], "durum": en["durum"]} if en else None,
            "no2_orani": _ay_no2(a, b),
            "kismi": c["kismi"].strip()}, c


def _karsilastirilan_aylar(state, a, b):
    """Sorudaki ay listesi (2-3, sirali); soru yoksa/anlasilmazsa pencerenin ilk ve son ayi."""
    ak = ay_karsilastirma(fold(state.get("soru") or ""))
    if ak and ak[0] == "ok":
        return list(ak[1:])
    return [(a.year, a.month), (b.year, b.month)]


def _ay_karsilastir(state):
    """Iki ya da uc ayi ayri ayri ayni tarama kuraliyla ozetler, yan yana verir. Yeni karar kurali yoktur."""
    a, b = date.fromisoformat(state["start"][:10]), date.fromisoformat(state["end"][:10])
    aylar = _karsilastirilan_aylar(state, a, b)
    kayit = []
    for y, m in aylar:
        k, c = _ay_ozeti(y, m)
        if k is None:
            return c
        kayit.append(k)
    p = []
    for k in kayit:
        s = (f"{k['ay']}: {k['taranan']} gün tarandı, {k['degerlendirilebilen']} günü değerlendirilebildi; {k['sapma']} sapma günü "
             f"({k['dusus']} düşüş, {k['artis']} artış)")
        if k["en_sapan"]:
            s += f"; en çok sapan gün {_gun(k['en_sapan']['gun'])} (oran {k['en_sapan']['oran']:.2f})"
        p.append(s + (" " + k["kismi"] if k["kismi"] else ""))
    hv = [f"{k['ay']} {k['no2_orani']:.2f}" for k in kayit if k.get("no2_orani") is not None]
    hava = ("; hava kalitesi (NO2) normal düzeye göre oran: " + ", ".join(hv) + " (ek bilgi, sonucu değiştirmez)") if len(hv) == len(kayit) else ""
    ar = [_aralik_yaz(date(y, m, 1), date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)) for y, m in aylar]
    adl = [f"{k['ay']} ({r})" for k, r in zip(kayit, ar)]
    ayl = " ile ".join(adl) if len(adl) == 2 else ", ".join(adl[:-1]) + " ve " + adl[-1]
    ozet = (f"Karşılaştırılan aylar: {ayl}. "
            + "; ".join(p) + hava + ". Yalnız eşiği aşan gün sayıları yan yana verildi; her gün kendi önceki 4 haftasıyla kıyaslanır, "
            "aylar arası mutlak trafik farkı ölçülmez. Karşılaştırma yeni bir karar kuralı değildir.")
    return {"plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "ay_karsilastir"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik", "ay_karsilastirma": kayit}}


def _normal_gun(state):
    """'Bu gun neden normal?': oran, esikler, baseline gunleri ve eksik saat ile aciklar. Yeni karar kurali yoktur:
    scan.classify (ayni esikler) sonucu soylenir; ajan/hipotez calismaz."""
    import scan
    import evidence
    gun = state["start"][:10]
    g = date.fromisoformat(gun)
    if not _overlap(COVER["traffic"], g, g):
        return {"sonuc": {"tip": "kapsam_disi",
                          "nedenler": [f"trafik verisi yüklü değil: {gun}", f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    pencere = f"{state['start']} - {state['end']}"
    ortak = {"tip": "analiz", "pencere": pencere, "hipotezler": {}, "insan_gerekli": False, "nihai_durum": "otomatik"}
    try:
        c = scan._compare(f"{gun} 00:00", f"{gun} 23:00")
    except Exception:
        c = {"error": "hesaplanamadi"}
    plan = ["kapsam_kontrol", "normal_gun_aciklama"]
    if not isinstance(c, dict) or "error" in c:
        return {"plan": plan, "sonuc": {**ortak, "ozet": f"{_gun(gun)}: karşılaştırma hesaplanamadı; normal ya da anormal denemez."}}
    durum, oran = scan.classify(c)
    lo, hi = evidence.LOW, evidence.HIGH
    top, eks = c.get("hours_in_window", 24), c.get("hours_missing", 0)
    base = list(c.get("baseline_days_of_first_hour") or [])
    btk = []
    for b in base:
        try:
            btk += takvim_notu(date.fromisoformat(b), date.fromisoformat(b))
        except Exception:
            pass
    ad = _gun(gun)
    bas = ", ".join(_gun(b) for b in base) if base else "–"
    os_ = f"{oran:.2f}" if oran is not None else None
    if durum == "normal":
        ozet = (f"{ad}: normal gün. Önceki 4 haftanın aynı günlerinin ({bas}) tipik düzeyine göre oran {os_}; eşik aralığı {lo}-{hi} içinde, "
                f"eksik saat {eks}/{top}. Bu yüzden olağandışı sayılmadı. 'Normal', 'sorunsuz' demek değildir: günün genel oranı kısa süreli sapmaları seyreltir.")
    elif durum in ("dusus", "artis"):
        ozet = (f"{ad}: normal değil. Oran {os_}, eşik aralığının ({lo}-{hi}) {'altında' if durum == 'dusus' else 'üstünde'}. "
                f"Nedenini görmek için '{ad} neden {'düştü' if durum == 'dusus' else 'arttı'}' diye sorun.")
    elif durum == "eksik_veri":
        ozet = (f"{ad}: oran {os_} ile eşik aralığında ({lo}-{hi}) ama {eks}/{top} saat eksik (eşik: %{int(evidence.GAP_SHARE * 100)}). "
                "Veri eksik olduğu için bu günü 'normal' diye işaretlemiyorum.")
    elif durum == "eksik_veri_ve_sapma":
        ozet = f"{ad}: oran {os_} eşik aralığı dışında ve {eks}/{top} saat eksik. Normal değil; bir kısmı veri eksikliğinden olabilir."
    elif durum == "veri_yok":
        ozet = f"{ad}: bu gün için trafik verisi yok (tüm saatler eksik); normal ya da anormal denemez."
    else:
        ozet = f"{ad}: karşılaştırma kurulamadı (önceki 4 haftadan en az 3 geçerli hafta gerekir); normal ya da anormal denemez."
    tk = takvim_notu(g, g)
    return {"plan": plan, "sonuc": {**ortak, "ozet": ozet,
            "normal_gun": {"gun": gun, "durum": durum, "oran": oran, "esik_alt": lo, "esik_ust": hi,
                           "eksik_saat": eks, "toplam_saat": top, "baseline_gunleri": base, "baseline_takvim": btk},
            **({"takvim_notu": tk} if tk else {})}}


def _ay_gun_sayisi(a, b):
    return (b - a).days + 1


def _gun_listesi_ham(a, b):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def _donem_ozeti(gunler, kap, ad=None):
    """Gun listesi -> {aralik, gun_sayisi, yuklu_gun, degerlendirilen, medyan_oran, dusus_gun, gunler}. Ayni tarama kurali (scan.classify)."""
    import statistics
    kayit = [_gun_kaydi(g, None, kap) for g in gunler]
    ol = [k["oran"] for k in kayit if k["oran"] is not None]
    return {"ad": ad, "baslangic": str(gunler[0]), "bitis": str(gunler[-1]), "aralik": _aralik_yaz(gunler[0], gunler[-1]),
            "gun_sayisi": len(gunler), "yuklu_gun": sum(1 for k in kayit if k["yuklu"]), "degerlendirilen": len(ol),
            "medyan_oran": round(statistics.median(ol), 2) if ol else None,
            "dusus_gun": sum(1 for k in kayit if k["durum"] == "dusus"), "gunler": kayit}


def _oran_txt(d):
    if not d["degerlendirilen"]:
        return "trafik oranı hesaplanamadı"
    return f"değerlendirilen {d['degerlendirilen']}/{d['gun_sayisi']} günün ortanca oranı {d['medyan_oran']:.2f}; {d['dusus_gun']} gün düşüş eşiğinin altında"


def _gun_siralama(state):
    """'Hangi gun en cok dustu / artti': aylik taramanin adaylari, sirala_gunler ile (yeni karar kurali yok)."""
    r, c = _ay_tara(state)
    if r is None:
        return c
    metin = fold(state["soru"])
    yon = {"dusus": "dusus", "artis": "artis"}.get(siralama_sorusu(metin))
    n = siralama_sayisi(metin)
    sirali = sirala_gunler(r["adaylar"], yon)[:n]
    yon_tr = {"dusus": "düşen", "artis": "artan", None: "en çok sapan"}[yon]
    liste = [{"gun": g["gun"], "oran": g["medyan_oran"], "durum": g["durum"], "eksik_saat": g.get("eksik_saat"), "toplam_saat": g.get("toplam_saat")} for g in sirali]
    on = f"{c['ay_ad']}: {c['kapsam_txt']}."
    if liste:
        ozet = (f"{on} En çok {yon_tr} ilk {len(liste)} gün (oranın 1'den sapmasına göre): "
                + "; ".join(f"{_gun(x['gun'])} (oran {x['oran']:.2f})" for x in liste) + ".")
    else:
        ozet = f"{on} {yon_tr.capitalize() if yon else 'Sapan'} yönünde eşiği aşan gün yok."
    ozet += (c["kismi"] + " Yalnız eşiği aşan günler sıralanır; oran her günün kendi önceki 4 haftasının aynı günlerine göredir. "
             "Bir günün nedenini görmek için o günü tek gün olarak sor. Bu bir sıralamadır, yeni bir karar kuralı değildir.")
    return {"plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "gun_siralama"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik",
                      "gun_siralama": {"yon": yon, "gunler": liste, "aday_sayisi": c["sapma"]}, "tarama": r}}


def _eksik_veri_say(state):
    """'Nisan 2024'te kac gun eksik veri vardi': taramadaki eksik_veri / eksik_veri_ve_sapma / veri_yok gunlerini sayar ve listeler."""
    r, c = _ay_tara(state)
    if r is None:
        return c
    try:
        import evidence
        pay = int(evidence.GAP_SHARE * 100)
    except Exception:
        pay = 25
    kod = {"eksik_veri": "eksik veri", "eksik_veri_ve_sapma": "eksik veri ve sapma", "veri_yok": "veri yok"}
    gunler = [{"gun": x["gun"], "durum": x["durum"], "eksik_saat": x.get("eksik_saat"), "toplam_saat": x.get("toplam_saat")}
              for x in r["adaylar"] if x["durum"] in kod]
    a, b = date.fromisoformat(state["start"][:10]), date.fromisoformat(state["end"][:10])
    yuklu_degil = _ay_gun_sayisi(a, b) - len(c["kapsamli"])
    say = {k: sum(1 for x in gunler if x["durum"] == k) for k in kod}
    if gunler:
        ozet = (f"{c['ay_ad']}: {c['kapsam_txt']}. Eksik veri bulunan gün sayısı: {len(gunler)} "
                f"({say['eksik_veri']} eksik veri, {say['eksik_veri_ve_sapma']} eksik veri ve sapma, {say['veri_yok']} veri yok). Günler: "
                + "; ".join(f"{_gun(x['gun'])} ({x['eksik_saat']}/{x['toplam_saat']} saat eksik)" if x["durum"] != "veri_yok" else f"{_gun(x['gun'])} (veri yok)"
                            for x in gunler) + ".")
    else:
        ozet = f"{c['ay_ad']}: {c['kapsam_txt']}. Eksik veri eşiğini (günün saatlerinin %{pay}'i) aşan gün yok."
    if yuklu_degil:
        ozet += f" Ayın {yuklu_degil} günü için trafik verisi hiç yüklü değil (bu günler sayıma girmez)."
    ozet += (f" Yalnız eksik saat payı %{pay}'i aşan günler (ve hiç verisi olmayan günler) eksik veri sayılır; diğer günlerdeki küçük boşluklar sayılmaz."
             " Bu bir sayımdır, yeni bir karar kuralı değildir.")
    return {"plan": ["ay_coz", "kapsam_kontrol", "gun_gun_tarama", "eksik_veri_say"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik",
                      "eksik_veri_gunleri": {"sayi": len(gunler), "esik_pay": pay, "yuklu_olmayan_gun": yuklu_degil, "gunler": gunler}, "tarama": r}}


def _hafta_ici_sonu(state, takvim=None):
    """Ayin hafta ici ve hafta sonu gunlerinin trafik oranlari (her gun kendi onceki 4 haftasina gore). Resmi tatil gunleri disarida tutulur."""
    a, b = date.fromisoformat(state["start"][:10]), date.fromisoformat(state["end"][:10])
    kap = lambda d: _overlap(COVER["traffic"], d, d)
    if not any(kap(g) for g in _gun_listesi_ham(a, b)):
        return {"sonuc": {"tip": "kapsam_disi", "nedenler": [f"trafik verisi yüklü değil: {a} - {b}", f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    tk = takvim if takvim is not None else _tr_takvim({a.year})
    tum = _gun_listesi_ham(a, b)
    haric = [g for g in tum if tk.get(g)]
    hi = [g for g in tum if g.weekday() < 5 and not tk.get(g)]
    hs = [g for g in tum if g.weekday() >= 5 and not tk.get(g)]
    ay_ad = f"{_AY_TR[a.month]} {a.year}"
    if not hi or not hs:
        return {"sonuc": {"tip": "kapsam_disi", "nedenler": [f"{ay_ad}: hafta içi ya da hafta sonu günü kalmadı"]}}
    dh, ds = _donem_ozeti(hi, kap, "Hafta içi"), _donem_ozeti(hs, kap, "Hafta sonu")
    ozet = f"{ay_ad}: hafta içi ile hafta sonu karşılaştırıldı. Hafta içi ({dh['gun_sayisi']} gün): {_oran_txt(dh)}. Hafta sonu ({ds['gun_sayisi']} gün): {_oran_txt(ds)}. "
    if dh["medyan_oran"] is not None and ds["medyan_oran"] is not None:
        f = round(abs(dh["medyan_oran"] - ds["medyan_oran"]), 2)
        ozet += "İki grubun ortanca oranı aynı. " if f == 0 else f"Ortanca oran farkı: {f:.2f} ({(dh if dh['medyan_oran'] < ds['medyan_oran'] else ds)['ad']} daha düşük). "
    if haric:
        ozet += "Resmî tatil olduğu için dışarıda tutulan günler: " + _gun_listesi(haric) + ". "
    ozet += ("Her gün kendi önceki 4 haftasının aynı günüyle kıyaslanır; bu yüzden hafta içi ile hafta sonunun mutlak trafik düzeyi değil, "
             "kendi normaline göre durumu karşılaştırılır. Yeni bir karar kuralı değildir.")
    return {"plan": ["ay_coz", "kapsam_kontrol", "takvim_kontrol", "hafta_ici_sonu"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik",
                      "hafta_ici_sonu": {"hafta_ici": dh, "hafta_sonu": ds, "haric_tatil": [str(g) for g in haric]}}}


BAYRAM_PENCERE = 7  # bayramdan once/sonra bakilan gun sayisi


def bayram_cevresi(metin, takvim=None):
    """'Ramazan Bayrami 2023 oncesi ve sonrasi trafik nasil': ('ok', anahtar, yil, bayram_gunleri) | ('hata', mesaj). Yili tahmin etmez."""
    var = [k for k, rx in (("ramazan", _RAMAZAN_RE), ("kurban", _KURBAN_RE)) if rx.search(metin)]
    yillar = sorted({int(y) for y in _YIL_RE.findall(metin)})
    ys = lambda k: ", ".join(map(str, _bayram_yillari(k, takvim))) or "yok"
    ornek = "'Ramazan Bayramı 2023 öncesi ve sonrası trafik nasıl'"
    if len(var) != 1:
        return ("hata", f"Bayram öncesi/sonrası için hangi bayram olduğu gerekli (Ramazan ya da Kurban). Yüklü yıllar: Ramazan Bayramı {ys('ramazan')}; "
                        f"Kurban Bayramı {ys('kurban')}. Örnek: {ornek}.")
    k = var[0]
    if len(yillar) != 1:
        return ("hata", f"Bayram öncesi/sonrası için tek bir yıl gerekli. {_BAYRAM_AD[k]} için yüklü yıllar: {ys(k)}. Örnek: {ornek}. Yılı tahmin etmem.")
    tk = takvim if takvim is not None else _tr_takvim({yillar[0]})
    g = _bayram_gunleri(tk, k, yillar[0])
    if not g:
        return ("hata", f"Bayram öncesi/sonrası için {_BAYRAM_AD[k]} {yillar[0]} takvimde bulunamadı. Yüklü yıllar: {ys(k)}.")
    return ("ok", k, yillar[0], g)


def _bayram_oncesi_sonrasi(state, takvim=None):
    """Bayramdan onceki 7 gun, bayram gunleri ve sonraki 7 gun: ayni tarama kuraliyla ayri ayri ozetlenir (yeni karar kurali yok)."""
    bc = bayram_cevresi(fold(state["soru"]), takvim)
    if bc[0] != "ok":
        return {"sonuc": {"tip": "hata", "mesaj": bc[1]}}
    k, yil, bg = bc[1], bc[2], bc[3]
    kap = lambda d: _overlap(COVER["traffic"], d, d)
    oncesi = [bg[0] - timedelta(days=i) for i in range(BAYRAM_PENCERE, 0, -1)]
    sonrasi = [bg[-1] + timedelta(days=i) for i in range(1, BAYRAM_PENCERE + 1)]
    if not any(kap(g) for g in oncesi + bg + sonrasi):
        return {"sonuc": {"tip": "kapsam_disi", "nedenler": [f"{_BAYRAM_AD[k]} {yil} çevresi için trafik verisi yüklü değil",
                                                             f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    tk = takvim if takvim is not None else _tr_takvim({yil})
    donemler = [_donem_ozeti(oncesi, kap, "Bayram öncesi"), _donem_ozeti(bg, kap, "Bayram"), _donem_ozeti(sonrasi, kap, "Bayram sonrası")]
    ozet = f"{_BAYRAM_AD[k]} {yil} çevresi: "
    ozet += "; ".join(f"{d['ad']} ({d['aralik']}): {_oran_txt(d)}" if d["yuklu_gun"] else f"{d['ad']} ({d['aralik']}): trafik verisi yüklü değil" for d in donemler) + ". "
    d0, d1, d2 = donemler
    if None not in (d0["medyan_oran"], d1["medyan_oran"], d2["medyan_oran"]):
        ozet += f"Ortanca oran: öncesi {d0['medyan_oran']:.2f}, bayram {d1['medyan_oran']:.2f}, sonrası {d2['medyan_oran']:.2f}. "
    diger = [g for g in oncesi + sonrasi if tk.get(g)]
    if diger:
        ozet += "Bu pencerelerde başka resmî tatil günü de var: " + _gun_listesi(diger) + ". "
    ozet += (f"Bayramdan önceki ve sonraki {BAYRAM_PENCERE} gün alındı (hafta sonları ve arife dahil). Her gün kendi önceki 4 haftasının aynı günüyle kıyaslanır; "
             "mutlak trafik düzeyi ölçülmez. Yeni bir karar kuralı değildir.")
    return {"plan": ["kapsam_kontrol", "takvim_kontrol", "bayram_oncesi_sonrasi"],
            "sonuc": {"tip": "analiz", "pencere": f"{oncesi[0]} 00:00 - {sonrasi[-1]} 23:00", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik",
                      "bayram_cevresi": {"ad": _BAYRAM_AD[k], "yil": yil, "oncesi": d0, "bayram": d1, "sonrasi": d2}}}


def _normal_hafta(state):
    """'Bu hafta neden normaldi': gun gun oran ve esikler (tek gun 'neden normal' yolunun hafta surumu). Yeni karar kurali yoktur."""
    import evidence
    a, b = date.fromisoformat(state["start"][:10]), date.fromisoformat(state["end"][:10])
    kap = lambda d: _overlap(COVER["traffic"], d, d)
    gunler = _gun_listesi_ham(a, b)
    if not any(kap(g) for g in gunler):
        return {"sonuc": {"tip": "kapsam_disi", "nedenler": [f"trafik verisi yüklü değil: {a} - {b}", f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    lo, hi = evidence.LOW, evidence.HIGH
    d = _donem_ozeti(gunler, kap)
    kay = d["gunler"]
    yuklu = [k for k in kay if k["yuklu"]]
    normal = [k for k in yuklu if k["durum"] == "normal"]
    disi = [k for k in yuklu if k["durum"] != "normal"]
    ar = _aralik_yaz(a, b)
    gl = ", ".join(f"{_gun(k['gun'])[:5]} " + (f"{k['oran']:.2f}" if k["oran"] is not None else "hesaplanamadı") for k in kay if k["yuklu"])
    if yuklu and not disi:
        ozet = (f"{ar}: yüklü {len(yuklu)} günün hepsi normal; her günün oranı kendi önceki 4 haftasına göre eşik aralığı {lo}-{hi} içinde "
                f"(ortanca oran {d['medyan_oran']:.2f}). Günler: {gl}. 'Normal', 'sorunsuz' demek değildir: günün genel oranı kısa süreli sapmaları seyreltir.")
    else:
        ozet = (f"{ar}: yüklü {len(yuklu)} günden {len(normal)} gün normal, {len(disi)} gün normal değil ya da değerlendirilemedi. "
                + "Eşik dışı/yetersiz günler: " + ", ".join(f"{_gun(k['gun'])[:5]} ({_DURUM_TR.get(k['durum'], k['durum'] or 'hesaplanamadı')}"
                                                            + (f", oran {k['oran']:.2f}" if k["oran"] is not None else "") + ")" for k in disi)
                + f". Eşik aralığı {lo}-{hi}. Günler: {gl}. Bu hafta tamamen normal denemez; bir günün nedenini görmek için o günü tek gün olarak sor.")
    if len(yuklu) < len(gunler):
        ozet += f" Penceredeki {len(gunler) - len(yuklu)} gün için trafik verisi yüklü değil."
    return {"plan": ["kapsam_kontrol", "hafta_normal_aciklama"],
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": ozet, "hipotezler": {},
                      "insan_gerekli": False, "nihai_durum": "otomatik",
                      "normal_hafta": {"baslangic": str(a), "bitis": str(b), "esik_alt": lo, "esik_ust": hi, "normal_gun": len(normal),
                                       "yuklu_gun": len(yuklu), "donem": d}}}


def analiz(state: State):
    onek, secim = "", None
    pl = state.get("plan", [])
    for adim, fn in (("bayram_oncesi_sonrasi", _bayram_oncesi_sonrasi), ("hafta_ici_sonu", _hafta_ici_sonu), ("eksik_veri_say", _eksik_veri_say),
                     ("gun_siralama", _gun_siralama), ("hafta_normal_aciklama", _normal_hafta)):
        if adim in pl:
            return fn(state)
    if "normal_gun_aciklama" in state.get("plan", []):
        return _normal_gun(state)
    if "gun_karsilastir" in state.get("plan", []):
        return _gun_karsilastir(state)
    if "bayram_karsilastir" in state.get("plan", []):
        return _bayram_karsilastir(state)
    if "tatil_haftalari" in state.get("plan", []):
        return _tatil_haftalari(state)
    if "hava_birlikte_ozet" in state.get("plan", []):
        return _ay_hava_birlikte(state)
    if "bayram_hava_ozet" in state.get("plan", []):
        return _bayram_hava(state)
    if "saatlik_iliski_ozet" in state.get("plan", []):
        return _saatlik_iliski(state)
    if "gun_profil_ozet" in state.get("plan", []):
        return _gun_profil(state)
    if "tespit_ozet" in state.get("plan", []):
        return _tespit(state)
    if "hava_iliski_ozet" in state.get("plan", []):
        return _hava_iliski(state)
    if "ay_karsilastir" in state.get("plan", []):
        return _ay_karsilastir(state)
    if "ay_coz" in state.get("plan", []) and "en_sapmali_gun" not in state["plan"]:
        return _ay_var(state, haftalik="haftalik_ozet" in state["plan"])
    if "en_sapmali_gun" in state.get("plan", []):
        s = _ay_sec(state)
        if "sonuc" in s:
            return s
        state = {**state, "start": s["start"], "end": s["end"]}
        onek, secim = s["onek"], s["secim"]
    a, b = date.fromisoformat(state["start"][:10]), date.fromisoformat(state["end"][:10])
    if (b - a).days + 1 > MAX_GUN:
        return {"sonuc": {"tip": "kapsam_disi", "nedenler": [f"en fazla {MAX_GUN} günlük pencere analiz edilir"]}}
    disi = [str(a + timedelta(days=i)) for i in range((b - a).days + 1)
            if not _overlap(COVER["traffic"], a + timedelta(days=i), a + timedelta(days=i))]
    if disi:
        return {"sonuc": {"tip": "kapsam_disi",
                          "nedenler": [f"trafik verisi yüklü değil: {', '.join(disi)}", f"Yüklü trafik dönemleri: {yuklu_donemler()}"]}}
    if (b - a).days >= 1 and varlik_sorusu_mu(state["soru"]):
        import scan  # 'var miydi' sorusu: gun gun tarama (neden aramaz, aday gun listeler)
        r = scan.scan(str(a), str(b))
        yapilmayan = ("araclari_cagir", "hipotezleri_puanla", "rapor")  # tarama yolunda calismaz: plan gercegi yazsin
        return {"plan": [a for a in state["plan"] if a not in yapilmayan] + ["gun_gun_tarama"],
                "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}", "ozet": tarama_ozeti(r),
                          "hipotezler": {}, "insan_gerekli": False, "nihai_durum": "otomatik", "tarama": r}}
    import api  # mevcut ajan + HITL (/analyze ile ayni kod yolu)
    kar = list(state.get("kararlar") or [])
    body = {"start": state["start"], "end": state["end"]}
    if len(kar) > 0:
        body["karar"] = kar[0]
    if len(kar) > 1:
        body["karar2"] = kar[1]
    code, obj = api.analyze(body)
    if code != 200:
        return {"sonuc": {"tip": "hata", "mesaj": obj.get("hata", str(obj))}}
    tk = takvim_notu(a, b)
    es = ek_sinyal(a, b)
    if obj.get("durum") == "insan_onayi_bekleniyor":
        return {"plan": state["plan"] + ["insan_onayi_bekleniyor"] + (["ek_sinyal_hava_kalitesi"] if es else []),
                "sonuc": {"tip": "bekliyor", "soru": obj["soru"], **({"secim": secim} if secim else {}),
                          **({"takvim_notu": tk} if tk else {}), **({"ek_sinyal": es} if es else {})}}
    rep = obj["rapor"]
    ac = _llm_aciklama(rep)
    return {"plan": state["plan"] + (["insan_onayi"] if kar else []) + (["aciklama_yaz"] if ac else []) + (["ek_sinyal_hava_kalitesi"] if es else []),
            "sonuc": {"tip": "analiz", "pencere": f"{state['start']} - {state['end']}",
                      "ozet": onek + rep["summary_tr"],
                      "hipotezler": {h["name"]: h["status"] for h in rep["hypotheses"]},
                      "insan_gerekli": bool(rep.get("needs_human")),
                      "nihai_durum": rep.get("nihai_durum"),
                      **({"secim": secim} if secim else {}),
                      **({"takvim_notu": tk} if tk else {}),
                      **({"ek_sinyal": es} if es else {}),
                      **({"aciklama": ac} if ac else {})}}


builder = StateGraph(State)
for ad, fn in (("planla", planla_ana), ("bilgi", bilgi), ("eksik", eksik), ("analiz", analiz)):
    builder.add_node(ad, fn)
builder.add_edge(START, "planla")
builder.add_conditional_edges("planla", yonlendir,
                              {"bilgi": "bilgi", "eksik": "eksik", "analiz": "analiz"})
for ad in ("bilgi", "eksik", "analiz"):
    builder.add_edge(ad, END)
app = builder.compile()
