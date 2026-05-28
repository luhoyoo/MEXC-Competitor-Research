from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import load_yaml


def build_agent_research_brief(
    config_path: Path,
    reports_dir: Path,
    evidence_dir: Path,
    run_date: str | None = None,
) -> Path:
    report_date = run_date or date.today().isoformat()
    config = load_yaml(config_path.read_text(encoding="utf-8"))
    reports_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / report_date
    evidence_path.mkdir(parents=True, exist_ok=True)

    brief_path = reports_dir / f"{report_date}-codex-ai-research-brief.md"
    final_report_path = reports_dir / f"{report_date}-web3-product-visual-trend-report.md"
    previous_report_path = find_previous_report(reports_dir, report_date)

    brief_path.write_text(
        render_brief(config, report_date, evidence_path, final_report_path, previous_report_path),
        encoding="utf-8",
    )
    return brief_path


def find_previous_report(reports_dir: Path, run_date: str) -> Path | None:
    current = datetime.strptime(run_date, "%Y-%m-%d").date()
    candidates: list[tuple[date, Path]] = []
    for path in reports_dir.glob("*-web3-product-visual-trend-report.md"):
        date_text = path.name[:10]
        try:
            candidate_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            continue
        if candidate_date < current:
            candidates.append((candidate_date, path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def render_brief(
    config: dict[str, Any],
    run_date: str,
    evidence_path: Path,
    final_report_path: Path,
    previous_report_path: Path | None,
) -> str:
    competitors = config.get("competitors", [])
    research_scope = config.get("research_scope", {})
    search_policy = config.get("search_policy", {})
    evidence_rules = config.get("evidence_rules", {})
    analysis_requirements = config.get("analysis_requirements", {})
    continuity_policy = analysis_requirements.get("continuity_policy", {})
    report_budget = config.get("report_budget", {})
    target_minutes = report_budget.get("target_read_minutes", 5)
    max_words = report_budget.get("max_words_chinese", 1200)
    writing_principle = report_budget.get(
        "writing_principle",
        "宁可少而准；能用一句话讲清楚就不要写一段。",
    )

    lines = [
        f"# Codex 每日 AI 研究任务 - {run_date}",
        "",
        "你现在不是爬虫，也不是素材下载工具。",
        "你是一个给平面设计部门主管服务的 Web3 竞品产品与视觉趋势研究员。",
        "",
        "## 我方品牌基准",
        "",
        f"- 我方品牌：{config.get('own_brand', 'MEXC')}",
        f"- 使用方式：{config.get('own_brand_role', '用于判断可跟进方向、品牌冲突和同质化风险')}",
        "",
        "## 最终目标",
        "",
        f"请基于今天或最近 {search_policy.get('recency_days', 2)} 天公开网络信息，自动搜索、浏览、判断，并生成一份正式报告：",
        "",
        f"- 最终报告路径：`{final_report_path}`",
        f"- 关键证据目录：`{evidence_path}`",
        "",
        "报告必须回答两件事：",
        "",
        "1. 竞品的视觉风格正在怎么变化？",
        "2. 竞品的产品逻辑正在怎么变化？",
        "",
        "## 连续观察要求",
        "",
        f"- 分析模式：{continuity_policy.get('mode', 'incremental')}",
        f"- 要求：{continuity_policy.get('instruction', '先读取上一份报告，再做增量分析。')}",
        f"- 上一份正式报告：`{previous_report_path}`" if previous_report_path else "- 上一份正式报告：未找到。这是第一份基线报告，请建立初始观察框架。",
        "",
        "如果找到了上一份报告，必须先读取它作为基线，并在今天的 TL;DR 和重点发现中嵌入“相对上一期”的变化信号。不要再单独写“相对上一期变化”章节，避免重复表达。",
        "",
        "需要在心里对照（但不用单独成章）：",
        "",
        *[f"- {item}" for item in continuity_policy.get("compare_dimensions", [])],
        "",
        "今天报告不要重复大段行业背景；只保留和上一期相比真正变化、强化、减弱、反转或持续值得跟踪的内容，并写得更短。",
        "",
        "## 研究对象",
        "",
        *[f"- {name}" for name in competitors],
        "",
        "## 重点产品方向",
        "",
        *[f"- {topic}" for topic in research_scope.get("product_topics", [])],
        "",
        "## 重点视觉方向",
        "",
        *[f"- {topic}" for topic in research_scope.get("visual_topics", [])],
        "",
        "## 搜索方式",
        "",
        "不要依赖固定站点。你要主动组合关键词搜索。",
        "每个竞品至少搜索产品动作和活动视觉两个方向。",
        "",
        "建议搜索词示例：",
        "",
        "```text",
        "{competitor} campaign",
        "{competitor} launchpool",
        "{competitor} launchpad",
        "{competitor} earn",
        "{competitor} web3 wallet",
        "{competitor} trading bot",
        "{competitor} airdrop",
        "{competitor} new listing",
        "{competitor} app promotion",
        "{competitor} product update",
        "{competitor} X campaign image",
        "{competitor} Instagram campaign",
        "```",
        "",
        f"- 时间范围：优先最近 {search_policy.get('recency_days', 2)} 天；如果当天信息不足，可以扩展到最近 {search_policy.get('fallback_recency_days', 7)} 天，但要注明。",
        f"- 来源策略：{search_policy.get('source_policy', '优先官方来源')}",
        f"- 语言策略：{search_policy.get('language', '中英文都可以')}",
        "",
        "## 来源等级",
        "",
        *[f"- {item}" for item in search_policy.get("source_quality", [])],
        "",
        "## 证据数量要求",
        "",
        f"- 总证据来源不少于 {evidence_rules.get('minimum_total_sources', 10)} 条；如果当天公开信息不足，要说明不足原因。",
        f"- 官方来源不少于 {evidence_rules.get('minimum_official_sources', 5)} 条；优先用官方证据支撑核心判断。",
        f"- 关键视觉证据最多 {evidence_rules.get('max_key_visual_evidence', 8)} 条。",
        f"- 重点发现最多 {evidence_rules.get('max_findings', 6)} 条，宁可少而准。",
        "",
        "每条重点发现必须包含：",
        "",
        *[f"- {item}" for item in evidence_rules.get("each_finding_requires", [])],
        "",
        "## 图片处理原则",
        "",
        f"{search_policy.get('image_policy', '不批量下载图片，只保存关键证据。')}",
        "",
        "具体执行：",
        "",
        "- 浏览页面时可以观察视觉，不需要把所有图片下载下来。",
        "- 只有当一张图能支撑你的核心判断时，才把它作为关键证据。",
        "- 每天关键视觉证据控制在 3-8 张以内。",
        "- 如果工具环境不方便保存图片，可以在报告中放图片来源链接和页面链接。",
        "- 不要把报告写成图片清单，图片只是证据。",
        "",
        "## 分析要求",
        "",
        *[f"- {item}" for item in analysis_requirements.get("must_answer", [])],
        "",
        "额外要求：",
        "",
        "- 必须区分“产品逻辑变化”和“视觉风格变化”。",
        "- 必须解释二者之间的关系，例如：为什么某类产品会带来某种视觉表达。",
        "- 必须判断 MEXC 是否应该跟进，而不是只描述别人做了什么。",
        "- 不做投资建议，不写行情判断。",
        "- 不写技术抓取过程。",
        f"- 写作口吻：{analysis_requirements.get('report_tone', '设计策略分析语言')}",
        "",
        "## 最终报告结构（严格遵守）",
        "",
        f"**体量预算**：目标阅读时间 {target_minutes} 分钟，全文中文字数控制在 {max_words} 字以内。",
        f"**写作原则**：{writing_principle}",
        "**章节顺序与字数限制必须遵守**，每个章节都要克制；后台你看了 10+ 条证据，但报告里只呈现精华。",
        "",
        "---",
        "",
        f"# Web3 竞品产品与视觉趋势日报 - {run_date}",
        "",
        "## 🎯 TL;DR（30 秒读完）",
        "用 3 行各一句话，必须把变化信号嵌进来，不要再单独写“相对上一期变化”章节。",
        "",
        "- 🎨 视觉：（一句话讲今天视觉风格相对上一期最关键的变化）",
        "- 📦 产品：（一句话讲今天产品逻辑相对上一期最关键的变化）",
        "- ✅ MEXC 行动：（一句话给主管一个可执行的设计动作）",
        "",
        "## 🔍 重点发现（最多 3 条，每条 80 字以内）",
        "",
        "格式必须是这样，每条只有 5 行，不要展开：",
        "",
        "```text",
        "### N. 竞品名：一句话标题（10 字以内）",
        "- 产品逻辑：一句话",
        "- 视觉风格：一句话",
        "- MEXC 启发：一句话",
        "- 证据：链接",
        "```",
        "",
        "选条标准：相对上一期最有“变化”信号的 3 条；同质化老调子不要再写。",
        "",
        "## 🎨 视觉与产品的联动（合并表达，不超过 5 行）",
        "",
        "用“产品逻辑变化 → 视觉表达变化”的因果对照写，每行一对，不要分两个章节铺开：",
        "",
        "- 例：Copy Trading 走向声誉化 → 主视觉从收益数字转向徽章/等级体系",
        "- 例：AI 工具走向货架化 → 视觉语言从赛博概念转向目录/分类/评分",
        "",
        "## ✅ MEXC 可跟进（3 条，每条 1 行可执行动作）",
        "",
        "只给设计与产品包装层面的动作，不写空话。",
        "",
        "## ⚠️ 不建议跟进（2 条，每条 1 行）",
        "",
        "指出同质化、品牌冲突或资源投入风险即可。",
        "",
        "## 🔗 证据链接（裸链接，不超过 8 条）",
        "",
        "只列 URL，不写描述、不写标题。每行一条。",
        "",
        "---",
        "",
        "**禁止事项**：",
        "- 不要单独写“相对上一期变化”章节，把变化信号嵌入 TL;DR 和重点发现",
        "- 不要把“视觉风格变化”和“产品逻辑变化”分两个章节展开（在联动章节合并）",
        "- 不要写来源等级、置信度（后台用，不进报告）",
        "- 不要写大段行业背景或访问失败日志",
        "- 单条发现超过 80 字必须重写更短",
        "",
        "## 执行提示",
        "",
        f"完成后，请把正式报告写入：`{final_report_path}`",
        f"全文写完后请自检字数，超过 {max_words} 字必须再压缩一轮。",
        "如果某些网站访问失败，可以在最末尾用 1 行说明，不要展开。",
        "",
    ]
    return "\n".join(lines)
