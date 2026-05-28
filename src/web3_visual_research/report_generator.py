from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def generate_markdown_report(items: list[dict[str, Any]], run_date: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item["competitor_name"]].append(item)

    lines: list[str] = [
        f"# Web3 竞品视觉日报 - {run_date}",
        "",
        "## 今日视觉趋势总结",
        *build_trend_summary(items),
        "",
        "## 竞品视觉动态",
        "",
    ]

    if not items:
        lines.extend(
            [
                "今天没有抓取到可归档图片。建议检查网络、站点反爬策略，或临时开启 Playwright 渲染模式。",
                "",
            ]
        )

    for competitor_name in sorted(grouped):
        lines.extend([f"### {competitor_name}", ""])
        for item in grouped[competitor_name]:
            analysis = parse_analysis(item.get("analysis_json"))
            image_path = item.get("image_path") or ""
            thumb_path = relative_report_image_path(image_path, output_path.parent)
            dimensions = dimensions_text(item)
            lines.extend(
                [
                    f"#### {item.get('page_title') or '未识别标题'}",
                    "",
                    f"![缩略图]({thumb_path})" if thumb_path else "_图片下载失败，暂无缩略图_",
                    "",
                    f"- 来源链接：[{item.get('source_type')}]({item.get('page_url')})",
                    f"- 活动标题：{item.get('page_title') or '未识别'}",
                    f"- 发布时间：{item.get('published_at') or '页面未公开标注'}",
                    f"- 图片尺寸：{dimensions}",
                    f"- 视觉类型：{analysis.get('visual_type') or item.get('visual_type') or '待识别'}",
                    f"- 主色调：{join_list(analysis.get('main_colors'))}",
                    f"- 画面风格：{join_list(analysis.get('style_tags'))}",
                    f"- 版式分析：{analysis.get('layout') or '待分析'}",
                    f"- 标题文案层级：{analysis.get('copy_hierarchy') or '待分析'}",
                    f"- 视觉元素：{join_list(analysis.get('visual_elements'))}",
                    f"- 品牌资产使用方式：{analysis.get('brand_asset_usage') or '待分析'}",
                    f"- 活动类型：{analysis.get('campaign_type') or '待识别'}",
                    f"- 设计亮点：{analysis.get('design_highlights') or '待分析'}",
                    f"- 可借鉴点：{analysis.get('reference_points') or '待分析'}",
                    f"- 风险提醒：{analysis.get('risk_notes') or '暂无'}",
                    "",
                ]
            )

    lines.extend(
        [
            "## 今日可借鉴设计机会",
            *build_design_opportunities(items),
            "",
            "## 素材归档",
            *build_archive(items),
            "",
        ]
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_trend_summary(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return [
            "- 今日主流风格：暂无足够样本",
            "- 高频颜色：暂无足够样本",
            "- 高频视觉元素：暂无足够样本",
            "- 值得关注的设计方向：先确保抓取链路稳定，再进入视觉判断",
        ]

    styles: Counter[str] = Counter()
    colors: Counter[str] = Counter()
    elements: Counter[str] = Counter()
    campaign_types: Counter[str] = Counter()
    for item in items:
        analysis = parse_analysis(item.get("analysis_json"))
        styles.update(as_list(analysis.get("style_tags")))
        colors.update(as_list(analysis.get("main_colors")))
        elements.update(as_list(analysis.get("visual_elements")))
        campaign = analysis.get("campaign_type")
        if campaign:
            campaign_types[campaign] += 1

    leading_style = counter_text(styles, "暂无明确集中风格")
    leading_colors = counter_text(colors, "暂无明确高频颜色")
    leading_elements = counter_text(elements, "暂无明确高频元素")
    leading_campaign = campaign_types.most_common(1)[0][0] if campaign_types else "产品推广 / 内容封面"

    return [
        f"- 今日主流风格：{leading_style}",
        f"- 高频颜色：{leading_colors}",
        f"- 高频视觉元素：{leading_elements}",
        f"- 值得关注的设计方向：围绕「{leading_campaign}」提炼可复用的首屏视觉模板，同时避免与头部交易所形成过强同质感",
    ]


def build_design_opportunities(items: list[dict[str, Any]]) -> list[str]:
    opportunities = []
    for item in items:
        analysis = parse_analysis(item.get("analysis_json"))
        point = analysis.get("reference_points")
        if point and point not in opportunities and "待" not in point[:4]:
            opportunities.append(point)
        if len(opportunities) >= 5:
            break

    fallback = [
        "建立交易赛、Launchpool、新币上线三类常用 KV 模板，方便快速换主题和币种资产。",
        "把主色调、标题层级、奖品信息拆成可复用规范，降低每日活动图的设计波动。",
        "重点观察头部交易所如何处理金币、奖杯、排行榜等高频元素，避免素材堆叠造成廉价感。",
        "为 Blog / Academy 封面建立更强的系列化识别，让教育内容也能形成品牌资产。",
        "保留 MEXC 品牌绿的高识别度，同时谨慎跟进过度蓝紫科技风，避免行业同质化。",
    ]
    opportunities.extend(point for point in fallback if point not in opportunities)
    return [f"{index}. {text}" for index, text in enumerate(opportunities[:5], start=1)]


def build_archive(items: list[dict[str, Any]]) -> list[str]:
    archive = []
    for item in items:
        image_path = item.get("image_path")
        if image_path:
            archive.append(f"- {item['competitor_name']}：`{image_path}`")
    return archive or ["- 今日暂无成功下载的素材。"]


def parse_analysis(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def join_list(value: Any) -> str:
    items = as_list(value)
    return "、".join(items) if items else "待分析"


def counter_text(counter: Counter[str], empty: str) -> str:
    if not counter:
        return empty
    return "、".join(item for item, _ in counter.most_common(5))


def dimensions_text(item: dict[str, Any]) -> str:
    width = item.get("image_width")
    height = item.get("image_height")
    return f"{width}x{height}" if width and height else "未识别"


def relative_report_image_path(image_path: str, report_dir: Path) -> str:
    if not image_path:
        return ""
    path = Path(image_path)
    return os.path.relpath(path, report_dir).replace(os.sep, "/")
