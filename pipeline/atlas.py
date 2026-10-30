"""The atlas: where Thompson's traditions are, on a papercut world map.

    uv run python pipeline/atlas.py        (also run at the end of static.py)

Projects Natural Earth's land outlines (public domain, naturalearthdata.com)
with the Natural Earth projection, centred on 11°E so that the seam falls in
the Pacific between Samoa and the Cook Islands, simplifies and rounds them
like cut paper, and places every tradition from places.py. Writes
docs/data/atlas.json:

  w, h        size of the map in map units
  sheet       the outline of the map (the sea)
  land        the continents and islands, one SVG path
  grat        meridians and parallels every 30°
  places      [key, name, kind, x, y] per place; kind p (place), b (broad region), t (tradition)
  culture_place   per tradition in meta.json's order: its place's index, or -1
  figures     [art name, x, y, width, mirrored] for the papercut figures in the sea
"""

import json
import math
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "naturalearth"
URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson"
sys.path.insert(0, str(ROOT / "pipeline"))
from places import PLACES, place_of  # noqa: E402

LON0 = 11.0          # central meridian
LAT_TOP, LAT_BOTTOM = 84.0, -57.0
W = 1000.0
TOLERANCE = 0.45     # simplification, in map units
MIN_AREA = 0.6       # islands smaller than this (map units²) are dropped, unless a place is on them

# papercut figures in the sea: art name, latitude, longitude, width in map units, mirrored
FIGURES = [
    ("atlas-serpent", 41, -42, 74, False),     # North Atlantic
    ("atlas-whale", 36, -152, 78, False),      # North Pacific
    ("atlas-ship", -31, 79, 62, False),        # Indian Ocean
    ("atlas-compass", -41, -128, 58, False),   # South Pacific
    ("atlas-isle", -38.5, -13, 40, False),     # a far-off island in the South Atlantic, about where Tristan da Cunha is
]


def ne_xy(lon, lat):
    """Natural Earth projection (Šavrič et al. 2015), in radians-based units."""
    lam, phi = math.radians(lon), math.radians(lat)
    p2 = phi * phi
    p4 = p2 * p2
    x = lam * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * p2 * (0.003971 - 0.001529 * p2)))
    y = phi * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return x, y


K = W / 2 / ne_xy(180, 0)[0]
Y_TOP = ne_xy(0, LAT_TOP)[1]
H = round((Y_TOP - ne_xy(0, LAT_BOTTOM)[1]) * K, 1)


def shift(lon):
    return (lon - LON0 + 180) % 360 - 180


def project(lon, lat):
    """Map units for a longitude already shifted to the central meridian."""
    x, y = ne_xy(lon, max(min(lat, 89.9), -89.9))
    return W / 2 + x * K, (Y_TOP - y) * K


def place_xy(lat, lon):
    return project(shift(lon), lat)


def rdp(pts, eps):
    """Ramer–Douglas–Peucker on a closed ring (iterative)."""
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = pts[a], pts[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * (px - ax) - dx * (py - ay)) / L if L else math.hypot(px - ax, py - ay)
            if d > best:
                best, idx = d, i
        if best > eps:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def chaikin(pts):
    """One round of corner cutting: soft, cut-paper coastlines."""
    out = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        out += [(0.75 * x1 + 0.25 * x2, 0.75 * y1 + 0.25 * y2), (0.25 * x1 + 0.75 * x2, 0.25 * y1 + 0.75 * y2)]
    return out


def path(rings):
    """Rings as one compact SVG path in relative coordinates."""
    out = []
    for ring in rings:
        q = [(round(x * 10), round(y * 10)) for x, y in ring]
        cmd = [f"M{q[0][0] / 10:g} {q[0][1] / 10:g}l"]
        px, py = q[0]
        steps = []
        for x, y in q[1:]:
            if (x, y) != (px, py):
                steps.append(f"{(x - px) / 10:g} {(y - py) / 10:g}")
                px, py = x, y
        out.append(cmd[0] + " ".join(steps).replace(" -", "-") + "z")
    return "".join(out)


def land(place_pts):
    src = RAW / "ne_50m_land.geojson"
    if not src.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, src)
    data = json.load(open(src))
    rings = []
    for f in data["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            outer = poly[0]
            if max(lat for _, lat in outer) < -60:      # Antarctica
                continue
            lons = [shift(lon) for lon, _ in outer]
            # a ring that crosses the seam is drawn twice, once on each side; the sheet clips it
            crosses = any(abs(a - b) > 180 for a, b in zip(lons, lons[1:]))
            variants = [[lo + 360 if lo < 0 else lo for lo in lons], [lo - 360 if lo > 0 else lo for lo in lons]] if crosses else [lons]
            for lv in variants:
                pts = [project(lo, lat) for lo, (_, lat) in zip(lv, outer)]
                simple = rdp(pts, TOLERANCE)
                a = area(simple if len(simple) >= 3 else pts)
                if a < MIN_AREA:
                    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                    near = any(min(xs) - 3 <= x <= max(xs) + 3 and min(ys) - 3 <= y <= max(ys) + 3 for x, y in place_pts)
                    if not near:
                        continue
                    simple = pts if len(simple) < 4 else simple
                if len(simple) < 4:
                    simple = pts
                rings.append(chaikin(simple[:-1] if simple[0] == simple[-1] else simple))
    return rings


def sheet():
    left = [project(-180, lat) for lat in range(int(LAT_BOTTOM), int(LAT_TOP) + 1)]
    right = [project(180, lat) for lat in range(int(LAT_TOP), int(LAT_BOTTOM) - 1, -1)]
    return path([left + right])


def graticule():
    out = []
    for lon in range(-180, 180, 30):
        if abs(shift(lon)) > 179:
            continue
        pts = [project(shift(lon), lat) for lat in range(int(LAT_BOTTOM), int(LAT_TOP) + 1, 2)]
        out.append("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts))
    for lat in (-30, 0, 30, 60):
        pts = [project(lon, lat) for lon in range(-180, 181, 5)]
        out.append("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts))
    return "".join(out)


def export(cultures, out_dir):
    keys = sorted({k for k in (place_of(c) for c in cultures) if k},
                  key=lambda k: (PLACES[k]["kind"] != "b", PLACES[k]["name"]))
    index = {k: i for i, k in enumerate(keys)}
    places = []
    for k in keys:
        p = PLACES[k]
        x, y = place_xy(p["lat"], p["lon"])
        places.append([k, p["name"], p["kind"], round(x, 1), round(y, 1)])
    rings = land([(p[3], p[4]) for p in places])
    figures = []
    for name, lat, lon, width, mirrored in FIGURES:
        x, y = place_xy(lat, lon)
        figures.append([name, round(x, 1), round(y, 1), width, mirrored])
    out = {"w": W, "h": H, "sheet": sheet(), "land": path(rings), "grat": graticule(), "places": places,
           "culture_place": [index.get(place_of(c), -1) for c in cultures], "figures": figures}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(out_dir) / "atlas.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    placed = sum(1 for i in out["culture_place"] if i >= 0)
    print(f"atlas: {len(places)} places for {placed} of {len(cultures)} traditions, "
          f"{len(rings)} land rings, {len(out['land']) / 1e3:.0f} kB of coastline", file=sys.stderr)
    return out


if __name__ == "__main__":
    meta = json.load(open(ROOT / "docs" / "data" / "meta.json"))
    export(meta["cultures"], ROOT / "docs" / "data")
