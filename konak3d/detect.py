"""Karo bazli otomatik cati/bina tespiti (MobileSAM, CPU)."""
import sys, time, pickle, numpy as np, cv2
from rasterio.windows import Window
from shapely.geometry import Polygon, box

def run(raster, aoi_px, out_pkl, sam_ckpt, gsd_down=2, tile=1024, overlap=128, max_tiles=None, points=36, log=print):
    sys.path.insert(0, "/tmp/MobileSAM")
    import torch; torch.set_num_threads(2)
    from mobile_sam import sam_model_registry, SamAutomaticMaskGenerator
    P = Polygon(aoi_px); S = tile - overlap; TF = tile * gsd_down
    minx, miny, maxx, maxy = P.bounds
    tiles = [(x, y) for y in range(int(miny), int(maxy), S * gsd_down) for x in range(int(minx), int(maxx), S * gsd_down)
             if box(x, y, x + TF, y + TF).intersection(P).area > 0.04 * TF * TF]
    if max_tiles: tiles = tiles[:max_tiles]
    log(f"{len(tiles)} tiles")
    sam = sam_model_registry["vit_t"](checkpoint=sam_ckpt).eval()
    gen = SamAutomaticMaskGenerator(sam, points_per_side=points, pred_iou_thresh=0.84, stability_score_thresh=0.88, min_mask_region_area=150)
    res = []
    for x0, y0 in tiles:
        t0 = time.time(); w = min(TF, raster.width - x0); h = min(TF, raster.height - y0)
        a = raster.read(window=Window(x0, y0, w, h)).transpose(1, 2, 0)
        tl = np.zeros((tile, tile, 3), np.uint8); sm = cv2.resize(a, (w // gsd_down, h // gsd_down), interpolation=cv2.INTER_AREA)
        tl[:sm.shape[0], :sm.shape[1]] = sm
        masks = gen.generate(tl); fl = tl.astype(float)
        exg = (2 * fl[..., 1] - fl[..., 0] - fl[..., 2]) / (fl.sum(-1) + 1e-6)
        for m in masks:
            seg = m["segmentation"].astype("uint8"); ar = m["area"]
            if ar < 500 or ar > 40000: continue
            cs, _ = cv2.findContours(seg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            c = max(cs, key=cv2.contourArea); ca = cv2.contourArea(c)
            sol = ca / max(cv2.contourArea(cv2.convexHull(c)), 1)
            (_, _), (bw, bh), _ = cv2.minAreaRect(c); rect = ca / max(bw * bh, 1); arr = max(bw, bh) / max(min(bw, bh), 1)
            bx, by, bw2, bh2 = cv2.boundingRect(c)
            if bx <= 1 or by <= 1 or bx + bw2 >= sm.shape[1] - 1 or by + bh2 >= sm.shape[0] - 1 or bx + bw2 >= tile - 1 or by + bh2 >= tile - 1: continue
            if sol > 0.86 and rect > 0.72 and arr < 5 and exg[seg > 0].mean() < 0.03:
                res.append(dict(c=(c.reshape(-1, 2) * gsd_down + [x0, y0]).astype(np.float64)))
        log(f"{x0} {y0} {len(masks)} {len(res)} {round(time.time()-t0)}")
        pickle.dump(dict(res=res, tiles=tiles, done=(x0, y0)), open(out_pkl, "wb"))
    log("DONE")
