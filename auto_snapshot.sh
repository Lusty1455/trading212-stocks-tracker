#!/usr/bin/env bash
# 每日自动记录持仓与收盘涨跌快照脚本 (可加入 crontab)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$DIR/snapshot.log"

echo "----------------------------------------" >> "$LOG"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行每日持仓快照记录..." >> "$LOG"
"$DIR/run.sh" snapshot >> "$LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 执行完成。" >> "$LOG"
