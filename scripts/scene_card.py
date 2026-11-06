"""把一张历史场景示意画做成图卡：加标题、几处带底色的标签（也用来盖住模型画出的假字）和“示意”说明，再用无头 Chrome 截图。
图可以来自 gen_image.py，也可以是用户在自己手机上的生图 App（豆包、即梦、ChatGPT 等）里生成后交回的。只用标准库。

用法: python3 -I scene_card.py <card.json> <out.png> [--html <out.html>]

card.json:
{
  "image": "images/01-tianqiao-scene.png",      // 相对 card.json 所在目录
  "title": "蚌埠天桥 · 百年前的桥头",
  "subtitle": "1920 年代，跨铁路的木桥两头，一个早晨",
  "tag": "01 / 03　图卡",
  "labels": [{"text": "桥顶残棋", "x": 520, "y": 1012}],
  "label_space": "image",   // 可选：labels 写原图像素坐标，脚本自动换算；不写就是卡面 1080×1920 坐标
  "badge": "示意，不是照片", // 可选：页脚粗体字。真老地图、老照片做卡时改成“真图”或“老地图，1927 年编绘”
  "source": "画面依据……；桥的结构和铺面样子由 AI 生成。"
}
图按 1080 宽铺满，从顶部起裁到 1920 高（Seedream 的 1152×2048 等比缩成 1080×1920，正好不裁）。
App 自带的“AI 生成”水印保留，不要裁掉。场景画的提示词见 references/scene-prompt-template.md。
"""
import html
import json
import os
import shutil
import subprocess
import sys

args = sys.argv[1:]
html_out = None
if "--html" in args:
    i = args.index("--html")
    html_out = args[i + 1]
    del args[i:i + 2]
cfg_path, out_png = args[:2]
c = json.load(open(cfg_path, encoding="utf-8"))
root = os.path.dirname(os.path.abspath(cfg_path))
html_out = os.path.abspath(html_out or os.path.splitext(out_png)[0] + ".html")
img = os.path.relpath(os.path.join(root, c["image"]), os.path.dirname(html_out))
esc = html.escape

k = 1.0
if c.get("label_space") == "image":
    w = subprocess.run(["sips", "-g", "pixelWidth", os.path.join(root, c["image"])], capture_output=True, text=True).stdout.split()[-1]
    k = 1080 / int(w)
labels = "\n".join(f'<div class="lb" style="left:{lb["x"] * k:.0f}px;top:{lb["y"] * k:.0f}px">{esc(lb["text"])}</div>' for lb in c.get("labels", []))
page = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<style>
  :root {{ --paper:#f6efe2; --ink:#3b3227; --red:#b4472c; }}
  html,body {{ margin:0; width:1080px; height:1920px; overflow:hidden; background:var(--paper); }}
  body {{ position:relative; font-family:"PingFang SC","Hiragino Sans GB",sans-serif; color:var(--ink); }}
  .bg {{ position:absolute; left:0; top:0; width:1080px; height:1920px; object-fit:cover; object-position:top; }}
  .top {{ position:absolute; left:0; right:0; top:0; height:300px; background:linear-gradient(var(--paper) 55%, rgba(246,239,226,0)); }}
  h1 {{ position:absolute; left:60px; top:48px; margin:0; font:700 58px "Songti SC",serif; }}
  .sub {{ position:absolute; left:60px; top:128px; font-size:28px; opacity:.8; }}
  .tag {{ position:absolute; left:60px; top:172px; font-size:25px; color:var(--red); }}
  .lb {{ position:absolute; transform:translate(-50%,-50%); background:var(--paper); font-size:24px; font-weight:600;
    padding:3px 12px; border-radius:6px; border:2px solid var(--red); white-space:nowrap; }}
  .foot {{ position:absolute; left:0; right:0; bottom:0; padding:22px 60px 26px; background:rgba(246,239,226,.94); font-size:21px; line-height:1.5; }}
  .foot b {{ color:var(--red); font-size:26px; }}
</style></head>
<body>
  <img class="bg" src="{esc(img)}">
  <div class="top"></div>
  <h1>{esc(c["title"])}</h1>
  <div class="sub">{esc(c.get("subtitle", ""))}</div>
  <div class="tag">{esc(c.get("tag", ""))}</div>
  {labels}
  <div class="foot"><b>{esc(c.get("badge", "示意，不是照片"))}</b><br>{esc(c.get("source", ""))}</div>
</body></html>
"""
open(html_out, "w", encoding="utf-8").write(page)

chrome = next((p for p in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           shutil.which("google-chrome") or "", shutil.which("chromium") or ""] if p and os.path.exists(p)), None)
if not chrome:
    sys.exit(f"已写出 {html_out}；没找到 Chrome，请用浏览器打开后截图（1080×1920）")
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1080,1920",
                f"--screenshot={os.path.abspath(out_png)}", "file://" + html_out], capture_output=True)
print(f"{out_png}（叠加页 {html_out}）")
