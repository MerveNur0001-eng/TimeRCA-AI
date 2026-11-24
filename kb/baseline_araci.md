# Beklenen düzey (baseline) aracı: compare_same_weekday_history

Girdi: başlangıç ve bitiş zamanı. Baseline: önceki 4 haftanın aynı gün ve saatinin medyanı, en az 3 geçerli hafta gerekir, yoksa o saat için baseline yok denir.
Çıktı: temiz saatlerin medyan oranı (median_ratio_excl_etl_flagged), ETL'in işaretlediği saat sayısı, 0,7 altı ve 1,3 üstü temiz saat sayıları, en sapan temiz saatler, baseline günleri (baseline_days_of_first_hour).
ETL'in işaretlediği saatler ayrı sayılır, aksi halde tek bozuk saat günün özetini bozar.
Sınır: tatil veya yağışlı haftalar baseline'ı kirletebilir, baseline günlerini takvim ve hava aracıyla kontrol et. Saatlik oranlar gürültülüdür, çok saatlik ve günlük düzeye güvenilir.
Örnek: 4 Mayıs 2023 baseline Perşembe'leri (6, 13, 20, 27 Nisan) günlük toplamda birbirine yakındı (4,05-4,16 milyon), sapma baseline kirliliğinden gelmiyor gibi görünüyor.
