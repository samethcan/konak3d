# PyInstaller spec — tek dosyalik masaustu uygulamasi
# Kullanim:  pyinstaller konak3d.spec
# mobile_sam.pt dosyasini bu klasordeki models/ altina koyun.
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
for pkg in ("rasterio", "pyproj", "geopandas", "shapely", "fiona"):
    try: datas += collect_data_files(pkg)
    except Exception: pass
if os.path.exists("models/mobile_sam.pt"):
    datas += [("models/mobile_sam.pt", "models")]

hidden = []
for pkg in ("rasterio", "rasterio.sample", "rasterio._shim", "rasterio.vrt", "pyproj",
            "mobile_sam", "timm", "torch", "ezdxf", "trimesh", "mapbox_earcut"):
    try: hidden += collect_submodules(pkg)
    except Exception: hidden.append(pkg)

a = Analysis(["konak3d/gui.py"], pathex=["."], datas=datas, hiddenimports=hidden,
             excludes=["matplotlib", "IPython", "pytest", "notebook"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="konak3d",
          console=False, upx=False, icon=None)
