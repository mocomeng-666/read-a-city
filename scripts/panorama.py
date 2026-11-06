"""按配置绘制代码版鸟瞰全景（SVG，1080×1920），作为生图的构图参考，也是没有生图时的兜底。
河流、道路、编号位置来自 OSM；楼房按居住用地程序生成，只是示意。配置格式见 config.example.json。
用法: python3 -I panorama.py <config.json> <elements.json> <out.svg>
同时写出 <out>.marks.json：编号牌和路名在画面上的位置，供无字生图后由 overlay.py 叠加；
以及 <out>.sketch.svg：去掉文字、编号牌、图例和普通楼房的轻量布局草图，作为生图的参考图。
"""
import json
import math
import random
import sys

cfg_path, src, out_svg = sys.argv[1:4]
cfg = json.load(open(cfg_path, encoding="utf-8"))
els = json.load(open(src))["elements"]
c = cfg["panorama"]
random.seed(c.get("seed", 11))
LAT0, LON0 = c["origin"]
COS = math.cos(math.radians(LAT0))
BEAR = math.radians(c["bear"])
U_MAX, V_MIN, V_MAX, GRID = c["u_max"], c["v_min"], c["v_max"], c["grid"]
RIVER_W = c.get("river_m", 12)
W, FH, BASE = 1080, 1920, 1490
S = W / (2 * U_MAX * 0.92)
G, HZ, PERSP = c.get("ground", 0.84), c.get("height_scale", 0.95), c.get("persp", 0.45)


def m(lat, lon):
    """经纬度 → (u 横向, v 纵深)，单位米。v 沿视线向前，u 向右。"""
    x, y = (lon - LON0) * 111320 * COS, (lat - LAT0) * 111320
    return x * math.cos(BEAR) - y * math.sin(BEAR), x * math.sin(BEAR) + y * math.cos(BEAR)


def k(v):
    return 1 - PERSP * (v - V_MIN) / (V_MAX - V_MIN)


def ground_y(v):
    t = v - V_MIN
    return BASE - S * G * (t - PERSP * t * t / (2 * (V_MAX - V_MIN)))


def P(u, v, z=0.0):
    return (W / 2 + u * S * k(v), ground_y(v) - z * S * HZ * k(v))


def pts(seq):
    return " ".join("%.1f,%.1f" % p for p in seq)


def inside(p):
    return -U_MAX * 2 < p[0] < U_MAX * 2 and V_MIN - 300 < p[1] < V_MAX + 300


INK, PAPER, RED, RIVER, ROAD = "#3b3227", "#f6efe2", "#b4472c", "#a9c6cf", "#e8ddc8"
SANS = "'PingFang SC','Hiragino Sans GB',sans-serif"
SERIF = "'Songti SC','STSong',serif"
WIDTH_M = {"motorway": 26, "trunk": 24, "primary": 22, "secondary": 16, "tertiary": 12, "residential": 8,
           "living_street": 6, "service": 5, "unclassified": 7, "pedestrian": 4}

roads, rivers, streams, zones, areas, rails, special = [], [], [], [], [], [], {}
for e in els:
    t, g = e.get("tags", {}), e.get("geometry")
    if not g or e["type"] != "way":
        continue
    uv = [m(p["lat"], p["lon"]) for p in g]
    special[e["id"]] = uv
    if t.get("highway") in WIDTH_M:
        roads.append((t, uv, WIDTH_M[t["highway"]]))
    if t.get("railway") == "rail":
        rails.append((uv, "service" not in t))
    if t.get("waterway") == "river":
        rivers.append(uv)
    if t.get("waterway") == "stream":
        streams.append(uv)
    if t.get("landuse") == "residential":
        zones.append(uv)
    if t.get("landuse") in c.get("area_landuse", ["quarry"]):
        areas.append(uv)


def in_poly(x, y, poly):
    hit = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def seg_dist(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / L))
    return math.hypot(px - a[0] - t * dx, py - a[1] - t * dy)


def near(px, py, lines, r):
    for uv, w in lines:
        for a, b in zip(uv, uv[1:]):
            if min(a[0], b[0]) - r - w > px or max(a[0], b[0]) + r + w < px:
                continue
            if min(a[1], b[1]) - r - w > py or max(a[1], b[1]) + r + w < py:
                continue
            if seg_dist(px, py, a, b) < r + w / 2:
                return True
    return False


road_lines = [(uv, w) for _, uv, w in roads] + [(uv, 10 if main else 5) for uv, main in rails]
water_lines = [(uv, RIVER_W) for uv in rivers] + [(uv, 8) for uv in streams]
stops = [dict(s, uv=m(s["lat"], s["lon"])) for s in cfg["stops"] if "lat" in s]
core = [(*m(a[0], a[1]), a[2]) for a in c.get("old_core", [])]
hmin, hmax = c.get("house_height", [9, 18])
only_zones = c.get("only_residential", True) and zones

items = []
for gu in range(-U_MAX, U_MAX, GRID):
    for gv in range(V_MIN, V_MAX, GRID):
        u, v = gu + GRID / 2 + random.uniform(-4, 4), gv + GRID / 2 + random.uniform(-4, 4)
        if near(u, v, water_lines, 12) or near(u, v, road_lines, 8):
            continue
        if any(math.hypot(u - s["uv"][0], v - s["uv"][1]) < 34 for s in stops):
            continue
        if any(in_poly(u, v, a) for a in areas):
            continue
        if only_zones and not any(in_poly(u, v, z) for z in zones):
            if random.random() < c.get("tree_outside", 0.12):
                items.append(("tree", u, v, 7))
            continue
        if random.random() < 0.1:
            items.append(("tree", u, v, 5))
        elif any(math.hypot(u - a, v - b) < r for a, b, r in core):
            items.append(("old", u, v, (random.uniform(11, 15), random.uniform(9, 12), random.choice([4, 5, 7]))))
        else:
            d = GRID * 0.62
            items.append(("house", u, v, (random.uniform(d * 0.8, d), random.uniform(d * 0.7, d * 0.9), random.uniform(hmin, hmax))))
for s in stops:
    if s.get("kind"):
        items.append(("landmark", s["uv"][0], s["uv"][1], s["kind"]))

WALL_F, WALL_S, ROOF = "#ecdfca", "#d6c4a6", "#c8ab83"


def box(u, v, w, d, h, roof=ROOF, wall_f=WALL_F, wall_s=WALL_S, windows=True):
    u0, u1, v0, v1 = u - w / 2, u + w / 2, v - d / 2, v + d / 2
    su = u0 if u > 0 else u1
    out = [f'<polygon points="{pts([P(su, v0), P(su, v1), P(su, v1, h), P(su, v0, h)])}" fill="{wall_s}" stroke="{INK}" stroke-width="1.2"/>',
           f'<polygon points="{pts([P(u0, v0), P(u1, v0), P(u1, v0, h), P(u0, v0, h)])}" fill="{wall_f}" stroke="{INK}" stroke-width="1.3"/>',
           f'<polygon points="{pts([P(u0, v0, h), P(u1, v0, h), P(u1, v1, h), P(u0, v1, h)])}" fill="{roof}" stroke="{INK}" stroke-width="1.3"/>']
    if windows and h >= 9:
        cols = max(2, int(w // 4.5))
        for f in range(int(h // 3)):
            for i in range(cols):
                wu = u0 + (i + 0.5) * w / cols
                a, b = P(wu - 0.8, v0, f * 3 + 1.0), P(wu + 0.8, v0, f * 3 + 2.2)
                out.append(f'<rect x="{a[0]:.1f}" y="{b[1]:.1f}" width="{max(b[0]-a[0],1):.1f}" height="{max(a[1]-b[1],1):.1f}" fill="{INK}" opacity="0.32"/>')
    return out


def tree(u, v, r, big=False):
    g, t = P(u, v), P(u, v, r * 1.5)
    rr = r * S * k(v)
    return [f'<line x1="{g[0]:.1f}" y1="{g[1]:.1f}" x2="{t[0]:.1f}" y2="{t[1]:.1f}" stroke="{INK}" stroke-width="{3 if big else 1.4}"/>',
            f'<ellipse cx="{t[0]:.1f}" cy="{t[1]-rr*0.4:.1f}" rx="{rr:.1f}" ry="{rr*0.8:.1f}" fill="{"#879f72" if big else "#a5b78c"}" stroke="{INK}" stroke-width="1.1"/>']


def gable(u, v, w, d, h, ridge=INK):
    out = box(u, v, w, d, h, roof="#bdb8aa", wall_f="#e8dfcf", wall_s="#cfc3ae", windows=False)
    a, b = P(u, v - d / 2, h + 2.4), P(u, v + d / 2, h + 2.4)
    for uu in (u - w / 2, u + w / 2):
        out.append(f'<polygon points="{pts([P(uu, v - d / 2, h), P(uu, v + d / 2, h), b, a])}" fill="#aaa598" stroke="{INK}" stroke-width="1.1"/>')
    out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{ridge}" stroke-width="2.4"/>')
    return out


def landmark(kd, u, v):
    """只画通用样子，不充当实景。"""
    if kd == "pavilion":
        return gable(u, v, 14, 10, 5) + tree(u + 16, v - 4, 6)
    if kd == "school":
        return box(u, v, 40, 20, 12, roof="#d8ccb6")
    if kd == "gallery":
        return gable(u, v, 22, 8, 3.5)
    if kd == "wall":
        out = []
        for i in range(-3, 4):
            out += box(u + i * 12, v, 11.5, 5, 6, roof="#a9a294", wall_f="#c9c0ae", wall_s="#b5ab98", windows=False)
        return out
    if kd == "market":
        return box(u, v, 40, 26, 7, roof="#b5c3c6", windows=False)
    return []


svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{FH}" viewBox="0 0 {W} {FH}">']
ground = [P(-U_MAX, V_MIN), P(U_MAX, V_MIN), P(U_MAX, V_MAX), P(-U_MAX, V_MAX)]
svg.append(f"""<defs>
<filter id="ink"><feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="3"/><feDisplacementMap in="SourceGraphic" scale="2.2"/></filter>
<filter id="wash"><feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="3" seed="9"/><feDisplacementMap in="SourceGraphic" scale="14"/><feGaussianBlur stdDeviation="1.5"/></filter>
<clipPath id="land"><polygon points="{pts(ground)}"/></clipPath>
<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PAPER}"/><stop offset="1" stop-color="{PAPER}" stop-opacity="0"/></linearGradient>
<linearGradient id="fadeb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PAPER}" stop-opacity="0"/><stop offset="1" stop-color="{PAPER}"/></linearGradient>
</defs>""")
svg.append(f'<rect width="{W}" height="{FH}" fill="{PAPER}"/>')
svg.append('<g clip-path="url(#land)">')
svg.append(f'<polygon points="{pts(ground)}" fill="{c.get("ground_fill", "#e6e2c6")}"/>')
svg.append('<g filter="url(#wash)">')
for uv in areas:  # 矿区：一圈圈台阶
    cx = sum(p[0] for p in uv) / len(uv)
    cy = sum(p[1] for p in uv) / len(uv)
    for f, col in ((1, "#d3ccbc"), (0.72, "#c4bcaa"), (0.45, "#b3aa96"), (0.2, "#a0967f")):
        svg.append(f'<polygon points="{pts(P(cx + (a - cx) * f, cy + (b - cy) * f) for a, b in uv)}" fill="{col}" stroke="{INK}" stroke-opacity="0.25"/>')
for uv, wd in [(r, RIVER_W) for r in rivers] + [(s, 8) for s in streams]:
    seq = [p for p in uv if inside(p)]
    left, right = [], []
    for a, b in zip(seq, seq[1:] + seq[-1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L == 0:
            continue
        nx, ny = -dy / L * wd / 2, dx / L * wd / 2
        left.append(P(a[0] + nx, a[1] + ny))
        right.append(P(a[0] - nx, a[1] - ny))
    if left:
        svg.append(f'<polygon points="{pts(left + right[::-1])}" fill="{RIVER}"/>')
svg.append("</g>")
svg.append('<g filter="url(#ink)">')
for col, extra, op in ((INK, 2.5, 0.3), (ROAD, 0, 1)):
    for t, uv, w in sorted(roads, key=lambda r: r[2]):
        seq = [p for p in uv if inside(p)]
        if len(seq) < 2:
            continue
        svg.append(f'<polyline points="{pts(P(a, b) for a, b in seq)}" fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="{w*S*k(seq[len(seq)//2][1])*0.8+extra:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
for uv, main in sorted(rails, key=lambda r: r[1]):  # 铁路：正线画枕木，站线只画细线
    seq = [p for p in uv if inside(p)]
    if len(seq) < 2:
        continue
    line = pts(P(a, b) for a, b in seq)
    wd = S * k(seq[len(seq) // 2][1])
    svg.append(f'<polyline points="{line}" fill="none" stroke="{INK}" stroke-opacity="{0.75 if main else 0.45}" stroke-width="{wd * (2.2 if main else 1.2):.1f}"/>')
    if main:
        svg.append(f'<polyline points="{line}" fill="none" stroke="{INK}" stroke-opacity="0.5" stroke-width="{wd * 6:.1f}" stroke-dasharray="1.5 6"/>')
if c.get("bridge_way") and c["bridge_way"] in special:  # 石桥：桥面加桥墩
    uv = special[c["bridge_way"]]
    a, b = uv[0], uv[-1]
    n = 8
    for i in range(n + 1):
        u, v = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
        p, q = P(u, v), P(u, v, 8)
        svg.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="{INK}" stroke-width="5"/>')
    svg.append(f'<polyline points="{pts([P(a[0], a[1], 8), P(b[0], b[1], 8)])}" fill="none" stroke="{INK}" stroke-width="13"/>')
    svg.append(f'<polyline points="{pts([P(a[0], a[1], 8), P(b[0], b[1], 8)])}" fill="none" stroke="#cfc6b4" stroke-width="10"/>')
svg.append("</g>")
svg.append('<g filter="url(#ink)">')
sketch = list(svg)
for it in sorted(items, key=lambda i: -i[2]):
    if it[0] == "house":
        svg += box(it[1], it[2], *it[3])
        continue
    if it[0] == "old":
        part = gable(it[1], it[2], *it[3])
    elif it[0] == "tree":
        part = tree(it[1], it[2], it[3])
    else:
        part = landmark(it[3], it[1], it[2])
    svg += part
    sketch += part
fy = P(0, V_MAX)[1]
for doc in (svg, sketch):
    doc.append("</g></g>")
    doc.append(f'<rect x="0" y="{fy-60:.0f}" width="{W}" height="230" fill="url(#fade)"/>')
    doc.append(f'<rect x="0" y="{BASE-70}" width="{W}" height="75" fill="url(#fadeb)"/>')
sketch.append("</svg>")
open(out_svg.rsplit(".", 1)[0] + ".sketch.svg", "w", encoding="utf-8").write("\n".join(sketch))


marks = {"labels": [], "pins": []}


def label(text, a, b, dz=0):
    (x1, y1), (x2, y2) = P(*a), P(*b)
    ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
    if ang > 90 or ang < -90:
        ang += 180
    x, y = (x1 + x2) / 2, (y1 + y2) / 2 + dz
    marks["labels"].append({"text": text, "x": round(x), "y": round(y), "angle": round(ang)})
    svg.append(f'<text x="{x:.0f}" y="{y:.0f}" transform="rotate({ang:.0f} {x:.0f} {y:.0f})" font-family="{SANS}" font-size="30" fill="{INK}" fill-opacity="0.8" text-anchor="middle" dominant-baseline="middle" paint-order="stroke" stroke="{PAPER}" stroke-width="6" stroke-opacity="0.85">{text}</text>')


for lb in c.get("road_labels", []):
    uv = [p for p in max((uv for t, uv, w in roads if t.get("name") == lb["name"]), key=len) if inside(p)]
    i = max(1, min(len(uv) - 1, int(len(uv) * lb.get("at", 0.5))))
    label(lb["name"], uv[i - 1], uv[i], lb.get("dz", 0))
for lb in c.get("text_labels", []):
    a = m(lb["lat"], lb["lon"])
    (x, y) = P(*a)
    marks["labels"].append({"text": lb["text"], "x": round(x), "y": round(y), "angle": 0})
    svg.append(f'<text x="{x:.0f}" y="{y:.0f}" font-family="{SANS}" font-size="30" fill="{INK}" fill-opacity="0.8" text-anchor="middle" paint-order="stroke" stroke="{PAPER}" stroke-width="6" stroke-opacity="0.85">{lb["text"]}</text>')
for s in stops:
    g = P(*s["uv"], 8)
    px, py = g[0], g[1] - 64
    num = s["no"].isdigit()
    marks["pins"].append({"no": s["no"], "x": round(g[0]), "y": round(g[1])})
    svg.append(f'<line x1="{g[0]:.0f}" y1="{g[1]:.0f}" x2="{px:.0f}" y2="{py:.0f}" stroke="{INK}" stroke-width="2"/>')
    svg.append(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="24" fill="{RED if num else PAPER}" stroke="{INK}" stroke-width="2.5"/>')
    svg.append(f'<text x="{px:.0f}" y="{py+9:.0f}" font-family="{SANS}" font-size="26" font-weight="700" fill="{PAPER if num else INK}" text-anchor="middle">{s["no"]}</text>')

svg.append(f'<text x="60" y="110" font-family="{SERIF}" font-size="64" font-weight="700" fill="{INK}">{c["title"]}</text>')
svg.append(f'<text x="60" y="170" font-family="{SANS}" font-size="30" fill="{INK}" opacity="0.75">{c["subtitle"]}</text>')
svg.append(f'<text x="60" y="230" font-family="{SANS}" font-size="26" fill="{RED}">{c.get("tag", "01 / 03　图卡")}</text>')
ny = BASE + 60
for i, s in enumerate(c["legend"]):
    cx, cy = 80 + (i % 4) * 250, ny + (i // 4) * 60
    num = s[0].isdigit()
    svg.append(f'<circle cx="{cx}" cy="{cy-9}" r="19" fill="{RED if num else PAPER}" stroke="{INK}" stroke-width="2"/>')
    svg.append(f'<text x="{cx}" y="{cy}" font-family="{SANS}" font-size="22" font-weight="700" fill="{PAPER if num else INK}" text-anchor="middle">{s[0]}</text>')
    svg.append(f'<text x="{cx+32}" y="{cy}" font-family="{SANS}" font-size="27" fill="{INK}">{s[1]}</text>')
fy = ny + 165
svg.append(f'<text x="60" y="{fy}" font-family="{SANS}" font-size="28" font-weight="700" fill="{RED}">氛围示意，不作导航</text>')
for i, line in enumerate(c.get("footnotes", [])):
    svg.append(f'<text x="60" y="{fy+42+i*32}" font-family="{SANS}" font-size="22" fill="{INK}" opacity="0.65">{line}</text>')
svg.append("</svg>")
open(out_svg, "w", encoding="utf-8").write("\n".join(svg))
json.dump(marks, open(out_svg.rsplit(".", 1)[0] + ".marks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("items", len(items), "far edge y", round(P(0, V_MAX)[1]), {s["no"]: tuple(round(x) for x in s["uv"]) for s in stops})
