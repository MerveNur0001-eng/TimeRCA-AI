# 15 - Demo kontrol listesi

## Hazırlık
- [ ] cd C:\Users\Merve\TimeRCA-AI ; .\.venv\Scripts\Activate.ps1
- [ ] python tests\run_all.py -> TUMU TEMIZ
- [ ] node tests\ui_date_test.js (19 kapı), node tests\ui_range_test.js (22 kapı) ve node tests\ui_ek_test.js (16 kapı)
- [ ] python src\api.py (127.0.0.1:8000), tarayıcıda Ctrl+F5
- [ ] Demo bilgisayarında tarayıcı dili Türkçe (g1/g2 ve t1/t2 yerel tarih kutuları bu dile göre görünür)
- [ ] Prova sonrası logs\feedback.sqlite test kayıtları temizlendi (yedek alınarak)

## Akışlar (beklenen değerler provada doğrulanacak)
1. Hızlı örnekler: Kurban 2023 (~0,63), Ramazan 2024 (~0,65), Cumhuriyet 2022 (~0,83); yalnız tatil hipotezi destekleniyor.
2. Hava destekleyen günler: 22.11.2022 (0,81), 28.09.2023 (0,81), 06.05.2023 (1,17), 12.01.2022 (1,19). 22.03.2023'ü örnek olarak kullanmayın.
3. İnsan onayı: 25.01.2022 (oran 0,56) -> açıklanamayan + insan onayı. Reddet akışında iddia aynı araçlarla sınanır, otomatik kabul edilmez.
4. 23.04.2024: gün düzeyinde sapma yok; bölge 05-11 arası tatil destekliyor.
5. 28.04.2024: ETL işaretli saat oranı yüksek (14 saat); veri hatası destekleniyor, açıklanamayan desteklenmiyor (flag_share_test).
6. 01.01.2023 ve 27.08.2024 (27.08.2024'te veri yok mesajı).
7. Tarih doğrulaması: boş tarih, ters aralık, 63 günlük günlük görünüm, 15 günlük saatlik görünüm -> Türkçe mesajlar.
8. Hava kalitesi ek sinyali: 10 Nisan 2024 trafik neden düştü (trafik ve NO2 birlikte düşük) ve 08.04.2024 (NO2 ve PM10 trafikten çok daha fazla düşmüş; hava etkisi olabilir uyarısı). Kutu karar kuralını değiştirmez.

## Anlatım notları
- Sistem neden uydurmaz: kanıt yoksa kesin sonuca varmaz, insana sorar (docs/14, docs/13).
- Sınırları doğrudan söyleyin: hava tek nokta reanalysis, deprem USGS, okul tatili/arife yarım günü yok.
## n8n demo notları
- Akış n8n'de kayıtlı (Authentication: None). Yeniden içeri alma, kayıtlı akışı kullanın. Değişiklikten sonra Ctrl+S.
- API'yi anahtarsız başlatın (TIMERCA_API_KEY tanımsız olmalı): python src\api.py
- SORU değeri: 25.01.2022 anomali incele. Execute workflow -> ONAY FORMU -> reddet -> RET FORMU (Executions'taki bekleyen çalıştırmanın form adresi).
- Eski askıda kalan çalıştırmaları (form-waiting/NN) kapatın, göndermeyin.
- Aynı anda arayüzü ve n8n akışını çalıştırmayın (analiz istekleri sıralanır, aynı anda tek analiz çalışır).
- Demo sonrası test kaydını temizleyin (Blok 2).
## KB veya RAG dizini değiştiyse
- API'yi açmadan önce: python -c "import sys; sys.path.insert(0,'src'); import rag; print(rag.index_status())" -> ok True olmalı. False ise Ollama açıkken rag.build_index() çalıştırın.
- kb_check.py (59/59) ve rag_selftest.py (19/19) run_all içinde değil, elle koşulur; Ollama açık olmalı.

## Ek demo örneği: gerçek sel, sistem uydurma yapmıyor
- "05.09.2023 anomali incele": sapma yok (0,90), otomatik tamamlandı, hava aracı çağrılmadı. 2. bölümde 05.09.2023 18:00 - 06.09.2023 01:00 penceresi aynı sonucu verir. Anlatım: gerçek bir sel vardı (İPA notu), ama trafik toplamında sapma yok ve hava aracı tek nokta olduğu için yerel sağanağı görmüyor; docs/14'e bakın.
