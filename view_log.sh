#!/bin/bash
# GoTube 服务日志查看脚本
# 用法: ./view_log.sh [行数]
# 例如: ./view_log.sh 50

LINES=${1:-30}
LOG_FILE="/root/gotube/server.log"

echo "=== GoTube 服务日志 (最近 ${LINES} 条) ==="
echo "日志文件: ${LOG_FILE}"
echo ""

if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
    tail -n "$LINES" "$LOG_FILE"
else
    echo "本地日志文件为空或不存在，尝试从 systemd 获取..."
    echo ""
    journalctl -u gotube --no-pager -n "$LINES"
fi
