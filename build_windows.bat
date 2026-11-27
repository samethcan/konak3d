@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title konak3d - Windows exe uretimi

set "ROOT=%USERPROFILE%\konak3d-build"
set "SRC=%ROOT%\konak3d-main"
set "VENV=%ROOT%\venv"

echo.
echo ========================================
echo   konak3d - Windows exe uretimi
echo ========================================
echo   Klasor : %ROOT%
echo   Sure   : yaklasik 15-30 dakika
echo   Indirme: yaklasik 700 MB
echo ========================================
echo.
pause

where python >nul 2>&1
if errorlevel 1 (
  echo [HATA] Python bulunamadi.
  echo        https://www.python.org/downloads/windows/ adresinden kurun.
  echo        Kurulumda "Add python.exe to PATH" kutusunu isaretleyin.
  pause & exit /b 1
)
for /f "tokens=2" %%v in ('python -V 2^>^&1') do set PYV=%%v
echo [1/7] Python %PYV% bulundu.

if not exist "%ROOT%" mkdir "%ROOT%"
cd /d "%ROOT%" || (echo [HATA] Klasore girilemedi & pause & exit /b 1)

echo [2/7] Kaynak kod indiriliyor...
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'https://github.com/samethcan/konak3d/archive/refs/heads/main.zip' -OutFile '%ROOT%\src.zip' -UseBasicParsing}catch{exit 1}"
if errorlevel 1 (echo [HATA] Kaynak kod indirilemedi. Internet/proxy kontrol edin. & pause & exit /b 1)
if exist "%SRC%" rmdir /s /q "%SRC%"
powershell -NoProfile -Command "Expand-Archive -Path '%ROOT%\src.zip' -DestinationPath '%ROOT%' -Force"
if not exist "%SRC%\konak3d.spec" (echo [HATA] Arsiv acilamadi. & pause & exit /b 1)

echo [3/7] Sanal ortam kuruluyor...
if not exist "%VENV%" python -m venv "%VENV%"
call "%VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet

echo [4/7] PyTorch (CPU surumu) kuruluyor... en uzun adim
pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 (echo [HATA] PyTorch kurulamadi. & pause & exit /b 1)

echo [5/7] Bagimliliklar ve konak3d kuruluyor...
cd /d "%SRC%"
pip install --quiet -e . pyinstaller timm
if errorlevel 1 (echo [HATA] Bagimliliklar kurulamadi. & pause & exit /b 1)
pip install --quiet "https://github.com/ChaoningZhang/MobileSAM/archive/refs/heads/master.zip"
if errorlevel 1 (
  echo        zip ile olmadi, git ile deneniyor...
  pip install --quiet "git+https://github.com/ChaoningZhang/MobileSAM.git"
  if errorlevel 1 (echo [HATA] MobileSAM kurulamadi. & pause & exit /b 1)
)

echo [6/7] Model dosyasi indiriliyor... 40 MB
if not exist "%SRC%\models" mkdir "%SRC%\models"
if not exist "%SRC%\models\mobile_sam.pt" (
  powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt' -OutFile '%SRC%\models\mobile_sam.pt' -UseBasicParsing}catch{exit 1}"
  if errorlevel 1 (echo [HATA] Model indirilemedi. & pause & exit /b 1)
)

echo [7/7] exe derleniyor... birkac dakika surebilir
pyinstaller --noconfirm konak3d.spec
if not exist "%SRC%\dist\konak3d.exe" (
  echo [HATA] exe uretilemedi. Yukaridaki mesajlari kopyalayip gonderin.
  pause & exit /b 1
)

echo.
echo ========================================
echo   BITTI
echo   Dosya: %SRC%\dist\konak3d.exe
echo ========================================
explorer "%SRC%\dist"
pause
