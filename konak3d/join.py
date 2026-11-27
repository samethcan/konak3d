"""Ayak izi <-> kat defteri birlestirme + kalite kontrol."""
import numpy as np, geopandas as gpd
from shapely.geometry import Polygon
from shapely.strtree import STRtree

def run(fp, ncz_items, aoi_poly_map, floor_h=3.0, min_ov=0.2, log=print):
    nc = [(i["geom"], i["kat"], i["bina_no"]) for i in ncz_items if aoi_poly_map.contains(i["geom"].representative_point())]
    log(f"kat_defteri_birimi_AOI={len(nc)}")
    tr = STRtree([g for g, _, _ in nc]); kat, no, nunit = [], [], []
    for g in fp.geometry:
        best = None; bi = 0; cnt = 0
        for j in tr.query(g):
            q, k, n = nc[j]; inter = g.intersection(q).area
            if inter > 0.5 * q.area: cnt += 1
            if inter > bi: bi, best = inter, (k, n)
        ok = best is not None and bi > min_ov * g.area
        kat.append(best[0] if ok else 0); no.append(best[1] if ok else ""); nunit.append(cnt)
    fp = fp.copy(); fp["kat"] = kat; fp["bina_no"] = no; fp["n_birim"] = nunit
    fp["height_m"] = [k * floor_h if k > 0 else floor_h for k in kat]
    fp["kat_kaynak"] = ["kat_defteri" if k > 0 else "yok(varsayim)" for k in kat]
    fp["alan_m2"] = fp.geometry.area.round(1)
    st = STRtree(list(fp.geometry)); cov = []
    for g, _, _ in nc:
        a = sum(fp.geometry.iloc[j].intersection(g).area for j in st.query(g)); cov.append(a / g.area)
    cov = np.array(cov); rec = int((cov >= 0.5).sum()); rec30 = int((cov >= 0.3).sum())
    qa = dict(footprints=len(fp), kat_matched=int((fp.kat > 0).sum()), ncz_units=len(nc), ncz_covered=int(rec),
              coverage=round(rec / max(len(nc), 1), 3), ncz_covered30=rec30, coverage30=round(rec30 / max(len(nc), 1), 3), floor_h=floor_h, min_overlap=min_ov,
              kat_hist={int(k): int(v) for k, v in fp.kat.value_counts().sort_index().items()})
    log(f"matched={qa['kat_matched']}/{qa['footprints']}")
    log(f"unit_cover>=50%={rec}/{len(nc)} ({qa['coverage']*100:.1f}%)  >=30%={rec30}/{len(nc)} ({qa['coverage30']*100:.1f}%)")
    return fp, qa
