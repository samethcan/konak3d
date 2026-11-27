"""Sentetik demo verisi uretir: ortofoto benzeri GeoTIFF + kat defteri + alan siniri.

Hicbir kurum verisi icermez. Tum geometriler ve doku programla uretilir.
    python demo/make_demo.py            -> demo/ortofoto.tif, demo/units.gpkg, demo/aoi.geojson
"""
import os, numpy as np, cv2, rasterio, geopandas as gpd
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box

RNG = np.random.default_rng(7)
GSD = 0.11                      # m/px
W = H = 2400                    # px  -> ~264 x 264 m
CRS = "EPSG:32635"
X0, Y0 = 500000.0, 4250000.0    # keyfi UTM baslangici
OUT = os.path.dirname(os.path.abspath(__file__))

def noise(h, w, scale, amp):
    small = RNG.normal(0, 1, (max(h // scale, 2), max(w // scale, 2)))
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC) * amp

def main():
    # zemin: asfalt/toprak karisimi
    img = np.zeros((H, W, 3), np.float32)
    base = np.array([116, 112, 104], np.float32)
    img[:] = base + noise(H, W, 26, 9)[..., None]
    img += noise(H, W, 4, 4)[..., None]

    roads = np.zeros((H, W), np.uint8)
    step = 300
    for x in range(step, W, step): cv2.rectangle(roads, (x - 16, 0), (x + 16, H), 255, -1)
    for y in range(step, H, step): cv2.rectangle(roads, (0, y - 16), (W, y + 16), 255, -1)
    img[roads > 0] = np.array([92, 90, 90], np.float32) + noise(H, W, 8, 5)[roads > 0][:, None]

    units, nb = [], 0
    for by in range(0, H - step, step):
        for bx in range(0, W - step, step):
            cx0, cy0 = bx + 26, by + 26
            cw, ch = step - 68, step - 68
            # blok icinde 2x2..3x3 parsel
            nx, ny = RNG.integers(2, 4), RNG.integers(2, 4)
            for i in range(nx):
                for j in range(ny):
                    if RNG.random() < 0.12: continue           # bos parsel
                    px = cx0 + i * cw / nx + RNG.integers(3, 12)
                    py = cy0 + j * ch / ny + RNG.integers(3, 12)
                    pw = cw / nx - RNG.integers(14, 30)
                    ph = ch / ny - RNG.integers(14, 30)
                    if pw < 40 or ph < 40: continue
                    ang = float(RNG.normal(0, 2.5))
                    rect = cv2.boxPoints(((px + pw / 2, py + ph / 2), (pw, ph), ang)).astype(np.float32)
                    kat = int(RNG.choice([1, 2, 3, 4, 5, 6], p=[.26, .30, .20, .12, .08, .04]))
                    # golge (kat ile orantili)
                    off = np.array([0.55, -0.42]) * kat * 3.0 / GSD * 0.28
                    hull = cv2.convexHull(np.vstack([rect, rect + off]).astype(np.float32))
                    cv2.fillConvexPoly(img, hull.astype(np.int32), (58, 56, 54))
                    # cati
                    tone = RNG.choice([(168, 164, 158), (142, 120, 108), (120, 128, 136), (186, 178, 166), (108, 96, 92)])
                    cv2.fillConvexPoly(img, rect.astype(np.int32), tuple(float(c) for c in tone))
                    m = np.zeros((H, W), np.uint8); cv2.fillConvexPoly(m, rect.astype(np.int32), 255)
                    img[m > 0] += noise(H, W, 3, 6)[m > 0][:, None]
                    cv2.polylines(img, [rect.astype(np.int32)], True, tuple(float(c) * 0.82 for c in tone), 2)
                    nb += 1
                    units.append((rect, kat))
    # agaclar
    for _ in range(420):
        c = (int(RNG.integers(0, W)), int(RNG.integers(0, H)))
        cv2.circle(img, c, int(RNG.integers(8, 20)), (58, 104, 62), -1)
    img = np.clip(img + noise(H, W, 2, 2.5)[..., None], 0, 255).astype(np.uint8)

    tr = from_origin(X0, Y0, GSD, GSD)
    with rasterio.open(f"{OUT}/ortofoto.tif", "w", driver="GTiff", height=H, width=W, count=3,
                       dtype="uint8", crs=CRS, transform=tr, compress="deflate") as d:
        d.write(img.transpose(2, 0, 1))

    # kat defteri: binalarin %88'i, hafif kaydirma ve kucultme ile
    geoms, kats, nos = [], [], []
    for k, (rect, kat) in enumerate(units):
        if RNG.random() < 0.12: continue
        c = rect.mean(0); r = (rect - c) * RNG.uniform(0.80, 0.94) + c + RNG.normal(0, 2.0, 2)
        geoms.append(Polygon([tr * (x, y) for x, y in r])); kats.append(kat); nos.append(f"{k:05d}")
    gpd.GeoDataFrame({"kat": kats, "bina_no": nos}, geometry=geoms, crs=CRS).to_file(f"{OUT}/units.gpkg", driver="GPKG")

    aoi = box(*gpd.GeoSeries([box(X0 + 40 * GSD, Y0 - (H - 40) * GSD, X0 + (W - 40) * GSD, Y0 - 40 * GSD)], crs=CRS).total_bounds)
    gpd.GeoDataFrame(geometry=[aoi], crs=CRS).to_crs(4326).to_file(f"{OUT}/aoi.geojson", driver="GeoJSON")
    print(f"ortofoto.tif  {W}x{H} px  {GSD} m  {CRS}")
    print(f"binalar       {nb} adet cizildi")
    print(f"units.gpkg    {len(geoms)} kat defteri birimi")
    print(f"aoi.geojson   {aoi.area/1e4:.1f} ha")

if __name__ == "__main__":
    main()
