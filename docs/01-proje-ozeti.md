# 01 - Proje Özeti

## Problem
Zaman serisinde ani düşüş veya sıçrama olduğunda, nedenin veri hatası mı yoksa gerçek bir dış olay mı olduğunu ayırt etmek zaman alır.

## Çözüm
Anomaliyi kodla tespit eden, ardından araç çağırarak ve RAG ile kanıt toplayan, hipotezleri güven skoruyla değerlendiren ve emin olamadığında insana soran bir ajan. Sayıları, araç seçimini ve hipotez puanlarını kod hesaplar; LLM serbest soruyu araç çağrısına çevirir, kanıtları açıklar ve emin olunmadığında insana sorulacak soruyu yazar.

## Kapsam (ilk sürüm)
- Şehir: İstanbul. Yüklü veri: 18 ay (2021-12; 2022-01, 10, 11; 2023-01 ile 09 arası; 2023-11, 12; 2024-01, 03, 04). Eşik ayarı ve pilot: Nisan 2023. İlk planda Ocak-Mayıs 2023 (beş ay) vardı, kapsam sonradan genişledi.
- Ana seri: saatlik toplam araç sayısı (trafik hacmi göstergesi).
- Hipotez sınıfları: (a) veri hatası, (b) hava, (c) resmî tatil/bayram, (d) deprem/afet, (e) açıklanamayan.
- Deprem sınıfı: pilotta olumlu vaka yok. 6 Şubat 2023'te trafikte iz görülmedi (günlük düzey -%6). Sınıf, "olay olsa bile trafikte iz yoksa deprem deme" davranışını test etmek için tutuluyor.

## Sürdürülebilirlik çerçevesi
Trafik, elektrik tüketimi ve hava kalitesi şehir sürdürülebilirliğinin izlenen göstergeleridir. Ajan, bu göstergelerdeki olağandışı değişimin nedenini kanıtla açıklamayı amaçlar (BM SKH 11 ve 7 ile ilişkili). Uygulanan seri yalnızca İBB saatlik trafiğidir. Elektrik tüketimi (EPİAŞ) ve hava kalitesi planlanan uygulama alanlarıdır; erişim, geçmiş uzunluğu ve saatlik çözünürlük doğrulanmadı, hiçbiri denenmedi.

## Kapsam dışı
Etkinlik takvimi, tüm Türkiye, MGM istasyon verisi, canlı veri akışı. Yol çalışması verisi (araştırmada İBB'den açık veri seti bulunamadı) ve okul tatili takvimi (araç yok; MEB takvimi v4 adayı).

## Başarı ölçütü
20-30 etiketli senaryoda kök neden doğruluğu tablosu ve hata analizi. Etiketler araçların kendi kurallarından üretilmez (döngüsel ölçüm olur); etiket kaynağı 9-13 Kasım'da belirlenecek.

## Güncel durum (17 Kasım 2026)
Çalışan bileşenler: 5 araç (MCP üzerinden), LangGraph ajanı (HITL dahil), rapor katmanı (olası nedenler, kanıt türü, genel değerlendirme, kaynak bilgisi), anomali taraması, trafik yoğunluğu grafiği ve tek sayfalık arayüz, geri bildirim kaydı, n8n akışı. Değerlendirme: v0-v3 (docs/07), yalnızca v3 bağımsızdır. v3 sonrası eklenenler ve ölçülmemiş kısımlar docs/09 bölüm 10 ve docs/07 sonunda ayrı yazılıdır.
