"""按配置计算步行路线并绘制随身漫步图（SVG，1080×1920）。配置格式见 config.example.json。
walkmap 可加 "tag"（图卡角标，默认“漫步图”）和 "footnotes"（长句自动折行）。
站点可加 "via": true（只让路线经过，不画不列）、"estimate": true（位置是估计的，加虚线圈）、"route": false（不进路线）。
用法: python3 -I walkmap.py <config.json> <elements.json> <out.svg> <route.json>
"""
import heapq
import json
import math
import sys

cfg_path, src, out_svg, out_route = sys.argv[1:5]
cfg = json.load(open(cfg_path, encoding="utf-8"))
els = json.load(open(src))["elements"]
c = cfg["walkmap"]
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = c["lat_min"], c["lat_max"], c["lon_min"], c["lon_max"]
COS = math.cos(math.radians((LAT_MIN + LAT_MAX) / 2))
W, FH, TOP = 1080, 1920, 300
SCALE = W / ((LON_MAX - LON_MIN) * COS)
H = int((LAT_MAX - LAT_MIN) * SCALE)
SNAP = c.get("snap_m", 120)


def xy(lat, lon):
    return ((lon - LON_MIN) * COS * SCALE, TOP + (LAT_MAX - lat) * SCALE)


def dist(a, b):
    return math.hypot((a[1] - b[1]) * 111320 * COS, (a[0] - b[0]) * 111320)


WALKABLE = {"primary", "secondary", "tertiary", "residential", "living_street", "footway", "service",
            "pedestrian", "path", "steps", "unclassified", "primary_link", "secondary_link",
            "tertiary_link", "cycleway"}
graph, coords, ways = {}, {}, []
for e in els:
    t, g = e.get("tags", {}), e.get("geometry")
    if e["type"] != "way" or not g or "highway" not in t:
        continue
    ways.append((t, g))
    if t["highway"] not in WALKABLE:
        continue
    for n, p in zip(e["nodes"], g):
        coords[n] = (p["lat"], p["lon"])
    for a, b in zip(e["nodes"], e["nodes"][1:]):
        d = dist(coords[a], coords[b])
        graph.setdefault(a, []).append((b, d))
        graph.setdefault(b, []).append((a, d))


def route_near(s, t):
    """起终点各取 SNAP 米内的路网节点，连同走到路上的距离一起取最短，容忍断头路。"""
    sp, tp = (s["lat"], s["lon"]), (t["lat"], t["lon"])
    start = {n: dist(coords[n], sp) for n in graph if dist(coords[n], sp) < SNAP}
    goal = {n: dist(coords[n], tp) for n in graph if dist(coords[n], tp) < SNAP}
    best, prev = dict(start), {}
    pq = [(d, n) for n, d in start.items()]
    heapq.heapify(pq)
    while pq:
        d, n = heapq.heappop(pq)
        if d > best[n]:
            continue
        for m, w in graph[n]:
            if d + w < best.get(m, 1e18):
                best[m], prev[m] = d + w, n
                heapq.heappush(pq, (d + w, m))
    end = min((n for n in goal if n in best), key=lambda n: best[n] + goal[n])
    path = [end]
    while path[-1] in prev:
        path.append(prev[path[-1]])
    return path[::-1], best[end] + goal[end]


stops = cfg["stops"]
on_route = [s for s in stops if s.get("route", True) and "lat" in s]
legs, total = [], 0
for s, t in zip(on_route, on_route[1:]):
    p, d = route_near(s, t)
    legs.append((s, t, p, d))
    total += d
    print(f'{s["no"]}->{t["no"]} {s["name"]} -> {t["name"]}: {d:.0f} m')
print(f"total {total:.0f} m")
json.dump({"total_m": round(total), "legs_m": [round(l[3]) for l in legs]}, open(out_route, "w"), ensure_ascii=False)

INK, PAPER, RIVER, ROAD, ROUTE = "#3b3227", "#f6efe2", "#a9c6cf", "#d9ccb4", "#b4472c"
SANS = "'PingFang SC','Hiragino Sans GB','Heiti SC',sans-serif"
SERIF = "'Songti SC','STSong',serif"


def poly(g):
    return " ".join("%.1f,%.1f" % xy(p["lat"], p["lon"]) for p in g)


svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{FH}" viewBox="0 0 {W} {FH}">']
svg.append(f"""<defs><filter id="rough"><feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="2" seed="7"/>
<feDisplacementMap in="SourceGraphic" scale="3"/></filter>
<clipPath id="mapclip"><rect x="0" y="{TOP}" width="{W}" height="{H}"/></clipPath></defs>""")
svg.append(f'<rect width="{W}" height="{FH}" fill="{PAPER}"/>')
svg.append(f'<text x="60" y="110" font-family="{SERIF}" font-size="64" font-weight="700" fill="{INK}">{c["title"]}</text>')
sub = c["subtitle"].replace("{km}", f"{total/1000:.1f}")
svg.append(f'<text x="60" y="170" font-family="{SANS}" font-size="30" fill="{INK}" opacity="0.75">{sub}</text>')
svg.append(f'<text x="60" y="230" font-family="{SANS}" font-size="26" fill="{ROUTE}">{c.get("tag", "漫步图")}</text>')

svg.append('<g clip-path="url(#mapclip)" filter="url(#rough)">')
for area in c.get("areas", []):  # 按名称填充的面（如矿区）
    for e in els:
        if e.get("tags", {}).get("name") == area["name"] and e.get("geometry") and e["tags"].get("landuse"):
            svg.append(f'<polygon points="{poly(e["geometry"])}" fill="{area.get("fill", "#d8d2c4")}"/>')
for e in els:
    t, g = e.get("tags", {}), e.get("geometry")
    if g and t.get("waterway") in ("river", "stream", "canal"):
        w = c.get("river_px", 26) if t["waterway"] == "river" else 8
        svg.append(f'<polyline points="{poly(g)}" fill="none" stroke="{RIVER}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')
WIDTH = {"motorway": 10, "trunk": 12, "primary": 13, "secondary": 11, "tertiary": 9, "residential": 6,
         "unclassified": 6, "living_street": 5, "service": 3, "footway": 2, "steps": 2, "cycleway": 2}
for t, g in sorted(ways, key=lambda w: WIDTH.get(w[0]["highway"], 3)):
    svg.append(f'<polyline points="{poly(g)}" fill="none" stroke="{ROAD}" stroke-width="{WIDTH.get(t["highway"], 3)}" stroke-linecap="round" stroke-linejoin="round"/>')
for e in els:  # 铁路：正线粗、站线细，不参与步行路线
    t, g = e.get("tags", {}), e.get("geometry")
    if g and t.get("railway") == "rail":
        main = "service" not in t
        svg.append(f'<polyline points="{poly(g)}" fill="none" stroke="{INK}" stroke-width="{4 if main else 1.6}" opacity="{0.7 if main else 0.4}"/>')
        if main:
            svg.append(f'<polyline points="{poly(g)}" fill="none" stroke="{INK}" stroke-width="12" stroke-dasharray="2 12" opacity="0.5"/>')
svg.append("</g>")

svg.append('<g clip-path="url(#mapclip)">')
for s, t, p, _ in legs:
    seq = [(s["lat"], s["lon"])] + [coords[n] for n in p] + [(t["lat"], t["lon"])]
    pts = " ".join("%.1f,%.1f" % xy(*q) for q in seq)
    svg.append(f'<polyline points="{pts}" fill="none" stroke="{ROUTE}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="2 14"/>')


def text_on(x, y, ang, text):
    svg.append(f'<text x="{x:.0f}" y="{y:.0f}" transform="rotate({ang:.0f} {x:.0f} {y:.0f})" font-family="{SANS}" font-size="26" fill="{INK}" opacity="0.65" text-anchor="middle" dominant-baseline="middle" paint-order="stroke" stroke="{PAPER}" stroke-width="5">{text}</text>')


def label_road(name, at=0.5, offset=26):
    """街名按道路几何放置：取该名称在图内点数最多的一段，按位置和走向沿法线偏移。"""
    segs = [[q for q in (xy(p["lat"], p["lon"]) for p in g) if 0 < q[0] < W and TOP < q[1] < TOP + H]
            for t, g in ways if t.get("name") == name]
    pts = max(segs, key=len, default=[])
    if len(pts) < 2:
        print(f"路名 {name} 在图内不足两个点，跳过")
        return
    i = max(1, min(len(pts) - 1, int(len(pts) * at)))
    (x1, y1), (x2, y2) = pts[i - 1], pts[i]
    ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
    if ang > 90 or ang < -90:
        ang += 180
    nx, ny = -math.sin(math.radians(ang)), math.cos(math.radians(ang))
    text_on((x1 + x2) / 2 + nx * offset, (y1 + y2) / 2 + ny * offset, ang, name)


for lb in c.get("road_labels", []):
    label_road(lb["name"], lb.get("at", 0.5), lb.get("offset", 26))
for lb in c.get("text_labels", []):  # 数据里没有路名、需要推定的地物，配置里写明
    x, y = xy(lb["lat"], lb["lon"])
    text_on(x, y, lb.get("angle", 0), lb["text"])
for s in stops:
    if "lat" not in s or s.get("via"):
        continue
    x, y = xy(s["lat"], s["lon"])
    num = s["no"].isdigit()
    if s.get("estimate"):  # 位置是估计的：外加一圈虚线
        svg.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="40" fill="none" stroke="{ROUTE}" stroke-width="3" stroke-dasharray="6 6"/>')
    svg.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="26" fill="{ROUTE if num else PAPER}" stroke="{INK}" stroke-width="3"/>')
    svg.append(f'<text x="{x:.0f}" y="{y+10:.0f}" font-family="{SANS}" font-size="28" font-weight="700" fill="{PAPER if num else INK}" text-anchor="middle">{s["no"]}</text>')
svg.append("</g>")

nx, ny = W - 80, TOP + 80
svg.append(f'<path d="M{nx},{ny-40} L{nx-16},{ny+10} L{nx},{ny} L{nx+16},{ny+10} Z" fill="{INK}"/>')
svg.append(f'<text x="{nx}" y="{ny+45}" font-family="{SANS}" font-size="24" fill="{INK}" text-anchor="middle">北</text>')
bar = 200 / 111320 * SCALE
by, bx = TOP + H - 50, W - 60 - bar
svg.append(f'<rect x="{bx-16:.0f}" y="{by-48}" width="{bar+32:.0f}" height="68" fill="{PAPER}" opacity="0.85"/>')
svg.append(f'<line x1="{bx:.0f}" y1="{by}" x2="{W-60}" y2="{by}" stroke="{INK}" stroke-width="5"/>')
svg.append(f'<text x="{bx:.0f}" y="{by-14}" font-family="{SANS}" font-size="22" fill="{INK}">200 米</text>')
svg.append(f'<rect x="0" y="{TOP}" width="{W}" height="{H}" fill="none" stroke="{INK}" stroke-width="3"/>')

y = TOP + H + 62
for s in stops:
    if s.get("via"):
        continue
    num = s["no"].isdigit()
    svg.append(f'<circle cx="80" cy="{y-10}" r="20" fill="{ROUTE if num else PAPER}" stroke="{INK}" stroke-width="{0 if num else 2}"/>')
    svg.append(f'<text x="80" y="{y-1}" font-family="{SANS}" font-size="22" font-weight="700" fill="{PAPER if num else INK}" text-anchor="middle">{s["no"]}</text>')
    svg.append(f'<text x="120" y="{y}" font-family="{SANS}" font-size="29" fill="{INK}">{s["name"]}<tspan fill-opacity="0.6" font-size="23">　{s.get("note", "")}</tspan></text>')
    y += 50
y += 8
for note in c.get("footnotes", []):
    for line in [note[i:i + 44] for i in range(0, len(note), 44)]:  # 长脚注自动折行
        svg.append(f'<text x="60" y="{y}" font-family="{SANS}" font-size="21" fill="{INK}" opacity="0.65">{line}</text>')
        y += 30
svg.append("</svg>")
open(out_svg, "w", encoding="utf-8").write("\n".join(svg))
print("map height", H, "footer ends", y)
if y < FH - 250:
    print(f"提示：图下面空了约 {FH - y} px。想让地图更高（现在 {H} px），加大纬度跨度：每加 {100 / SCALE:.4f} 度约高 100 px（现在是 {LAT_MAX - LAT_MIN:.4f}）。")
if y > FH:
    print("提示：图例和脚注超出 1920，删减站点说明或脚注。")
