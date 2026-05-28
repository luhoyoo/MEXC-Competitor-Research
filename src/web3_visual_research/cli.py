from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    load_dotenv(Path(".env"))
    parser = argparse.ArgumentParser(description="Web3 竞品产品功能与活动视觉调研系统")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="抓取图片、分析视觉并生成 Markdown 日报")
    run_parser.add_argument("--date", dest="run_date", help="日报日期，格式 YYYY-MM-DD")
    run_parser.add_argument("--config", default="config/competitors.yaml", help="竞品配置文件路径")
    run_parser.add_argument("--db", default="data/research.sqlite3", help="SQLite 数据库路径")
    run_parser.add_argument("--data-dir", default="data", help="素材保存根目录")
    run_parser.add_argument("--reports-dir", default="reports", help="日报输出目录")
    run_parser.add_argument("--use-playwright", action="store_true", help="使用 Playwright 渲染页面后再抓取")
    run_parser.add_argument("--skip-vision", action="store_true", help="跳过 AI 视觉分析，仅下载归档并生成日报")
    run_parser.add_argument("--limit-per-source", type=int, default=8, help="每个来源最多保留的图片数")
    run_parser.add_argument("--include-web", action="store_true", help="额外抓取官网首页和 Blog 图片。默认只抓社媒。")

    research_parser = subparsers.add_parser("research", help="收集产品功能页、活动页和官媒线索，生成 Codex 分析输入")
    research_parser.add_argument("--date", dest="run_date", help="日期，格式 YYYY-MM-DD")
    research_parser.add_argument("--config", default="config/market_research_sources.yaml", help="产品/活动页来源配置")
    research_parser.add_argument("--data-dir", default="data", help="证据包保存根目录")
    research_parser.add_argument("--reports-dir", default="reports", help="分析输入输出目录")
    research_parser.add_argument("--use-playwright", action="store_true", help="使用 Playwright 渲染页面后再采集")
    research_parser.add_argument("--screenshots", action="store_true", help="保存页面首屏截图")
    research_parser.add_argument("--image-limit", type=int, default=6, help="每个页面最多归档图片数量")

    brief_parser = subparsers.add_parser("brief", help="生成 Codex 每日 AI 搜索浏览研究任务单")
    brief_parser.add_argument("--date", dest="run_date", help="日期，格式 YYYY-MM-DD")
    brief_parser.add_argument("--config", default="config/ai_research.yaml", help="AI 研究配置")
    brief_parser.add_argument("--reports-dir", default="reports", help="报告目录")
    brief_parser.add_argument("--evidence-dir", default="reports/evidence", help="关键证据目录")

    args = parser.parse_args()
    if args.command == "run":
        from .pipeline import run_pipeline

        report_path = run_pipeline(
            config_path=Path(args.config),
            db_path=Path(args.db),
            data_dir=Path(args.data_dir),
            reports_dir=Path(args.reports_dir),
            run_date=args.run_date,
            use_playwright=args.use_playwright,
            skip_vision=args.skip_vision,
            limit_per_source=args.limit_per_source,
            include_web=args.include_web,
        )
        print(f"[done] 日报已生成：{report_path.resolve()}")
    elif args.command == "research":
        from .page_researcher import run_market_research

        json_path, input_path = run_market_research(
            config_path=Path(args.config),
            data_dir=Path(args.data_dir),
            reports_dir=Path(args.reports_dir),
            run_date=args.run_date,
            use_playwright=args.use_playwright,
            take_screenshots=args.screenshots,
            image_limit=args.image_limit,
        )
        print(f"[done] 证据包已生成：{json_path.resolve()}")
        print(f"[done] Codex 分析输入已生成：{input_path.resolve()}")
    elif args.command == "brief":
        from .agent_brief import build_agent_research_brief

        brief_path = build_agent_research_brief(
            config_path=Path(args.config),
            reports_dir=Path(args.reports_dir),
            evidence_dir=Path(args.evidence_dir),
            run_date=args.run_date,
        )
        print(f"[done] Codex AI 研究任务单已生成：{brief_path.resolve()}")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
