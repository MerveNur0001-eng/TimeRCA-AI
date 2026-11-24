"""RAG v2: Chroma + embeddinggemma (Ollama).

Degismeyenler (olcumleri bozmamak icin): parca kimligi dosya#n, embedding metin bicimleri (fq, fd), cosine uzakligi.
Yeni: bayat indeks kontrolu, anlasilir Ollama hatalari, tur/arac metadata, kapsam entegrasyonu (answer_context).
"""
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "kb"
DB = ROOT / "data" / "processed" / "chroma"
META = ROOT / "data" / "processed" / "index_meta.json"
MODEL = "embeddinggemma"
HOST = "http://localhost:11434"
COLLECTION = "timerca_kb"
CHUNKER = "line-v1"
SCOPE_FILE = "kapsam_ve_sinirlar.md"
OFF_TOPIC_DIST = 0.70  # yaklasik karar: yalnizca belirgin konu disi sorulari ayirir
RELATED_LABEL = "ilgili not (doğrudan cevap olmayabilir)"

TUR = {"trafik_veri_sozlugu.md": "veri_sozlugu", "veri_kalitesi_kurallari.md": "veri_kalitesi",
       "gecmis_vakalar.md": "vaka", "kapsam_ve_sinirlar.md": "kapsam"}
ARAC = {"deprem_araci.md": "get_earthquakes", "etl_araci.md": "check_etl_log",
        "hava_durumu_araci.md": "get_weather", "resmi_tatil_bilgileri.md": "get_calendar",
        "baseline_araci.md": "compare_same_weekday_history"}


class RagError(RuntimeError):
    """Kullaniciya gosterilebilir RAG hatasi (Turkce mesaj)."""


def fq(q):
    return f"task: search result | query: {q}"


def fd(title, text):
    return f"title: {title} | text: {text}"


def embed(texts):
    body = json.dumps({"model": MODEL, "input": texts}).encode("utf-8")
    req = urllib.request.Request(HOST + "/api/embed", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RagError(f"Ollama '{MODEL}' modelini bulamadı. Çalıştır: ollama pull {MODEL}") from e
        raise RagError(f"Ollama HTTP {e.code} hatası verdi.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RagError(f"Ollama yanıt vermiyor ({HOST}). Başka bir pencerede 'ollama serve' çalıştırıp tekrar dene.") from e
    v = np.array(data["embeddings"], dtype=float)
    return (v / np.linalg.norm(v, axis=1, keepdims=True)).tolist()


def chunks():
    out = []
    for p in sorted(KB.glob("*.md")):
        lines = [l.strip() for l in p.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
        title = lines[0].lstrip("# ").strip()
        for i, l in enumerate(lines[1:], 1):
            out.append({"id": f"{p.name}#{i}", "file": p.name, "title": title, "text": l.lstrip("- ").strip(),
                        "tur": TUR.get(p.name, "arac" if p.name in ARAC else "diger"),
                        "arac": ARAC.get(p.name, "")})
    return out


def fingerprint():
    """KB icerigi (satir sonu ve BOM'dan bagimsiz) + model + parcalayici surumu."""
    h = hashlib.sha256(f"{MODEL}|{CHUNKER}".encode("utf-8"))
    for c in chunks():
        h.update(json.dumps([c["id"], c["title"], c["text"]], ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


def _make(client):
    try:
        return client.get_or_create_collection(COLLECTION, configuration={"hnsw": {"space": "cosine"}})
    except Exception:
        return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def build_index():
    cs = chunks()
    vecs = embed([fd(c["title"], c["text"]) for c in cs])  # once embedding: hata olursa eski indeks bozulmaz
    client = chromadb.PersistentClient(path=str(DB))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = _make(client)
    col.add(ids=[c["id"] for c in cs], embeddings=vecs, documents=[c["text"] for c in cs],
            metadatas=[{"file": c["file"], "title": c["title"], "tur": c["tur"], "arac": c["arac"]} for c in cs])
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps({"fingerprint": fingerprint(), "n": len(cs), "model": MODEL, "chunker": CHUNKER,
                                "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")
    return len(cs)


def index_status():
    try:
        col = chromadb.PersistentClient(path=str(DB)).get_collection(COLLECTION)
        n = col.count()
    except Exception:
        return {"ok": False, "reason": "indeks yok"}
    try:
        meta = json.loads(META.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "reason": "indeks bilgi dosyası yok"}
    cur = chunks()
    if n != len(cur):
        return {"ok": False, "reason": f"parça sayısı farklı (indeks {n}, KB {len(cur)})"}
    if meta.get("fingerprint") != fingerprint():
        return {"ok": False, "reason": "KB, model veya parçalayıcı indeks kurulduktan sonra değişmiş"}
    return {"ok": True, "reason": "güncel", "n": n}


def _collection(auto_rebuild=False):
    st = index_status()
    if not st["ok"]:
        if auto_rebuild:
            build_index()
        else:
            raise RagError(f"İndeks güncel değil ({st['reason']}). Çalıştır: python src\\rag.py --build")
    return chromadb.PersistentClient(path=str(DB)).get_collection(COLLECTION)


# --- Yeniden siralama (rerank): kural tabanli, deterministik, LLM yok ---------------------------
# Varsayilan KAPALI. Acmak icin: TIMERCA_RERANK=1. Olcum: python tests\rag_rerank_olc.py
# Skor = (1 - cosine uzakligi) + RERANK_W * kelime ortusmesi. Ortusme, sorudaki anlamli kelimelerin
# (ilk 5 harf, Turkce ek farklarini yumusatmak icin) parcada ne kadarinin gectigidir.
RERANK_ADAY = 8
RERANK_W = 0.15
_DURAK = {"nedir", "midir", "mıdır", "mudur", "müdür", "hangi", "nasıl", "nasil", "neden", "kaç", "kac", "için", "icin",
          "gibi", "olan", "olarak", "veya", "ile", "bir", "bu", "şu", "mi", "mı", "mu", "mü", "var", "yok", "ne", "da", "de"}


def rerank_acik():
    return os.environ.get("TIMERCA_RERANK", "0").strip() == "1"


def _kok(metin):
    t = str(metin).replace("İ", "i").replace("I", "ı").lower()
    out = set()
    for w in re.findall(r"[0-9a-zçğıöşü_]+", t):
        if w not in _DURAK and (len(w) >= 3 or w.isdigit()):
            out.add(w[:5])
    return out


def rerank_hits(question, hits, w=RERANK_W):
    """Adaylari (cosine + w * kelime ortusmesi) skoruyla yeniden siralar. Esitlikte cosine'i kucuk olan once gelir.
    cos_distance DEGISMEZ (konu disi karari bu degerle verilir); yalniz sira ve 'rank' alani guncellenir."""
    q = _kok(question)
    skorlu = []
    for h in hits:
        ortusme = (len(q & _kok(h["text"] + " " + h.get("title", ""))) / len(q)) if q else 0.0
        skorlu.append(((1.0 - h["cos_distance"]) + w * ortusme, -h["cos_distance"], h["id"], h))
    skorlu.sort(key=lambda x: (-x[0], -x[1], x[2]))
    out = []
    for i, (_, _, _, h) in enumerate(skorlu):
        d = dict(h)
        d["rank"] = i + 1
        out.append(d)
    return out


def _nearest(hits):
    return min(h["cos_distance"] for h in hits)


def retrieve(question, k=3, auto_rebuild=False, exclude_scope=False, rerank=None):
    col = _collection(auto_rebuild)
    kw = {"where": {"file": {"$ne": SCOPE_FILE}}} if exclude_scope else {}
    rr = rerank_acik() if rerank is None else bool(rerank)
    n = max(k, RERANK_ADAY) if rr else k
    r = col.query(query_embeddings=embed([fq(question)]), n_results=n, **kw)
    hits = [{"rank": i + 1, "id": cid, "file": m["file"], "title": m["title"], "tur": m.get("tur", ""),
             "arac": m.get("arac", ""), "text": d, "cos_distance": round(float(dist), 3)}
            for i, (cid, d, m, dist) in enumerate(zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]))]
    if not rr or not hits:
        return hits
    en_yakin = _nearest(hits)  # konu disi karari, yeniden siralamadan etkilenmesin diye tum adaylardan alinir
    hits = rerank_hits(question, hits)[:k]
    for h in hits:
        h["aday_en_yakin"] = en_yakin
    return hits


def scope_text():
    return (KB / SCOPE_FILE).read_text(encoding="utf-8-sig")


def retrieve_context(question, k=3):
    """Eski arayuz (rag_answer_test.py icin)."""
    hits = retrieve(question, k, exclude_scope=True)
    return {"off_topic": hits[0].get("aday_en_yakin", hits[0]["cos_distance"]) > OFF_TOPIC_DIST, "hits": hits, "scope": scope_text()}


def answer_context(question, k=3, auto_rebuild=False):
    """Ajanin kullanacagi giris. LLM yok: kural + getirme.
    status: out_of_scope | off_topic | ok. 'ok' ilgili not demektir, dogrudan cevap garantisi degildir."""
    from scope import check_scope
    sc = check_scope(question)
    base = {"question": question, "reasons": sc["reasons"], "notes": sc["notes"]}
    if sc["status"] == "out":
        return {**base, "status": "out_of_scope", "hits": [], "scope_note": scope_text()}
    hits = retrieve(question, k, auto_rebuild, exclude_scope=True)
    nearest = hits[0].get("aday_en_yakin", hits[0]["cos_distance"])
    if nearest > OFF_TOPIC_DIST:
        return {**base, "status": "off_topic", "hits": [], "nearest_distance": nearest}
    for h in hits:
        h["label"] = RELATED_LABEL
    return {**base, "status": "ok", "hits": hits, "scope_note": scope_text()}


TOOL_NAMES = tuple(sorted(set(ARAC.values())))
TOOL_NOTE_LABEL = "araç yorumlama notu"
# Hipotez -> o hipotezi kanitlayan araclar (ajan akisi icin sabit esleme)
HYP_TOOLS = {"veri_hatasi": ["check_etl_log", "compare_same_weekday_history"],
             "hava": ["get_weather"], "tatil": ["get_calendar"],
             "deprem": ["get_earthquakes"], "aciklanamayan": ["compare_same_weekday_history"]}


def tool_notes(tool, auto_rebuild=False):
    """Bir aracin yorumlama ve sinir notlari. Metadata ile secilir: embedding yok, Ollama kapaliyken de calisir."""
    if tool not in TOOL_NAMES:
        raise RagError(f"Bilinmeyen araç: {tool}. Geçerli araçlar: {', '.join(TOOL_NAMES)}")
    col = _collection(auto_rebuild)
    d = col.get(where={"arac": tool}, include=["documents", "metadatas"])
    rows = sorted(zip(d["ids"], d["documents"], d["metadatas"]),
                  key=lambda x: (x[2]["file"], int(x[0].split("#")[1])))
    return [{"id": i, "file": m["file"], "title": m["title"], "tur": m.get("tur", ""), "arac": m["arac"],
             "text": t, "label": TOOL_NOTE_LABEL} for i, t, m in rows]


def notes_for_tools(tools_used, auto_rebuild=False):
    """Calisan araclarin notlari, tekrarsiz, arac sirasini koruyarak."""
    seen, out = set(), []
    for tool in tools_used:
        for n in tool_notes(tool, auto_rebuild):
            if n["id"] not in seen:
                seen.add(n["id"])
                out.append(n)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        if "--build" in sys.argv:
            print("indekslenen parca:", build_index())
        elif "--status" in sys.argv:
            print(index_status())
        elif "--ask" in sys.argv:
            q = " ".join(sys.argv[sys.argv.index("--ask") + 1:])
            print(json.dumps(answer_context(q), ensure_ascii=False, indent=2))
        else:
            print("kullanim: python src\\rag.py --build | --status | --ask <soru>")
    except RagError as e:
        print("HATA:", e)
        sys.exit(1)
