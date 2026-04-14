#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== 英超名人堂 — 启动 ==="

# 1. 生成 players.json（从现有 CSV，不重新爬取）
echo ""
echo ">> 生成 players.json ..."
cd "$ROOT/backend"
python3 export_json_quick.py

# 2. 安装前端依赖（首次或依赖变化时）
echo ""
echo ">> 检查前端依赖 ..."
cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "   首次运行，安装 npm 依赖..."
  npm install
else
  echo "   node_modules 已存在，跳过安装"
fi

# 3. 启动开发服务器
echo ""
echo ">> 启动前端开发服务器 ..."
echo "   访问: http://localhost:5174"
echo "   按 Ctrl+C 停止"
echo ""
npm run dev
