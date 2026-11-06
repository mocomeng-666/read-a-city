"""调用用户自己的生图 API，按提示词和参考图生成全景插画。只用标准库。

用法:
  python3 -I gen_image.py --prompt <提示词.md|.txt> --ref <参考图> [--ref ...] --out <成图.png>
                          [--provider wan|seedream|kling|openai|gemini] [--config <image.local.json>] [--send]

不加 --send 时只演练：打印服务商、模型、地址、参数和预计费用，不发请求，也不需要 Key。
加 --send 才真正调用，并计费。调用前须已向用户报价并得到同意。

Key 只从环境变量或本地配置（image.local.json，不进仓库）读取，从不打印。
提示词文件是 .md 时，取第一个 ```text 代码块。
各家接口以官方文档为准，差异都收在下面的适配函数里。
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "..", "image.local.json")
EXAMPLE_CONFIG = os.path.join(HERE, "..", "image.example.json")

KEY_ENV = {
    "wan": "DASHSCOPE_API_KEY",
    "kling": "DASHSCOPE_API_KEY",
    "seedream": "ARK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class ProviderError(Exception):
    pass


# ---------- 通用 ----------

def read_prompt(path):
    s = open(path, encoding="utf-8").read()
    if path.endswith(".md"):
        m = re.search(r"```text\n(.*?)\n```", s, re.S)
        if not m:
            raise SystemExit(f"{path} 里没有 ```text 代码块")
        s = m.group(1)
    return s.strip()


def sniff_mime(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise SystemExit("参考图只支持 PNG、JPEG、WEBP")


def load_ref(path):
    """返回 (mime, bytes)；URL 原样保留，由适配函数决定能不能用。"""
    if path.startswith(("http://", "https://")):
        return ("url", path)
    data = open(path, "rb").read()
    if len(data) > 10 * 1024 * 1024:
        raise SystemExit(f"{path} 超过 10MB，多数服务商不收")
    return (sniff_mime(data), data)


def data_uri(ref):
    kind, v = ref
    return v if kind == "url" else f"data:{kind};base64,{base64.b64encode(v).decode()}"


def http(method, url, headers, body=None, timeout=300):
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        raise ProviderError(f"HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise ProviderError(f"连不上 {url.split('?')[0]}: {e.reason}")


def post_json(url, headers, payload, timeout=300):
    h = {"Content-Type": "application/json", **headers}
    return json.loads(http("POST", url, h, json.dumps(payload).encode(), timeout))


def fetch(url):
    return http("GET", url, {}, timeout=120)


# ---------- 适配层：每家一个 build（演练也用）和一个 call ----------
# build 返回 (method, url, headers 不含 Key, 请求体摘要)；call 返回图片 bytes 列表。

def wan_build(p, prompt, refs):
    content = [{"text": prompt}] + [{"image": data_uri(r)} for r in refs]
    params = {"n": 1, "size": p.get("size", "1152*2048"), "watermark": False,
              "prompt_extend": False}
    if p.get("negative_prompt"):
        params["negative_prompt"] = p["negative_prompt"]
    payload = {"model": p["model"],
               "input": {"messages": [{"role": "user", "content": content}]},
               "parameters": params}
    if not 1 <= len(refs) <= 4:
        raise SystemExit("万相图像编辑需要 1–4 张参考图")
    url = p["base_url"].rstrip("/") + "/api/v1/services/aigc/multimodal-generation/generation"
    return url, payload


def wan_images(out):
    """万相和可灵在百炼上的结果结构相同。"""
    imgs = [c["image"] for ch in out.get("output", {}).get("choices", [])
            for c in ch.get("message", {}).get("content", []) if c.get("image")]
    if not imgs:
        raise ProviderError(f"没有返回图片: {json.dumps(out, ensure_ascii=False)[:800]}")
    return [fetch(u) for u in imgs]


def wan_call(p, key, prompt, refs):
    url, payload = wan_build(p, prompt, refs)
    out = post_json(url, {"Authorization": f"Bearer {key}"}, payload)
    return wan_images(out)


def kling_build(p, prompt, refs):
    for r in refs:
        if r[0] != "url":
            raise SystemExit("可灵（百炼）的参考图只收公网 URL，不收本地文件或 Base64；"
                             "先把参考图放到可访问的地址，或换万相")
    if len(refs) > 1 and "omni" not in p["model"]:
        raise SystemExit("kling-v3-image-generation 只收一张参考图；多图用 omni 型号")
    content = [{"text": prompt}] + [{"image": r[1]} for r in refs]
    payload = {"model": p["model"],
               "input": {"messages": [{"role": "user", "content": content}]},
               "parameters": {"n": 1, "aspect_ratio": p.get("aspect_ratio", "9:16"),
                              "resolution": p.get("resolution", "2k"), "watermark": False}}
    url = p["base_url"].rstrip("/") + "/api/v1/services/aigc/image-generation/generation"
    return url, payload


def kling_call(p, key, prompt, refs, poll=5, limit=600):
    url, payload = kling_build(p, prompt, refs)
    auth = {"Authorization": f"Bearer {key}"}
    out = post_json(url, {**auth, "X-DashScope-Async": "enable"}, payload)
    task = out.get("output", {}).get("task_id")
    if not task:
        raise ProviderError(f"没有拿到任务号: {json.dumps(out, ensure_ascii=False)[:800]}")
    q = p["base_url"].rstrip("/") + f"/api/v1/tasks/{task}"
    t0 = time.time()
    while time.time() - t0 < limit:
        time.sleep(poll)
        out = json.loads(http("GET", q, auth, timeout=60))
        st = out.get("output", {}).get("task_status")
        if st == "SUCCEEDED":
            return wan_images(out)
        if st in ("FAILED", "CANCELED", "UNKNOWN"):
            raise ProviderError(f"任务{st}: {json.dumps(out, ensure_ascii=False)[:800]}")
    raise ProviderError(f"等了 {limit} 秒还没出图，任务号 {task}（24 小时内可查）")


def seedream_build(p, prompt, refs):
    imgs = [data_uri(r) for r in refs]
    payload = {"model": p["model"], "prompt": prompt, "size": p.get("size", "1152x2048"),
               "response_format": "b64_json", "watermark": False}
    if imgs:
        payload["image"] = imgs[0] if len(imgs) == 1 else imgs
    if p.get("output_format"):
        payload["output_format"] = p["output_format"]
    url = p["base_url"].rstrip("/") + "/api/v3/images/generations"
    return url, payload


def seedream_call(p, key, prompt, refs):
    url, payload = seedream_build(p, prompt, refs)
    out = post_json(url, {"Authorization": f"Bearer {key}"}, payload)
    if out.get("error"):
        raise ProviderError(f"{out['error'].get('code')}: {out['error'].get('message')}")
    res = []
    for d in out.get("data", []):
        if d.get("b64_json"):
            res.append(base64.b64decode(d["b64_json"]))
        elif d.get("url"):
            res.append(fetch(d["url"]))
    if not res:
        raise ProviderError(f"没有返回图片: {json.dumps(out, ensure_ascii=False)[:800]}")
    return res


def openai_build(p, prompt, refs):
    if any(r[0] == "url" for r in refs):
        raise SystemExit("OpenAI 图像编辑接口按文件上传，参考图请给本地路径")
    fields = {"model": p["model"], "prompt": prompt, "n": "1",
              "size": p.get("size", "1024x1536")}
    if p.get("quality"):
        fields["quality"] = p["quality"]
    url = p["base_url"].rstrip("/") + ("/v1/images/edits" if refs else "/v1/images/generations")
    return url, {**fields, "image[]": [f"<{r[0]} {len(r[1])} 字节>" for r in refs]}


def openai_call(p, key, prompt, refs):
    url, summary = openai_build(p, prompt, refs)
    auth = {"Authorization": f"Bearer {key}"}
    fields = {k: v for k, v in summary.items() if k != "image[]"}
    if not refs:
        fields["n"] = 1
        out = post_json(url, auth, fields)
    else:
        boundary = uuid.uuid4().hex
        parts = []
        for k, v in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for i, (mime, data) in enumerate(refs):
            ext = mime.split("/")[1]
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; '
                         f'filename="ref{i}.{ext}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + data + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        out = json.loads(http("POST", url, {**auth, "Content-Type": f"multipart/form-data; boundary={boundary}"}, body))
    res = [base64.b64decode(d["b64_json"]) if d.get("b64_json") else fetch(d["url"])
           for d in out.get("data", [])]
    if not res:
        raise ProviderError(f"没有返回图片: {json.dumps(out, ensure_ascii=False)[:800]}")
    return res


def gemini_build(p, prompt, refs):
    if any(r[0] == "url" for r in refs):
        raise SystemExit("Gemini 这里按内嵌数据发送参考图，请给本地路径")
    parts = [{"text": prompt}] + [{"inline_data": {"mime_type": m, "data": base64.b64encode(d).decode()}}
                                  for m, d in refs]
    payload = {"contents": [{"parts": parts}],
               "generationConfig": {"responseModalities": ["IMAGE"],
                                    "imageConfig": {"aspectRatio": p.get("aspect_ratio", "9:16")}}}
    url = p["base_url"].rstrip("/") + f"/v1beta/models/{p['model']}:generateContent"
    return url, payload


def gemini_call(p, key, prompt, refs):
    url, payload = gemini_build(p, prompt, refs)
    out = post_json(url, {"x-goog-api-key": key}, payload)
    res = []
    for cand in out.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                res.append(base64.b64decode(blob["data"]))
    if not res:
        raise ProviderError(f"没有返回图片: {json.dumps(out, ensure_ascii=False)[:800]}")
    return res


PROVIDERS = {
    "wan": (wan_build, wan_call),
    "seedream": (seedream_build, seedream_call),
    "kling": (kling_build, kling_call),
    "openai": (openai_build, openai_call),
    "gemini": (gemini_build, gemini_call),
}


# ---------- 主流程 ----------

def redact(obj):
    """演练输出里把 Base64 截短，避免刷屏。"""
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str) and len(obj) > 200 and ("base64," in obj or re.fullmatch(r"[A-Za-z0-9+/=]+", obj)):
        return obj[:40] + f"…（共 {len(obj)} 字符）"
    if isinstance(obj, str) and len(obj) > 300:
        return obj[:120] + f"…（共 {len(obj)} 字）"
    return obj


def load_config(path):
    for f in (path, EXAMPLE_CONFIG):
        if f and os.path.exists(f):
            return json.load(open(f, encoding="utf-8")), f
    raise SystemExit("找不到配置：复制 image.example.json 为 image.local.json 再改")


def get_key(name, p):
    key = os.environ.get(p.get("api_key_env") or KEY_ENV[name]) or p.get("api_key")
    if not key:
        raise SystemExit(f"没有 Key：设置环境变量 {p.get('api_key_env') or KEY_ENV[name]}，"
                         f"或写进 image.local.json 的 providers.{name}.api_key")
    return key


def save(images, out):
    """按真实格式定扩展名；返回保存的路径。"""
    paths = []
    stem, _ = os.path.splitext(out)
    for i, data in enumerate(images):
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[sniff_mime(data)]
        path = stem + ("" if i == 0 else f"-{i + 1}") + ext
        open(path, "wb").write(data)
        paths.append(path)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--send", action="store_true", help="真正调用并计费")
    a = ap.parse_args()

    cfg, cfg_path = load_config(a.config)
    name = a.provider or cfg.get("provider")
    if name not in PROVIDERS:
        raise SystemExit(f"不认识的服务商 {name}，可选 {', '.join(PROVIDERS)}")
    p = cfg["providers"][name]
    prompt = read_prompt(a.prompt)
    refs = [load_ref(r) for r in a.ref]
    build, call = PROVIDERS[name]
    url, payload = build(p, prompt, refs)

    price = p.get("price_per_image")
    cost = f"约 {price} {p.get('currency', '')}/张 × 1 张" if price is not None else "未配置单价，查官方价格页后填 price_per_image"
    print(f"服务商 {name}｜模型 {p['model']}｜配置 {os.path.relpath(cfg_path)}")
    print(f"地址 {url}")
    print(f"提示词 {len(prompt)} 字｜参考图 {len(refs)} 张｜预计费用 {cost}")
    if p.get("billing_note"):
        print(f"计费说明 {p['billing_note']}")

    if not a.send:
        print("演练模式，未发请求。请求体：")
        print(json.dumps(redact(payload), ensure_ascii=False, indent=2))
        return

    key = get_key(name, p)
    t0 = time.time()
    try:
        images = call(p, key, prompt, refs)
    except ProviderError as e:
        print(f"调用失败：{e}", file=sys.stderr)
        sys.exit(2)
    paths = save(images, a.out)
    meta = {"provider": name, "model": p["model"], "seconds": round(time.time() - t0, 1),
            "prompt_sha1": hashlib.sha1(prompt.encode()).hexdigest()[:12],
            "refs": a.ref, "files": [os.path.basename(x) for x in paths],
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(meta, open(os.path.splitext(a.out)[0] + ".gen.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"完成，用时 {meta['seconds']} 秒：{', '.join(paths)}")


if __name__ == "__main__":
    main()
