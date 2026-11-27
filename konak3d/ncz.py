"""Netcad .NCZ (ikili) okuyucu - kayit duzeni tersine muhendislikle cozuldu.

Kayit duzeni (Netcad GIS 8.5.6 dosyasinda gozlenen):
  kose        : Y(float64) X(float64) Z(float64)  -> 24 bayt adim
  kose dizisi : ardisik koseler = polyline/poligon
  son ek      : 0x05 <5 haneli bina no> 00*11 0x01 <kat sayisi (1 ASCII hane)>
Bu bir sezgiseldir (resmi format belgesi yok); sonuclar ortofoto ile dogrulanir.
"""
import re, numpy as np
from collections import Counter
from shapely.geometry import Polygon

TAIL = re.compile(rb"\x05(\d{5})\x00{11}\x01(.)")

def _scan_pairs(b, xr, yr):
    pts = {}
    for s in range(8):
        arr = np.frombuffer(b[s:s + (len(b) - s) // 8 * 8], dtype="<f8")
        ym = (arr > yr[0]) & (arr < yr[1]); xm = (arr > xr[0]) & (arr < xr[1])
        for i in np.where(ym[:-1] & xm[1:])[0]:
            pts[s + 8 * int(i)] = (float(arr[i + 1]), float(arr[i]))
    return pts

def parse(path, bounds):
    b = open(path, "rb").read()
    xr = (bounds.left, bounds.right); yr = (bounds.bottom, bounds.top)
    pts = _scan_pairs(b, xr, yr); offs = sorted(pts)
    runs, cur = [], [offs[0]]
    for o in offs[1:]:
        if o - cur[-1] == 24: cur.append(o)
        else: runs.append(cur); cur = [o]
    runs.append(cur)
    out = []
    for r in runs:
        if len(r) < 3: continue
        m = TAIL.search(b[r[-1] + 24: r[-1] + 224])
        if not m: continue
        P = Polygon([pts[o] for o in r])
        if P.is_valid and P.area > 0:
            out.append(dict(geom=P, bina_no=m.group(1).decode(), kat=int(m.group(2))))
    return out, len(runs)

def kat_histogram(items):
    c = Counter(i["kat"] for i in items); return dict(sorted(c.items()))
