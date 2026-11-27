"""konak3d - Windows kurulum ve exe uretimi.

Cift tiklayin. Python 3.11+ kurulu olmasi yeterli.
Betik kaynak kodu indirir, sanal ortam kurar, bagimliliklari yukler,
model dosyasini ceker ve dist/konak3d.exe uretir.
"""
import os, sys, subprocess, urllib.request, zipfile, shutil, time, platform

ROOT = os.path.join(os.path.expanduser("~"), "konak3d-build")
SRC = os.path.join(ROOT, "konak3d-main")
VENV = os.path.join(ROOT, "venv")
SRC_ZIP = "https://github.com/samethcan/konak3d/archive/refs/heads/main.zip"
SAM_ZIP = "https://github.com/ChaoningZhang/MobileSAM/archive/refs/heads/master.zip"
WEIGHTS = "https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt"
STEPS = 7

def head(i, msg): print(f"\n[{i}/{STEPS}] {msg}", flush=True)
def die(msg):
    print("\n[HATA] " + msg)
    print("\nYukaridaki mesaji kopyalayip gonderin.")
    input("\nKapatmak icin Enter'a basin...")
    sys.exit(1)

def run(args, cwd=None):
    print("    > " + " ".join(str(a) for a in args[-3:]), flush=True)
    p = subprocess.run(args, cwd=cwd)
    return p.returncode == 0

def download(url, path, label):
    def hook(b, bs, total):
        if total > 0:
            pct = min(100, b * bs * 100 // total)
            print(f"\r    {label}: %{pct}", end="", flush=True)
    urllib.request.urlretrieve(url, path, hook); print()

def py(venv=True):
    if not venv: return sys.executable
    return os.path.join(VENV, "Scripts", "python.exe")

def pip(*args):
    return run([py(), "-m", "pip", "install", "--disable-pip-version-check", *args])

def main():
    print("=" * 50)
    print("  konak3d - Windows exe uretimi")
    print("=" * 50)
    print(f"  Klasor : {ROOT}")
    print(f"  Python : {platform.python_version()}  ({sys.executable})")
    print("  Sure   : 15-30 dakika,  indirme ~700 MB")
    print("=" * 50)
    if sys.version_info < (3, 10):
        die(f"Python 3.10+ gerekiyor, bu surum {platform.python_version()}.")
    input("\nBaslamak icin Enter'a basin...")

    head(1, "Klasor hazirlaniyor")
    os.makedirs(ROOT, exist_ok=True)

    head(2, "Kaynak kod indiriliyor")
    zp = os.path.join(ROOT, "src.zip")
    try: download(SRC_ZIP, zp, "kaynak")
    except Exception as e: die(f"Kaynak kod indirilemedi: {e}\nKurum aginda github.com engelli olabilir.")
    if os.path.isdir(SRC): shutil.rmtree(SRC, ignore_errors=True)
    with zipfile.ZipFile(zp) as z: z.extractall(ROOT)
    if not os.path.exists(os.path.join(SRC, "konak3d.spec")): die("Arsiv acilamadi.")

    head(3, "Sanal ortam kuruluyor")
    if not os.path.exists(py()):
        if not run([sys.executable, "-m", "venv", VENV]): die("Sanal ortam kurulamadi.")
    pip("--upgrade", "pip")

    head(4, "PyTorch (CPU surumu) kuruluyor - en uzun adim")
    if not pip("torch", "--index-url", "https://download.pytorch.org/whl/cpu"):
        die("PyTorch kurulamadi. Kurum agi download.pytorch.org adresini engelliyor olabilir.")

    head(5, "konak3d ve bagimliliklari kuruluyor")
    if not pip("-e", SRC): die("konak3d kurulamadi.")
    if not pip("pyinstaller", "timm"): die("PyInstaller kurulamadi.")
    if not pip(SAM_ZIP):
        print("    zip ile olmadi, git ile deneniyor...")
        if not pip("git+https://github.com/ChaoningZhang/MobileSAM.git"):
            die("MobileSAM kurulamadi.")

    head(6, "Model dosyasi indiriliyor (40 MB)")
    md = os.path.join(SRC, "models"); os.makedirs(md, exist_ok=True)
    wp = os.path.join(md, "mobile_sam.pt")
    if not os.path.exists(wp) or os.path.getsize(wp) < 1_000_000:
        try: download(WEIGHTS, wp, "model")
        except Exception as e: die(f"Model indirilemedi: {e}")

    head(7, "exe derleniyor - birkac dakika surebilir")
    t0 = time.time()
    if not run([py(), "-m", "PyInstaller", "--noconfirm", "konak3d.spec"], cwd=SRC):
        die("PyInstaller hata verdi.")
    exe = os.path.join(SRC, "dist", "konak3d.exe")
    if not os.path.exists(exe): die("exe uretilemedi.")

    print("\n" + "=" * 50)
    print("  BITTI  ({:.0f} dk)".format((time.time() - t0) / 60 + 0.5))
    print(f"  Dosya: {exe}")
    print("  Boyut: {:.0f} MB".format(os.path.getsize(exe) / 1e6))
    print("=" * 50)
    try: os.startfile(os.path.dirname(exe))
    except Exception: pass
    input("\nKapatmak icin Enter'a basin...")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nIptal edildi.")
    except Exception as e:
        import traceback; traceback.print_exc(); die(str(e))
