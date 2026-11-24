# TimeRCA-AI

İstanbul trafiğindeki ani düşüş ve artışları bulan, **nedenini kanıtla araştıran** yerel bir yapay zekâ ajanı.

Örnek: "22 Nisan 2023 trafik neden düştü?" sorusuna sistem şöyle yanıt verir: o gün trafik normalin %74'ündeydi, o gün Ramazan Bayramı'ydı, hava ve deprem açıklamıyor, veri hatası yok. Kanıt yetmezse uydurmaz: "açıklanamayan" der ve **insana sorar**.

- Veri: İBB Açık Veri Portalı saatlik trafik yoğunluğu (gerçek veri, 18 ay: 2021-12 ... 2024-04).
- Karar kural tabanlıdır ve her zaman aynı sonucu verir. Yerel dil modeli (Ollama, `gemma3:4b`) karar vermez; yalnızca soruyu anlamaya ve doğrulanmış bir açıklama yazmaya yardım eder.
- Her şey kendi bilgisayarında çalışır: bulut yapay zekâ servisi ve API anahtarı gerekmez.

## İçindekiler
1. [Hızlı başlangıç](#hızlı-başlangıç)
2. [Gereksinimler](#gereksinimler)
3. [Kurulum (adım adım)](#kurulum-adım-adım)
4. [Kullanım](#kullanım)
5. [Sorun giderme](#sorun-giderme)
6. [Nasıl çalışır](#nasıl-çalışır)
7. [Veri](#veri)
8. [Proje yapısı](#proje-yapısı)
9. [Bilgi tabanı (RAG)](#bilgi-tabanı-rag)
10. [Testler ve değerlendirme](#testler-ve-değerlendirme)
11. [Sürdürülebilir şehir çerçevesi](#sürdürülebilir-şehir-çerçevesi)
12. [Bilinen sınırlar](#bilinen-sınırlar)
13. [Kaynaklar ve lisans](#kaynaklar-ve-lisans)

## Hızlı başlangıç
Windows PowerShell, proje klasöründe. Ollama kurulu ve çalışıyor olmalı (bkz. Gereksinimler).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --no-deps -r requirements.lock.txt
ollama pull gemma3:4b
ollama pull embeddinggemma
python src\rag.py --build
python src\api.py
```
Sonra tarayıcıda **http://127.0.0.1:8000** adresini açın. Veri depoda hazır gelir, ayrıca veri indirmek gerekmez.

## Çalışması için gerekenler
Uygulamayı çalıştırmak için yalnızca şu parçalar gerekir: `src/`, `kb/`, `data/` (küçük veri dosyaları), `logs/etl_log.jsonl`, `requirements.lock.txt` ve bu `README.md`. `tests/`, `scripts/`, `eval/`, `docs/`, `deney_llm/` ve `notebooks/` klasörleri çalıştırmak için **gerekli değildir**; bu depoda yoksa aşağıdaki "isteğe bağlı" adımları ve bu klasörlere yapılan göndermeleri atlayabilirsiniz.

## Gereksinimler
| Gereksinim | Not |
|---|---|
| İşletim sistemi | Windows 10/11 ve PowerShell. Proje bu ortamda geliştirildi ve test edildi. Linux/macOS denenmedi (kod yolları taşınabilir yazıldı; komutlardaki `\` yerine `/`, etkinleştirme için `source .venv/bin/activate` gerekir; `requirements.lock.txt` içindeki `pywin32` yalnız Windows'ta kurulur, diğer sistemlerde o satırı silin). |
| Python | **3.12** (geliştirme sürümü 3.12.1) |
| Ollama | https://ollama.com adresinden kurulur; arka planda çalışıyor olmalı (`http://localhost:11434`) |
| Modeller | `gemma3:4b` (~3 GB, soru anlama ve açıklama) ve `embeddinggemma` (~0,6 GB, bilgi tabanı araması) |
| Bellek ve disk | En az 8 GB RAM önerilir; modeller ve paketler için ~6 GB boş disk |
| İnternet | Yalnızca kurulumda (paketler, modeller). Çalışırken gerekmez; hava, tatil, deprem ve trafik verisi depoda hazırdır |
| Node.js | İsteğe bağlı; yalnız arayüz testleri (`tests\*.js`) için |

## Kurulum (adım adım)
**1. Projeyi indirin.** ZIP olarak indirip bir klasöre çıkarın ya da `git clone` ile alın. PowerShell'de proje klasörüne girin:
```powershell
cd C:\...\TimeRCA-AI
```

**2. Python ortamını kurun.**
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --no-deps -r requirements.lock.txt
```
`Activate.ps1` "betik çalıştırma devre dışı" hatası verirse bu pencerede bir kez şunu çalıştırın: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. Satır başında `(.venv)` görünmelidir.

`--no-deps` bilerek kullanılır: `requirements.lock.txt` tüm paketleri (alt bağımlılıklar dahil) tek tek sürümleriyle içerir. Bu yüzden pip'in bağımlılık çözümlemesi gerekmez; çözümleme, birbirine zıt sürüm aralıkları isteyen iki paket yüzünden (`holidays` ve `kubernetes`, `python-dateutil` için) kurulumu yanlışlıkla engelleyebilir.

**3. Ollama ve modeller.** Ollama'yı kurun, açık olduğundan emin olun (görev çubuğunda simgesi görünür), sonra:
```powershell
ollama pull gemma3:4b
ollama pull embeddinggemma
```
Kontrol: `ollama list` iki modeli de göstermeli.

**4. Bilgi tabanı indeksini oluşturun** (bir kez, ~1 dakika). İndeks git'te olmadığı için her yeni kurulumda yapılır:
```powershell
python src\rag.py --build
```
Çıktının sonunda `indekslenen parca: 59` yazmalı. Kontrol: `python src\rag.py --status`.

**5. Sunucuyu başlatın.**
```powershell
python src\api.py
```
Pencere açık kalmalıdır (kapatınca sunucu durur). Tarayıcıda http://127.0.0.1:8000 adresini açın. İlk soru modelleri belleğe yüklediği için 1-2 dakika sürebilir, sonrakiler daha hızlıdır.

**6. Kurulumu doğrulayın (isteğe bağlı; `tests/` klasörü gerekir).** Sunucu açıkken ikinci bir PowerShell penceresinde (ortam etkin, proje klasöründe):
```powershell
python tests\e2e_final.py --hepsi
```
Beklenen son satır: `=== OZET: 26/26 PASS ===`. Bu test tüm test paketini de çalıştırır, birkaç dakika sürer. Not: yalnızca `git calisma agaci temiz` kontrolü, klasörde dosya değiştirdiyseniz başarısız olur.

## Kullanım
### Arayüz
Sayfanın üstündeki "Nasıl kullanılır?" kutusu kısa özeti verir. Ana bölümler:
- **Trafik yoğunluğu (grafik):** tarih aralığı seçip "Göster"e basın. Günlük (oran) ya da saatlik görünüm. Gri şerit veri bulunmayan saatleri, renkli bölgeler normalin dışındaki saatleri gösterir.
- **1. Anomali taraması:** aralıktaki günleri tarar, sapma olanları listeler.
- **2. Pencere incelemesi:** seçtiğiniz tarih-saat aralığını inceler; hipotezleri (veri hatası, hava, tatil, deprem, açıklanamayan) kanıtla değerlendirir.
- **3. İnsan onayı / 4. Ret nedeni:** kanıt yetersizse sistem karar vermez, size sorar: Onayla, Ek inceleme iste ya da Reddet. Reddederseniz iddianız aynı araçlarla sınanır ve kaydedilir.
- **Soru ve kaynak arama:** Türkçe bir soru yazın. Örnekler: `22 Nisan 2023 trafik neden düştü`, `Nisan 2024'te anomali var mıydı`, `Nisan 2024'te hangi haftalar tatilden etkilendi`, `2023 Ramazan Bayramı ile Kurban Bayramı karşılaştır`, `Nisan 2024'te hangi gün en çok düştü`, `Nisan 2024'te kaç gün eksik veri vardı`, `Nisan 2024'te hafta içi ile hafta sonu karşılaştır`, `Ramazan Bayramı 2023 öncesi ve sonrası trafik nasıl`, `Şubat Mart Nisan 2024 karşılaştır`, `8-14 Nisan 2024 neden normaldi`, `Nisan 2024'te trafik düşen kaç günde NO2 de düştü?`, `Bayramlarda trafik ve NO2 ne kadar düşüyor?`, `Trafik ile NO2 ilişkisi nedir?`, `10 Mart ile 17 Mart 2024 karşılaştır`, `Bayramlarda trafik ne kadar düşüyor?`. Hazır örnek düğmeleri de vardır.

Sonuç kartında şunlar görünür: normale göre oran (1,00 = normal; 0,85'in altı düşük, 1,15'in üstü yüksek), hipotezlerin durumu, **Takvim notu** (resmî tatil), **Ek sinyal: hava kalitesi** (trafik değişimini hava kirliliğiyle karşılaştıran ek ipucu; kararı değiştirmez), izlenen adımlar ve ham araç çıktısı. Tek günlük sonuçta **Saatlik trafik ve NO2 eğrilerini üst üste göster** düğmesi vardır. Sonuç Markdown olarak indirilebilir.

Sistem yalnızca **yüklü 18 ayı** inceler: 2021-12, 2022-01, 2022-10, 2022-11, 2023-01 ... 2023-09, 2023-11, 2023-12, 2024-01, 2024-03, 2024-04 (2022-12 ve 2023-10 gibi boşluklar vardır). Başka bir tarih sorarsanız "kapsam dışı" der ve yüklü dönemleri söyler; neden uydurmaz.

### API
Sunucu çalışırken (varsayılan `127.0.0.1:8000`):
```powershell
# Serbest soru
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ask -ContentType "application/json" `
  -Body '{"soru":"22 Nisan 2023 trafik neden düştü"}'

# Belirli pencere
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analyze -ContentType "application/json" `
  -Body '{"start":"2023-04-22 00:00","end":"2023-04-22 23:00"}'
```
Uç noktalar: `GET /` (arayüz), `/health`, `/ornekler`; `POST /ask`, `/analyze`, `/scan`, `/series`, `/feedback`. Başka port için `python src\api.py --port 8080`. İsteğe bağlı koruma: `TIMERCA_API_KEY` ortam değişkeni tanımlanırsa istekler anahtar ister.

### MCP sunucusu
Araçlar standart bir MCP sunucusu olarak da sunulur (stdio, yani standart girdi/çıktı üzerinden): `python src\mcp_server.py`. 5 hipotez aracı (veri yükleme kaydı, geçmiş karşılaştırma, hava, tatil, deprem) ve hipotez puanına girmeyen 1 ek kanıt aracı (hava kalitesi) vardır. Ajan araçları varsayılan olarak bu sunucu üzerinden çağırır (kendiliğinden başlatılır). Doğrudan çağrı için `TIMERCA_TOOLS=direct`.

### n8n ile insan onayı (isteğe bağlı)
İnsan onayı akışının n8n sürümü `docs/n8n-akisi.json` dosyasındadır; API'ye `http://host.docker.internal:8000` üzerinden bağlanır. Arayüz ve n8n akışı aynı anda çalıştırılmamalıdır (analiz istekleri sıralanır, aynı anda tek analiz çalışır).

### Ortam değişkenleri (hepsi isteğe bağlı)
| Değişken | Etkisi |
|---|---|
| `TIMERCA_ACIKLAMA_LLM=0` | Sunucuda tek gün analizine LLM açıklaması eklenmesini kapatır (varsayılan açık) |
| `TIMERCA_SORU_LLM=0` | Kuralın çözemediği sorular için LLM yedek yolunu kapatır |
| `TIMERCA_TOOLS=direct` | Araçları MCP yerine doğrudan çağırır |
| `TIMERCA_RERANK=1` | Bilgi tabanı aramasında kural tabanlı yeniden sıralamayı açar (varsayılan kapalı; ölçüm: `python tests\rag_rerank_olc.py`) |
| `TIMERCA_API_KEY` | API için anahtar zorunlu kılar |

PowerShell'de: `$env:TIMERCA_SORU_LLM="0"`, sonra `python src\api.py`.

## Sorun giderme
| Belirti | Çözüm |
|---|---|
| `ConnectionRefused` / Ollama'ya bağlanılamadı | Ollama açık değil. Uygulamayı başlatın, `ollama list` ile kontrol edin |
| `python src\rag.py --build` model bulunamadı der | `ollama pull embeddinggemma` çalıştır |
| "Bayat indeks" / bilgi tabanı hatası | `python src\rag.py --build` ile indeksi yeniden oluştur (Ollama açık olmalı) |
| `Activate.ps1` çalışmıyor | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `pip install` hata verir (pywin32 vb.) | Windows ve Python 3.12 kullandığınızdan emin olun; Windows dışında `pywin32` satırını silin |
| 8000 portu dolu | Eski sunucu penceresini kapat ya da `python src\api.py --port 8001` |
| İlk soru çok yavaş | Normal: model bellekte değil. Tek gün analizi 30-70 sn sürebilir; sorular tek tek sorulmalı |
| "Kapsam dışı" yanıtı | Sorduğun tarih yüklü 18 ayda yok; sistem yüklü dönemleri söyler |
| Açıklamada "kural metni; LLM çıktısı doğrulamayı geçmedi" | Beklenen güvenlik davranışı: dil modelinin yazdığı açıklama sayı/tarih doğrulamasını geçemezse kural metni gösterilir; karar değişmez |
| Ek sinyal kutusu görünmüyor | Trafik normalse hava sinyali üretilmez; bu hata değil |

## Nasıl çalışır
1. Pencere seçilir (başlangıç, bitiş). Karar kuralı pencere medyanını önceki 4 haftanın aynı gün-saati medyanıyla karşılaştırır (en az 3 geçerli hafta gerekir). Oran 0,85'in altı düşüş, 1,15'in üstü artıştır.
2. Araçlar (deterministik Python) kanıt toplar: veri yükleme (ETL) kaydı, geçmiş karşılaştırma, hava (Open-Meteo), resmî tatil (`holidays`), deprem (USGS yerel katalog).
3. Hipotezler: veri hatası, hava, tatil/bayram, deprem, açıklanamayan. Karar kuralda verilir; yerel LLM (`gemma3:4b`) yalnızca doğrulamalı açıklama yazar ve kuralın çözemediği soruları anlamaya yardım eder.
4. Güven düşükse ajan insana sorar (onayla, ek_inceleme, reddet).
5. Çıktı: Pydantic ile doğrulanan JSON rapor; her hipotez için kaynak araç, bilgi tabanından kaynaklı notlar ve ham araç çıktıları.

**Ek sinyaller** (hava kalitesi, resmî tatil notu) yalnızca gösterim içindir; hipotez puanını ve kararı değiştirmez (testle sabit). Kural: **kanıt yoksa neden uydurulmaz.**

## Veri
Uygulamanın çalışması için gereken küçük dosyalar depoda hazırdır (~2 MB):
- `data/processed/hourly_YYYY-MM.parquet`: 18 ayın saatlik toplam araç sayısı (İBB verisinden üretilmiş).
- `data/processed/weather_*.parquet`: saatlik yağış, rüzgâr, sıcaklık (Open-Meteo, tek nokta).
- `data/raw/usgs_quakes.csv`: deprem kataloğu (USGS, M≥4).
- `data/processed/aqi_hourly.csv`: saatlik NO2/PM10/O3 şehir medyanı (İBB Hava Kalitesi).
- `logs/etl_log.jsonl`: veri yükleme (ETL) kaydı; hangi saatlerin kaynakta eksik olduğunu söyler.

İBB'nin aylık ham CSV dosyaları (toplam ~2 GB) depoda yoktur. Aşağıdaki adımlar yalnızca veriyi sıfırdan üretmek isteyenler içindir ve `scripts/` klasörü gerekir:
```powershell
# 1) Aylık CSV'yi İBB portalından indirin, data\raw\traffic_YYYY-MM.csv olarak kaydedin
#    https://data.ibb.gov.tr/dataset/hourly-traffic-density-data-set
# 2) Saatlik seriye çevir ve veri yükleme (ETL) kaydını yaz
python scripts\veri\ingest.py --month 2023-04
# 3) Bağlam verileri (hava, deprem) ve hava kalitesi (internet gerekir)
python scripts\veri\fetch_more.py
python scripts\veri\fetch_hava_kalitesi.py --ay 2023-04
```
Yeni bir ayı sisteme tanıtmak için `src/tools.py` içindeki `MONTHS` listesine eklemek de gerekir. Veri ayrıntıları ve keşif bulguları `docs/03-veri.md` dosyasındadır (varsa).

## Proje yapısı
```
src/        çekirdek uygulama (api, router_graph, agent, evidence, tools, rag, scan, series, air_quality ...) ve ui/index.html
tests/      testler ve doğrulama betikleri (run_all, e2e_final, final_check, kb_check, rag_* testleri)
scripts/
  veri/     veri çekme ve hazırlama (ingest, fetch_*, make_scope_kb)
  olcum/    ölçüm, değerlendirme, etiketleme (eval_*, *_olc, rag_eval, toolcall_*)
  kesif/    keşif ve hata ayıklama (probe, debug, profil çıkarma)
kb/         bilgi tabanı (RAG kaynağı, 10 dosya)
eval/       ölçüm çıktıları ve etiket dosyaları
docs/       proje belgeleri (01-15); örnek çıktılar docs/demo/
deney_llm/  LLM model karşılaştırma deneyi
logs/       koşu kayıtları (bir kısmı git dışı)
data/       saatlik seri, hava, deprem, hava kalitesi; ham CSV git dışı
```
Tüm komutlar proje kökünden çalıştırılır. `tests/`, `scripts/`, `eval/`, `docs/`, `deney_llm/` geliştirme ve değerlendirme içindir; GitHub'da olmayabilir, uygulama bunlar olmadan çalışır.

Önemli dosyalar:
- `src/api.py`: HTTP API ve arayüz sunucusu (Python standart kütüphanesi `http.server`).
- `src/ui/index.html`: tek dosya arayüz; saf HTML, CSS ve JavaScript, dış kütüphane ve internet gerekmez; grafikler elle çizilen SVG.
- `src/router_graph.py`: soru kutusu yönlendiricisi (LangGraph). Önce kural çalışır (tarih/aralık/hafta/ay çözme, karşılaştırma, bayram karşılaştırması, bayram öncesi/sonrası, tatilden etkilenen haftalar, hafta içi/sonu, en çok düşen gün, eksik veri sayımı, haftalık özet, normal gün ve normal hafta açıklaması); çözemezse doğrulamalı LLM yedek yolu (`src/soru_llm.py`).
- `src/agent.py` (LangGraph): araçları toplar, hipotezleri `src/evidence.py` kurallarıyla puanlar, güven düşükse insana sorar (HITL), rapor üretir. `src/scan.py` gün gün tarama, `src/series.py` grafik verisi, `src/llm_explain.py` doğrulamalı açıklama yazarı.
- `src/tools.py`, `src/mcp_server.py`, `src/mcp_client.py`: araçlar ve MCP sunucusu (standart girdi/çıktı üzerinden, stdio).
- `src/air_quality.py`: hava kalitesi ek sinyali (trafik ile NO2/PM10 çapraz kontrolü).
- `src/rag.py` ve `kb/`: bilgi tabanı.

## Bilgi tabanı (RAG)
- Kaynak: `kb/*.md` (her biri bir araç, kural ya da sınır notu). Parçalama (`line-v1`): dosyanın ilk satırı başlık, sonraki her dolu satır bir parça (şu an 59 parça). Parça kimliği `dosya#satır`.
- Vektörleştirme: `embeddinggemma` (Ollama, 768 boyut). Depo: Chroma, kosinüs uzaklığı, `data/processed/chroma` (git dışı; `--build` ile üretilir).
- Bilgi sorularında kaynaklı notlar olduğu gibi getirilir (LLM serbest cevap üretmez); en yakın parça uzaklığı 0,70'in üstündeyse soru konu dışı sayılır.
- KB, model ya da parçalayıcı değişirse bayat indeks algılanır ve hata verir; `python src\rag.py --status` ile bakılır.

## Testler ve değerlendirme
Bu bölüm `tests/` ve `docs/` klasörleri depoda varsa geçerlidir.
```powershell
python tests\run_all.py              # tüm birim ve kural testleri
python tests\e2e_final.py --hepsi    # uçtan uca (sunucu açıkken)
node tests\ui_range_test.js          # arayüz testleri (Node.js)
```
Uçtan uca test, 127.0.0.1:8000 adresindeki sunucuya bağlanır ve MCP kayıtlarını bulunduğunuz klasörün `logs/` dizininde arar. Bu yüzden `e2e_final.py` çalıştırılan klasörün kendi sunucusu (`python src\api.py`) açık olmalı; başka bir klasörden başlatılmış sunucu açıksa "MCP çağrıları kaydedildi" denetimi başarısız olur.

Test paketi `TUMU TEMIZ` yazmalı. Ölçülen doğruluk (ayrıntı `docs/07-degerlendirme.md`, varsa):

| Set | Sonuç | Not |
|---|---|---|
| v0 (16 pencere) | 14/16 | eşikler bu veriye ayarlı, iyimser |
| v1 (12 pencere) | 8/12, düzeltme sonrası 10/12 | düzeltme bu vakalardan türedi |
| v2 (14 pencere) | 11/14, düzeltme sonrası 12/14 | küçük doğrulama |
| v3 (13 pencere, dış etiket) | 11/13, yanlış alarm 0/7 | ilk koşu, düzeltme yok; 4/7 kontrol "değerlendirilemedi" |

## Sürdürülebilir şehir çerçevesi
Trafik, elektrik tüketimi ve hava kalitesi birbirine bağlı şehir göstergeleridir. Bu göstergelerdeki ani değişimin nedenini (bayram, hava olayı, veri hatası, afet) kanıtla açıklamak izlemeyi güvenilir kılar; proje BM Sürdürülebilir Kalkınma Hedefi 11 (sürdürülebilir şehirler) ile ilgilidir.
- **Uygulanan:** şehir hareketliliği (İBB saatlik trafik) ve ek veri olarak hava kalitesi (İBB, saatlik NO2/PM10/O3). Hava kalitesi trafikle aynı normal düzey kuralıyla (önceki 4 haftanın aynı gün ve saatinin ortancası) çapraz kontrol edilir; yalnızca "ek sinyal" olarak gösterilir, karar kuralını değiştirmez. Hipotez puanlamasına katmak ayrı bir ölçüm gerektirir, yapılmadı.
- **Planlanan, yapılmadı:** elektrik tüketimi (EPİAŞ Şeffaflık Platformu; erişim için kayıt gerekir).
- Karar kural tabanlıdır, LLM yalnızca doğrulamalı açıklama yazar. Bu tercihin enerji tüketimi ölçülmedi, bu nedenle verimlilik iddiası yoktur.

## Bilinen sınırlar
- Karar kapısı gün düzeyi medyana bakar; yerel/saatlik etkileri (ör. kar fırtınası) kaçırabilir.
- Deprem hipotezi en fazla "belirsiz" olur; ajan nedensellik iddia etmez, insana sorar.
- Takvim aracı yalnızca resmî tatilleri bilir (okul tatili, etkinlik yok).
- Hava tek nokta reanalysis verisidir (istasyon ölçümü değil); hava kalitesi şehir değeri istasyon medyanıdır ve NO2'nin araç dışı kaynakları vardır. Ek sinyal nedensellik değil çakışmadır.
- Her ay boşluklu veri içerir; veri yükleme kaydı boşluğun nedenini söylemez.
- Örneklem küçük: sonuçlar eğilim gösterir, kesin değildir.
- Tam liste `docs/14-bilinen-sinirlamalar.md` dosyasındadır (varsa).

## Kaynaklar ve lisans
- Trafik ve hava kalitesi: İBB Açık Veri Portalı, İBB Açık Veri Lisansı. **Kaynak: İBB Açık Veri Portalı.**
- Hava: Open-Meteo Historical Weather API. Deprem: USGS FDSN katalogu. Resmî tatil: Python `holidays` paketi.
- Ek belgeler (`docs/` varsa): `docs/01-proje-ozeti.md` (özet), `docs/02-mimari.md` (mimari), `docs/09-final-rapor.md` (final rapor), `docs/15-demo-kontrol-listesi.md` (demo).

Ek örnek sorular: "Trafik ve NO2 arasında saatlik gecikme var mı?", "Bayram günlerinde gün içi trafik ve NO2 profili", "Sistem bilinen olayları ne kadar yakalıyor?" (bulgular için docs/16-bulgular-ozeti.md).
