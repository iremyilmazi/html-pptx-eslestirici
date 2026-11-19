# HTML → PPTX Çeviri Eşleştirici (yerel / offline)

Bu proje, **çevirisi HTML dosyalarına dağılmış mevcut bir sunum** için güvenli bir eşleştirme iş akışı sağlar. Orijinal PPTX'i yeniden tasarlamaz; seçilen metin kutularının yazısını değiştirir. Tüm işlemler bilgisayarınızda gerçekleşir. **Dosyalar hiçbir sunucuya gönderilmez.**

> **Önemli:** HTML'de slayt sınırları veya orijinal kaynak metin eşleştirmesi yoksa otomatik, hatasız slayt/metin eşleştirmesi garanti edilemez. Bu nedenle güvenli varsayılan **manuel onay**dır. `suggested_*` sütunları otomatik hizalama önerileridir; doğrulama olmadan uygulanmamalıdır.

## Desteklenen HTML yapıları

- `<p>`, `<h1>`–`<h6>`; iç içe `<strong>` / diğer inline etiketler metin olarak okunur.
- `<br>` yeni satır olarak korunur.
- Boş paragraflar atlanır.
- `<div class="table-scroll"><table>...</table></div>` içindeki her tablo hücresi ayrı `table_cell` olarak envantere alınır.
- Üç veya daha fazla `.html` / `.htm` dosyası, **dosya adına göre alfabetik sıralanarak** işlenir. Dosyaları `01_`, `02_`, `03_` şeklinde adlandırın.

## Windows 11 – adım adım kurulum

1. Bilgisayarınıza Python 3.11 veya 3.12 kurun (kurum politikasına uyun). Kurulumda `Add Python to PATH` seçeneğini açın. Python zaten varsa yeniden kurmayın.
2. Bu projeyi ZIP olarak indirin, örneğin `C:\html-pptx-eslestirici` klasörüne çıkarın.
3. Windows Komut İstemi’ni (CMD) açın. Proje klasörüne geçin. Sanal ortamınız zaten etkinse `py -3 -m venv .venv` ve etkinleştirme adımlarını atlayıp bağımlılıkları kurun.

   ```cmd
   cd /d "C:\html-pptx-eslestirici"
   py -3 -m venv .venv
   .venv\Scripts\activate.bat
   python -m pip install -r requirements.txt
   ```

   CMD satırının başında `(.venv)` görünüyorsa sanal ortam etkindir. Yeni bir CMD penceresi açarsanız proje klasörüne geçip `.venv\Scripts\activate.bat` komutunu tekrar çalıştırın.

4. Aynı klasörde `veri` adında bir klasör oluşturun. Sunumu ve HTML dosyalarını bu klasöre koyun:

   ```text
   html-pptx-eslestirici/
   ├─ src/main.py
   ├─ requirements.txt
   ├─ veri/
   │  ├─ orijinal.pptx
   │  └─ html/
   │     ├─ 01_ceviri.html
   │     ├─ 02_ceviri.html
   │     └─ 03_ceviri.html
   └─ cikti/ (otomatik oluşur)
   ```

5. Envanter ve eşleştirme şablonunu üretin:

   ```cmd
   python src\main.py hazirla --pptx "veri\orijinal.pptx" --html-dir "veri\html" --output "cikti"
   ```

6. `cikti\pptx_envanter.csv` dosyasını Excel ile açın: Slayt numarası (`slide`), metin kutusu kimliği (`shape_id`), türü ve orijinal metin listelenir. `cikti\html_bloklar.csv` tüm çeviri bloklarını listeler.

7. `cikti\eslestirme_sablonu.csv` dosyasını Excel ile açın. **Her çevrilecek blok için** `target_slide` ve `target_shape_id` alanlarını envanterdeki doğru hedefe göre doldurun. HTML tablo hücreleri için ayrıca **1’den başlayan** `target_row` ve `target_col` değerlerini doldurun. Sonra `apply` alanına `EVET` yazın. `suggested_slide` / `suggested_shape_id` sütunları **doğrulanmış değildir**, fakat otomatik önerilen hedefler `target_*` alanlarına da önceden yazılır; `apply` boş kaldığı için hiçbir değişiklik onaysız uygulanmaz. Excel'de `CSV UTF-8 (Comma delimited)` olarak kaydetmeyin: Bu proje **noktalı virgül ayrımlı UTF-8 BOM CSV** kullanır. Excel `CSV UTF-8` seçeneği ayırıcıyı değiştirebiliyorsa, dosyayı Notepad veya VS Code'da `;` ayırıcısı korunacak şekilde kaydedin.

8. Onaylanmış metin kutularını güncelleyin:

   ```cmd
   python src\main.py uygula --pptx "veri\orijinal.pptx" --mapping "cikti\eslestirme_sablonu.csv" --output "cikti\cevrilmis.pptx"
   ```

9. Oluşan dosyayı PowerPoint'te açıp özellikle uzun metin, font, satır atlaması, grafik, animasyon ve tabloları kontrol edin.

## Tablolar hakkında önemli sınırlama

HTML tablo hücreleri ayrı `table_cell` satırlarına ayrılır. Envanterde tablo `shape_id`'sini bulun. Hedef tablonun **1’den başlayan** satır/sütun numaralarını (`target_row`, `target_col`) **tek tek onaylayın**. Birleşik hücrelerde özellikle dikkatli olun: hedef hücrenin kaplanan (`spanned`) konumu reddedilir. HTML tablonun PPTX tablosuyla boyut olarak aynı olduğu varsayılmaz.

## Bilinen sınırlamalar

- Metin kutularında birden fazla renk/bold/run kullanılmışsa yazı değişimi ilk run'ın biçimini kullanır; paragraf içi kısmi biçimlendirme korunmayabilir.
- Slaytların animasyon ve geçiş nesneleri genellikle dosyada kalır, ancak bire bir koruma için PowerPoint kontrolü gerekir.
- Resim üzerindeki yazılar, SmartArt, bağlı grafik yazıları, gruplanmış şekiller ve slide master metinleri işlenmez.
- Aynı metin alanını iki kez değiştirmeye çalışmak hata oluşturur. Hata olursa **çıktı PPTX kaydedilmez**.
- HTML/PPTX içerikleri burada kullanılmadığından gerçek dosyalardaki uyumluluk ayrıca test edilmelidir.

## Güvenlik

- Gizli dosyaları GitHub'a, e-postaya ya da çevrimiçi araca yüklemeyin.
- `.gitignore` sunum/HTML/CSV/XLSX verilerini engellemek için hazırlanmıştır. Yine de `git status` ile commit öncesi dosyaları kontrol edin.
- Orijinal PPTX'e yazılmaz; çıktı ayrı dosyaya kaydedilir.

## Sorun giderme

`py tanınmıyor`: `python --version` komutunu deneyin; Python kurulumunu ve PATH'i kontrol edin.

`ModuleNotFoundError`: `pip` komutu yerine yukarıdaki `python -m pip install -r requirements.txt` komutunu kullanın.

`PermissionError`: Sunumu PowerPoint'te kapatın veya başka bir çıktı dosya adı seçin.

`Hedef shape bulunamadı`: CSV'de hedef slayt/shape kimliğini `pptx_envanter.csv` ile karşılaştırın.

`Tablo hücre satır/sütun indeksi geçersiz`: Hedef tabloyu açıp hücre numaralarını 1’den başlayarak kontrol edin.

## Şirket içi kullanım için önerilen iş akışı

İlk denemede yalnızca 2–3 metin kutusuna `EVET` yazın. Çıktıyı PowerPoint'te doğrulayın, sonra diğerlerini açın. Özellikle finansal tabloları ve kritik metrikleri iki kişiyle kontrol edin.

## v2: Otomatik eşleştirme ve yerel kontrol ekranı

`hazirla` komutu artık otomatik öneriler üretir. HTML ve sunumdaki sıralamayı, rakamları, yüzdeleri, kelime/metin benzerliğini, metin uzunluğunu ve tablo-metinkutusu türünü birleştiren **monoton dizi hizalama** kullanır. Çıktıdaki `confidence` (`yuksek`, `orta`, `dusuk`, `eslesmedi`) yalnızca **kural tabanlı kontrol önceliğidir, istatistiksel doğruluk olasılığı değildir**. İngilizce-Türkçe çeviri semantiğini anlamaz; benzer sayılar veya sıra bazen yanıltıcı olabilir. **Her satırın insan tarafından onayı gerekir.**

### Kontrol ekranını açma

`hazirla` komutunu çalıştırdıktan sonra şu komutu yazın:

```cmd
python src\gui.py --mapping "cikti\eslestirme_sablonu.csv" --inventory "cikti\pptx_envanter.csv"
```

- **Filtre:** Onaysız, düşük/eşleşmedi, orta, yüksek ve onaylı satırları filtreleyin.
- **Üstteki liste:** Kaynak çeviriyi, güven etiketini, önerilen hedefi ve onayı gösterir.
- **Alt alanda:** Seçili çeviri ve önerilen PPTX şeklinin mevcut metni yer alır.
- **Hedef slayt / şekil ID:** Öneri yanlışsa envanterden doğru numarayı girin. PPTX tablo hücresinde satır ve sütun **1'den başlar**.
- **Hedefi önizle:** Seçilen PowerPoint şeklinin içeriğini kontrol edin.
- **Hedefi kaydet:** Manuel değiştirdiğiniz hedefi kaydedilecek eşleştirmeye işler.
- **Onayla:** Satırın `apply` alanına EVET yazar; `Onayı kaldır` geri alır.
- **Kaydet (Ctrl+S):** CSV'yi UTF-8 BOM ve `;` ayracıyla kaydeder.

Arayüzdeki tüm dosya işlemleri bilgisayarınızda yapılır. `tkinter` genellikle resmi Windows Python kurulumuyla gelir. Hata alırsanız `python -m tkinter` komutuyla test edin.

### Tam akış

Bu komutları sanal ortam etkinken CMD’de çalıştırın.

```cmd
cd /d "C:\html-pptx-eslestirici"
python src\main.py hazirla --pptx "veri\orijinal.pptx" --html-dir "veri\html" --output "cikti"
python src\gui.py --mapping "cikti\eslestirme_sablonu.csv" --inventory "cikti\pptx_envanter.csv"
python src\main.py uygula --pptx "veri\orijinal.pptx" --mapping "cikti\eslestirme_sablonu.csv" --output "cikti\cevrilmis.pptx"
```

**Mutlaka kontrol edin:** Çevirisi farklı dilde olan uzun bloklarda otomatik hizalama yanlış yapabilir. Aynı slayttaki bir metin kutusu birden çok HTML paragrafa karşılık geliyorsa bu sürüm bunları otomatik birleştirmez. PDF, SmartArt, grafik gömülü etiketleri ve grup içi metin kutuları işlenmez. Uzun metinlerin taşma kontrolü PowerPoint'te gereklidir.

### Veri güvenliği

Program verileri çevrimiçi servislere göndermez, bulut AI veya harici API kullanmaz. `veri/` ve `cikti/` klasörleri Git tarafından hariç tutulur. İş amaçlı dosyaları **public GitHub reposuna asla göndermeyin**; yalnızca kaynak kodu ve sahte test verileri yayınlayın.
