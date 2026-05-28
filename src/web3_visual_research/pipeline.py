from __future__ import annotations

from datetime import date
from pathlib import Path

from .config import load_competitors
from .db import VisualDatabase
from .image_downloader import download_image
from .report_generator import generate_markdown_report
from .scraper import scrape_competitor, scrape_social_competitor
from .vision_analyzer import analyze_image


def run_pipeline(
    config_path: Path,
    db_path: Path,
    data_dir: Path,
    reports_dir: Path,
    run_date: str | None = None,
    use_playwright: bool = False,
    skip_vision: bool = False,
    limit_per_source: int = 12,
    include_web: bool = False,
) -> Path:
    report_date = run_date or date.today().isoformat()
    competitors = load_competitors(config_path)
    db = VisualDatabase(db_path)

    try:
        db.clear_run_date(report_date)
        for competitor in competitors:
            print(f"[pipeline] 抓取 {competitor.name} 社媒当日图片")
            visuals = scrape_social_competitor(
                competitor=competitor,
                run_date=report_date,
                limit_per_source=limit_per_source,
            )
            if include_web:
                print(f"[pipeline] 补充抓取 {competitor.name} 官网/Blog 图片")
                visuals.extend(
                    scrape_competitor(
                        competitor=competitor,
                        run_date=report_date,
                        use_playwright=use_playwright,
                        limit_per_source=limit_per_source,
                    )
                )
            for index, visual in enumerate(visuals, start=1):
                record = visual.to_record()
                item_id = db.upsert_item(record)
                output_dir = data_dir / "images" / report_date / competitor.slug
                downloaded = download_image(
                    visual.image_url,
                    output_dir=output_dir,
                    prefix=f"{visual.source_type}-{index:02d}",
                )
                if not downloaded:
                    continue
                db.update_download(
                    item_id=item_id,
                    image_path=downloaded.path,
                    width=downloaded.width,
                    height=downloaded.height,
                    file_sha256=downloaded.sha256,
                )
                analysis = analyze_image(downloaded.path, skip_vision=skip_vision)
                db.update_analysis(item_id, analysis)

        items = db.list_items(report_date)
    finally:
        db.close()

    report_path = reports_dir / f"{report_date}-visual-competitor-report.md"
    return generate_markdown_report(items, report_date, report_path)
