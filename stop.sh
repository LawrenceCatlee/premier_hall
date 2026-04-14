#!/usr/bin/env bash
echo "=== 英超名人堂 — 停止 ==="
PIDS=$(lsof -ti tcp:5174 2>/dev/null)
if [ -n "$PIDS" ]; then
  echo ">> 关闭端口 5174 上的进程: $PIDS"
  kill $PIDS
  echo "   已停止"
else
  echo ">> 未检测到运行中的开发服务器"
fi
