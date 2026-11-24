"""Cevap katmani v1: kod karar verir, LLM yalnizca dogrulanabilirse kullanilir.

answer(soru, use_llm=False) -> {"status", "mode", "answer", "sources", "hits", "reasons", "llm_reject"}
mode: refused | extractive | llm_validated
"""
import json, re, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rag
from scope import tr_lower

MODEL = "qwen2.5:3b"
MONTHS = ("ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos",
          "eylül", "ekim", "kasım", "aralık")
NUM = re.compile(r"\d+(?:[.,]\d+)?")
MON = re.compile(r"\b(" + "|".join(MONTHS) + ")")

SYSTEM = ("You answer questions about an Istanbul traffic root cause analysis project. "
          "Use ONLY the notes provided, each marked with an [id]. "
          "Reply with a single JSON object: {\"cevap_var\": true or false, \"cevap\": \"...\", \"kaynaklar\": [\"id\", ...]}. "
          "cevap is Turkish, at most two sentences, and copies numbers, months and dates exactly as written in the notes. "
          "kaynaklar lists only the ids of the notes you used. "
          "If the notes do not directly answer the question, set cevap_var to false, cevap to an empty string and kaynaklar to an empty list. "
          "Never use outside knowledge.")


def _facts(text):
    t = tr_lower(text)
    return {n.replace(".", ",") for n in NUM.findall(t)} | set(MON.findall(t))


def _llm(question, hits):
    notes = "\n".join(f"[{h['id']}] {h['text']}" for h in hits)
    body = {"model": MODEL, "stream": False, "format": "json", "keep_alive": "10m",
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 300},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": f"NOTLAR:\n{notes}\n\nSORU: {question}"}]}
    req = urllib.request.Request(rag.HOST + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(json.load(r)["message"]["content"])


def validate(j, hits, question):
    """(gecerli_mi, neden). Sayi ve ay adlari kontrol edilir, mantik hatasi kontrol EDILMEZ."""
    if not isinstance(j, dict) or j.get("cevap_var") is not True:
        return False, "model cevap yok dedi"
    ans = str(j.get("cevap") or "").strip()
    cites = j.get("kaynaklar")
    if not ans:
        return False, "bos cevap"
    if not isinstance(cites, list) or not cites:
        return False, "kaynak yok"
    notes = {h["id"]: h["text"] for h in hits}
    cites = [str(c) for c in cites]
    if any(c not in notes for c in cites):
        return False, "kaynak getirilen notlar arasinda degil"
    allowed = _facts(" ".join(notes[c] for c in cites) + " " + question)
    extra = _facts(ans) - allowed
    if extra:
        return False, f"atif yapilan notta olmayan sayi/ay: {sorted(extra)}"
    return True, ""


def answer(question, use_llm=False, k=3):
    r = rag.answer_context(question, k=k)
    st = r["status"]
    base = {"status": st, "hits": r["hits"], "reasons": r["reasons"], "llm_reject": None}
    if st == "out_of_scope":
        return {**base, "mode": "refused", "sources": [],
                "answer": "Bu soru veri kapsamının dışında: " + "; ".join(r["reasons"])}
    if st == "off_topic":
        return {**base, "mode": "refused", "sources": [],
                "answer": "Bu soru projenin konusu dışında görünüyor."}
    hits = r["hits"]
    if use_llm:
        try:
            j = _llm(question, hits)
            ok, why = validate(j, hits, question)
        except Exception as e:
            ok, why, j = False, f"LLM hatası: {str(e)[:80]}", None
        if ok:
            return {**base, "mode": "llm_validated", "answer": j["cevap"].strip(),
                    "sources": [str(c) for c in j["kaynaklar"]]}
        base["llm_reject"] = why
    text = "İlgili notlar (doğrudan cevap olmayabilir):\n" + "\n".join(f"- [{h['id']}] {h['text']}" for h in hits)
    return {**base, "mode": "extractive", "answer": text, "sources": [h["id"] for h in hits]}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = [a for a in sys.argv[1:] if a != "--llm"]
    try:
        res = answer(" ".join(args), use_llm="--llm" in sys.argv)
    except rag.RagError as e:
        print("HATA:", e)
        sys.exit(1)
    print(f"[{res['mode']}] {res['answer']}")
    print("kaynaklar:", res["sources"], "| llm_reject:", res["llm_reject"])
