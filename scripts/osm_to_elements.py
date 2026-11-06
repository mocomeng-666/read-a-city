"""把 OSM 主 API 的 XML（/api/0.6/map?bbox=...）转成脚本使用的 elements JSON。
Overpass 取不到数据时用它兜底。Overpass 的 `out geom` 结果无需转换。
用法: python3 -I osm_to_elements.py <in.osm> <out.json>
"""
import json
import sys
import xml.etree.ElementTree as ET

src, out = sys.argv[1:3]
root = ET.parse(src).getroot()
pos = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in root.findall("node")}
els = []
for n in root.findall("node"):
    tags = {t.get("k"): t.get("v") for t in n.findall("tag")}
    if tags and "power" not in tags:
        la, lo = pos[n.get("id")]
        els.append({"type": "node", "id": int(n.get("id")), "lat": la, "lon": lo, "tags": tags})
for w in root.findall("way"):
    refs = [x.get("ref") for x in w.findall("nd") if x.get("ref") in pos]
    if len(refs) < 2:
        continue
    els.append({"type": "way", "id": int(w.get("id")), "nodes": [int(r) for r in refs],
                "geometry": [{"lat": pos[r][0], "lon": pos[r][1]} for r in refs],
                "tags": {t.get("k"): t.get("v") for t in w.findall("tag")}})
json.dump({"elements": els}, open(out, "w"), ensure_ascii=False)
print("elements", len(els))
