"""Soru-cevap. Kullanım:  python src\ask.py   (etkileşimli)   veya   python src\ask.py "soru"
Boş satır çıkış yapar. Ajan insan onayı isterse karar sorulur."""
import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from router_graph import app

VALID = ("onayla", "ek_inceleme", "reddet")


def run(soru):
    kararlar = []
    while True:
        o = app.invoke({"soru": soru, "istek_tipi": "", "start": None, "end": None,
                        "plan": [], "sonuc": {}, "kararlar": kararlar})
        s = o["sonuc"]
        if s["tip"] == "bekliyor" and len(kararlar) < 2:
            print("\n[ajan insan onayı istiyor]")
            q = s["soru"]
            print(q if isinstance(q, str) else json.dumps(q, ensure_ascii=False, indent=2))
            while True:
                k = input(f"Karar ({' / '.join(VALID)}): ").strip().lower()
                if k in VALID:
                    break
            kararlar.append(k)
            continue
        break
    print(f"\n[yol: {o['istek_tipi']}] plan: {' > '.join(o['plan'])}")
    t = s["tip"]
    if t == "bilgi":
        print("durum:", s["durum"])
        for n in s["nedenler"]:
            print("neden:", n)
        for n in s["notlar"]:
            print(f"- ({n['id']}) {n['metin']}\n    [{n['etiket']}]")
    elif t == "analiz":
        print("pencere:", s["pencere"])
        print("özet:", s["ozet"])
        print("hipotezler:", s["hipotezler"])
        print("insan incelemesi gerekli:", s["insan_gerekli"], "| nihai durum:", s.get("nihai_durum"))
    elif t == "eksik":
        print(s["mesaj"])
    elif t == "hata":
        print("hata:", s["mesaj"])
    elif t == "bekliyor":
        print("ajan ikiden fazla karar istedi, durduruldu:", s["soru"])
    else:
        for n in s["nedenler"]:
            print("kapsam dışı:", n)


if len(sys.argv) > 1:
    run(" ".join(sys.argv[1:]))
else:
    while True:
        q = input("\nSoru> ").strip()
        if not q:
            break
        run(q)
