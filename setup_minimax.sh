#!/bin/zsh
cd "$(dirname "$0")"

echo "正在检查 MiniMax CLI..."

if ! command -v npm >/dev/null 2>&1; then
  echo "没有检测到 npm。请先安装 Node.js：https://nodejs.org/"
  exit 1
fi

if ! command -v mmx >/dev/null 2>&1; then
  echo "正在安装 MiniMax CLI：mmx"
  npm install -g mmx-cli
fi

if [ -f ".env" ]; then
  source ".env"
fi

if [ -z "$MINIMAX_API_KEY" ] || [ "$MINIMAX_API_KEY" = "your-minimax-key-here" ]; then
  echo "还没有填写 MINIMAX_API_KEY。"
  echo "请打开 .env，把 MINIMAX_API_KEY=your-minimax-key-here 改成你的真实 MiniMax Key。"
  exit 1
fi

echo "正在登录 MiniMax CLI..."
mmx auth login --api-key "$MINIMAX_API_KEY"

echo ""
echo "MiniMax 已配置完成。现在可以运行："
echo "zsh run_daily.sh"
