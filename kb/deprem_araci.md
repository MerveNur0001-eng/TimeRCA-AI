# Deprem aracı: get_earthquakes

Kaynak: USGS FDSN, önceden indirilmiş yerel katalog (2021-11/2022-02, 2022-09/2022-12, 2023-02/2024-02 ve 2024-03/2024-05 aralıkları). USGS saatleri UTC, yerel saate +3 saat çevriliyor.
Tamlık: USGS belgelerine göre dünya genelinde yaklaşık M4,5'e kadar tam (docs/05). M4-4,5 arası eksik olabilir.
İlgili deprem kuralı: M>=4,5 ve İstanbul'a en fazla 500 km, veya M>=6,5 her mesafe. Eşikler seçimdir, trafik etkisi için bilinen bir eşik değildir.
Araç pencerenin başlangıcından önceki 12 saati de tarar, bu yüzden olay pencereden önce olmuş olabilir (inside_window alanı).
Büyüklük ve mesafe tek başına neden sayılmaz: zaman sırası ve trafik sapması da uyumlu olmalı.
AFAD API'si geçmiş sorgulara boş döndü, kullanılmıyor.
