# read-a-city · 从一条街读懂一座城

<img src="docs/cover.jpg" width="360" align="right" alt="走在街上，看见一百年前">

一个 [Claude Code](https://claude.com/claude-code) Skill。告诉它你要去哪座城市，它帮你挑一条有故事、又不太挤的老街，讲讲这条街从前是什么样，配几张“百年前”的场景画，最后做成一个手机上能翻的网页。

走在街上，你看到的就不只是今天的样子。

灵感来自宋念申的《西塔：一个东北街区中的空间、国家与日常》：以一条具体的街为入口，看城市的变迁怎样进入普通人的日子。

**它不是导航，也不是历史课。** 位置大体不错就行，路线只给先后顺序和时长；讲的是人、手艺、一碗早饭、一句老话。传说写“据说”，推测写“我猜”，底线是不编造事实。

<br clear="right">

## 看看样例

三份读本都是单个 HTML 文件，图片内嵌，下载后用手机或浏览器打开就能看，也能直接发微信。

| 读本 | 一句话 | 在线预览 |
|---|---|---|
| [蚌埠 · 从天桥读城](examples/bengbu-tianqiao.html) | 一座被火车拉来的城，和铁路边一百年的早饭 | [打开](https://raw.githack.com/mocomeng-666/read-a-city/main/examples/bengbu-tianqiao.html) |
| [天津 · 从大直沽读城](examples/tianjin-dazhigu.html) | 先有大直沽，后有天津卫 | [打开](https://raw.githack.com/mocomeng-666/read-a-city/main/examples/tianjin-dazhigu.html) |
| [武汉 · 从粮道街读城](examples/wuhan-liangdaojie.html) | 一条叫“粮道”的街，后来成了读书和过早的街 | [打开](https://raw.githack.com/mocomeng-666/read-a-city/main/examples/wuhan-liangdaojie.html) |

武汉那份是一个全新的会话只看这份 Skill、不看其他样例，从头独立做出来的，用了约 21 分钟。

## 安装

```bash
git clone https://github.com/mocomeng-666/read-a-city.git ~/.claude/skills/read-a-city
```

装好以后，在 Claude Code 里任何地方都能用。

## 怎么用

只说城市就够了，其他它会自己补，或者问你一两句：

- “我下个月去泉州，帮我找一条能读懂这座城的街。”
- “我现在在武汉司门口附近，有两个小时，附近有什么街可以走走？”
- “想去武汉走走，你直接选，要完整版。”

它会先给两三条候选街，说清看点和取舍，你挑一条（说“你直接选”它就自己定）；接着查资料、写故事、画漫步图、配图，最后打包成一个网页。

## 你会拿到什么

一个 `reading.html`，往下翻，一屏一站：

- **封面和一句话**：这条街是什么，约几公里，走多久；
- **出发前**：带着一个问题去，什么时候去，一张漫步图；
- **寻宝清单**：路上要找的小东西，手机上可以打勾；
- **每一站**：大致在哪 / 叠影（眼前是什么，从前是什么）/ 留意一下（一个现场的小任务）；
- **资料说明和来源**：哪些说法不确定、资料出自哪里，默认折叠。

走完回来说“我走完了”，它会问你三个问题，把这条街从“读过”记成“走过”，存进 `walked-streets.md`。

## 配图：三档随你挑

| 档位 | 怎么做 | 花费 |
|---|---|---|
| 不配场景画 | 只有文字、代码画的漫步图和公有领域老地图 | 0 |
| 手机上的生图 App | 它写好提示词，你复制到豆包、即梦这类 App 里生成，发回给它，它检查后加标题和“示意”说明 | 看 App |
| 自己的生图 API Key | 配好 Key（豆包 Seedream、通义万相等，见 `references/image-providers.md`），它直接生成；每次花钱前先报价，等你同意 | 一份约 0.5 元 |

Key 只放环境变量或 `image.local.json`（已在 `.gitignore` 里），不要写进仓库。所有 AI 生成的图都会标“示意，不是照片”。

## 目录

```
SKILL.md                 工作流程（Claude 读的）
references/              样例读本、提示词模板、生图服务商说明
scripts/                 打包网页、画漫步图、做场景图卡、调用生图 API 的脚本（只用 Python 标准库 + macOS 自带工具）
examples/                三份样例读本
image.example.json       生图配置样例，复制为 image.local.json 再改
```

脚本里做图卡和截图用到了 macOS 的 `sips` 和 Google Chrome 的无头模式；在其他系统上，打包网页时没有 `sips` 会原样内嵌图片。

## 说明

- 读本只靠网页资料写成，没有实地核验；今天的店铺、施工、开放时间以现场为准。
- 样例中的场景画由豆包 Seedream 生成，是示意画；漫步图道路数据 © OpenStreetMap 贡献者（ODbL）；天津样例中的 1946 年老地图来自 Wikimedia Commons（公有领域）。
- 这是个人项目，给自己和身边的人用，还在慢慢打磨。欢迎提 issue 告诉我你读了哪条街。

## 许可

[MIT](LICENSE)
