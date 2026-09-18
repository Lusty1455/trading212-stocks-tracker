#!/usr/bin/env python3
"""Unified entry point for Stock Daily Tracker (CLI & Web Dashboard)."""

from __future__ import annotations
import sys
import os

def run_web(host: str = "127.0.0.1", port: int = 26212):
    import uvicorn
    print(f"\n🚀 启动 Web 资产看板: http://{host}:{port}")
    print("💡 按 Ctrl+C 可停止运行\n")
    uvicorn.run("web_app:app", host=host, port=port, reload=False)

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("web", "--web", "server"):
        port = 26212
        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            port = int(sys.argv[2])
        run_web(port=port)
    else:
        import cli
        cli.main()

if __name__ == "__main__":
    main()
