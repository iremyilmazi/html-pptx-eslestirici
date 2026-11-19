# GitHub'a yayınlama (yalnızca kaynak kod)

Bu projeyi yeni, istenen şekilde **public** bir repository'de saklamak daha güvenlidir. Aşağıdaki komutlar Git for Windows yüklüyse PowerShell'de çalışır. Şirket verilerini repository'ye **koymayın**.

1. GitHub'da `html-pptx-eslestirici` adlı yeni bir repository oluşturun. **Public** seçin (kurumunuzun açık kaynak paylaşım politikasını kontrol edin). `Initialize with README` işaretlemeyin.
2. Kaynak kodu çıkardığınız klasörde PowerShell açın:

```powershell
cd C:\html-pptx-eslestirici
git init
git branch -M main
git add README.md GITHUB_YAYINLAMA.md requirements.txt .gitignore src examples tests
git status
git commit -m "Add offline HTML PPTX alignment and review GUI"
git remote add origin https://github.com/KULLANICI_ADINIZ/html-pptx-eslestirici.git
git push -u origin main
```

`git status` çıktısında gizli şirket dosyaları, HTML/PPTX veya CSV görürseniz **push yapmayın**. Bu proje kullanıcıya teslim edildiğinde GitHub'a otomatik yüklenmiş sayılmaz.
