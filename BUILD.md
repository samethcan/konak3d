# Masaüstü uygulaması (.exe) oluşturma

Windows'ta, Python 3.11+ kurulu bir makinede:

```bat
git clone https://github.com/samethcan/konak3d.git
cd konak3d
python -m venv .venv && .venv\Scripts\activate
pip install -e . pyinstaller
git clone https://github.com/ChaoningZhang/MobileSAM %TEMP%\MobileSAM
pip install -e %TEMP%\MobileSAM

mkdir models
copy %TEMP%\MobileSAM\weights\mobile_sam.pt models\

pyinstaller konak3d.spec
```

Sonuç: `dist\konak3d.exe`. Çift tıklayınca arayüz açılır.

## Notlar

- Paket boyutu büyük olur (PyTorch ve GDAL yaklaşık 1,5-2 GB). Daha küçük bir kurulum için `--onedir` tercih edin; `konak3d.spec` içindeki `EXE(...)` satırını `COLLECT` ile değiştirmek gerekir.
- `models/mobile_sam.pt` yoksa uygulama açılır ama model dosyasını elle seçmenizi ister.
- Arayüz Tkinter kullanır; Windows ve macOS'ta Python ile birlikte gelir. Linux'ta `python3-tk` paketi gerekebilir.
- Antivirüs PyInstaller çıktısını bazen karantinaya alır; kurum bilgisayarında dağıtmadan önce BT birimine imzalatın.
- Komut satırını tercih ederseniz arayüze gerek yok: `konak3d --help`.

## Arayüzden çalıştırma (kaynaktan)

```bash
konak3d gui
# veya
python -m konak3d gui
```
