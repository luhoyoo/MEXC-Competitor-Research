#!/bin/zsh
cd "$(dirname "$0")"
REPORT_DATE=$(date +%F)

echo "正在测试抓取 X / Instagram 当天图片..."
echo "如果提示需要安装 Playwright 浏览器，请先运行：.venv/bin/python -m playwright install chromium"
echo ""

PYTHONPATH=src .venv/bin/python -m web3_visual_research.cli run --skip-vision --date "$REPORT_DATE"

echo ""
echo "完成。报告文件在这里："
echo "$(pwd)/reports/$REPORT_DATE-visual-competitor-report.md"
echo ""
echo "图片素材文件夹在这里："
echo "$(pwd)/data/images/$REPORT_DATE"
echo ""
open "$(pwd)/reports" >/dev/null 2>&1 || true
