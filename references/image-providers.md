# 生图服务接入说明

用户配置自己的 API Key 后，Skill 用 `scripts/gen_image.py` 直接生成全景或历史场景示意画，不必手动去别的工具。

**构图与提示词原则**：全景提示词统一使用 `panorama-prompt-template.md` 的模板，历史场景使用 `scene-prompt-template.md`。参考图是代码生成的轻量草图时，开头先描述成品插画，再明确说明“参考图只是布局草图、只借位置关系”，点名草图里不要出现的元素（如梯形边界、方块房子、点状树），并最多限定 3 个锚点；不要写“严格保持构图”（模型会照抄方块草图），也不要逐条堆叠缺陷限制（容易改一处丢另一处）。

## 选型硬条件

1. 支持参考图（图生图）。全景靠代码版构图草图定位道路和方位关系，只能文字生图的模型不适合做全景。
2. 能输出竖版 9:16，或接近的比例（叠加页按 1080×1920 裁切填满）。
3. 服务条款允许这样使用，用户所在地区能开通和付费。主要面向国内网络环境时，国内服务优先。

## 已接入服务商（按推荐顺序）

首选豆包 Seedream（同一份模板下生活细节更丰富，单张约 0.12 元）；通义万相作备选（无字和留白守得更严，单张约 0.2 元），Seedream 不可用或效果不合预期时切换。

| 代号 | 服务 | 型号（默认） | 参考图 | 接口要点 | 环境变量 |
| --- | --- | --- | --- | --- | --- |
| `seedream` | 火山方舟 · 豆包 Seedream | `doubao-seedream-5-0-flash-260915`（开通 pro 时可换 pro 型号） | 5.0 pro/flash 最多 10 张，可用 Base64 | 同步，`/api/v3/images/generations`；尺寸写 `宽x高`，pro/flash 总像素 921600–4624220；默认加水印，脚本关掉 | `ARK_API_KEY` |
| `wan` | 阿里云百炼 · 通义万相 | `wan2.6-image` | 1–4 张，可用本地文件（Base64） | 同步，`/api/v1/services/aigc/multimodal-generation/generation`；尺寸写 `宽*高`，总像素 768²–2048²；返回图片链接 24 小时有效 | `DASHSCOPE_API_KEY` |
| `kling` | 阿里云百炼 · 可灵 | `kling/kling-v3-image-generation` | 只收 1 张，**只收公网 URL** | 异步，提交后每 5 秒查一次任务；只开放北京地域，要先在百炼控制台开通“可灵AI”；和万相共用百炼 Key | `DASHSCOPE_API_KEY` |
| `openai` | OpenAI 图像 API | `gpt-image-1` | 多张，文件上传 | `/v1/images/edits`，multipart；竖版只有 `1024x1536`（2:3），叠加时裁掉两侧 | `OPENAI_API_KEY` |
| `gemini` | Google Gemini 图像模型 | `gemini-2.5-flash-image` | 多张，内嵌数据 | `/v1beta/models/<型号>:generateContent`，`aspectRatio: 9:16` | `GEMINI_API_KEY` |

- 型号和接口地址均可在配置中调整，不写死在代码里；新型号上线时只改配置即可。
- **可灵的限制**：参考图必须有公网 URL，本地生成的代码版草图不能直接传；排在 Seedream、万相之后。
- **价格**：配置里的 `price_per_image` 可按各家最新官方价格页填写，演练模式据此向用户报价。

## 备选（未接入）

- 智谱 CogView：质量一般，只作兜底。
- 腾讯混元图像 3.5：中文语境好，可作补充选择。
- MiniMax image-01：强项是视频，生图一般。
- 开源自建 Qwen-Image、可图 Kolors：无 API 费用，需自有 GPU。

## 怎么用

1. 复制 `image.example.json` 为 `image.local.json`（已在 `.gitignore` 里），选好 `provider`，按需改型号、尺寸、单价。
2. Key 放环境变量（推荐），或填进 `image.local.json` 的 `api_key`。Key 不贴进对话。
3. 先演练（不加 `--send`），拿到接口地址、参数和预计费用，报给用户：

   ```bash
   python3 -I scripts/gen_image.py --prompt <城市>/01-panorama-prompt.md \
     --ref <城市>/images/01-panorama.sketch.png \
     --out <城市>/images/01-panorama-ai.png
   ```

4. 用户同意后，同一条命令加 `--send`。成图旁边会写一个 `.gen.json`，记下服务商、型号、用时和提示词指纹（不含 Key）。
5. 按提示词模板里的检查项核对，合格后对位编号牌，用 `overlay.py <config> <成图> <out.html> <marks.json>` 叠加标题、路名、编号牌和图例，再截图出最终图卡。

## 用手机上的生图 App（没有 Key 时首选）

没有配置 API Key 时，最短的路是借用户手机上已有的生图 App。

1. **整理提示词**：用 `panorama-prompt-template.md` 或 `scene-prompt-template.md` 的写法，生成一段完整的中文描述，去掉 Markdown 和代码块，直接发给用户。历史场景不需要参考图；全景要借位置关系时，让用户把轻量草图一起发进 App。
2. **告诉用户怎么做**：打开豆包、即梦或 ChatGPT，粘贴这段话；如果能选比例，选竖版 9:16；生成后挑一张最好的存下来，发回。
3. **交回后检查**：
   - 资料里写到的人、物、行当是否都在；
   - 有没有可读的假字；
   - 有没有不该出现的现代物件；
   - 建筑外观是否被画成了某处真实地标。
   不合格的话，请用户在 App 里“重画一张”，最多一两次。
4. **做成图卡**：用 `scene_card.py` 或 `overlay.py` 加标题、标签和“示意”说明，标签可以盖住假字。App 自带的“AI 生成”水印保留，不裁掉。

各 App 的免费额度、出图比例和水印规则以 App 内说明为准。

## 规则

- **Key 不进对话。** 不写进交付文件、日志和仓库；脚本从不打印 Key。
- **先报价后调用。** 不加 `--send` 不会发请求。告诉用户服务商、张数和预计费用，得到同意才加 `--send`。重试要再问一次，默认最多两次。
- **模型只画画，字由代码加。** 用计费 API 时统一用无字提示词（全景见 `panorama-prompt-template.md`，场景画见 `scene-prompt-template.md`）：不写任何字、不画编号牌，顶部和底部留白。`panorama.py` 会写出 `.marks.json`（编号牌和路名的位置，取自代码版全景），`overlay.py` 带上这个文件时加标题、路名和编号牌；看过成图后在副本里微调位置。若运行环境内置生图本身排字稳定，也可让模型写标题，两条路并存。
- **不支持或没配 Key 时不中断。** 交付代码版全景和提示词，继续后面的流程。
- **内容口径不变。** 提示词只描述有依据的画面，不写未经证实的历史判断。
