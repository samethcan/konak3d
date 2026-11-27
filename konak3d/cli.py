import argparse, pickle, json, os, sys, time
import geopandas as gpd, numpy as np
from shapely.geometry import Polygon
from . import geo, ncz as nczmod, footprint, join as joinmod, export as ex
W = "work"

def _r(a): return geo.open_raster(a.raster)

def cmd_inspect(a):
    r = _r(a); b = r.bounds
    print(f"file      : {os.path.basename(a.raster)}")
    print(f"size      : {r.width} x {r.height} px   bands={r.count}  dtype={r.dtypes[0]}")
    print(f"crs       : {r.crs.to_string()}  ({r.crs.to_wkt().split('\"')[1]})")
    print(f"gsd       : {abs(r.transform.a):.3f} m/px")
    print(f"extent    : {b.left:.1f} {b.bottom:.1f} {b.right:.1f} {b.top:.1f}")
    print(f"coverage  : {(b.right-b.left)*(b.top-b.bottom)/1e4:.1f} ha")

def cmd_aoi(a):
    r = _r(a); px, n = geo.load_aoi_px(a.aoi, r)
    pickle.dump(px, open(f"{W}/aoi_px.pkl", "wb"))
    print(f"vertices  : {n}"); print(f"crs       : EPSG:4326 -> {r.crs.to_string()}")
    print(f"area      : {geo.px_area_m2(px, r)/1e4:.1f} ha")

def cmd_ncz(a):
    r = _r(a); t0 = time.time()
    items, nruns = nczmod.parse(a.ncz, r.bounds)
    inv = ~r.transform; aoi = Polygon(pickle.load(open(f"{W}/aoi_px.pkl", "rb")))
    inside = [i for i in items if aoi.contains(Polygon([inv * (x, y) for x, y in i["geom"].exterior.coords]).representative_point())]
    pickle.dump(items, open(f"{W}/ncz_items.pkl", "wb"))
    print(f"records   : {nruns} polylines scanned")
    print(f"polygons  : {len(items)} with kat attribute")
    print(f"in AOI    : {len(inside)}")
    h = nczmod.kat_histogram(inside); print("kat dist. : " + " ".join(f"{k}k={v}" for k, v in h.items()))
    print(f"elapsed   : {time.time()-t0:.1f} s")

def cmd_units(a):
    """Vektor dosyadan (gpkg/geojson/shp) kat defteri birimleri."""
    r = _r(a); g = gpd.read_file(a.units).to_crs(r.crs)
    kc = a.kat_field; nc = a.id_field
    inv = ~r.transform; aoi = Polygon(pickle.load(open(f"{W}/aoi_px.pkl", "rb")))
    items, inside = [], 0
    for i, row in g.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty: continue
        if geom.geom_type == "MultiPolygon": geom = max(geom.geoms, key=lambda x: x.area)
        if geom.geom_type != "Polygon": continue
        it = dict(geom=geom, kat=int(row[kc]), bina_no=str(row[nc]) if nc in g.columns else str(i))
        items.append(it)
        if aoi.contains(Polygon([inv * p for p in geom.exterior.coords]).representative_point()): inside += 1
    pickle.dump(items, open(f"{W}/ncz_items.pkl", "wb"))
    from collections import Counter
    h = dict(sorted(Counter(i["kat"] for i in items).items()))
    print(f"source    : {os.path.basename(a.units)}  ({g.crs.to_string()} -> {r.crs.to_string()})")
    print(f"polygons  : {len(items)}")
    print(f"in AOI    : {inside}")
    print("kat dist. : " + " ".join(f"{k}k={v}" for k, v in h.items()))

def cmd_detect(a):
    from . import detect
    r = _r(a); px = pickle.load(open(f"{W}/aoi_px.pkl", "rb"))
    detect.run(r, px, f"{W}/det_raw.pkl", a.ckpt, max_tiles=a.max_tiles)

def cmd_footprint(a):
    r = _r(a); px = pickle.load(open(f"{W}/aoi_px.pkl", "rb"))
    fp = footprint.build(f"{W}/det_raw.pkl", r, px); fp.to_file(f"{W}/footprints.gpkg", driver="GPKG")
    print(f"saved     : {W}/footprints.gpkg")

def cmd_join(a):
    r = _r(a); inv = ~r.transform; tr = r.transform
    items = pickle.load(open(f"{W}/ncz_items.pkl", "rb"))
    aoi_map = Polygon([tr * p for p in pickle.load(open(f"{W}/aoi_px.pkl", "rb"))])
    fp = gpd.read_file(f"{W}/footprints_refined.gpkg" if os.path.exists(f"{W}/footprints_refined.gpkg") else f"{W}/footprints.gpkg")
    fp, qa = joinmod.run(fp, items, aoi_map, floor_h=a.floor_h, min_ov=a.min_overlap)
    fp.to_file(f"{W}/footprints_kat.gpkg", driver="GPKG"); json.dump(qa, open(f"{W}/qa.json", "w"), indent=1)
    print("kat hist  : " + " ".join(f"{k}k={v}" for k, v in qa["kat_hist"].items()))
    print(f"saved     : {W}/footprints_kat.gpkg, {W}/qa.json")

def cmd_export(a):
    fp = gpd.read_file(f"{W}/footprints_kat.gpkg"); os.makedirs("out", exist_ok=True)
    for f in a.format.split(","):
        if f == "geojson": p = ex.geojson(fp, "out/konak_binalar.geojson")
        elif f == "dxf": p = ex.dxf(fp, "out/konak_binalar_3b.dxf")
        elif f == "glb": p, n = ex.glb(fp, "out/konak_lod1.glb")
        elif f == "cityjson": p, n = ex.cityjson(fp, "out/konak_lod1.city.json")
        print(f"wrote     : {p}  ({os.path.getsize(p)/1024:.0f} KB)")

def cmd_gui(a):
    from .gui import main as gui_main
    gui_main()

def cmd_run(a):
    """Tek komutla tum hat: konfigurasyon dosyasindan okur, kunye yazar."""
    import json as _j, time as _t
    from . import pipeline, manifest
    cfg = _j.load(open(a.config, encoding="utf-8"))
    t0 = _t.time()
    qa = pipeline.run(cfg["raster"], cfg["units"], cfg.get("aoi"),
                      workdir=cfg.get("workdir", "work"), outdir=cfg.get("outdir", "out"),
                      floor_h=cfg.get("floor_h", 3.0), ckpt=cfg.get("ckpt"),
                      kat_field=cfg.get("kat_field", "kat"), id_field=cfg.get("id_field", "bina_no"),
                      formats=tuple(cfg.get("formats", ["geojson", "dxf", "glb"])),
                      skip_detect=a.skip_detect)
    p, man = manifest.build(cfg, {"ortofoto": cfg["raster"], "kat_katmani": cfg["units"],
                                  "alan_siniri": cfg.get("aoi"), "model": cfg.get("ckpt")},
                            qa, t0, cfg.get("outdir", "out"))
    print(f"kunye     : {p}")
    print(f"git       : {man['git_commit']}")

def main():
    p = argparse.ArgumentParser(prog="konak3d"); s = p.add_subparsers(dest="cmd", required=True)
    q = s.add_parser("inspect"); q.add_argument("raster"); q.set_defaults(f=cmd_inspect)
    q = s.add_parser("aoi"); q.add_argument("aoi"); q.add_argument("--raster", required=True); q.set_defaults(f=cmd_aoi)
    q = s.add_parser("ncz"); q.add_argument("ncz"); q.add_argument("--raster", required=True); q.set_defaults(f=cmd_ncz)
    q = s.add_parser("units"); q.add_argument("units"); q.add_argument("--raster", required=True); q.add_argument("--kat-field", default="kat"); q.add_argument("--id-field", default="bina_no"); q.set_defaults(f=cmd_units)
    q = s.add_parser("detect"); q.add_argument("--raster", required=True); q.add_argument("--ckpt", default="/tmp/MobileSAM/weights/mobile_sam.pt"); q.add_argument("--max-tiles", type=int); q.set_defaults(f=cmd_detect)
    q = s.add_parser("footprint"); q.add_argument("--raster", required=True); q.set_defaults(f=cmd_footprint)
    q = s.add_parser("join"); q.add_argument("--raster", required=True); q.add_argument("--floor-h", type=float, default=3.0); q.add_argument("--min-overlap", type=float, default=0.2); q.set_defaults(f=cmd_join)
    q = s.add_parser("export"); q.add_argument("--format", default="geojson,dxf,glb,cityjson"); q.set_defaults(f=cmd_export)
    q = s.add_parser("refine"); q.add_argument("--raster", required=True); q.add_argument("--relaxed", action="store_true"); q.add_argument("--ckpt", default="/tmp/MobileSAM/weights/mobile_sam.pt"); q.set_defaults(f=cmd_refine)
    q = s.add_parser("scene"); q.add_argument("--floor-h", type=float, default=3.0); q.add_argument("--exag", type=float, default=1.0); q.set_defaults(f=cmd_scene)
    q = s.add_parser("run"); q.add_argument("--config", required=True); q.add_argument("--skip-detect", action="store_true"); q.set_defaults(f=cmd_run)
    q = s.add_parser("gui"); q.set_defaults(f=cmd_gui)
    a = p.parse_args(); a.f(a)

def cmd_refine(a):
    from . import refine
    r = _r(a); tr = r.transform
    items = pickle.load(open(f"{W}/ncz_items.pkl", "rb"))
    aoi_map = Polygon([tr * p for p in pickle.load(open(f"{W}/aoi_px.pkl", "rb"))])
    fp = gpd.read_file(f"{W}/footprints_refined.gpkg" if a.relaxed else f"{W}/footprints.gpkg")
    tiles = pickle.load(open(f"{W}/det_raw.pkl", "rb"))["tiles"]
    out, ntodo, nnew = refine.run(r, fp, items, aoi_map, a.ckpt, tiles, relaxed=False, log=lambda m: None)
    print(f"pass 1 (strict) : {ntodo} units -> +{nnew}")
    out2, ntodo2, nnew2 = refine.run(r, out, items, aoi_map, a.ckpt, tiles, relaxed=True, log=lambda m: None)
    print(f"pass 2 (relaxed): {ntodo2} units -> +{nnew2}")
    out = out2; nnew = nnew + nnew2
    out.to_file(f"{W}/footprints_refined.gpkg", driver="GPKG")
    print(f"footprints: {len(fp)} -> {len(out)}  (+{nnew} prompted)")
    print(f"saved     : {W}/footprints_refined.gpkg")

def cmd_scene(a):
    import json
    fp = gpd.read_file(f"{W}/footprints_kat.gpkg")
    h = fp.height_m * a.exag
    gfa = float((fp.alan_m2 * fp.kat.clip(lower=1)).sum())
    sc = dict(n=len(fp), n_kat=int((fp.kat > 0).sum()), floor_h=a.floor_h, exag=a.exag, hmax=float(fp.height_m.max()),
              footprint_m2=float(fp.alan_m2.sum()), gfa_est_m2=gfa)
    json.dump(sc, open(f"{W}/scene.json", "w"), indent=1)
    print(f"extrusions : {sc['n']}  (kat defterinden {sc['n_kat']}, varsayim {sc['n']-sc['n_kat']})")
    print(f"height     : kat x {a.floor_h:.1f} m   max {sc['hmax']:.0f} m   exag x{a.exag:.1f}")
    print(f"footprint  : {sc['footprint_m2']:,.0f} m2")
    print(f"gfa (est.) : {gfa:,.0f} m2   (alan x kat)")
    print(f"saved      : {W}/scene.json")
