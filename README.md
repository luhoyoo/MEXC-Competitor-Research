# Web3 竞品产品与视觉趋势 AI 研究系统

这是一个给平面设计部门主管使用的每日友商观察工具。

它不是单纯下载图片，也不是固定爬某几个页面。新的主流程会让 Codex 像一个 AI 研究员一样每天主动搜索网络、浏览页面、观察关键视觉，并输出“视觉风格变化 + 产品逻辑变化”的判断报告。

## MVP 当前支持范围

当前先支持 3 个竞品：

- Binance
- OKX
- Bybit

当前重点研究：

- 竞品最新产品动作：Earn、Launchpool、Web3 Wallet、Trading Bot、空投、积分、上新等
- 活动视觉与活动机制：交易赛、节日活动、新币上线、App 推广、社媒 KV
- 视觉风格变化：颜色、KV、质感、版式、标题层级、视觉元素
- 产品逻辑变化：主推功能、用户转化路径、激励机制、功能包装方式

图片不需要全部下载。Codex 浏览时会分析，只有遇到能支撑关键判断的图片，才作为证据保存或引用。

## 项目结构

```text
.
├── config/ai_research.yaml          # 新版 AI 研究员配置
├── config/market_research_sources.yaml # 旧版固定页面采集配置
├── config/competitors.yaml          # 旧版图片抓取配置
├── data/
│   ├── images/YYYY-MM-DD/竞品名/     # 每天下载的图片素材
│   └── research.sqlite3             # SQLite 数据库
├── reports/
│   └── YYYY-MM-DD-visual-competitor-report.md
├── src/web3_visual_research/
│   ├── page_researcher.py           # 收集产品页/活动页证据包
│   ├── scraper.py                   # 旧版图片抓取
│   ├── image_downloader.py          # 下载图片并识别尺寸
│   ├── vision_analyzer.py           # 调用 MiniMax / OpenAI 做视觉分析
│   ├── report_generator.py          # 生成 Markdown 日报
│   ├── pipeline.py                  # 串起完整流程
│   └── cli.py                       # 命令行入口
└── .github/workflows/               # GitHub Actions 每日自动运行
```

## 第一次安装

请先确认电脑已经安装 Python 3.10 到 3.13。推荐使用 Python 3.11 或 3.12；如果你本机默认是 Python 3.14，少数依赖可能还没有完全适配，建议换成 Python 3.12。

在项目目录里运行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

如果只是先测试基础流程，也可以暂时不装 Playwright，默认会先用 requests 抓取页面。

## 配置 MiniMax Key

复制一份环境变量文件：

```bash
cp .env.example .env
```

打开 `.env`，把这一行改成你自己的 MiniMax Key：

```text
MINIMAX_API_KEY=your-minimax-key-here
```

确认这一行是 MiniMax：

```text
VISION_PROVIDER=minimax
```

然后安装并登录 MiniMax CLI：

```bash
zsh setup_minimax.sh
```

## 最重要：日常怎么用

你现在主要用这一句生成当天 AI 研究任务单：

```bash
zsh run_ai_research.sh
```

它会生成：

```text
reports/YYYY-MM-DD-codex-ai-research-brief.md
```

这个文件是给 Codex 自动化执行的研究任务单。

Codex 每天自动化会读取任务单，然后自己搜索、浏览、分析，并写正式报告：

```text
reports/YYYY-MM-DD-web3-product-visual-trend-report.md
```

它会自动延续上一份报告，不会每天从零开始。每天会先读取最近一份：

```text
reports/YYYY-MM-DD-web3-product-visual-trend-report.md
```

然后重点分析：

- 相比上一期新增了什么趋势
- 哪些产品逻辑在强化
- 哪些视觉风格在减弱
- 哪些判断需要修正
- 哪些信号还需要持续观察

正式报告的重点会是：

- 竞品最近重点推什么产品
- 产品逻辑有没有变化
- 视觉风格有没有变化
- 视觉变化和产品逻辑变化之间的关系
- MEXC 可以跟进什么
- 哪些方向不建议跟进

你已经有 Codex 自动化了，默认每天上午 10 点自动执行，不需要每天手动打开终端。

## 发布到 Lark / 飞书文档

第一次使用前，只需要做一次授权：

```bash
zsh setup_lark.sh
```

它会安装 Lark CLI，并让你用飞书/Lark 账号登录授权。

以后如果想手动把当天报告发到 Lark 文档，运行：

```bash
zsh publish_latest_to_lark.sh
```

每天 Codex 自动化生成正式报告后，也会自动尝试发布到 Lark 文档。

本地正式报告路径：

```text
reports/YYYY-MM-DD-web3-product-visual-trend-report.md
```

Lark 发布结果会保存在：

```text
data/lark/YYYY-MM-DD/publish-result.json
```

如果发布失败，通常是因为还没有运行 `zsh setup_lark.sh` 完成登录。

## 每日推送到 Lark 群

把 TL;DR 摘要 + 完整报告链接做成卡片，每天自动推到指定群。

**第一次配置**

1. 打开飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人
2. 复制 Webhook 地址；如果勾选了"签名校验"，把生成的密钥也复制下来
3. 本地：把 Webhook 写到 `.env`：
   ```text
   LARK_GROUP_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
   LARK_GROUP_WEBHOOK_SECRET=（如有签名才填）
   ```
4. GitHub Actions：在仓库 Settings → Secrets and variables → Actions 里加：
   - `LARK_GROUP_WEBHOOK`
   - `LARK_GROUP_WEBHOOK_SECRET`（可选）

**手动推一次**

```bash
zsh publish_latest_to_lark.sh
```

会先创建飞书云文档，再推一条群消息卡片，按钮跳转到刚创建的飞书文档。

**自动每日推送**

`.github/workflows/daily-lark-notify.yml` 已经配好，每天北京时间 12:00（UTC 04:00）运行。它只读取仓库里的 Markdown 报告并推群，按钮链接指向 GitHub 上的 Markdown 文件（GH Actions 没法做飞书文档 OAuth 登录）。

如果某天 12:00 时报告还没生成，workflow 会跳过推送并打印 warning，不会失败。

群消息卡片样式（示例）：

```text
🎯 Web3 竞品产品与视觉趋势日报 · 2026-05-29

🎨 视觉：……（一句话）
📦 产品：……（一句话）
✅ MEXC 行动：……（一句话）

[ 查看完整报告 ]  ← 按钮
```

卡片样式（颜色、文案、标题前缀）可以在 `config/lark_publish.yaml` 的 `lark.webhook` 段调整。

## 旧版图片抓取

如果你是第一次使用，推荐先用最简单的一键测试：

```bash
zsh run_test.sh
```

它会跳过 MiniMax 视觉分析，只测试抓取 X / Instagram 当天图片、归档和生成日报。

以后配置好 MiniMax Key 后，可以运行：

```bash
zsh run_daily.sh
```

完整运行，包含 AI 视觉分析：

```bash
PYTHONPATH=src python -m web3_visual_research.cli run
```

如果你现在还没有 API Key，只想先验证下载和报告生成：

```bash
PYTHONPATH=src python -m web3_visual_research.cli run --skip-vision
```

默认现在只抓 X / Instagram。如果你临时还想补充官网首页和 Blog 图片，可以加这个参数：

```bash
PYTHONPATH=src python -m web3_visual_research.cli run --include-web --use-playwright
```

运行完成后，日报会出现在：

```text
reports/YYYY-MM-DD-visual-competitor-report.md
```

图片会出现在：

```text
data/images/YYYY-MM-DD/competitor_name/
```

## 修改竞品列表

打开：

```text
config/competitors.yaml
```

每个竞品的格式如下：

```yaml
- name: Binance
  slug: binance
  homepage: https://www.binance.com/
  blog: https://www.binance.com/en/blog
  announcement: https://www.binance.com/en/support/announcement
  x: https://x.com/binance
```

MVP 目前默认使用 `x` 和 `instagram`。`homepage`、`blog`、`announcement` 先保留在配置里，方便下一阶段扩展。

## 每天自动运行

项目已经包含 GitHub Actions：

```text
.github/workflows/daily-visual-report.yml
```

默认每天 UTC 02:00 运行一次，大约是北京时间 10:00。

如果你使用 GitHub Actions，需要在 GitHub 仓库里配置：

1. 进入仓库 Settings
2. 打开 Secrets and variables
3. 新建 Secret：`MINIMAX_API_KEY`
4. 值填入你的 MiniMax Key

GitHub Actions 运行后，会把日报、图片和数据库作为 artifact 上传。

## 日报内容

正式报告以 5 分钟阅读为目标（中文 1200 字以内），结构固定为：

- 🎯 TL;DR：3 行讲清视觉、产品、MEXC 行动
- 🔍 重点发现：最多 3 条，每条只有 5 行（竞品 / 产品逻辑 / 视觉风格 / MEXC 启发 / 证据链接）
- 🎨 视觉与产品的联动：用"产品逻辑变化 → 视觉表达变化"因果对照
- ✅ MEXC 可跟进：3 条可执行动作
- ⚠️ 不建议跟进：2 条
- 🔗 证据链接：不超过 8 条裸链接

体量预算和章节顺序在 `config/ai_research.yaml` 里的 `report_budget` 部分配置，模板在 `src/web3_visual_research/agent_brief.py`。

旧版图片抓取流程的日报（`*-visual-competitor-report.md`）保留：
- 今日视觉趋势总结
- 竞品视觉动态
- 今日可借鉴设计机会
- 素材归档

每张图片会保存：

- 图片文件
- 来源链接
- 竞品名称
- 发布时间
- 页面标题
- 图片尺寸
- AI 视觉分析结果

## 注意事项

- X / Twitter 和 Instagram 页面结构经常变化，抓取结果可能会波动。
- 如果某天官媒没有发图，日报会显示没有抓到当日素材，这是正常情况。
- 部分社媒会出现登录墙、地区访问限制或反爬限制，这种情况下建议后续接官方 API 或内部社媒账号授权。
- 这套系统的目标是帮助设计主管做每日视觉判断，不是做投研或行情分析。
