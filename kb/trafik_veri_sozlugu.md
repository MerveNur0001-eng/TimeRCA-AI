# İBB Saatlik Trafik Yoğunluğu: Alanlar

Kaynak: İBB Açık Veri Portalı, saatlik trafik yoğunluğu veri seti (docs/05-dogrulama.md'de doğrulandı).

- DATE_TIME: saatlik damga. Saat dilimi sözlükte belirtilmemiş. Yerel saat varsayılıyor (gece dibi 03:00).
- GEOHASH: uzunluğu 6 olan hücre kodu.
- NUMBER_OF_VEHICLES: o saatte o hücredeki farklı araç sayısı.
- total_vehicles (bizim seri): hücre sayılarının toplamı. Bir araç birden fazla hücrede sayılabilir (çıkarım). Bu bir trafik hacmi göstergesidir, şehirdeki gerçek araç sayısı değildir.
- Hız alanları kullanılmadı. Nisan 2023'te maksimum hız değerlerinin %8,8'i 150 km/sa üstündeydi (sensör gürültüsü olabilir, doğrulanmadı).
