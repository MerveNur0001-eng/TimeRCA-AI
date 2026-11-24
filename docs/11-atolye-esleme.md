# 11 - Atölye Kazanımları ve Proje Eşlemesi (BTK, 25 Ekim - 22 Kasım 2026)

Durum: Tamam = projede çalışıyor ve test/kanıt var. Kısmen = yapıldı ama sınırlı. Yok = yapılmadı.

| Gün | Kazanım | Projede nerede | Durum |
|---|---|---|---|
| 2-3 | Yerel model, embedding, anlamsal benzerlik | Ollama qwen2.5:3b, embeddinggemma | Tamam |
| 3 | Yapılandırılmış çıktı | Pydantic ile doğrulanan JSON rapor | Tamam |
| 3 | Prompt injection riski, hassas veri | Araç çıktısı ve kullanıcı metni veri olarak ele alınır; arayüz DOM metin düğümü kullanır; yerel model, dış LLM servisine veri gitmez | Tamam |
| 3 | Üretken yapay zekâyı insan kontrolüyle kullanma | HITL: Onayla / Ek inceleme / Reddet; LLM yalnızca açıklama üretir, karar kuralda | Tamam |
| 4 | Lokal LLM kurma ve programatik kullanma | Ollama, Python çağrıları; tool calling testi 10 vakanın 9'u | Tamam |
| 4 | Unit test, hata giderme | tests/run_all.py kapıları (final_check, agent_test, reliability_test, selection_test, scan_test, series_real_test vb.) | Tamam |
| 4 | Prompt Engineering, RAG, fine-tuning karşılaştırması | Prompt engineering ve RAG ölçüldü (qwen2.5:3b serbest cevapta 7 sorunun 2'sinde bilgi tabanıyla çelişti; RAG ile kaynaklı not döndürmek bu riski kaldırdı). Fine-tuning DENENMEDİ; gerekçeli karşılaştırma aşağıda | Kısmen |
| 5 | Chunking, metadata, embedding, vektör veri tabanı, similarity search, metadata filtering | kb/*.md 59 parça, satır bazlı parçalayıcı (line-v1), embeddinggemma, Chroma; tool_notes(arac) metadata ile seçim | Tamam |
| 6 | Retrieve, Rerank, Generate | Retrieve ve Generate var (kaynaklı not, LLM serbest cevap üretmez). Rerank: kural tabanlı (cosine + kelime örtüşmesi, deterministik) yazıldı, birim testli (17/17) ve ölçüldü (tests/rag_rerank_olc.py, 23 Kasım). dev2 cevapli 20 soruda ilk sonuç 14→16, MRR 0,804→0,850; final cevapli 14 soruda ilk sonuç 11→11, MRR 0,893→0,881 (2 sorunun sırası değişti). Önceden yazılmış kabul ölçütü (hiçbir ölçüte gerileme olmaması) sağlanmadı, bu yüzden varsayılan KAPALI kaldı (TIMERCA_RERANK=1 ile açılır). Örneklem küçük; fark kesin sayılmaz | Kısmen |
| 6 | Kaynaklı cevap, halüsinasyon azaltma, çıktı doğrulama | İlgili not kaynak dosyasıyla döner; doğrulayıcı reddederse kural metni kullanılır; qwen2.5:3b serbest cevapta 7 sorunun 2'sinde KB ile çelişti, bu yüzden serbest cevap yok | Tamam |
| 6 | RAG kalitesini değerlendirme | eval/rag_final.jsonl, 24 soru (docs/09 bölüm 5.1); eşik "cevap yok"u ayırt edemez (AUC 0,80), bilinen zayıflık | Tamam |
| 6 | RAG güvenlik riskleri | KB içeriği ve araç metni veri olarak ele alınır, talimat sayılmaz | Tamam |
| 7 | Görev planlama, koşullu karar | İki aşamalı araç seçimi (evidence.context_plan), karışık durum, insana sor / ek inceleme dalları | Tamam |
| 7 | LangGraph Node, State, Edge, Conditional Routing | src/agent.py (toplama, hipotez, not, insana sor, ek inceleme, rapor), src/router_graph.py | Tamam |
| 7 | MCP | src/mcp_server.py, mcp_client.py, tools_gw.py; mcp_test eşdeğerlik testleri; MCP hata verirse doğrudan çağrıya düşer | Tamam |
| 7 | Tool calling ve retry | Tool calling var. Retry: her araç çağrısı en çok 3 kez denenir, aralar 0,5 sn ve 1 sn bekleme (src/agent.py `_retry`); her hata ve toparlanma logs/agent_log.jsonl'e yazılır (tool_error, retry_ok, tool_failed). Kalıcı hatada süreç çökmez, aracın çıktısı "error" alanıyla döner ve diğer araçlar etkilenmez. Ayrıca MCP -> doğrudan çağrı geri dönüşü (fallback) var. Test: tests/agent_robust_test.py (geçici hata 3. denemede toparlanır, kalıcı hata süreci çökertmez) | Tamam |
| 7 | Human-in-the-loop | LangGraph interrupt/Command; durumsuz API'de karar ile yeniden koşu | Tamam |
| 8 | n8n otomasyonu, dış sistem entegrasyonu | docs/n8n-akisi.json (12 düğüm), /ask ve /feedback uçları. Ek inceleme yolu 20 Kasım'da, ret kolu 23 Kasım'da n8n içinde denendi: 08.04.2024 penceresi, "Reddet" seçildi, ret formu (iddia: tatil/bayram) dolduruldu, GERİ BİLDİRİM adımı /feedback'ten kayıt döndürdü (kanıt durumu kanit_yok, sonuç sonuc_korundu); test kaydı sonra silindi | Tamam |
| 8 | Hata yönetimi, loglama, izleme | logs/agent_log.jsonl, logs/mcp_calls.jsonl, logs/etl_log.jsonl; API hata kodları (400/401/413/500) | Tamam |
| 8 | Agent güvenliği | İsteğe bağlı X-API-Key, gövde sınırı, girdi doğrulama, araç çıktısı veri olarak | Tamam |
| 9-10 | Uçtan uca çözüm, farklı senaryolarla test | Gerçek veri, v0-v3 değerlendirme, keşif koşuları, demo senaryoları (docs/demo) | Tamam |
| 10 | Çıktıyı değerlendirme, iyileştirme yönlerini belirleme | docs/07 ve docs/09 bilinen sınırlar, v4 adayları | Tamam |

Boşluklar (dürüstçe): Rerank (yazıldı ve ölçüldü; kabul ölçütü sağlanmadığı için kapalı), fine-tuning karşılaştırması (denenmedi, gerekçesi aşağıda).

## Fine-tuning: denenmedi, neden RAG (gerekçeli karşılaştırma, deney değildir)
- Proje bilgisi küçük ve sık değişen bir bilgi tabanı (10 dosya, 59 parça) ve gerçek veriyle sınanan kurallardır; RAG bu bilgiyi kaynak göstererek verir, fine-tuning bilgiyi model ağırlıklarına gömer ve kaynak gösteremez.
- Fine-tuning için etiketli eğitim verisi gerekir; projedeki etiketli pencere sayısı çok azdır (v3'te 57) ve bunlar değerlendirme için ayrıldı. Bu kadar veriyle ince ayar fazla uyum (overfitting) riski taşır.
- Karar zaten kuralda verilir; dil modeli yalnızca soru anlar ve doğrulamalı açıklama yazar. İnce ayar, kararın kalitesini değil yalnızca açıklama üslubunu etkilerdi.
- Yerel donanımda (Ollama, küçük model) ince ayar ayrıca GPU ve süre gerektirir; teslim takvimine sığmadı. Bu nedenle deney yapılmadı ve bir sonuç iddia edilmiyor.
