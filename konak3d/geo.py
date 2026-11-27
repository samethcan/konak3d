"""Ortak yardimcilar: raster, KMZ alan siniri."""
import re, zipfile, pickle
import numpy as np, rasterio, pyproj
from shapely.geometry import Polygon

def open_raster(path): return rasterio.open(path)

def load_aoi_px(path, raster):
    """Alan sinirini (.kmz/.kml/.geojson/.gpkg/.shp) raster piksel koordinatina cevirir."""
    inv = ~raster.transform
    if path.lower().endswith((".kmz", ".kml")):
        if path.lower().endswith(".kmz"):
            z = zipfile.ZipFile(path); kml = z.read(z.namelist()[0]).decode("utf8", "ignore")
        else:
            kml = open(path, encoding="utf8", errors="ignore").read()
        coords = re.search(r"<coordinates>(.*?)</coordinates>", kml, re.S).group(1).split()
        ll = [tuple(map(float, c.split(",")[:2])) for c in coords]
        t = pyproj.Transformer.from_crs(4326, raster.crs, always_xy=True)
        return [inv * t.transform(x, y) for x, y in ll], len(ll)
    import geopandas as gpd
    g = gpd.read_file(path).to_crs(raster.crs)
    geom = g.geometry.union_all()
    if geom.geom_type == "MultiPolygon": geom = max(geom.geoms, key=lambda a: a.area)
    ring = list(geom.exterior.coords)
    return [inv * p for p in ring], len(ring)

# geriye donuk ad
load_kmz_polygon_px = load_aoi_px

def px_area_m2(poly_px, raster):
    gsd = abs(raster.transform.a)
    return Polygon(poly_px).area * gsd * gsd
