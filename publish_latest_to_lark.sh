#!/bin/zsh
cd "$(dirname "$0")"
REPORT_DATE=$(date +%F)
REPORT_PATH="reports/$REPORT_DATE-web3-product-visual-trend-report.md"

if [ ! -f "$REPORT_PATH" ]; then
  echo "没有找到今天的正式报告：$REPORT_PATH"
  echo "请先生成报告："
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

DOC_URL=""
DOC_TITLE="Web3 竞品产品与视觉趋势日报 · $REPORT_DATE"

if [ -n "$LARK_APP_ID" ] && [ -n "$LARK_APP_SECRET" ]; then
  echo "1/2 正在创建 Lark 云文档..."
  DOC_URL=$(PYTHONPATH=src .venv/bin/python -m web3_visual_research.lark_doc_publisher \
      --report "$REPORT_PATH" \
      --title "$DOC_TITLE" 2>&1) || {
    echo "❌ Lark 文档创建失败："
    echo "$DOC_URL"
    DOC_URL=""
  }
  if [ -n "$DOC_URL" ] && [[ "$DOC_URL" == https://* ]]; then
    echo "   ✔ 文档已创建：$DOC_URL"
  else
    DOC_URL=""
    echo "   ⚠ 没拿到文档 URL，按钮将退回到本地 markdown 提示"
  fi
else
  echo "⚠ 未配置 LARK_APP_ID / LARK_APP_SECRET，跳过文档创建。"
  echo "  请在 .env 中补充这两项以获得跳转按钮体验。"
fi

echo ""
echo "2/2 推送群消息..."
EXTRA_ARGS=(--report "$REPORT_PATH" --date "$REPORT_DATE")
if [ -n "$DOC_URL" ]; then
  EXTRA_ARGS+=(--doc-url "$DOC_URL")
fi
PYTHONPATH=src .venv/bin/python -m web3_visual_research.lark_chat_notifier "${EXTRA_ARGS[@]}"

echo ""
echo "完成。结果文件："
echo "  $(pwd)/data/lark/$REPORT_DATE/chat-notify-result.json"
