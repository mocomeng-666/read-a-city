"""把读本 Markdown 打包成一个手机上直接打开的图文页（单个 HTML，图片内嵌，可离线、可发微信）。只用标准库。

用法: python3 -I build_page.py <reading.md> <out.html> [--max-width 1080] [--quality 72]

读本写法约定（普通 Markdown 的一个小子集）：
- 开头的 --- 块里取 title（“城市 · 从某街读城”）、subtitle（“一句话介绍｜约几公里，连停留约几小时”）；cover: images/x.png 放在标题下当封面图（选最能“看见从前”的那张）。
- ## 是一屏（一站一个），### 是屏内小标题。标题以数字或单个大写字母加空格开头（“## 1 天桥”“## A 铁路桥”）时，编号显示成红色圆标；“## 出发前”这类不带编号。
- ![说明](images/x.png) 单独一行：内嵌图片，说明写在图下。图片用 macOS 自带的 sips 压成 JPEG 再内嵌；没有 sips 时原样内嵌。
- - [ ] 要找的东西：寻宝清单，手机上可以打勾，勾选只记在本机浏览器里。
- > 引用、**粗体**、[链接](url)、- 列表、1. 列表、`代码`。
- 标题以“资料说明”“来源”开头的那一屏默认折叠。
"""
import base64
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

args = sys.argv[1:]
opts = {"--max-width": "1080", "--quality": "72"}
for k in list(opts):
    if k in args:
        i = args.index(k)
        opts[k] = args[i + 1]
        del args[i:i + 2]
src, out = args[:2]
base = os.path.dirname(os.path.abspath(src))
text = open(src, encoding="utf-8").read()

meta = {}
m = re.match(r"---\n(.*?)\n---\n", text, re.S)
if m:
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    text = text[m.end():]
FOLD = ("资料说明", "来源")


def image_data(path):
    """压成 JPEG（宽超过 --max-width 才缩小，竖图不按长边缩，免得字糊）后转 base64；sips 不可用时原样内嵌。"""
    full = os.path.join(base, path)
    if shutil.which("sips"):
        tmp = os.path.join(tempfile.mkdtemp(), "x.jpg")
        w = subprocess.run(["sips", "-g", "pixelWidth", full], capture_output=True, text=True).stdout.split()[-1]
        size = ["--resampleWidth", opts["--max-width"]] if int(w) > int(opts["--max-width"]) else []
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", opts["--quality"],
                            *size, full, "--out", tmp], capture_output=True)
        if r.returncode == 0:
            return "image/jpeg", open(tmp, "rb").read()
    ext = os.path.splitext(full)[1].lower().lstrip(".")
    return f"image/{'jpeg' if ext == 'jpg' else ext}", open(full, "rb").read()


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a>', s)
    return s


sections, cur = [], None
blocks, para, lst = [], [], None
task_no = 0


def flush():
    global para, lst
    if para:
        blocks.append("<p>" + inline(" ".join(para)) + "</p>")
        para = []
    if lst:
        tag, items = lst
        blocks.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
        lst = None


def close_section():
    flush()
    if cur is not None:
        sections.append((cur, blocks[:]))
    blocks.clear()


quote = []
for raw in text.splitlines() + [""]:
    line = raw.rstrip()
    if quote and not line.startswith(">"):
        blocks.append("<blockquote>" + inline(" ".join(quote)) + "</blockquote>")
        quote = []
    if line.startswith("## "):
        close_section()
        cur = line[3:].strip()
        continue
    if cur is None and not line.strip():
        continue
    if cur is None:
        cur = ""
    if line.startswith("### "):
        flush()
        blocks.append("<h3>" + inline(line[4:]) + "</h3>")
    elif m := re.match(r"!\[([^\]]*)\]\(([^)]+)\)\s*$", line):
        flush()
        mime, data = image_data(m.group(2))
        cap = f"<figcaption>{inline(m.group(1))}</figcaption>" if m.group(1) else ""
        blocks.append(f'<figure><img alt="{html.escape(m.group(1))}" src="data:{mime};base64,{base64.b64encode(data).decode()}">{cap}</figure>')
    elif line.startswith(">"):
        flush()
        quote.append(line.lstrip("> ").strip())
    elif m := re.match(r"- \[( |x)\] (.*)", line):
        if para:
            flush()
        if not lst or lst[0] != "ul class=\"hunt\"":
            flush()
            lst = ("ul class=\"hunt\"", [])
        task_no += 1
        lst[1].append(f'<li><label><input type="checkbox" data-k="{task_no}"><span>{inline(m.group(2))}</span></label></li>')
    elif m := re.match(r"(-|\d+\.) (.*)", line):
        if para:
            flush()
        tag = "ul" if m.group(1) == "-" else "ol"
        if not lst or lst[0] != tag:
            flush()
            lst = (tag, [])
        lst[1].append("<li>" + inline(m.group(2)) + "</li>")
    elif not line.strip():
        flush()
    else:
        if lst:
            flush()
        para.append(line.strip())
close_section()

body = []
for title, bl in sections:
    inner = "".join(bl)
    if not title:
        body.append(f'<section class="lead">{inner}</section>')
    elif title.startswith(FOLD):
        body.append(f'<details class="screen"><summary>{inline(title)}</summary>{inner}</details>')
    else:
        m = re.match(r"(\S{1,2}) (.*)", title)
        badge = f'<span class="no">{html.escape(m.group(1))}</span>' if m and re.fullmatch(r"\d+|[A-Z]", m.group(1)) else ""
        name = m.group(2) if badge else title
        body.append(f'<section class="screen"><h2>{badge}{inline(name)}</h2>{inner}</section>')

title = meta.get("title", "读城")
cover = ""
if meta.get("cover"):
    mime, data = image_data(meta["cover"])
    cover = f'<figure class="cover"><img alt="" src="data:{mime};base64,{base64.b64encode(data).decode()}"></figure>'
page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ --paper:#f6efe2; --card:#fbf7ee; --ink:#3b3227; --ink2:#6e6253; --red:#b4472c; --line:#e3d8c3; }}
@media (prefers-color-scheme: dark) {{ :root {{ --paper:#1f1b16; --card:#29241d; --ink:#efe6d6; --ink2:#b9ab95; --red:#e07a5c; --line:#3d352a; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font:17px/1.75 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif; }}
main {{ max-width:640px; margin:0 auto; padding:0 16px 48px; }}
header {{ padding:36px 4px 8px; }}
h1 {{ font:700 30px/1.3 "Songti SC","STSong",serif; margin:0 0 8px; }}
.sub {{ color:var(--ink2); font-size:15px; }}
.lead p {{ font-size:18px; }}
.screen {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px 18px 8px; margin:22px 0; }}
h2 {{ font:700 22px/1.4 "Songti SC","STSong",serif; margin:2px 0 10px; display:flex; gap:10px; align-items:center; }}
h3 {{ font-size:17px; margin:18px 0 4px; }}
.no {{ flex:none; width:32px; height:32px; border-radius:50%; background:var(--red); color:#fff; font:700 17px/32px sans-serif; text-align:center; }}
figure {{ margin:4px -18px 14px; }}
figure img {{ width:100%; display:block; }}
figure.cover {{ margin:12px -16px 0; }}
figcaption {{ font-size:13px; color:var(--ink2); padding:6px 18px 0; }}
blockquote {{ margin:12px 0; padding:8px 14px; border-left:3px solid var(--red); color:var(--ink2); background:var(--paper); border-radius:0 8px 8px 0; }}
strong {{ color:var(--red); }}
a {{ color:var(--red); word-break:break-all; }}
ul, ol {{ padding-left:22px; }}
ul.hunt {{ list-style:none; padding:0; }}
ul.hunt li {{ border-bottom:1px dashed var(--line); padding:8px 0; }}
ul.hunt label {{ display:flex; gap:12px; align-items:flex-start; }}
ul.hunt input {{ width:22px; height:22px; margin-top:4px; accent-color:var(--red); flex:none; }}
ul.hunt input:checked + span {{ text-decoration:line-through; color:var(--ink2); }}
details.screen summary {{ font:700 18px "Songti SC",serif; cursor:pointer; padding-bottom:10px; }}
details.screen {{ font-size:14px; }}
code {{ font-size:13px; }}
</style></head>
<body><main>
<header><h1>{html.escape(title)}</h1><div class="sub">{inline(meta.get("subtitle", ""))}</div></header>
{cover}
{''.join(body)}
</main>
<script>
(function () {{
  var key = "read-a-city:" + document.title;
  var saved = {{}};
  try {{ saved = JSON.parse(localStorage.getItem(key) || "{{}}"); }} catch (e) {{}}
  document.querySelectorAll("ul.hunt input").forEach(function (box) {{
    box.checked = !!saved[box.dataset.k];
    box.addEventListener("change", function () {{
      saved[box.dataset.k] = box.checked;
      try {{ localStorage.setItem(key, JSON.stringify(saved)); }} catch (e) {{}}
    }});
  }});
}})();
</script>
</body></html>
"""
open(out, "w", encoding="utf-8").write(page)
kb = os.path.getsize(out) // 1024
print(f"{out}: {len(sections)} 屏，{task_no} 项寻宝，{kb} KB")
if kb > 6000:
    print("提示：页面超过 6 MB，微信里打开会慢。试试 --quality 60，或减少一两张图。")
