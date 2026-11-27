"""Tum hatti tek fonksiyonda calistirir. GUI ve CLI ayni kodu kullanir."""
import os, json, pickle, time
import geopandas as gpd
from shapely.geometry import Polygon
from . import geo, ncz as nczmod, footprint as fpmod, join as joinmod, export as ex

STEPS = ["inspect", "aoi", "kat katmani", "detect", "footprint", "refine", "join", "export"]

def _units_from_vector(path, raster, kat_field, id_field):
    g = gpd.read_file(path).to_crs(raster.crs); items = []
    for i, row in g.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty: continue
        if geom.geom_type == "MultiPolygon": geom = max(geom.geoms, key=lambda x: x.area)
        if geom.geom_type != "Polygon": continue
        items.append(dict(geom=geom, kat=int(row[kat_field]),
                          bina_no=str(row[id_field]) if id_field in g.columns else str(i)))
    return items

def run(raster_path, units_path, aoi_path=None, workdir="work", outdir="out", floor_h=3.0,
        ckpt="/tmp/MobileSAM/weights/mobile_sam.pt", kat_field="kat", id_field="bina_no",
        formats=("geojson", "dxf", "glb"), skip_detect=False, log=print, on_step=lambda i, n: None):
    """Hatti bastan sona calistirir ve ozet sozlugu dondurur."""
    os.makedirs(workdir, exist_ok=True); os.makedirs(outdir, exist_ok=True)
    t_all = time.time(); n = len(STEPS); s = 0

    on_step(s, n); s += 1
    r = geo.open_raster(raster_path); b = r.bounds
    log(f"raster     : {r.width}x{r.height} px  {abs(r.transform.a):.3f} m  {r.crs.to_string()}")

    on_step(s, n); s += 1
    if aoi_path:
        aoi_px, nv = geo.load_aoi_px(aoi_path, r)
        log(f"alan       : {nv} kose  {geo.px_area_m2(aoi_px, r)/1e4:.1f} ha")
    else:
        aoi_px = [(0, 0), (r.width, 0), (r.width, r.height), (0, r.height)]
        log(f"alan       : tum raster  {geo.px_area_m2(aoi_px, r)/1e4:.1f} ha")
    pickle.dump(aoi_px, open(f"{workdir}/aoi_px.pkl", "wb"))
    aoi_map = Polygon([r.transform * p for p in aoi_px])

    on_step(s, n); s += 1
    if units_path.lower().endswith(".ncz"):
        items, nruns = nczmod.parse(units_path, b)
        log(f"kat katmani: {len(items)} poligon  ({nruns} kayit tarandi)")
    else:
        items = _units_from_vector(units_path, r, kat_field, id_field)
        log(f"kat katmani: {len(items)} poligon")
    inside = [i for i in items if aoi_map.contains(i["geom"].representative_point())]
    log(f"alan icinde: {len(inside)} birim")
    pickle.dump(items, open(f"{workdir}/ncz_items.pkl", "wb"))

    on_step(s, n); s += 1
    raw = f"{workdir}/det_raw.pkl"
    if skip_detect and os.path.exists(raw):
        log("detect     : atlandi (onceki sonuc kullanildi)")
    else:
        from . import detect
        t0 = time.time(); detect.run(r, aoi_px, raw, ckpt, log=log)
        log(f"detect     : {time.time()-t0:.0f} s")

    on_step(s, n); s += 1
    fp = fpmod.build(raw, r, aoi_px, log=log)
    fp.to_file(f"{workdir}/footprints.gpkg", driver="GPKG")

    on_step(s, n); s += 1
    from . import refine
    tiles = pickle.load(open(raw, "rb"))["tiles"]
    fp, n1, a1 = refine.run(r, fp, items, aoi_map, ckpt, tiles, relaxed=False, log=lambda m: None)
    log(f"refine 1   : {n1} bosluk -> +{a1}")
    fp, n2, a2 = refine.run(r, fp, items, aoi_map, ckpt, tiles, relaxed=True, log=lambda m: None)
    log(f"refine 2   : {n2} bosluk -> +{a2}")
    fp.to_file(f"{workdir}/footprints_refined.gpkg", driver="GPKG")

    on_step(s, n); s += 1
    fp, qa = joinmod.run(fp, items, aoi_map, floor_h=floor_h, log=log)
    fp.to_file(f"{workdir}/footprints_kat.gpkg", driver="GPKG")
    json.dump(qa, open(f"{workdir}/qa.json", "w"), indent=1)

    on_step(s, n); s += 1
    written = []
    for f in formats:
        if f == "geojson": p = ex.geojson(fp, f"{outdir}/binalar.geojson")
        elif f == "dxf": p = ex.dxf(fp, f"{outdir}/binalar_3b.dxf")
        elif f == "glb": p, _ = ex.glb(fp, f"{outdir}/lod1.glb")
        else: continue
        written.append(p); log(f"yazildi    : {os.path.basename(p)}  ({os.path.getsize(p)/1024:.0f} KB)")
    on_step(n, n)

    qa["gfa_est_m2"] = float((fp.alan_m2 * fp.kat.clip(lower=1)).sum())
    qa["footprint_m2"] = float(fp.alan_m2.sum())
    qa["files"] = written
    qa["seconds"] = round(time.time() - t_all, 1)
    log(f"toplam     : {qa['seconds']} s")
    return qa
