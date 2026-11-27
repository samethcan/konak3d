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


# ---------------------------------------------------------------- CityJSON
def cityjson(fp, path, crs_epsg=None, lod="1.2", scale=0.001):
    """LoD1 CityJSON 1.1 yazar: semantik yuzeyler (Ground/Wall/Roof) ve oznitelikler.

    Geometri Solid olarak yazilir. Koordinatlar tamsayiya olceklenir (CityJSON 'transform').
    """
    import json, numpy as np
    from shapely.geometry import Polygon

    if crs_epsg is None:
        crs_epsg = fp.crs.to_epsg()
    verts, index = [], {}

    def vid(p):
        k = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
        if k not in index:
            index[k] = len(verts); verts.append(k)
        return index[k]

    cityobjects = {}
    for i, r in fp.iterrows():
        g = r.geometry
        if g.is_empty or g.geom_type != "Polygon":
            continue
        ring = list(g.exterior.coords)[:-1]
        if Polygon(ring).exterior.is_ccw:          # disa donuk normal icin saat yonu
            ring = ring[::-1]
        h = float(r.height_m)
        n = len(ring)
        ground = [vid((x, y, 0.0)) for x, y in ring]
        roof = [vid((x, y, h)) for x, y in ring]
        # zemin yuzeyi asagi bakar: ters sirayla
        boundaries = [[list(reversed(ground))]]
        semantics = [0]
        for k in range(n):
            k2 = (k + 1) % n
            boundaries.append([[ground[k], ground[k2], roof[k2], roof[k]]])
            semantics.append(1)
        boundaries.append([roof])
        semantics.append(2)

        oid = f"BINA_{int(r.fid) if 'fid' in fp.columns else i:05d}"
        cityobjects[oid] = {
            "type": "Building",
            "attributes": {
                "kat_sayisi": int(r.kat),
                "yukseklik_m": round(h, 2),
                "taban_alani_m2": round(float(r.alan_m2), 1),
                "kat_kaynak": str(r.kat_kaynak),
                "bina_no": str(r.bina_no) if "bina_no" in fp.columns else "",
                "tespit_kaynak": str(r.src) if "src" in fp.columns else "auto",
            },
            "geometry": [{
                "type": "Solid", "lod": lod,
                "boundaries": [boundaries],
                "semantics": {
                    "surfaces": [{"type": "GroundSurface"}, {"type": "WallSurface"}, {"type": "RoofSurface"}],
                    "values": [semantics],
                },
            }],
        }

    V = np.array(verts, float)
    origin = V.min(axis=0)
    ints = np.round((V - origin) / scale).astype(np.int64)
    doc = {
        "type": "CityJSON", "version": "2.0",
        "metadata": {
            "referenceSystem": f"https://www.opengis.net/def/crs/EPSG/0/{crs_epsg}",
            "geographicalExtent": [float(origin[0]), float(origin[1]), float(origin[2]),
                                   float(V[:, 0].max()), float(V[:, 1].max()), float(V[:, 2].max())],
        },
        "transform": {"scale": [scale] * 3, "translate": [float(o) for o in origin]},
        "CityObjects": cityobjects,
        "vertices": ints.tolist(),
    }
    json.dump(doc, open(path, "w"), separators=(",", ":"))
    return path, len(cityobjects)


def validate_solids(fp, log=print):
    """LoD1 katilarini dogrular: kapali (watertight) ve hacimli mi, hacim ne kadar."""
    import numpy as np, trimesh
    ok = bad = 0; vols = []
    for _, r in fp.iterrows():
        try:
            m = trimesh.creation.extrude_polygon(r.geometry, float(r.height_m))
        except Exception:
            bad += 1; continue
        if m.is_watertight and m.is_volume and m.volume > 0:
            ok += 1; vols.append(float(m.volume))
        else:
            bad += 1
    rep = {"kati_sayisi": int(ok), "hatali": int(bad),
           "toplam_hacim_m3": round(float(np.sum(vols)), 1) if vols else 0.0,
           "ortalama_hacim_m3": round(float(np.mean(vols)), 1) if vols else 0.0}
    log(f"katilar   : {ok} kapali, {bad} hatali, toplam {rep['toplam_hacim_m3']:,.0f} m3")
    return rep
