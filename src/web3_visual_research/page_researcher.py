from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import load_yaml
from .image_downloader import download_image
from .scraper import DEFAULT_HEADERS, extract_image_urls, fetch_html, first_non_empty, meta_content


@dataclass
class PageEvidence:
    competitor_name: str
    competitor_slug: str
    source_group: str
    source_name: str
    topic: str
    url: str
    status: str
    title: str | None = None
    description: str | None = None
    headings: list[str] | None = None
    cta_texts: list[str] | None = None
    image_urls: list[str] | None = None
    downloaded_images: list[str] | None = None
    screenshot_path: str | None = None
    error: str | None = None


def run_market_research(
    config_path: Path,
    data_dir: Path,
    reports_dir: Path,
    run_date: str | None = None,
    use_playwright: bool = False,
    take_screenshots: bool = False,
    image_limit: int = 6,
) -> tuple[Path, Path]:
    report_date = run_date or date.today().isoformat()
    config = load_yaml(config_path.read_text(encoding="utf-8"))
    evidence_items: list[PageEvidence] = []

    for competitor in config.get("competitors", []):
        competitor_name = competitor["name"]
        competitor_slug = competitor["slug"]
        print(f"[research] 收集 {competitor_name} 产品功能页和活动页")

        for group_name in ("product_pages", "activity_pages"):
            for source in competitor.get(group_name, []):
                evidence = collect_page_evidence(
                    competitor_name=competitor_name,
                    competitor_slug=competitor_slug,
                    source_group=group_name,
                    source=source,
                    report_date=report_date,
                    data_dir=data_dir,
                    use_playwright=use_playwright,
                    take_screenshots=take_screenshots,
                    image_limit=image_limit,
                )
                evidence_items.append(evidence)

        social = competitor.get("social", {})
        for platform, url in social.items():
            evidence_items.append(
                PageEvidence(
                    competitor_name=competitor_name,
                    competitor_slug=competitor_slug,
                    source_group="social",
                    source_name=platform,
                    topic="官媒线索入口，用于观察当天活动与产品传播方向",
                    url=url,
                    status="linked",
                    title=f"{competitor_name} {platform}",
                    description="社媒内容建议由 Codex 自动化结合当天公开页面进一步判断，不再只做图片下载。",
                    headings=[],
                    cta_texts=[],
                    image_urls=[],
                    downloaded_images=[],
                )
            )

    packet_dir = data_dir / "evidence_packets" / report_date
    packet_dir.mkdir(parents=True, exist_ok=True)
    json_path = packet_dir / "market-research-evidence.json"
    json_path.write_text(
        json.dumps([item.__dict__ for item in evidence_items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    reports_dir.mkdir(parents=True, exist_ok=True)
    input_path = reports_dir / f"{report_date}-product-activity-analysis-input.md"
    input_path.write_text(
        build_analysis_input_markdown(evidence_items, config, report_date),
        encoding="utf-8",
    )
    return json_path, input_path


def collect_page_evidence(
    competitor_name: str,
    competitor_slug: str,
    source_group: str,
    source: dict[str, str],
    report_date: str,
    data_dir: Path,
    use_playwright: bool,
    take_screenshots: bool,
    image_limit: int,
) -> PageEvidence:
    url = source["url"]
    source_name = source.get("name", url)
    topic = source.get("topic", "")
    html = fetch_html(url, use_playwright=use_playwright)
    if not html:
        return PageEvidence(
            competitor_name=competitor_name,
            competitor_slug=competitor_slug,
            source_group=source_group,
            source_name=source_name,
            topic=topic,
            url=url,
            status="failed",
            error="页面请求失败，可能是地区限制、反爬或页面地址变动。",
        )

    parsed = parse_marketing_page(html, url)
    image_dir = data_dir / "research_images" / report_date / competitor_slug / safe_name(source_name)
    downloaded_images = []
    for index, image_url in enumerate(parsed["image_urls"][:image_limit], start=1):
        downloaded = download_image(image_url, image_dir, prefix=f"page-{index:02d}", min_width=320, min_height=160)
        if downloaded:
            downloaded_images.append(str(downloaded.path))

    screenshot_path = None
    if take_screenshots:
        screenshot_path = capture_page_screenshot(
            url,
            data_dir / "screenshots" / report_date / competitor_slug / f"{safe_name(source_name)}.png",
        )

    return PageEvidence(
        competitor_name=competitor_name,
        competitor_slug=competitor_slug,
        source_group=source_group,
        source_name=source_name,
        topic=topic,
        url=url,
        status="ok",
        title=parsed["title"],
        description=parsed["description"],
        headings=parsed["headings"],
        cta_texts=parsed["cta_texts"],
        image_urls=parsed["image_urls"][:image_limit],
        downloaded_images=downloaded_images,
        screenshot_path=screenshot_path,
    )


def parse_marketing_page(html: str, base_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    title = first_non_empty(
        meta_content(soup, "property", "og:title"),
        meta_content(soup, "name", "twitter:title"),
        soup.title.string.strip() if soup.title and soup.title.string else None,
    )
    description = first_non_empty(
        meta_content(soup, "property", "og:description"),
        meta_content(soup, "name", "description"),
        meta_content(soup, "name", "twitter:description"),
    )
    headings = unique_texts(tag.get_text(" ", strip=True) for tag in soup.select("h1, h2, h3"))[:18]
    cta_texts = unique_texts(
        tag.get_text(" ", strip=True)
        for tag in soup.select("a, button")
        if 2 <= len(tag.get_text(" ", strip=True)) <= 40
    )[:20]
    image_urls = [url for url in dict.fromkeys(extract_image_urls(soup, base_url)) if url]
    return {
        "title": title,
        "description": description,
        "headings": headings,
        "cta_texts": cta_texts,
        "image_urls": image_urls,
    }


def capture_page_screenshot(url: str, output_path: Path) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"], viewport={"width": 1440, "height": 1600})
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.screenshot(path=str(output_path), full_page=False)
            browser.close()
        return str(output_path.resolve())
    except Exception:
        return None


def build_analysis_input_markdown(items: list[PageEvidence], config: dict[str, Any], report_date: str) -> str:
    focus = config.get("analysis_focus", {})
    lines = [
        f"# Web3 友商产品功能与活动视觉分析输入 - {report_date}",
        "",
        "## 给 Codex 的分析任务",
        "",
        f"- 目标读者：{focus.get('audience', '平面设计部门主管')}",
        f"- 分析目标：{focus.get('goal', '分析友商产品功能介绍页和活动视觉情况')}",
        f"- 写作口吻：{focus.get('output_style', '偏设计分析，不写技术过程')}",
        "",
        "请基于下面证据，输出正式分析报告，重点不是罗列链接，而是判断：",
        "",
        "1. 友商今天/当前重点包装的产品功能是什么",
        "2. 活动页或功能介绍页的核心卖点和转化路径是什么",
        "3. 视觉表现：KV、主色、元素、版式、标题层级、CTA",
        "4. 哪些设计表达值得 MEXC 跟进，哪些容易同质化或冲突",
        "5. 给平面设计团队 5 条可执行建议",
        "",
        "## 建议正式报告结构",
        "",
        f"# Web3 友商产品功能与活动视觉分析日报 - {report_date}",
        "",
        "## 今日重点判断",
        "## 友商产品功能包装动态",
        "## 活动视觉与转化打法观察",
        "## 对 MEXC 设计团队的机会点",
        "## 风险与不建议跟进方向",
        "## 素材与页面归档",
        "",
        "## 采集证据",
        "",
    ]

    for item in items:
        lines.extend(
            [
                f"### {item.competitor_name} / {item.source_name}",
                "",
                f"- 类型：{source_group_label(item.source_group)}",
                f"- 主题：{item.topic or '未标注'}",
                f"- 页面：{item.url}",
                f"- 状态：{item.status}",
                f"- 标题：{item.title or '未识别'}",
                f"- 简介：{item.description or '未识别'}",
            ]
        )
        if item.error:
            lines.append(f"- 错误：{item.error}")
        if item.headings:
            lines.append(f"- 页面标题层级：{' / '.join(item.headings[:10])}")
        if item.cta_texts:
            lines.append(f"- CTA / 按钮文案：{' / '.join(item.cta_texts[:12])}")
        if item.downloaded_images:
            lines.append("- 已归档视觉素材：")
            for path in item.downloaded_images:
                lines.append(f"  - `{path}`")
        if item.screenshot_path:
            lines.append(f"- 首屏截图：`{item.screenshot_path}`")
        lines.append("")
    return "\n".join(lines)


def unique_texts(values) -> list[str]:
    result = []
    for value in values:
        text = " ".join(value.split()) if value else ""
        if text and text not in result:
            result.append(text)
    return result


def safe_name(value: str) -> str:
    parsed = urlparse(value)
    source = parsed.netloc or value
    return "".join(char.lower() if char.isalnum() else "-" for char in source).strip("-")[:60] or "source"


def source_group_label(value: str) -> str:
    return {
        "product_pages": "产品功能介绍页",
        "activity_pages": "活动页 / 活动中心",
        "social": "官媒线索",
    }.get(value, value)
