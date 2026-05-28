#!/bin/zsh
cd "$(dirname "$0")"
REPORT_DATE=$(date +%F)

echo "正在收集友商产品功能介绍页和活动视觉证据包..."
PYTHONPATH=src .venv/bin/python -m web3_visual_research.cli research --date "$REPORT_DATE"

echo ""
echo "完成。Codex 分析输入文件在这里："
echo "$(pwd)/reports/$REPORT_DATE-product-activity-analysis-input.md"
echo ""
echo "素材证据包在这里："
echo "$(pwd)/data/evidence_packets/$REPORT_DATE"
echo ""
open "$(pwd)/reports" >/dev/null 2>&1 || true
