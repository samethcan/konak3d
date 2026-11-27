"""Ham maskeler -> temiz, dik acili bina ayak izleri (EPSG:5253)."""
import pickle, numpy as np, cv2, geopandas as gpd
from shapely.geometry import Polygon
from shapely.strtree import STRtree
import buildingregulariser as br

def build(raw_pkl, raster, aoi_px, log=print):
    d = pickle.load(open(raw_pkl, "rb")); tr = raster.transform; inv = ~tr; KP = Polygon(aoi_px)
    dets = []
    for x in d["res"]:
        c = x["c"].astype(np.int32).reshape(-1, 1, 2)
        p = cv2.approxPolyDP(c, 4.0, True).reshape(-1, 2)
        if len(p) < 3: continue
        P = Polygon(p)
        if P.is_valid and P.area > 0 and KP.contains(P.representative_point()): dets.append(P)
    dets.sort(key=lambda P: -P.area); keep = []
    for P in dets:
        if any(P.intersects(Q) and P.intersection(Q).area / min(P.area, Q.area) > 0.5 for Q in keep[-400:]): continue
        keep.append(P)
    t = STRtree(keep); rm = set()
    for i, P in enumerate(keep):
        if i in rm: continue
        for j in t.query(P):
            if j > i and j not in rm and P.intersection(keep[j]).area / min(P.area, keep[j].area) > 0.5: rm.add(int(j))
    keep = [P for i, P in enumerate(keep) if i not in rm]
    log(f"candidates={len(dets)}  after_nms={len(keep)}")
    gdf = gpd.GeoDataFrame(geometry=[Polygon([tr * (x, y) for x, y in P.exterior.coords]) for P in keep], crs=raster.crs)
    reg = br.regularize_geodataframe(gdf, parallel_threshold=1.0, simplify=True, simplify_tolerance=0.35,
                                     allow_45_degree=False, allow_circles=False, neighbor_alignment=True, num_cores=1)
    geoms = []
    for g in reg.geometry:
        if g is None or g.is_empty: continue
        if g.geom_type == "MultiPolygon": g = max(g.geoms, key=lambda a: a.area)
        if g.geom_type == "Polygon" and g.area > 20: geoms.append(g)
    log(f"regularized={len(geoms)}  (orthogonalized, tol=0.35 m)")
    return gpd.GeoDataFrame({"fid": range(len(geoms))}, geometry=geoms, crs=raster.crs)
