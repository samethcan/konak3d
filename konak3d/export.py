"""Cikti formatlari: GeoJSON (yukseklik alanli), DXF (3B), GLB (LoD1)."""
import json, numpy as np, ezdxf, trimesh, geopandas as gpd

PAL = {0: 8, 1: 3, 2: 2, 3: 30, 4: 1, 5: 6}   # AutoCAD renk indeksleri

def geojson(fp, path):
    fp.to_crs(4326).to_file(path, driver="GeoJSON"); return path

def dxf(fp, path):
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    for k in sorted(set(min(int(v), 5) for v in fp.kat)):
        doc.layers.add(f"BINA_KAT_{k}", color=PAL[k])
    for _, r in fp.iterrows():
        p = list(r.geometry.exterior.coords)[:-1]; k = min(int(r.kat), 5)
        msp.add_polyline3d([(x, y, 0.0) for x, y in p], close=True, dxfattribs={"layer": f"BINA_KAT_{k}"})
        msp.add_polyline3d([(x, y, float(r.height_m)) for x, y in p], close=True, dxfattribs={"layer": f"BINA_KAT_{k}"})
        for x, y in p: msp.add_line((x, y, 0.0), (x, y, float(r.height_m)), dxfattribs={"layer": f"BINA_KAT_{k}"})
    doc.saveas(path); return path

def glb(fp, path):
    meshes = []
    cx, cy = fp.total_bounds[[0, 1]]
    for _, r in fp.iterrows():
        try:
            m = trimesh.creation.extrude_polygon(r.geometry, float(r.height_m))
        except Exception:
            continue
        m.apply_translation([-cx, -cy, 0])
        rgb = {0: (150, 150, 150), 1: (110, 220, 90), 2: (255, 215, 40), 3: (255, 150, 30), 4: (240, 60, 40), 5: (255, 60, 200)}[min(int(r.kat), 5)]
        m.visual.face_colors = rgb + (255,); meshes.append(m)
    trimesh.util.concatenate(meshes).export(path); return path, len(meshes)
