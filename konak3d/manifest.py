"""Calistirma kunyesi: girdi ozetleri, parametreler, surumler, sonuclar.

Amac: ucuncu bir kisi ayni girdi ve ayni konfigurasyonla ayni ciktiyi uretebilsin.
"""
import hashlib, json, os, platform, subprocess, sys, time
from datetime import datetime, timezone

PKGS = ["numpy", "opencv-python-headless", "rasterio", "geopandas", "shapely",
        "pyproj", "buildingregulariser", "ezdxf", "trimesh", "torch", "timm"]

def sha256(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def versions():
    out = {}
    for p in PKGS:
        try:
            from importlib.metadata import version
            out[p] = version(p)
        except Exception:
            out[p] = None
    return out

def git_commit(path):
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:
        return None

def build(config, inputs, qa, started, outdir):
    """inputs: {rol: dosya yolu}. Hepsinin SHA-256 ozeti alinir."""
    man = {
        "arac": "konak3d",
        "surum": __import__("konak3d").__version__,
        "git_commit": git_commit(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "calistirma": {
            "baslangic_utc": datetime.fromtimestamp(started, timezone.utc).isoformat(timespec="seconds"),
            "bitis_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sure_s": round(time.time() - started, 1),
        },
        "ortam": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "islemci_sayisi": os.cpu_count(),
            "paketler": versions(),
        },
        "girdiler": {k: {"yol": os.path.abspath(v), "bayt": os.path.getsize(v), "sha256": sha256(v)}
                     for k, v in inputs.items() if v and os.path.exists(v)},
        "parametreler": config,
        "sonuclar": qa,
        "notlar": [
            "Tespit asamasi belirlenimci calisir: nokta izgarasi sabittir, rastgele ornekleme yoktur.",
            "Ayni girdi, ayni parametre ve ayni paket surumleriyle sonuc tekrar edilebilir.",
            "Yukseklik kat sayisi x kat yuksekligi varsayimidir, olculmus degildir.",
            "refine asamasi kat katmaninin konumlarini istem olarak kullanir; bu asamada eklenen binalar tam otomatik tespit degildir.",
        ],
    }
    p = os.path.join(outdir, "run_manifest.json")
    json.dump(man, open(p, "w"), indent=1, ensure_ascii=False)
    return p, man
