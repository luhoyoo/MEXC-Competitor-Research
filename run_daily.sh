#!/bin/zsh
cd "$(dirname "$0")"
REPORT_DATE=$(date +%F)
PYTHONPATH=src .venv/bin/python -m web3_visual_research.cli run --date "$REPORT_DATE"
echo ""
echo "完成。报告文件在这里："
echo "$(pwd)/reports/$REPORT_DATE-visual-competitor-report.md"
open "$(pwd)/reports" >/dev/null 2>&1 || true
