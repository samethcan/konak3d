"""Kat defteri noktalariyla yonlendirilen (prompted) segmentasyon.

Otomatik taramada kacan binalar icin: kat defteri biriminin kutusu + temsil noktasi
MobileSAM'e istem (prompt) olarak verilir; cikan cati maskesi duzenlenip ayak izi eklenir.
"""
import sys, pickle, time, numpy as np, cv2, geopandas as gpd
from rasterio.windows import Window
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
import buildingregulariser as br

def run(raster, fp, items, aoi_map, ckpt, tiles, down=2, T=1024, relaxed=False, log=print):
    sys.path.insert(0, "/tmp/MobileSAM")
    import torch; torch.set_num_threads(2)
    from mobile_sam import sam_model_registry, SamPredictor
    tr = raster.transform; inv = ~tr
    st = STRtree(list(fp.geometry))
    todo = []
    for i in items:
        g = i["geom"]; rp = g.representative_point()
        if not aoi_map.contains(rp): continue
        cov = sum(fp.geometry.iloc[j].intersection(g).area for j in st.query(g)) / g.area
        if cov >= 0.3: continue
        todo.append(i)
    log(f"uncovered kat units: {len(todo)}")
    sam = sam_model_registry["vit_t"](checkpoint=ckpt).eval(); pred = SamPredictor(sam)
    new = []; ious = []; TF = T * down
    # birimi, kenara >=80 px (yarim cozunurluk) olan bir karoya ata
    def pick(px, py):
        best = None
        for (x0, y0) in tiles:
            u = (px - x0) / down; v = (py - y0) / down
            m = min(u, v, T - u, T - v)
            if m > 80 and (best is None or m > best[0]): best = (m, x0, y0)
        return best
    groups = {}
    for i in todo:
        c = i["geom"].representative_point(); px, py = inv * (c.x, c.y); b = pick(px, py)
        if b: groups.setdefault((b[1], b[2]), []).append((i, px, py))
    log(f"tiles with prompts: {len(groups)}")
    for (x0, y0), lst in groups.items():
        t0 = time.time(); w = min(TF, raster.width - x0); h = min(TF, raster.height - y0)
        a = raster.read(window=Window(x0, y0, w, h)).transpose(1, 2, 0)
        tl = np.zeros((T, T, 3), np.uint8); sm = cv2.resize(a, (w // down, h // down), interpolation=cv2.INTER_AREA)
        tl[:sm.shape[0], :sm.shape[1]] = sm; pred.set_image(tl)
        for i, px, py in lst:
            g = i["geom"]; ring = np.array([inv * (x, y) for x, y in g.exterior.coords])
            ring = (ring - [x0, y0]) / down; cx, cy = (np.array([px, py]) - [x0, y0]) / down
            bx0, by0 = ring.min(0); bx1, by1 = ring.max(0); pad = 0.35 * max(bx1 - bx0, by1 - by0, 8)
            box = np.array([bx0 - pad, by0 - pad, bx1 + pad, by1 + pad])
            ms, sc, _ = pred.predict(point_coords=np.array([[cx, cy]]), point_labels=np.array([1]), box=box, multimask_output=True)
            Pg = Polygon(ring); best = None
            for m, s in zip(ms, sc):
                seg = m.astype("uint8"); cs, _ = cv2.findContours(seg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not cs: continue
                c = max(cs, key=cv2.contourArea); ca = cv2.contourArea(c)
                if ca < (0.45 if relaxed else 0.7) * Pg.area or ca > (10 if relaxed else 8) * Pg.area or ca < 100: continue
                sol = ca / max(cv2.contourArea(cv2.convexHull(c)), 1)
                if sol < (0.75 if relaxed else 0.82): continue
                Q = Polygon(c.reshape(-1, 2))
                if not Q.is_valid or not Q.contains(Point(cx, cy)): continue
                iou = Q.intersection(Pg).area / Q.union(Pg).area
                if best is None or iou > best[0]: best = (iou, c)
            if best:
                c = best[1]; p = cv2.approxPolyDP(c.reshape(-1, 1, 2).astype(np.int32), 2.0, True).reshape(-1, 2)
                if len(p) >= 3:
                    full = p * down + [x0, y0]
                    new.append(Polygon([tr * (x, y) for x, y in full])); ious.append(best[0])
        log(f"tile({x0},{y0}) prompts={len(lst)} new_total={len(new)} {time.time()-t0:.0f}s")
    # ayni binayi gosteren kopyalari ele
    new.sort(key=lambda P: -P.area); keep = []
    for P in new:
        if not P.is_valid: continue
        if any(P.intersection(Q).area / min(P.area, Q.area) > 0.5 for Q in keep): continue
        # mevcut ayak izleriyle cakisma
        if any(P.intersection(fp.geometry.iloc[j]).area / min(P.area, fp.geometry.iloc[j].area) > 0.5 for j in st.query(P)): continue
        keep.append(P)
    log(f"prompted footprints: {len(keep)} (median mask/kat IoU {np.median(ious):.2f})" if ious else "none")
    g2 = gpd.GeoDataFrame(geometry=keep, crs=fp.crs)
    if len(g2):
        g2 = br.regularize_geodataframe(g2, parallel_threshold=1.0, simplify=True, simplify_tolerance=0.35, allow_45_degree=False, allow_circles=False, neighbor_alignment=True, num_cores=1)
        g2 = g2[~g2.geometry.is_empty & g2.geometry.notna()]
    geoms = []
    for g in g2.geometry:
        if g.geom_type == "MultiPolygon": g = max(g.geoms, key=lambda a: a.area)
        if g.geom_type == "Polygon" and g.area > 20: geoms.append(g)
    out = gpd.GeoDataFrame({"src": ["auto"] * len(fp) + ["prompt"] * len(geoms)}, geometry=list(fp.geometry) + geoms, crs=fp.crs)
    out["fid"] = range(len(out)); return out, len(todo), len(geoms)
