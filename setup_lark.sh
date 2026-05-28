#!/bin/zsh
cd "$(dirname "$0")"

echo "正在检查 Lark CLI..."

if ! command -v npm >/dev/null 2>&1; then
  echo "没有检测到 npm。请先安装 Node.js：https://nodejs.org/"
  echo "安装完成后重新运行：zsh setup_lark.sh"
  exit 1
fi

if [ ! -x "node_modules/.bin/lark-cli" ] && ! command -v lark-cli >/dev/null 2>&1; then
  echo "正在安装 Lark CLI 到当前项目..."
  npm install @larksuite/cli
fi

echo ""
echo "接下来会打开 Lark CLI 配置/授权流程。"
echo "如果终端给出浏览器链接，请用你的飞书/Lark 账号登录并授权。"
echo ""
if [ -x "node_modules/.bin/lark-cli" ]; then
  node_modules/.bin/lark-cli config init --new
else
  lark-cli config init --new
fi

echo ""
echo "Lark CLI 配置完成。之后可以运行："
echo "zsh publish_latest_to_lark.sh"
