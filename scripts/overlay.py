"""生成叠加页：在生图成品底部加图例和示意说明，再用无头 Chrome 截图出最终图卡。
用法: python3 -I overlay.py <config.json> <生图路径（相对输出页）> <out.html> [marks.json]
给了 marks.json（panorama.py 写出的位置文件）时，按无字插画处理：标题、路名、编号牌也由这里加。
marks.json 里的 legend、notes 可覆盖配置里的图例和说明（只标锚点时用）；label 加 "box": true 时带纸色底，可盖住模型画出的假字。
位置默认取代码版全景；看过成图后在 marks.json 里改 x、y 对准。
截图: "<Chrome>" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
      --window-size=1080,1920 --screenshot=<final.png> file://<out.html>
"""
import html
import json
import sys

cfg_path, image, out = sys.argv[1:4]
marks = json.load(open(sys.argv[4], encoding="utf-8")) if len(sys.argv) > 4 else None
c = json.load(open(cfg_path, encoding="utf-8"))["panorama"]
if marks:
    c = {**c, **{k: marks[k] for k in ("legend", "overlay_notes") if k in marks}}
esc = html.escape
items = "\n".join(
    f'      <div class="item"><span class="pin{"" if n.isdigit() else " a"}">{esc(n)}</span>{esc(name)}</div>'
    for n, name in c["legend"])
notes = "<br>".join(esc(x) for x in c["overlay_notes"])

text_layer = ""
if marks:
    labels = "\n".join(
        f'  <div class="label{" boxed" if lb.get("box") else ""}" style="left:{lb["x"]}px; top:{lb["y"]}px; transform:translate(-50%,-50%) rotate({lb.get("angle", 0)}deg)">{esc(lb["text"])}</div>'
        for lb in marks["labels"])
    pins = "\n".join(
        f'  <div class="stick" style="left:{p["x"]}px; top:{p["y"] - 64}px"></div>'
        f'<div class="pin big{"" if p["no"].isdigit() else " a"}" style="left:{p["x"]}px; top:{p["y"] - 64}px">{esc(p["no"])}</div>'
        for p in marks["pins"])
    text_layer = f"""  <div class="head">
    <h1>{esc(c["title"])}</h1>
    <p>{esc(c["subtitle"])}</p>
    <p class="tag">{esc(c.get("tag", "全景"))}</p>
  </div>
{labels}
{pins}
"""

open(out, "w", encoding="utf-8").write(f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<style>
  :root {{ --paper:#f6efe2; --ink:#3b3227; --red:#b4472c; }}
  html,body {{ margin:0; width:1080px; height:1920px; overflow:hidden; background:var(--paper); }}
  body {{ position:relative; font-family:"PingFang SC","Hiragino Sans GB",sans-serif; color:var(--ink); }}
  img {{ position:absolute; inset:0; width:1080px; height:1920px; object-fit:cover; }}
  .panel {{ position:absolute; left:0; right:0; bottom:0; height:268px;
    background:linear-gradient(to bottom, rgba(246,239,226,0) 0, rgba(246,239,226,.9) 40px, var(--paper) 62px); }}
  .legend {{ position:absolute; left:60px; right:40px; top:46px;
    display:grid; grid-template-columns:repeat(4, 1fr); row-gap:12px; }}
  .item {{ display:flex; align-items:center; gap:12px; font-size:27px; white-space:nowrap; }}
  .pin {{ width:38px; height:38px; border-radius:50%; background:var(--red); color:#fff;
    font-size:22px; font-weight:700; display:flex; align-items:center; justify-content:center;
    box-shadow:0 0 0 2px var(--ink) inset; }}
  .pin.a {{ background:#fff; color:var(--ink); }}
  .note {{ position:absolute; left:60px; right:60px; top:146px; }}
  .note b {{ color:var(--red); font-size:26px; }}
  .note p {{ margin:8px 0 0; font-size:21px; opacity:.7; line-height:1.4; }}
  .head {{ position:absolute; left:0; right:0; top:0; height:300px; padding:58px 60px 0; box-sizing:border-box;
    background:linear-gradient(to top, rgba(246,239,226,0) 0, rgba(246,239,226,.9) 50px, var(--paper) 80px); }}
  .head h1 {{ margin:0; font-family:"Songti SC","STSong",serif; font-size:64px; line-height:1.1; }}
  .head p {{ margin:16px 0 0; font-size:30px; opacity:.75; }}
  .head p.tag {{ margin-top:12px; font-size:26px; color:var(--red); opacity:1; }}
  .label {{ position:absolute; font-size:30px; white-space:nowrap; color:rgba(59,50,39,.85);
    text-shadow:0 0 4px var(--paper), 0 0 4px var(--paper), 0 0 8px var(--paper); }}
  .label.boxed {{ background:var(--paper); padding:2px 12px; border-radius:6px; color:var(--ink); }}  /* 盖住模型画出的假字 */
  .stick {{ position:absolute; width:2px; height:64px; background:var(--ink); transform:translateX(-1px); }}
  .pin.big {{ position:absolute; width:48px; height:48px; font-size:26px; transform:translate(-50%,-50%);
    box-shadow:0 0 0 2.5px var(--ink) inset; }}
</style></head>
<body>
  <img src="{esc(image)}" alt="">
{text_layer}  <div class="panel">
    <div class="legend">
{items}
    </div>
    <div class="note">
      <b>氛围示意，不作导航</b>
      <p>{notes}</p>
    </div>
  </div>
</body></html>
""")
