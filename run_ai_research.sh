#!/bin/zsh
cd "$(dirname "$0")"
REPORT_DATE=$(date +%F)

echo "正在生成 Codex AI 研究任务单..."
PYTHONPATH=src .venv/bin/python -m web3_visual_research.cli brief --date "$REPORT_DATE"

echo ""
echo "任务单已生成："
echo "$(pwd)/reports/$REPORT_DATE-codex-ai-research-brief.md"
echo ""
echo "正式报告将由 Codex 自动化生成到："
echo "$(pwd)/reports/$REPORT_DATE-web3-product-visual-trend-report.md"
echo ""
open "$(pwd)/reports" >/dev/null 2>&1 || true
