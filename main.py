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
    elif len(sys.argv) > 1 and sys.argv[1] == "migrate":
        import storage
        src = "json"
        dst = "sqlite"
        for arg in sys.argv[2:]:
            if arg.startswith("--from="):
                src = arg.split("=")[1]
            elif arg.startswith("--to="):
                dst = arg.split("=")[1]
        print(f"\n🔄 正在执行数据迁移: {src} -> {dst} ...")
        res = storage.migrate_storage(src, dst)
        print(f"✅ {res['message']}")
        print(f"📊 迁移统计: 持仓标的 {res['migrated']['holdings']} 个, 历史快照 {res['migrated']['snapshots']} 条, 回收站 {res['migrated']['trash_items']} 条\n")
    elif len(sys.argv) > 1 and sys.argv[1] == "storage":
        import json
        import storage
        s = storage.get_storage()
        print("\n💾 当前存储引擎状态与统计:")
        print(json.dumps(s.get_stats(), indent=2, ensure_ascii=False) + "\n")
    else:
        import cli
        cli.main()

if __name__ == "__main__":
    main()
