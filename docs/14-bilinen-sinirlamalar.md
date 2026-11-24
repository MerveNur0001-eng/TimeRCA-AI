# 14 - Bilinen sınırlamalar (19 Kasım 2026)

Bu liste ölçülmüş veya kodda görülmüş maddelerden oluşur. Her madde karar mantığını nasıl etkilediğini söyler; hiçbiri nedensellik iddiası değildir.

## Veri
- Kapsam: 882 takvim günü (2021-12-01 ... 2024-04-30); 523'ünde en az bir saatlik veri var, 21168 saatin 12189'u dolu.
- Veri olmayan aylar: 2022-02...2022-09, 2022-12, 2023-10, 2024-02, 2024-05 sonrası. Bu dönemlerde sistem "veri yok" der, sonuç üretmez.
- Hava ve deprem verisi trafik verisinin var olduğu dönemler için indirilmiştir.
- Boşluğun nedeni kaynak veriden bilinemez (ETL hatası mı, gerçek veri yok mu).

## Baseline ve sapma kuralı
- Baseline: önceki 4 haftanın aynı gün ve saat medyanı; en az 3 geçerli hafta yoksa "Değerlendirilemedi". Eşikler: düşük 0,85, yüksek 1,15; tam 0,85 olan gün "<0,85" değildir.
- Baseline boşluk ve düzey kaymasına kırılgandır (docs/07: Ocak 2024).
- Baseline, bayram ve arife dönemleriyle kirlenebilir (Ramazan sonrası haftalar, 9 Nisan 2024 arifesi).
- Gün düzeyi medyan yerel düşüşleri seyreltir (docs/09); saatlik yerel bölgeler ayrı gösterilir ve günlerin büyük kısmında çıkar (docs/07).
- Gösterim yuvarlaması: grafik ve araç aynı günde en çok 0,01 farklı gösterebilir; sınıf ve karar farkı yoktur (consistency_test, 328 gün).
- Tek günlük resmî tatiller eşiğe yakındır; çok günlü bayramlarda düşüş belirgindir ve yalnız tatil hipotezi desteklenir.

## Hava (ayrıntısı: docs/13)
- Open-Meteo reanalysis, tek nokta (41.01, 28.98); istasyon ölçümü değil, tüm İstanbul'u temsil etmez.
- Kural yalnız yağış ve rüzgâra bakar; sıcaklık kullanılmaz; yön (düşüş/artış) ayrımı yoktur.
- Hava kuralı penceredeki en yağışlı günün toplam yağışını günlük p90 ile karşılaştırır (precip_max_day_mm; 19 Kasım 2026 düzeltmesi, ölçülmemiş karar kuralı değişikliği, bkz. docs/13). Bir günden kısa pencerede kısmi gün toplamı kullanılır (daha tutucu).
- Kar gibi yerel ve zamanlı olaylar reanalysis'te eksik veya kaymış görünebilir (E01).

## Deprem
- Kaynak USGS kataloğu, yalnız indirilen dönemler için; Ocak 2023 ve Şubat 2024 kapsam dışıdır. AFAD ve Kandilli yoktur.
- Ölçülen dönemde deprem hipotezi hiçbir günde desteklenmedi.

## Takvim
- Resmî tatil ve bayram var; okul tatili, arife yarım günü, il kapanışları (kar tatili vb.) ve etkinlik takvimi yoktur (docs/12).

## ETL
- ETL işaretli saat oranı >= 0,25 ise ajan "sapma yok" sonucunu günün tamamı için geçerli saymaz ve veri hatasını destekler (örnek: 28 Nisan 2024, flag_share_test). 28-30 Nisan 2024 penceresinde medyan oran 1,12, sapma yok, veri hatası destekliyor, güven orta, insan gerekmiyor; temiz saat çok az olduğu için sonuç dikkatle okunmalı. docs/07'deki eski ifade bu kural eklenmeden önceki durumdur.

## Tasarım gereği
- Yeterli kanıt yoksa sistem kesin neden söylemez, insan onayına gider; insanın girdiği iddia aynı araçlarla sınanır, otomatik kabul edilmez.

## Gelecek çalışma (yapılmadı)
- Sürdürülebilir şehir genişlemesi: elektrik tüketimi (EPİAŞ Şeffaflık Platformu, kayıt gerekir). Hava kalitesi serisi 22 Kasım'da ek sinyal olarak eklendi (aşağıdaki "Hava kalitesi" bölümüne bakın); elektrik için erişim, saatlik çözünürlük ve geçmiş uzunluğu doğrulanmadı, denenmedi.
- AFAD ve Kandilli deprem katalogları, toplu taşıma verisiyle çapraz doğrulama, etkinlik ve okul takvimi, eksik ayların eklenmesi.

## n8n entegrasyonu (19 Kasım 2026 canlı test)
- Akış docs/n8n-akisi.json (12 düğüm): statik doğrulandı (bağlantı hatası yok) ve n8n 2.47.7 (Docker) üzerinde canlı denendi.
- Denenen yol: SORU "25.01.2022 anomali incele" -> /ask -> insan onayı formu (güven düşük, açıklanamayan) -> reddet -> RET FORMU -> /feedback.
- Sonuç: kayıt düştü (kanıt_yok, sonuç_korundu, doğrulama bekliyor). İddia (hava) aynı araçlarla sınandı: yağış 3,7 mm (eşik 7,5), rüzgâr 31,2 km/sa (eşik 40), eşik aşılmadı; otomatik kabul edilmedi.
- Sınır: test, API anahtarı kapalıyken yapıldı (TIMERCA_API_KEY tanımsız, dört HTTP düğümünde Authentication: None). Anahtar yolu yalnız kısmen doğrulandı: anahtarsız istek 401 döndürdü; doğru anahtarla tam doğrulama yapılmadı.
- JSON'daki dört HTTP düğümü Header Auth bekler (docs/02). Akışı yeniden içeri alırsanız kimlik bilgisi oluşturun veya yetkiyi None yapın.
- Form adresleri "test" modundadır: akış editörden Execute workflow ile çalışır, editör açık kalmalıdır.
- api.py ThreadingHTTPServer kullanır (20 Kasım 2026): analiz istekleri (POST) tek kilitle sıralanır, bir /ask sürerken diğer POST'lar bekler; yalnız GET /health ve arayüz beklemez. Paylaşımlı duruma (sqlite, chroma, önbellek) POST'lar aynı anda girmez; test: tests/api_esz_test.py.

## Grafik gösterim notları (20 Kasım 2026; yalnız gösterim, karar kuralı değil)
- Günlük grafikte ETL işaretli saat oranı >= 0,25 olan ve durumu normal olan günler bej çizilir (etl_pay_yuksek; etl_share_chart_test). "Sapma yok" sonucu bu günlerde güvenilir değildir.
- Bölge tablosunda gece yarısını geçen bölgelerin bitiş tarihi gösterilir. Seçilen aralıkta hiç kaynak veri yoksa "kaynak veri yok" yazılır.

## İdari izin ve uzatılmış tatiller
- 2024 Ramazan Bayramı: 10-12 Nisan resmî tatil; kamuda 8 Nisan tam gün, 9 Nisan yarım gün idari izin (6-14 Nisan, 9 gün). Kaynak: Cumhurbaşkanlığı duyurusu ve idari izin yazısı, Mart 2024 (TRT Haber, NTV, Ekonomist).
- get_calendar yalnız resmî tatilleri bilir, idari izin günlerini bilmez. 8 Nisan 2024 "açıklanamayan, insan onayı" döner; takvim bağlamı notunda yalnız okul ara tatili görünür. Bu doğru davranıştır: neden uydurulmaz.
- İdari izin yalnız kamu çalışanlarını kapsar. Trafiğe etkisi ölçülmedi, neden olarak iddia edilmez. 13 Nisan 2024 idari izin değil, hafta sonudur.
- v4 adayı: takvim bağlamına idari izin günleri (docs/08 ve bulgular dosyasındaki MEB takvimi maddesiyle birlikte).

## Yerel sağanak ve hava aracının kapsamı (5 Eylül 2023 sel)
- 5 Eylül 2023 akşamı İstanbul'un kuzeybatı ilçelerinde (Başakşehir, Küçükçekmece, Arnavutköy vb.) sel yaşandı. Kaynak: İPA bilgi notu (yağış 17.30'da arttı, 20.30'dan itibaren şiddetlendi) ve basın haberleri: https://ipa.istanbul/wp-content/uploads/2023/09/05-06-Eylul-Taskin_IPA-Bilgi-Notu.pdf
- get_weather (Open-Meteo reanalysis, tek nokta 41.01, 28.98) aynı saatler için: 05.09 18:00 - 06.09 01:00 yağış 0,1 mm; 05.09 gün toplamı 0,8 mm (dönem günlük p90 7,5 mm); 06.09 0,1 mm. Araç bu yerel sağanağı görmüyor.
- Trafik: 05.09 gün medyan oranı 0,90; 18:00-01:00 penceresi 0,89; 0,85 eşiğinin altına inmedi, sapma yok, hava aracı çağrılmadı (rapor bunu "Araç çağrılmadı: belirgin sapma yok" diye açıkça yazar). 06.09 günü grafikte bant içinde (yaklaşık 1,05), bölge yok.
- Sonuç: yerel bir afet hem hava aracında hem şehir geneli trafik toplamında görünmeyebilir. Sapma olsaydı sistem havayı desteklemez diyerek "açıklanamayan" ve insan onayı verirdi, nedeni uydurmazdı; insan "hava" iddiası girse aynı araçla sınanır ve kanıt_yok döner. Bu bir araç sınırlamasıdır, karar kuralı değişikliği gerekçesi değildir (tek olay için eşik ayarlanmaz).
- Gelecek çalışma: ilçe bazlı veya çoklu nokta yağış (AKOM istasyonları) ve ilçe bazlı trafik.

## Soru kutusunda tarih biçimi
- Doğrulanan biçim: GG.AA.YYYY (örnek: "05.09.2023 anomali incele"). "2023 yılının 9. ayının 6. günü" gibi dolaylı ifadeler tarih olarak tanınmaz; soru bilgi aramasına düşer ve ilgisiz notlar gösterilir ("doğrudan cevap olmayabilir" etiketiyle). Demoda GG.AA.YYYY kullanılmalı.

## Çok noktalı yağış denemesi (5 Eylül 2023, keşif, karar kuralına girmez)
- Aynı model (Open-Meteo arşiv), 7 nokta; betik: scripts/kesif/weather_multipoint_probe.py. 05.09 gün toplamı: Fatih ve Kadıköy (aynı hücre) 0,8; Küçükçekmece 1,1; Başakşehir 2,8; Pendik 3,0; Arnavutköy 9,1; Sarıyer 15,4 mm. Günlük p90 = 7,5 mm.
- Noktalar arası maksimum (Sarıyer 15,4 mm) p90'ı aşar, yani 5 Eylül "aşırı hava" sayılırdı. Ancak en çok etkilenen ilçeler (Başakşehir, Küçükçekmece) modelde 2,8 ve 1,1 mm; İPA notu 137 kg/m2, basında 125 kg/m2 gibi yerel değerler bildiriliyor. Model hem büyüklüğü hem yeri tutturamıyor (hücre boyutu yaklaşık 8 km).
- Sonuç: çok noktalı maksimum kısmen yardımcı olur ama yağış miktarını çok düşük tahmin eder; ayrıca maksimum almak normal günlerde "aşırı hava" oranını artırır, günlük p90 çok noktalı veriden yeniden hesaplanmalı. Karar kuralı değişikliği olduğundan etiketli doğrulama olmadan uygulanmadı (v4 adayı). Daha güvenilir çözüm istasyon verisi (AKOM/MGM).
- Kamu idari izni yalnızca elle girilmiş tarihler için bilinir (8 Nisan 2024 tam gün; 26 Haziran 2023 tam gün). Başka idari izinler takvimde yoktur. Yalnız tam gün idari izin karar kuralına girer (tatil: belirsiz); yarım günler bağlam notu. Ayrıntılar docs/07, ölçülmemiş kural.

## 20 Kasım ek sınırlamalar

- **Yoğunluk kuralı yapısal olarak gerçek trafik düşüşlerini veri sorunu sayar.** Kural hücre başına araç için ay medyanının yarısının altını şüpheli sayar; hücre sayısı sabitken yağış ya da kar yüzünden trafik azalırsa bayrak çıkar. `veri_sorunu` kesinliğinin 0/7 olmasının nedeni bu. Kural değiştirilmedi (aday E hiçbir sonucu değiştirmedi), sınırlama olarak kayıtlı.
- **ETL logu ayda en fazla 50 şüpheli saat tutuyor (`[:50]`).** Yalnız 2024-04'te yoğunluk listesi kesilmiş (gerçek 72, kayıtlı 50). Kesilen 22 saatin tamamı düşük hücre kapsamına da takıldığı için kapının kullandığı birleşim kümesi log ile birebir aynı (72 = 72); sonuçlara etkisi yok. Ancak sınır başka bir ayda aşılırsa bayraklar eksik kalabilir.
- **B kuralı ile ETL-payı kuralı arasında öncelik vardır:** ETL payı >= 0.25 ise B uygulanmaz.
- **Seri ve karar yuvarlama farkı:** grafikte tüm-saat oranı 0.84, karar katmanında 0.83 görünebilir (yuvarlama), tutarlılık testi bunu tolere eder.
- **Etiket seti küçük.** B tek pencereden esinlenerek yazıldı; v3'ün eski, önceki snapshot'ı bulunamadığı için B'nin v3 öncesi ve sonrası karşılaştırması yalnız v4 üzerinde yapılabildi. Okul takvimi karar kuralında kullanılmıyor.

## 20 Kasım: veri_sorunu kesinliği 0/7 nasıl okunmalı (ölçüm, post-hoc)
- v4'te 18 pencerenin hiçbirinde gerçek veri sorunu yok. 0/7 = 7 "bildirildi", 0 doğru; geri çağırma v4'te tanımsız (0/0).
- eval_v4.py'deki "veri_bildirildi" üç ayrı şeyi tek sayıda topluyor: iddia (veri_hatası destekliyor), belirsiz ve yalnız veri_kalitesi_uyarısı notu.
- Kademeler (snapshot'lardan, scripts/olcum/veri_kademe_olc.py): iddia v3'te 2/2 doğru (geri çağırma 2/3), v4'te iddia yok (yanlış iddia 0); belirsiz C01-C04 1/4 gerçek; yalnız uyarı notu v3'te 0/3, v4'te 0/7.
- Kod ve eşik DEĞİŞMEDİ. Kademe ayrımı sonuçlar görüldükten sonra yapıldı (post-hoc): açıklama, kanıt değil.
- Kaçan tek gerçek pozitif (C03) yoğunluk kuralından değil, yetersiz geçmiş veriden (belirsiz) geliyor; eşik kuralı bunu düzeltmez.
- Sınırlar: gerçek pozitif yalnız 3 (v3), v4'te sıfır; uyarı notunun içeriği (işaretli ve eksik saat) snapshot'ta yok, yoğunluk kuralı ile ilişkisi bu ölçümden doğrudan gösterilmedi.
- Sonuç: gate'te veri hatası iddiası için kanıtlanmış bir hata yok; "precision 0/7" ifadesi iddia kesinliği olarak okunmamalı.

## 20 Kasım: hava penceresi ve idari izin kurallarının etkisi (ölçüm, doğrulama değil)
- Yöntem: eval/kural_etki_onkayit.txt (ölçümden önce yazıldı), scripts/olcum/kural_etki_olc.py, eval/kural_etki_olcum.txt. İlk çalıştırmada yamalar tools ve calendar_ctx üzerine yapıldı, ama evidence.py "tools_gw" kullandığı için etkisizdi; "ölçülemedi" diye eval/kural_etki_olcum_1_yama_etkisiz.txt olarak saklandı. Düzeltilmiş ölçümde yama sayaçları var.
- İdari izin (4 gün): kural yalnız 2024-04-08'de etkili. Kapalıyken tatil "desteklemiyor", açıklanamayan "destekliyor"; açıkken tatil "belirsiz", açıklanamayan "desteklemiyor". Güven (düşük) ve insan onayı ikisinde de aynı. 2023-06-26 (sapma yok), 2023-06-27 ve 2024-04-09 (yarım gün; kural yalnız tam gün) değişmedi. 2024-04-08 etiketli pencerelerde yok: kuralın doğruluğu ölçülemez, etkisi 1 gün.
- Hava penceresi, etiketli 57 pencere: karar değişen 0; yalnız 1'i çok günlü, üç hava etiketli pencere tek gün (toplam = gün_max: 4.6, 13.8, 30.6 mm; p90 7.5). Etiketler bu kuralın doğruluğu hakkında bilgi vermez.
- Yalnız yağış, kayan pencere 2021-12-01..2024-04-30 (üst üste binen, birbirine bağımlı): 3 gün 555 pencere: eski kural (toplam > p90) 164, yeni (en yağışlı gün > p90) 134, bastırılan 30. 7 gün 567 pencere: eski 315, yeni 251, bastırılan 64.
- Yapısal bulgu: yeni kural da çok günlü pencerede "aşırı hava" oranını şişiriyor: tek günlük p90 (7.5 mm) ile pencere içindeki en yağışlı gün karşılaştırıldığı için 7 günlük pencerelerin %44'ü, 3 günlüklerin %24'ü aşırı sayılıyor (tek günde beklenen yaklaşık %10). Gün sayısına göre eşik düzeltmesi YAPILMADI; çok günlü pencerelerde "hava destekliyor" tek başına nedensellik kanıtı sayılmamalı. Hava, sapma varken ek kanıt olarak okunmalı.
- Sınırlar: yalnız-yağış sayımı judge'dan geçmedi (sapma şartı ve rüzgâr dışarıda); kayan pencereler bağımlı; hava etiketli yalnız 3 pencere.

## 21 Kasım: UYM trafik duyuruları, kapsam_dışı gösterimi ve açık sınırlamalar (ölçüm, doğrulama değil)
- UYM duyuruları (İBB Açık Veri, Ulaşım Yönetim Merkezi Trafik Duyuruları Verisi): 2021-12 ... 2024-04 arası 29 ayın hepsinde kayıt var (54.250 satır). Kaza, arıza ve bakım duyuruları neredeyse her gün var (878/882, 878, 831 gün): kanıt değil. Etkinlik kayıtları (bitiş tarihleriyle 26 gün) ve yolun trafiğe kapanması (372 gün) sapmalı günlerle ilişkili çıkmadı: etkinlik günlerinde sapmalı 2/12 (%16,7) | olaysız günlerde 57/385 (%14,8), Fisher p 0,554; kapanma 18/158 (%11,4) | 41/239 (%17,2). Etkinlik örneği 12 gün: güç düşük, bu "ilişki görülmedi" demektir, "ilişki yok" değil. Araç eklenmedi, karar kuralı değişmedi. Betikler ve çıktılar dal olay-duyuru-kesif'te (src/uym_*.py, eval/uym_*.txt); ön kayıt ve sonuç: proje dokümanı olay-duyuru-onkayit-20-kasim.
- Arayüz: veri olmayan bir tarih veya 7 günden uzun pencere sorulunca (sonuç tipi kapsam_dışı) ham JSON yerine okunur bir kutu gösterilir (etiket teslim-20261120p, yalnız gösterim).
- Açık sınırlamalar: 5 Eylül 2023 seli sistem tarafından görülmüyor (yerel sağanak, tek noktalı hava); E01 kaçırması; 4 hafta baseline ve 0,85-1,15 bandı ölçülerek seçilmedi (yalnız duyarlılık ölçüldü); çok günlü pencerede aşırı hava oranı yapısal olarak şişiyor; etiketli örnek küçük (13/57/18 pencere), doğruluk iddiası yoktur; belirlenemedi oranı yüksek olabilir ve bu bilinçli tasarımdır (kanıt yoksa neden uydurulmaz, insan onayı istenir).

## 21 Kasım: LLM ile soru anlama (soru kutusunda KULLANILIYOR; yalnız kural çözemezse)
- src/soru_llm.py (gemma3:4b) router_graph.planla_ana içinden çağrılır. LLM yalnız soruyu {niyet, başlangıç, bitiş} yapısına çevirir; karar vermez. Tarihin gün, ay ve yılı sorunun metninde yazılı olmak zorundadır; doğrulama geçmezse, Ollama kapalıysa ya da çıktı bozuksa router_graph kuralının cevabı aynen kullanılır. Kural zaten çözdüyse LLM çağrılmaz (A sınıfında 0 çağrı). TIMERCA_SORU_LLM=0 ile kapatılır. Örnek: "2024 yılında 23 nisan bayramının anomalisini incele" kuralla çözülemiyordu, LLM 23 Nisan 2024'ü buldu.
- Ölçüm (eval/soru_llm_olcum.txt, 22 el yapımı soru, tek çalıştırma, kabul ölçütü sonuçlardan önce yazıldı; bağlamadan ÖNCE yapıldı): yanlış kabul 0; B sınıfında (kuralın tanımadığı açık tarih yazımları) 8/8 doğru kabul; C sınıfında (yılsız, göreli, belirsiz tarih) 6/6 red; A sınıfında LLM çağrısı 0; D sınıfında analize dönen 0. soru_llm_test.py 18/18, router_llm_test.py 9/9. Model bir soruda yıl uydurdu (22 Nisan'da: 2024) ve doğrulama reddetti. Model karşılaştırması (deney_llm/model_karsilastir.py): qwen2.5:3b güvenlik eşiklerini sağladı, medyan 6,5 sn (gemma3:4b 11,7 sn) ama önceden yazılan "hızlı alternatif" ölçütünü (yarısından kısa) sağlamadı; qwen2.5:1.5b 1 yanlış kabulle elendi. Varsayılan model gemma3:4b.
- Kabul ölçütünün "Pazartesi'den önce alma yok" şartı kullanıcı kararıyla aşıldı; yerine run_all ve e2e_final --hepsi temiz çıkmadan alma yok kondu (26/26 temiz, teslim-20261121c).
- Aynı gün kuraldaki iki sessiz yanlış okuma düzeltildi: "2024 yılının 1. ayının 2. haftası" 2 Ocak tek günü olarak, "2024 Ocak 8 - 14" yalnız 8 Ocak olarak okunuyordu. Hafta ifadesi (kural tabanlı, LLM değil): ayın N. haftası = ayın (N-1)*7+1 ile N*7. günleri (ay sonuna kırpılır); takvim haftası (Pzt-Paz) veya ISO haftası DEĞİLDİR. Gün aralığı: "8-14 Ocak 2024", "2024 Ocak 8 - 14", "8 ile 14 Ocak 2024".
- "Var mı / var mıydı / oldu mu" soruları çok günlü pencerede gün gün tarama (scan.py) ile cevaplanır; neden aramaz. "Aday yok" "sorunsuz" değil "eşiği aşmadı" demektir (gün düzeyi medyan, saatlik ve yerel etkiler seyrelir).
- "Nisan 2024'te bir gün seç, trafik neden düştü" soruları: günü LLM değil sabit kural seçer. Ay gün gün taranır (scan.py, 30 gün < 1 sn), sorunun yönüne uyan (düştü/arttı; yön yoksa ikisi) adaylar arasında medyan oranın 1'den en çok saptığı gün alınır (eşitlikte erken tarih; salt eksik veri seçilmez), seçilen gün normal ajan yoluyla incelenir. Cevap seçimi açıkça yazar (ay, taranan gün, aday sayısı, kural, oran). Yıl veya ay yoksa tahmin edilmez, sorulur. Aday yoksa gün seçilmez ve "eşiği aşmadı" denir. Seçilen gün "en büyük sapmadır", "tek anomalidir" değil; nedeni yine kanıt eşleşmesidir, kesin kök neden değil. Ay penceresi 62 günle sınırlıdır (scan.MAX_SCAN_DAYS). Testler: tests/router_sec_test.py (36 kapı, sahte scan/api).
- Bilinen küçük tutarsızlıklar (kod değişmedi): /series geçersiz "mod" (örnek "yıllık") için 400 yerine sessizce "günlük" kullanır; hava durumu gibi araç soruları ("yarın yağmur yağacak mı?") konu dışı sayılmaz, bilgi tabanındaki hava aracı notları "doğrudan cevap olmayabilir" etiketiyle gösterilir (tahmin yapılmaz).
- Sınırlar: 22 soru az ve yazar tarafından seçildi (doğruluk değil, güvenlik eşikleri ölçüldü); LLM'e giden soru panelde yaklaşık 7-16 sn sürer (kuralın çözdüğü sorular saniyeler içinde); gün/ay denetimi sayısal tesadüfe açık; soru_llm.py tek kopyadır (src/soru_llm.py); deney_llm betikleri (ölçüm, test, model karşılaştırma) onu src'den kullanır; açıklama yazarı LLM (llm_explain.py, gemma3:4b) o gün henüz yalnız agent.py --llm komut satırındaydı, panelde yoktu (bu durum 22 Kasım'da değişti, aşağıya bakın).

## 22 Kasım: ek özellikler (soru kutusu) ve gelecek çalışmalar
- "Nisan 2024'te anomali var mıydı": ay boyunca gün gün tarama (scan.py, 62 güne kadar); neden aramaz, aday günleri ve DEĞERLENDİRİLEBİLEN gün sayısını yazar (veri yok ve baseline yetersiz günler "sorunsuz" gibi sunulmaz). Yıl yoksa tahmin edilmez: o ay için yüklü yıllar sayılır ("Nisan için yüklü yıllar: 2023, 2024").
- "Veri hatası olmayan en sapmalı günü seç": adaylar sıralanır, en çok 5 aday ajanla denenir, "veri hatası destekliyor" olanlar elenir; elenenler cevapta yazılır. Hepsi veri hatasıysa gün seçilmez ve bu söylenir. Bedeli: aday başına bir ajan çalışması (yaklaşık 3-8 sn).
- "En çok sapan 3 günü bul / ilk 3 gün": en çok 5 gün, her biri ajanla incelenir, tek özet satırında listelenir. Kanıt yetersiz gün için neden uydurulmaz ("insan onayı gerekir, tek gün olarak sor"); insan onayı akışı yalnız tek gün sorusunda çalışır.
- LLM açıklama yazarı artık panelde (yalnız tek gün analizi): sunucu başlarken TIMERCA_ACIKLAMA_LLM=1 varsayılır (0 ile kapatılır); testler ve import eden betikler etkilenmez. Karar değişmez: hipotezler ve özet kuraldan gelir, LLM metni ayrı bir kutuda gösterilir ("LLM, gemma3:4b; sayı, tarih ve hipotezler doğrulandı"). Sayı, tarih, yüzde ve desteklenmeyen hipotezin neden gibi sunulması denetlenir; geçmezse ya da Ollama yoksa kutu "kural metni" der. Her tek gün analizine yaklaşık 5-15 sn ekler (ilk istekte model yüklenirse daha uzun).
- LLM açıklama yazarının sınırları (22 Kasım canlı deneme, gemma3:4b): model 10 Nisan 2024 için oranı "%61" (bağlamda 0.61 var) ve tarihi yanlış yazdı; 22 Nisan 2023 için 0.74 oranını (düşüş) "yüksek bir artış" diye anlattı. Sayı ve tarih denetimi ilkini yakalar, ikincisini yakalamazdı; bu yüzden yön denetimi eklendi (kural özetindeki oran <0,85 ise metin "artış" diyemez, >1,15 ise "düşüş" diyemez) ve bağlama "Yön:" satırı konuldu. Küçük modelle metinlerin önemli bölümü reddedilip kural metnine düşer; arayüz bunu "kural metni; LLM çıktısı doğrulamayı geçmedi: <gerekçe>" diye gösterir. Denenen alternatifler: qwen3:4b (düşünme metnini İngilizce yazar, 50-70 sn, kullanılamaz), qwen2.5:3b (daha uyumlu ama Türkçesi zayıf, "hipoteziniz doğrudur" gibi); model değiştirmek yeni ölçüm gerektirdiğinden gemma3:4b kaldı. Karar her zaman kuralda; LLM yalnız okunabilir metin önerir.
- Testler: tests/router_ek_test.py (38 kapı) ve tests/llm_yon_test.py (11 kapı, yön denetimi); sahte scan/api/açıklama, Ollama gerekmez. Bu iki test o gün run_all'a eklenmemişti; sonradan router_ek_test run_all'a eklendi.
- Gelecek çalışma (YAPILMADI, nedenleriyle):
  - Bayram sonrası baseline düzeltmesi: tools.compare_same_weekday_history değişir; tüm ölçümleri (eval, kural etki ölçümü, e2e 26/26, run_all) ve ön kayıtlı ölçütleri yeniden koşmayı gerektirir. Teslimden önce ölçülmüş sonuçları değiştirmemek için yapılmadı.
  - İlçe/hücre düzeyi (ÖLÇÜLDÜ, varsayım desteklenmedi): ham CSV'de LATITUDE/LONGITUDE/GEOHASH var, ilçe eşlemesi yok. scripts/kesif/hucre_duzeyi_probe.py (eval/hucre_duzeyi_probe.txt) 5 Eylül 2023'ü 0,05 derecelik (yaklaşık 5 km) bloklarda inceledi: saat aralığı 12-18, 08-20, 06-12 ve 00-24 için en düşük blok oranı 0,68-0,80; blok oranı medyanı şehir toplamıyla aynı (0,91-1,00). Yani bu çözünürlükte sel yerel bir çöküş olarak görünmüyor; sıradan Salı günlerinde de 0,69 civarında bloklar çıkıyor (22 Ağustos). Ek bulgu: sıradan bir Salı'da (29 Ağustos) şehir toplamı 1,16-1,35 çıktı; gün düzeyi veri hacmi (hücre kapsamı) dalgalanıyor, bloklar bunu normalleştirmeden karşılaştırılamaz. Sonuç: "ilçe düzeyi seli çözer" iddiası yapılmaz; denenecekse önce kapsam normalleştirmesi ve daha ince saat penceresi gerekir.
  - "Dünü tara" / sabah taraması: veri Nisan 2024'te bitiyor, "dün" verisi yok; n8n akışı hazır ama canlı veri kaynağı yok.
  - Etiketli örnek setini büyütüp doğruluk ölçmek; insan kararlarından eşik öğrenme; AFAD ve olay duyuruları.

### Göreli tarihler ("dün", "bugün", "geçen hafta")

Veri Nisan 2024'te bitiyor; "dün", "bugün", "yarın", "geçen hafta/ay/yıl", "bu hafta/ay", "son N gün" gibi göreli tarihler çözülemez. Soru kutusu bunları tahmin etmez; `tip=eksik` kartında "Göreli tarih anlaşılamaz" mesajı, yüklü trafik dönemleri ve örnek bir soru gösterir. Bu cevapta LLM denenmez. Yüklü olmayan bir tarih sorulursa `kapsam_disi` cevabı da yüklü dönemleri listeler. Testler: `router_ek_test` 51 kapı (G1-G10 göreli tarih). "Dünü tara" özelliği bu yüzden yapılmadı (gelecek çalışma).

### 22 Kasım (akşam): beş küçük özellik (karar kuralları değişmedi)

- **İki gün karşılaştırma** ("10 Nisan ile 17 Nisan 2024 karşılaştır"): her gün mevcut ajanla ayrı ayrı, aynı kurallarla değerlendirilir; yan yana tablo gösterilir. Yeni karar kuralı yoktur; fark yalnız iki oranın farkı olarak yazılır. Yılsız, tek günlü ya da üç günlü sorularda tarih istenir (yıl tahmin edilmez).
- **Haftalık özet** ("Nisan 2024 haftalık özet"): ay taraması haftalara gruplanır (hafta = ayın 1-7, 8-14, ... günleri; `hafta_penceresi` ile aynı sözleşme). Her hafta için aday günler ve değerlendirilebilen gün sayısı yazılır; "aday yok" sorunsuz demek değildir.
- **Markdown indirme**: analiz kartında ve pencere raporunda düğme; dosya tarayıcıda üretilir, sunucuya bir şey gitmez.
- **Soru geçmişi**: son 5 soru yalnız tarayıcıda (localStorage) tutulur; depolama yoksa sessizce çalışmaz.
- **Güncel örnek sorular**: `GET /ornekler` yüklü verinin son döneminden örnek soru üretir (`router_graph.ornek_sorular`); sunucu yanıt vermezse sabit örnekler kalır.
- Testler: `router_ek_test` 79 kapı (K, W, O bölümleri bu özellikler için). Canlı doğrulama için API yeniden başlatılmalıdır.

### 22 Kasım (gece): takvim notu, ay karşılaştırma, demo modu

- **Takvim notu:** tek gün (ve en çok 7 günlük pencere) analizinde, gün resmî tatil, arife/yarım gün, idari izin ya da okul tatiline denk geliyorsa kartta kısa not çıkar. Kaynak `tools.get_calendar` (`calendar_ctx`); bu bilgi kanıttır, karar kuralında kullanılmaz ve sonucun hipotezlerini/özetini değiştirmez. Takvim aracı hata verirse not yazılmaz, analiz bozulmaz. İki gün karşılaştırmasında günün takvim bilgisi de tabloda yer alır.
- **İki ay karşılaştırma** ("Nisan 2023 ile Nisan 2024'ü karşılaştır", "Mart ile Nisan 2024"): her ay ayrı ayrı gün gün taranır; taranan/değerlendirilebilen gün, sapma günü, düşüş/artış sayısı ve en çok sapan gün yan yana yazılır. Her gün kendi önceki 4 haftasıyla kıyaslandığı için aylar arası mutlak trafik farkı ölçülmez; bu yeni bir karar kuralı değildir. Yıl yoksa tahmin edilmez.
- **Demo modu:** arayüzde 7 adımlık sunum akışı (bayram, veri hatası, insan kararı, deprem, sel sınırı, ay taraması, iki gün karşılaştırma). Sonuçlar canlı üretilir, kayıtlı değildir; adımlar mevcut `/ask` yolunu kullanır. **Sonradan arayüzden kaldırıldı (22 Kasım gece, görünüm nedeniyle); sunumda örnek soru düğmeleri ve soru kutusu kullanılır.**
- Testler: `router_ek_test` 98 kapı (TK, AK, O5 bölümleri).

## Normal gün açıklaması, CSV, üst üste grafik, soru önerisi (22 Kasım akşam, teslim-20261122b)
- Normal gün açıklaması: "17 Nisan 2024 neden normal / normal mi / neden anomali yok" tek günlük tam tarihle sorulursa mevcut kural (`scan.classify`, eşikler 0,85-1,15, eksik saat payı 0,25) sonucu açıklanır: oran, eşik aralığı, eksik saat, önceki 4 haftanın baseline günleri ve baseline günlerindeki takvim notları. Ajan ve hipotez çalışmaz; yeni karar kuralı yoktur. Oran eşiğin altı/üstündeyse "normal değil" denir ve "neden düştü/arttı" sorusu önerilir; eksik saat payı yüksekse "normal" denmez. Tarihsiz ya da çok tarihli sorular (ör. "Bayramlarda trafik normal mi olur?") bu yola girmez.
- "Normal gün", "sorunsuz gün" demek değildir: gün düzeyi medyan saatlik ve yerel sapmaları seyreltir. Eşik sınırındaki günler (ör. 23 Nisan 2024, oran 0,85) "normal" çıkabilir; 0,85 eşiği bu projede sabit bir sözleşmedir.
- Baseline kirliliği: baseline günlerinden biri tatil ya da bayramsa kutu bunu "baseline kirlenmiş olabilir" diye işaretler (ör. 17 Nisan 2024'ün baseline günlerinden biri 10 Nisan bayram günüdür). Karar kuralı değişmez; bkz. `eval\baz_temizlik_olcum.txt` (bayram baseline düzeltmesi bilerek yapılmadı).
- CSV indirme: gün karşılaştırması, haftalık özet, ay karşılaştırması, "var mıydı" aday günleri ve 1. bölümdeki tarama tablosu. Tarayıcıda üretilir; ayraç `;`, ondalık virgül, BOM (Excel Türkçe).
- Üst üste grafik: gün karşılaştırması kartında iki günün saatlik mutlak araç sayıları ve beklenen düzey çizgileri (`/series`, saatlik mod). Yalnızca görsel karşılaştırmadır; karar günün kendi beklenen düzeyine oranıyla verilir. İki gün farklı haftanın günü olabilir.
- Soru önerisi: yazdıkça son sorular, veriden üretilen örnek sorular ve sabit örnekler süzülür (Türkçe harflerden bağımsız). Enter, öneri seçili değilse soruyu gönderir.
- Testler: `router_ek_test` (NG1-NG9, normal gün), `ui_ek_test.js` (16 kapı: CSV, öneri süzme, grafik noktaları). Canlı doğrulama (Chrome, 22 Kasım): 17 Nisan oran 1,02 normal; 10 Nisan oran 0,61 normal değil; 15 Şubat 2024 kapsam dışı; tarihsiz soru bilgi yolunda; CSV düğmesi ve üst üste grafik çalıştı. CSV dosyası fiilen indirilmedi, içerik sayfa fonksiyonuyla doğrulandı.

### Klasör düzeni (22 Kasım gece, teslim-20261122f)
- `src/` yalnızca çekirdek uygulamayı tutar (api, router_graph, agent, evidence, tools, rag, scope, arayüz ...). Testler `tests/`, veri çekme/hazırlama `scripts/veri/`, ölçüm ve etiketleme `scripts/olcum/`, keşif ve hata ayıklama `scripts/kesif/` altına taşındı. Dosya içerikleri değişmedi; yalnızca yol hesapları (kök ve `src/` yolu) ve `run_all`/`e2e_final` içindeki dosya yolları güncellendi.
- Eski sürümlerde (`teslim-20261122e` ve öncesi) bütün dosyalar `src/` altındaydı; belgelerdeki komutlar yeni yollara çevrildi, `eval/` ve `logs/` altındaki eski ölçüm çıktılarındaki başlıklar olduğu gibi bırakıldı.
- Sınır: `scripts/` altındaki ölçüm ve keşif betiklerinin yeni konumdan çalıştığı yol hesabı olarak doğrulandı, ancak hepsi tek tek yeniden çalıştırılmadı (veri indirme ve LLM çağıran betikler dahil).

## Hava kalitesi ek verisi ve sinyali (22 Kasım gece)
- Kaynak: İBB Hava Kalitesi açık veri servisi (`GetAQIStations`, `GetAQIByStationId`; kimlik gerekmez). Servis geliştirme sırasında elle doğrulandı: saatlik kayıt, 28 istasyon, geçmiş trafik aylarının tamamını kapsıyor. İstasyonların ölçtüğü madde sayısı eşit değil (ör. bazı istasyonlarda NO2 ya da CO yok; mobil istasyon kısmi).
- `scripts/veri/fetch_hava_kalitesi.py` aylık, istasyon başına indirir ve her saat için istasyon medyanını `data/processed/aqi_hourly.csv` dosyasına yazar (no2, pm10, o3, so2, co ve istasyon sayıları). Bir saatte 3'ten az istasyon varsa değer boş kalır. Dosya depoda yer alır; silinirse ek sinyal görünmez, sistem eskisi gibi çalışır.
- Kullanım: `python scripts\veri\fetch_hava_kalitesi.py --liste`, `--ay 2023-04`, (parametresiz = eksik tüm proje ayları), `--kontrol` (NO2 saat profili: sabah ve akşam tepesi beklenir).
- Yalnızca gösterim amaçlıdır: hipotez puanlamasını, kararı ve özeti değiştirmez (testle sabit: AK8). Trafikle aynı kural: önceki 4 aynı gün/saat medyanı, 0.85/1.15 eşikleri; ana gösterge NO2, PM10 ve O3 yan bilgi. Trafik normalse sinyal üretilmez.
- `tools.get_air_quality_signal` ve `mcp_server.py`'de 6. MCP aracı; `agent.TOOL_NAMES`'e ve hipotez puanına girmez. Soru kutusundaki "Ek sinyal" kutusu aynı hesabı `router_graph.ek_sinyal` ile yapar. `kb/hava_kalitesi_araci.md` eklendi; `python src\rag.py --build` ile indeks yenilenmelidir.
- Sürdürülebilirlik ek özellikleri (23 Kasım, yalnızca gösterim): (a) tek günlük sonuç kartında saatlik trafik oranı ile saatlik NO2 oranı aynı grafikte (`air_quality.saatlik_oranlar`, `POST /hava_saatlik`); (b) soru kutusunda aylık özet, ör. "Nisan 2024'te trafik düşen kaç günde NO2 de düştü?": ay taramasındaki düşüş ve artış günleri aynı günün NO2 oranıyla sayılır (`router_graph._ay_hava_birlikte`, plan adımı `hava_birlikte_ozet`). Gün durumları `scan.py`'den aynen gelir; yeni karar kuralı, hipotez ve neden iddiası yoktur; birlikte hareket nedeni kanıtlamaz. `eksik_veri` günleri sayıma girmez. Testler: `tests/hava_birlikte_test.py` (19 kontrol), `tests/ui_ek_test.js` (H1, H2).
- Sürdürülebilirlik ek özellikleri, ikinci grup (23 Kasım, yalnızca gösterim): (c) "Bayramlarda trafik ve NO2 ne kadar düşüyor?" tüm resmî tatil günlerini tek tabloda verir (`hava_ozet.bayram_ozeti`); (d) "Trafik ile NO2 ilişkisi nedir?" gün gün nokta grafiği, bağıntı ve doğrusal eğim verir (`hava_ozet.iliski`; en az 20 gün yoksa hesaplanmaz); (e) aylık özette trafik ve NO2 düşen günlerin kaçında PM10 da düştüğü; (f) iki ay karşılaştırmasında NO2 oranı. Gün durumları `series.daily` ile `scan.py` ile aynı eşik ve temiz-saat kuralından gelir; eksik veri günleri oran hesabına girmez. Eğim ve bağıntı nedensellik değildir. Testler: `tests/hava_birlikte_test.py` (B ve M kontrolleri), `tests/ui_ek_test.js` (H3-H5).
- Gerçek veride ölçülen (23 Kasım, 384 gün): gün gün bağıntı zayıf (0,09), çünkü günlük NO2 rüzgâr ve yağış gibi hava koşullarından çok etkileniyor (NO2 oranı 0,36 ile 2,80 arasında). Buna karşılık trafiği normalin altında olan 33 günde NO2 oranının ortancası 0,80 (günlerin %58'inde NO2 de düşük), normal trafikli 332 günde 0,98 (%33). Düşük günler arasında 29.04.2024 gibi trafik oranı 0 olan, yani büyük olasılıkla veri kesintisi olan bir gün de var. Resmî tatil günlerinde: değerlendirilebilen 16 günün 10'unda trafik normalin altında, bunların 6'sında NO2 de düşük. Sistem bağıntı zayıfsa 'zayıf' der, eğim cümlesi kurmaz. Sunumda bu dürüst okuma kullanılmalı: NO2 trafiği tek başına açıklamaz, ama trafik düşük günlerde belirgin biçimde daha düşük.
- Hava koşulu süzgeci (23 Kasım, yalnızca gösterim): ilişki özeti, NO2'nin yağış ve rüzgârdan etkilenmesini azaltmak için ayrıca "hava benzer" günleri inceler (`hava_ozet.benzer_hava`): günlük yağış 1 mm'nin altında, kıyas günlerinden (önceki 4 haftanın aynı günü) en fazla biri yağışlı, günlük ortalama rüzgâr kıyas günlerinin 0,75-1,33 katı. Bu eşikler karar kuralı değil gösterim süzgecidir. Hava verisi Open-Meteo tek nokta reanalysis olduğundan (istasyon ölçümü değil) süzgeç kabadır; sınır tabakası yüksekliği, sıcaklık/ısınma gibi etkenler dışarıda kalır.
- Sınırlar: (1) İndirme gerçek veriyle çalıştırıldı: 18 proje ayının tamamı, 28 istasyon, her ay için NO2 saatlerinin tamamı dolu (ör. Nisan 2023: 720/720). NO2 saat profili sabah 08:00'de tepe yapıyor; akşam 17-19 tepesi belirgin değil, en yüksek değerler gece 22:00-00:00 civarında (NO2 yalnız trafiği değil, sınır tabakası ve ısınma gibi etkenleri de yansıtır; bu yüzden sinyal tek başına kanıt sayılmaz). Gerçek günlerde kontrol edildi: 22.04.2023 (trafik 0,74, NO2 0,80), 10.04.2024 (trafik 0,61, NO2 0,49) trafikle uyumlu düşüş; 08.04.2024'te trafik 0,82 iken NO2 0,36 ve PM10 0,34 çıktı, yani kirlilik trafikten çok daha fazla düştü (O3 2,75 kat arttı); bu yağış veya rüzgâr gibi hava etkisini düşündürür. Bu yüzden NO2 ve PM10 birlikte düşükse sinyal metni "araç azalmasıyla tek başına açıklanamaz" der (kod birlikte_dusus_hava_olabilir). Bunun gerçek nedeni bu projede doğrulanmadı. (2) Şehir değeri istasyon medyanıdır, İstanbul'un tamamını eşit temsil etmez. (3) NO2'nin araç dışı kaynakları (ısınma, sanayi) ve rüzgâr/yağış etkisi vardır; sinyal nedensellik değil çakışmadır. (4) Eşikler (0.85/1.15) trafik için seçilmiştir; hava serisi için ayrıca kalibre edilmedi. (5) Hipotez puanlamasına katmak ayrı, önceden kaydedilmiş bir ölçüm gerektirir (gelecek çalışma).

- Saatlik gecikme, gün içi profil ve tespit özeti (üçüncü grup): yalnızca gösterim; bağıntı sıra bağıntısıdır (nedeni kanıtlamaz), 100 saatten az veride hesaplanmaz, hava verisi yoksa açık mesaj verilir. Tespit özeti bir sayımdır, doğruluk ölçüsü değildir.

## Rerank: yazıldı, ölçüldü, kapalı (23 Kasım)
- Bilgi tabanı aramasında kural tabanlı yeniden sıralama (TIMERCA_RERANK=1) var; varsayılan KAPALI. Ölçümde bir soru kümesinde iyileşme (ilk sonuç 14→16, MRR 0,804→0,850), diğerinde hafif gerileme (MRR 0,893→0,881) çıktı; ölçümden önce yazılan kabul ölçütü sağlanmadığı için açılmadı. Örneklem 20 ve 14 soru olduğundan fark kesin değildir. Ayrıntı: docs/09 bölüm 5.1, docs/11.

## Tatil haftaları ve bayram karşılaştırması (24 Kasım)
- **"Nisan 2024'te hangi haftalar tatilden etkilendi"** (`router_graph._tatil_haftalari`): ay, haftalara bölünür (hafta = ayın 1-7, 8-14, ... günleri; takvim haftası değildir, haftalık özetle aynı sözleşme). Bir hafta, takvimde en az bir resmî tatil günü varsa "etkilendi" sayılır. Tatil günlerinin trafik oranı mevcut tarama kuralıyla (`scan.classify`, 0.85/1.15) verilir; idari izin ve yarım gün yalnız takvim bağlamı olarak yazılır, "etkilendi" sayılmaz. Her hafta için tarih aralığı yazılır. "Bu ay" gibi göreli ifadede tarih uydurulmaz, yıl yoksa yıl tahmin edilmez.
- **"2023 Ramazan Bayramı ile Kurban Bayramı karşılaştır"** (`_bayram_karsilastir`): iki bayram (tek yıl) ya da aynı bayramın iki yılı. Cevap karşılaştırılan dönemleri ve tarih aralıklarını açıkça yazar ("Karşılaştırılan dönemler: ... (21-23 Nisan 2023, 3 gün) ile ... (28 Haziran 2023 - 1 Temmuz 2023, 4 gün)"), her dönem için ortanca oranı, düşüş eşiğinin altındaki günleri ve iki dönemin ortanca oran farkını verir. Yıl yazılmazsa tahmin edilmez, yüklü yıllar söylenir. Ay karşılaştırması da artık karşılaştırılan ayların tarih aralığını yazar.
- Sınırlar: yalnız `holidays` paketindeki resmî tatil günleri alınır (arife dahil değil). Karşılaştırma yeni bir karar kuralı değildir; her gün kendi önceki 4 haftasıyla kıyaslanır, iki dönem arasında mutlak trafik farkı ölçülmez. Veride olmayan bayram (ör. Kurban Bayramı 2024) için kapsam dışı cevabı verilir. Testler: `tests/bayram_hafta_test.py` (37 kontrol, sahte takvim ve sahte oranlarla), `tests/ui_ek_test.js` (T1, T2).

## Dokuz yeni soru özelliği (24 Kasım, gece)
Hepsi `router_graph.py` içinde; yeni bir karar kuralı yoktur, her biri mevcut taramanın (`scan`, aynı eşikler 0,85-1,15) sayımı ya da özetidir. Test: `tests/yeni_sorular_test.py` (52 kontrol) ve `tests/ui_ek_test.js` (Y1-Y10).
- **"Nisan 2024'te hangi gün en çok düştü / arttı"** (`_gun_siralama`): yalnız eşiği aşan günler sıralanır (oranın 1'den sapmasına göre), varsayılan ilk 3, "ilk 2 gün" gibi sayı yazılabilir. İçinde neden/nicin/niye geçen sorular eski "günü sen seç, neden düştü" yoluna gider.
- **"Nisan 2024'te kaç gün eksik veri vardı"** (`_eksik_veri_say`): taramadaki eksik veri, eksik veri ve sapma ve veri yok günlerini sayar ve listeler. Yalnız eksik saat payı %25'i aşan günler sayılır; küçük boşluklar sayılmaz (cevap bunu yazar). Hiç yüklü olmayan günler ayrıca belirtilir.
- **"Nisan 2024'te hafta içi ile hafta sonu karşılaştır"** (`_hafta_ici_sonu`): iki grubun ortanca oranı ve düşüş günü sayısı. Resmî tatil günleri iki gruptan da çıkarılır ve yazılır. Her gün kendi önceki 4 haftasıyla kıyaslandığı için mutlak trafik düzeyi değil, kendi normaline göre durum karşılaştırılır.
- **"Ramazan Bayramı 2023 öncesi ve sonrası trafik nasıl"** (`_bayram_oncesi_sonrasi`): bayramdan önceki 7 gün, bayram günleri, sonraki 7 gün (hafta sonları ve arife dahil), tarih aralıklarıyla. Bayram adı ve yıl gerekir (yılı tahmin etmez); "trafik" kelimesi geçmeyen "bayram öncesi idari izin" gibi sorular bilgi yolunda kalır.
- **Üç ay karşılaştırma**: "Şubat Mart Nisan 2024 karşılaştır" ya da "Mart 2023 ile Nisan 2024 ..."; en fazla 3 ay, dört ay istenirse açık mesaj verir. Özet "Karşılaştırılan aylar: A (aralık), B (aralık) ve C (aralık)" diye başlar.
- **Bayram karşılaştırmasında NO2 sütunu**: `hava_ozet.bayram_ozeti` varsa her dönem için NO2 ortanca oranı ve kaç günün verisi olduğu eklenir; yalnız ek bilgidir, sonucu değiştirmez. NO2 verisi yoksa sütun boş kalır, cümle yazılmaz.
- **"8-14 Nisan 2024 neden normaldi" / "Nisan 2024 2. hafta neden normaldi"** (`_normal_hafta`): gün gün oran ve eşikler; tüm günler normalse söyler, değilse eşik dışı günleri listeler. En fazla 14 gün. "Bu hafta" gibi göreli ifade tarih tahmin edilmeden reddedilir. Tek günlük "neden normal" yolu aynen çalışır ("normaldi" biçimi de artık tanınır).
- **Arayüz**: sonuç tablolarındaki günler tıklanabilir; tıklayınca 2. bölümde o günün 00:00-23:00 penceresi doldurulur ve inceleme başlar. "Bilgi eksik" cevabında mesajdaki örnek sorular (en çok 3) "Tek tıkla dene" düğmesi olur; mesajda örnek yoksa yüklü örnek sorulardan 3'ü gösterilir. CSV ve Markdown indirmeleri yeni tabloları da içerir.
