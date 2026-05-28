#!/bin/zsh
cd "$(dirname "$0")"
REPORT_DATE=$(date +%F)
REPORT_PATH="reports/$REPORT_DATE-web3-product-visual-trend-report.md"

if [ ! -f "$REPORT_PATH" ]; then
  echo "没有找到今天的正式报告：$REPORT_PATH"
  echo "请先等待 GitHub Actions 自动生成，或手动运行："
  echo "  PYTHONPATH=src .venv/bin/python -m web3_visual_research.cli brief --date $REPORT_DATE"
  echo "  PYTHONPATH=src .venv/bin/python -m web3_visual_research.cloud_research_agent --date $REPORT_DATE"
  exit 1
fi

# 自动加载 .env
if [ -f ".env" ]; then
  set -a
  source ./.env
  set +a
fi

PYTHONPATH=src .venv/bin/python -m web3_visual_research.lark_chat_notifier \
  --report "$REPORT_PATH" \
  --date "$REPORT_DATE" \
  --mode full

echo ""
echo "已推送到 Lark 群。结果文件："
echo "  $(pwd)/data/lark/$REPORT_DATE/chat-notify-result.json"
