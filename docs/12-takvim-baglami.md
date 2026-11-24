# 12 — Takvim bağlamı ve araştırılan ek kanıt kaynakları (18 Kasım 2026)

Bu belge, n8n'e geçmeden önce yapılan "araç ve kanıt çeşitlendirme" turunu kaydeder. Eklenen şey **kanıttır, karar kuralı değildir**.

## 1. Eklenen: takvim bağlamı (`src/calendar_ctx.py`, `get_calendar` genişletmesi)

`get_calendar` artık her gün için şu alanları da döndürür (mevcut alanlar aynen durur):

| Alan | Anlamı |
|---|---|
| `half_day`, `half_day_note` | Arife yarım gün; açıklama ve kaynak |
| `admin_leave`, `admin_leave_note` | Kamu idari izni; kaynak |
| `school` | `tatil` / `ders` / `hafta_sonu` / `resmi_tatil` / `bilinmiyor` |
| `school_note` | Okul tatilinin adı ve kaynağı |

`evidence.py` pencerede bu alanlardan biri varsa notlara tek satır ekler: `Takvim bağlamı (kanıt, karar kuralına girmez): ...`. Hipotezler, güven ve `needs_human` değişmez.

### Tabloya giren tarihler (her biri kaynaklı)
- Arife yarım gün: 20 Nisan 2023, 27 Haziran 2023, 9 Nisan 2024.
- İdari izin (kamu): 26–27 Haziran 2023.
- MEB ulusal takvimi: 17–20 Nisan 2023 ara tatil; 17 Haziran – 10 Eylül 2023 yaz tatili; 13–17 Kasım 2023; 22 Ocak – 2 Şubat 2024; 8–12 Nisan 2024; 15 Haziran – 8 Eylül 2024.
- Okul kapsamı: 1 Mart 2023 – 8 Eylül 2024. Dışı `bilinmiyor` döner.

### Bilerek tabloya girmeyenler
- 8 Nisan 2024 idari izni: kaynak yalnızca koşullu ("kararlaştırılması durumunda") yazıyor, doğrulanmadı.
- Ocak–Şubat 2023 okul takvimi: deprem sonrası açılış tarihleri kaynaklarda farklı.
- 28 Ekim yarım günü ve 2024 Kurban arifesi: bu turda kaynak bulunmadı.

## 2. Sınırlar
- `school = ders` yalnızca "ulusal takvimde tatil kaydı yok" demektir. İl/ilçe kapanışları (kar tatili vb.) ve İstanbul il takvimi farkı yoktur.
- Tabloda olmayan gün "yok" demek değildir.
- Seçim günü, maç, konser, yol çalışması yoktur (aşağıya bakın).
- Bağlam notu yalnızca ölçülebilir trafik varken ve bağlam araçları çağrıldığında çıkar. Tüm saatleri eksik pencerede (ör. 19 Nisan 2023 09–12) çağrılmaz; bu bilinçli davranıştır.

## 3. Doğrulama
- `calendar_ctx_test`: 16/16 (gerçek takvim üzerinde).
- `calendar_note_test`: 11/11. Bağlam alanları silinince sonuç, not dışında birebir aynı kalır; bağlamsız pencerelerde çıktı değişmez; okul tatiline düşen ölçülebilir üç pencerede not çıkar.
- `run_all`: 14 adım temiz.
- Bu bir **doğrulama testidir, değerlendirme değildir.** v3 sonucu (13 etiketli pencerede 11/13, yanlış alarm 0/7) değişmedi. Bağlam notu karar kuralına girerse "v4, ölçülmemiş" olarak etiketlenmelidir.

## 4. Araştırıldı, eklenmedi
- **İBB Saatlik Toplu Ulaşım Veri Seti** (talep tarafı çapraz kontrol adayı): aylık CSV'ler Ocak 2020 – Aralık 2024 arası. Nisan 2023 dosyası yaklaşık 1,5 GB; datastore yalnızca 99 satır içeriyor, yani API üzerinden okumak eksik veri verir. Ham işlem düzeyinde (tarih, saat, hat, ilçe, ürün türü, geçiş/yolcu sayısı). 2025–2026 için kaynak bulunamadı. Uygulanmadı; zaman kalırsa ve indirme boyutu onaylanırsa yapılır.
- **Etkinlik/konser/maç** ve **yol çalışması/kazı:** İBB düzeyinde açık veri seti bulunamadı (aramada yalnızca başka şehirlerin verisi çıktı). Bu, yokluğun kanıtı değil, bulunamadığının kaydıdır. Sınır olarak kalır.
- **Ek deprem kaynağı (AFAD/Kandilli):** bu turda araştırılmadı; yalnızca USGS kullanılıyor.

## ETL'de işaretli saat payı kuralı (v4, ölçülmemiş)

**Sorun.** 28 Nisan 2024 tam gün incelendiğinde 24 saatin 14'ü ETL tarafından işaretliydi (n_cells çöküşü), eksik saat yoktu. Temiz saatlerde sapma bulunmadığı için sonuç "belirgin sapma yok, güven orta, otomatik tamamlandı" çıkıyordu. Bu sonuç yanıltıcıydı: günün çoğu zaten güvenilir değildi.

**Kural.** İşaretli saat payı >= 0.25, eksik saat payı < 0.25 ve temiz saatlerde sapma yoksa `veri_hatasi = destekliyor`, `aciklanamayan = desteklemiyor` olur ve nota nedeni yazılır. Eşik, eksik saat kuralıyla aynıdır (GAP_SHARE).

**Kapsam (dry-run, 882 takvim günü: 2021-12-01 ... 2024-04-30; bunlardan 523'ünde en az bir saatlik veri var, 21168 saatin 12189'u dolu).** İlk önerilen geniş kural (işaretli + eksik payı) 24 günü yakaladı. Bunların 23'ünde sorun eksik saatti ve sistem zaten veri hatası diyordu, bu yüzden kural yalnızca işaretli saat payına daraltıldı. Daraltılmış kural bu dönemde yalnız 2024-04-28'i etkiler.

**Durum.** Bu bir karar kuralı değişikliğidir ve ölçülmemiştir. v3 değerlendirmesi (13 dışarıdan etiketli pencere) bu kuralla yeniden çalıştırılmadı. `flag_share_test.py` bir doğrulama testidir, değerlendirme değildir: 28 Nisan'ın değiştiğini, 24 günlük kümede başka günün değişmediğini, 29 Nisan 2024 ve 19 Nisan 2023'ün etkilenmediğini kontrol eder.