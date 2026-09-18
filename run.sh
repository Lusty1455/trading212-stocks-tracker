#!/usr/bin/env bash
# Convenient launcher for Stock Portfolio Daily Tracker
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "⚡ 首次运行，正在初始化 Python 虚拟环境与依赖..."
    uv venv .venv
    uv pip install -p .venv yfinance rich requests pydantic tabulate fastapi uvicorn
fi

exec .venv/bin/python3 "$DIR/main.py" "$@"
