# -*- coding: utf-8 -*-
"""Takvim baglami (KANIT, karar kurali degil): yarim gun, idari izin, okul tatili.
Her kayitta kaynak var; kaynaksiz tarih eklenmez."""

_COTT = "https://cottgroup.com/en/legislation/item/2023-resmi-tatil-gunleri-ve-mesai-hesaplama"
_EKON = "https://www.ekonomist.com.tr/haberler/2024-resmi-tatil-takvimi-ramazan-bayrami-tatilinde-pazartesi-detayi-46660"
_M2223 = "https://www.turkedebiyati.org/2022-2023-meb-calisma-is-gunu-takvimi/"
_M2324A = "https://kirklareli.meb.gov.tr/meb_iys_dosyalar/2023_08/18101216_2023-2024_CalYYma_Takvimi.pdf"
_M2324B = "https://www.takvim.com.tr/egitim/1-donem-ilk-ara-tatil-ne-zaman-basliyor-2023-2024-meb-ara-tatil-tarihleri-kasim-ayi-ara-tatili-somestr-yariyil-ikinci-donem-5652062"
_M2324C = "https://www.yenisafak.com/okullar-ne-zaman-acilacak-15-tatil-ayin-kacinda-bitiyor-ara-tatil-uzatildi-mi-kac-gun-surecek-meb-son-dakika-aciklamalar-h-4598091"
_M2425 = "https://www.cnnturk.com/turkiye/okullar-ne-zaman-acilacak-bugun-mu-2023-meb-ilkokullar-ortaokullar-ve-liseler-ne-zaman-acilacak-2036075"

_CAPITAL = "https://www.capital.com.tr/haberler/tum-haberler/idari-yazisi-gonderildi-kamuda-bayram-tatili-9-gun"

HALF_DAYS = {
    "2023-04-20": ("Ramazan Bayram\u0131 arifesi", "13:00 sonras\u0131 yar\u0131m g\u00fcn resm\u00ee tatil", _COTT),
    "2023-06-27": ("Kurban Bayram\u0131 arifesi", "yar\u0131m g\u00fcn", _COTT),
    "2024-04-09": ("Ramazan Bayram\u0131 arifesi", "yar\u0131m g\u00fcn mesai", _EKON),
}

ADMIN_LEAVE = {
    "2024-04-08": ("Ramazan Bayram\u0131 \u00f6ncesi idari izin (kamu \u00e7al\u0131\u015fanlar\u0131, tam g\u00fcn)", _CAPITAL),
    "2024-04-09": ("Ramazan Bayram\u0131 \u00f6ncesi idari izin (kamu \u00e7al\u0131\u015fanlar\u0131, yar\u0131m g\u00fcn)", _CAPITAL),
    "2023-06-26": ("Kurban Bayram\u0131 \u00f6ncesi idari izin (kamu \u00e7al\u0131\u015fanlar\u0131)", _COTT),
    "2023-06-27": ("Kurban Bayram\u0131 \u00f6ncesi idari izin (kamu \u00e7al\u0131\u015fanlar\u0131)", _COTT),
}

SCHOOL_COVER = ("2023-03-01", "2024-09-08")
SCHOOL_BREAKS = [
    ("2023-04-17", "2023-04-20", "II. d\u00f6nem ara tatili (2022-2023)", _M2223),
    ("2023-06-17", "2023-09-10", "yaz tatili", _M2223),
    ("2023-11-13", "2023-11-17", "I. d\u00f6nem ara tatili (2023-2024)", _M2324A),
    ("2024-01-22", "2024-02-02", "y\u0131ar\u0131y\u0131l tatili (2023-2024)".replace("y\u0131ar\u0131y\u0131l", "yar\u0131y\u0131l"), _M2324B),
    ("2024-04-08", "2024-04-12", "II. d\u00f6nem ara tatili (2023-2024)", _M2324C),
    ("2024-06-15", "2024-09-08", "yaz tatili", _M2425),
]

LIMITS = ("Resm\u00ee tatil/bayram (holidays paketi) art\u0131 elle derlenen, kaynakl\u0131 k\u00fc\u00e7\u00fck tablo: "
          "2023-2024 aras\u0131 yar\u0131m g\u00fcn (arife), idari izin ve MEB ulusal \u00e7al\u0131\u015fma takvimi. "
          "Tabloda olmayan g\u00fcn 'yok' demek de\u011fildir. okul='ders' yaln\u0131z takvimde tatil kayd\u0131 olmad\u0131\u011f\u0131n\u0131 "
          "g\u00f6sterir; il/il\u00e7e kapan\u0131\u015flar\u0131 (kar vb.) ve \u0130stanbul il takvimi fark\u0131 yok say\u0131lm\u0131\u015ft\u0131r. "
          "Se\u00e7im g\u00fcn\u00fc, ma\u00e7, konser, yol \u00e7al\u0131\u015fmas\u0131 yok. Bu alanlar kan\u0131tt\u0131r, karar kural\u0131nda kullan\u0131lmaz.")


def day_context(ds, weekday, is_holiday):
    h = HALF_DAYS.get(ds)
    a = ADMIN_LEAVE.get(ds)
    out = {
        "half_day": h[0] if h else None,
        "half_day_note": (h[1] + " | kaynak: " + h[2]) if h else None,
        "admin_leave": bool(a),
        "admin_leave_note": (a[0] + " | kaynak: " + a[1]) if a else None,
    }
    school, note = "bilinmiyor", None
    if SCHOOL_COVER[0] <= ds <= SCHOOL_COVER[1]:
        brk = next((b for b in SCHOOL_BREAKS if b[0] <= ds <= b[1]), None)
        if weekday >= 5:
            school = "hafta_sonu"
        elif is_holiday:
            school = "resmi_tatil"
        elif brk:
            school, note = "tatil", brk[2] + " | kaynak: " + brk[3]
        else:
            school = "ders"
    out["school"] = school
    out["school_note"] = note
    return out
