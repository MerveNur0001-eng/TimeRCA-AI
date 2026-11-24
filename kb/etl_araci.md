# Veri kalitesi ve ETL log aracı: check_etl_log

Girdi: başlangıç ve bitiş zamanı. Çıktı: pencereye değen veya pencereye 1 saat içinde bitişik eksik saat blokları, düşük hücre kapsamı saatleri, yoğunluk şüpheli saatler.
Blok pencereyle çakışıyorsa overlaps_window true olur. Pencere ay sınırını aşarsa ilgili tüm ayların logu okunur, logu olmayan aylar months_without_log alanında bildirilir.
Sınır: log yalnızca bizim yüklememizde görülenleri kaydeder, boşluğun nedenini söylemez.
