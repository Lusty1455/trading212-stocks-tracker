"""FastAPI Web Dashboard for Stock Daily Tracking and Portfolio Analysis."""

from __future__ import annotations
import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from portfolio_engine import (
    calculate_portfolio,
    add_or_update_holding,
    remove_holding,
    set_cash,
    record_daily_snapshot,
    get_history,
    get_snapshot_detail,
    delete_snapshot,
    delete_snapshots_by_date_range,
    get_trash,
    restore_snapshot_from_trash,
    purge_trash,
    clear_all_snapshots,
    load_portfolio,
    verify_portfolio_integrity
)

app = FastAPI(title="Stock Portfolio Tracker", description="Daily Stock P&L Tracker without account credentials")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.api_route("/favicon.ico", methods=["GET", "HEAD"])
def get_favicon_ico():
    ico = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(ico):
        return FileResponse(ico, media_type="image/x-icon")
    raise HTTPException(status_code=404)


@app.api_route("/favicon.png", methods=["GET", "HEAD"])
def get_favicon_png():
    png = os.path.join(STATIC_DIR, "favicon.png")
    if os.path.exists(png):
        return FileResponse(png, media_type="image/png")
    raise HTTPException(status_code=404)


@app.api_route("/favicon.svg", methods=["GET", "HEAD"])
def get_favicon_svg():
    svg = os.path.join(STATIC_DIR, "favicon.svg")
    if os.path.exists(svg):
        return FileResponse(svg, media_type="image/svg+xml")
    raise HTTPException(status_code=404)


class HoldingRequest(BaseModel):
    symbol: str
    amount: Optional[float] = None
    currency: str = "GBP"
    shares: Optional[float] = None
    cost_basis: Optional[float] = None
    avg_price_usd: Optional[float] = None
    avg_price_gbp: Optional[float] = None


class CashRequest(BaseModel):
    gbp: Optional[float] = None
    usd: Optional[float] = None


class DateRangeDeleteRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@app.get("/api/portfolio")
def api_get_portfolio(refresh: bool = False):
    try:
        data = calculate_portfolio(force_refresh=refresh)
        return {"status": "ok", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/holding")
def api_add_holding(req: HoldingRequest):
    try:
        res = add_or_update_holding(
            symbol=req.symbol,
            amount=req.amount,
            currency=req.currency,
            shares=req.shares,
            cost_basis=req.cost_basis,
            cost_currency=req.currency,
            avg_price_usd=req.avg_price_usd,
            avg_price_gbp=req.avg_price_gbp
        )
        return {"status": "ok", "portfolio": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/holding/{symbol}")
def api_remove_holding(symbol: str):
    try:
        res = remove_holding(symbol)
        return {"status": "ok", "portfolio": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/cash")
def api_set_cash(req: CashRequest):
    try:
        if req.gbp is not None:
            set_cash("GBP", req.gbp)
        if req.usd is not None:
            set_cash("USD", req.usd)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/snapshot")
def api_record_snapshot():
    try:
        snap = record_daily_snapshot()
        return {"status": "ok", "snapshot": snap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
def api_get_history():
    try:
        hist = get_history()
        return {"status": "ok", "history": hist}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/snapshot/{identifier}")
def api_get_snapshot(identifier: str):
    try:
        snap = get_snapshot_detail(identifier)
        if not snap:
            raise HTTPException(status_code=404, detail="未找到该快照")
        return {"status": "ok", "snapshot": snap}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/snapshot/{identifier}")
def api_delete_snapshot(identifier: str):
    try:
        success = delete_snapshot(identifier, soft_delete=True)
        if not success:
            raise HTTPException(status_code=404, detail="未找到要删除的快照")
        return {"status": "ok", "message": "快照已移入回收站（可保留30天并随时还原）"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/snapshots/delete-range")
def api_delete_snapshots_range(req: DateRangeDeleteRequest):
    try:
        count = delete_snapshots_by_date_range(req.start_date, req.end_date, soft_delete=True)
        return {"status": "ok", "deleted_count": count, "message": f"已成功将 {count} 条快照移入回收站"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/snapshots")
def api_clear_snapshots():
    try:
        count = clear_all_snapshots(soft_delete=True)
        return {"status": "ok", "deleted_count": count, "message": f"已将所有 {count} 条快照移入回收站"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trash")
def api_get_trash():
    try:
        items = get_trash()
        return {"status": "ok", "trash": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trash/restore/{trash_id}")
def api_restore_trash(trash_id: str):
    try:
        success = restore_snapshot_from_trash(trash_id)
        if not success:
            raise HTTPException(status_code=404, detail="回收站中未找到该快照或已超期自动清除")
        return {"status": "ok", "message": "快照已成功还原至历史记录"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/trash/{trash_id}")
def api_purge_trash_item(trash_id: str):
    try:
        purged = purge_trash(trash_id)
        return {"status": "ok", "purged": purged, "message": "已彻底删除该快照记录"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/trash")
def api_purge_all_trash():
    try:
        purged = purge_trash("all")
        return {"status": "ok", "purged": purged, "message": f"回收站已清空，彻底清除 {purged} 条记录"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/verify")
def api_get_verify():
    try:
        report = verify_portfolio_integrity()
        return {"status": "ok", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


CHANGELOG_DATA = [
    {
        "version": "v1.4.0",
        "date": "2026-09-19",
        "commit": "feat/db",
        "title": "存储架构升级：引入存储适配器模式与 SQLite 数据库支持 (兼容 Cloudflare D1)",
        "is_latest": True,
        "items": [
            {"type": "arch", "icon": "💾", "tag": "存储解耦", "text": "设计抽象存储适配器基类 BaseStorage，使业务计算引擎、快照归档与底层持久化彻底解耦"},
            {"type": "feat", "icon": "📄", "tag": "保留纯JSON", "text": "通过 JSONStorage 适配器 100% 完整保留原有 portfolio.json / history.json 纯文本运行模式，向下完全兼容"},
            {"type": "feat", "icon": "🚀", "tag": "SQLite引擎", "text": "新增 SQLiteStorage 适配器，零额外依赖运行于本地 portfolio.db 单文件数据库，开启 WAL 高性能并发模式"},
            {"type": "cloud", "icon": "☁️", "tag": "Cloudflare D1", "text": "数据库表结构与 SQL 100% 同构契合 Cloudflare D1，内置 REST API 适配器支持随时直连边缘云端数据库"},
            {"type": "tool", "icon": "🔄", "tag": "双向迁移CLI", "text": "提供 python main.py migrate 与 python main.py storage 指令，支持 JSON 与 SQLite 之间随时双向自由无损迁移"},
            {"type": "feat", "icon": "🔀", "tag": "环境平滑切换", "text": "支持通过 STORAGE_BACKEND 环境变量（json / sqlite / cloudflare_d1）自由无缝切换活动存储引擎"}
        ]
    },
    {
        "version": "v1.3.1",
        "date": "2026-09-19",
        "commit": "1303df6",
        "title": "卡片边界无裁切优化与 Popover 定位对齐",
        "is_latest": False,
        "items": [
            {"type": "fix", "icon": "🐛", "tag": "边界修复", "text": "解绑外层资产卡片的 overflow-hidden，彻底解决标题 Popover 提示向上弹出时被卡片边框切断的问题"},
            {"type": "feat", "icon": "📐", "tag": "定位体系", "text": "引入 .pop-bottom.pop-left 定位规则与专用向上指示三角，卡片及弹窗标题说明统一向下自然延展并对准图标中心"},
            {"type": "ui", "icon": "🎨", "tag": "视觉一致", "text": "卡片表头独立增设 relative z-20 堆叠层级，横向滚动表格采用 rounded-b-2xl 保持圆角美观与平滑滚动"}
        ]
    },
    {
        "version": "v1.3.0",
        "date": "2026-09-18",
        "commit": "1c3422a",
        "title": "引入信息图标 ⓘ 与精简 Popover 交互",
        "is_latest": False,
        "items": [
            {"type": "ui", "icon": "ℹ️", "tag": "文案精简", "text": "精简持仓明细、现金账户、历史快照、日期范围删除等超长辅助文案，以统一精致的圆形 i 图标呈现"},
            {"type": "feat", "icon": "👆", "tag": "触控友好", "text": "支持鼠标悬停（Hover）及移动端触控点击常驻，点击外部空白区域自动优雅收起"},
            {"type": "ui", "icon": "🌓", "tag": "主题适配", "text": "双配色高对比度适配：深色模式使用 #1e293b 背景与发光边框，浅色模式采用纯净白底与柔和阴影"}
        ]
    },
    {
        "version": "v1.2.0",
        "date": "2026-09-18",
        "commit": "363fa12",
        "title": "快照回收站机制与日期范围批量删除",
        "is_latest": False,
        "items": [
            {"type": "feat", "icon": "♻️", "tag": "安全回收站", "text": "废弃物理直接删除机制，被删快照安全转入回收站暂存，支持随时一键全量还原，杜绝误操作风险"},
            {"type": "feat", "icon": "⏳", "tag": "30天生命周期", "text": "底层集成 TTL 自动过期引擎，进入回收站超过 30 天的废弃快照由系统自动执行安全物理抹除"},
            {"type": "feat", "icon": "📅", "tag": "范围批量删除", "text": "支持任意选定起止日期的快照批量删除，并提供「全选全部、仅今天、近7天、近30天」一键预设筛选"}
        ]
    },
    {
        "version": "v1.1.0",
        "date": "2026-09-18",
        "commit": "14d6703",
        "title": "历史快照管理面板与持仓穿透透视",
        "is_latest": False,
        "items": [
            {"type": "feat", "icon": "⚙️", "tag": "管理弹窗", "text": "历史快照卡片头部新增「快照管理」与「记录当前快照」双入口，大幅提升资产记录管理效率"},
            {"type": "feat", "icon": "🔍", "tag": "明细穿透", "text": "点击历史记录行任意位置，即刻弹出记录时刻的完整股票代码、每股现价、持仓市值与现金详情"},
            {"type": "feat", "icon": "🗑️", "tag": "单条管理", "text": "在明细穿透弹窗底部提供快捷安全删除操作，便于迅速剔除脏数据与异常快照"}
        ]
    },
    {
        "version": "v1.0.1",
        "date": "2026-09-18",
        "commit": "0ad63ff",
        "title": "黑白双配色主题一键切换与全局适配",
        "is_latest": False,
        "items": [
            {"type": "ui", "icon": "☀️/🌙", "tag": "双主题切换", "text": "顶部导航栏新增纯图标切换按钮（☀️/🌙），带防误触悬浮 Tooltip 提示"},
            {"type": "ui", "icon": "🎨", "tag": "全量适配", "text": "覆盖指标卡、饼图/柱状图容器、持仓明细表、历史快照表及所有模态弹窗的双主题配色深度调优"},
            {"type": "perf", "icon": "⚡", "tag": "无感持久化", "text": "基于 localStorage 与 HTML 根节点预执行脚本，刷新页面瞬时应用主题，告别白屏刺眼闪烁"}
        ]
    },
    {
        "version": "v1.0.0",
        "date": "2026-09-18",
        "commit": "7576f09",
        "title": "股票每日涨跌统计与资产分析小助手初始发布",
        "is_latest": False,
        "items": [
            {"type": "security", "icon": "🔒", "tag": "本地隐私", "text": "零券商绑定、免券商密码与 API Key，纯本地配置文件 portfolio.json 计算，保障绝对资金隐私安全"},
            {"type": "feat", "icon": "💷", "tag": "GBP基准统一", "text": "多币种股票与多币种现金实时汇率折算，剥离汇率波动干扰，真实追踪股票组合内生涨跌"},
            {"type": "feat", "icon": "📊", "tag": "双模式看板", "text": "同时提供 Terminal 终端实时彩色看板与现代化 Web 交互看板 (FastAPI + Tailwind + Chart.js, Port 26212)"},
            {"type": "feat", "icon": "📷", "tag": "自动化快照", "text": "自动化收盘快照记录与纽约交易时段智能识别备注，提供历史估值追溯与双向交叉核验对账"}
        ]
    }
]


@app.get("/api/storage/status")
def api_get_storage_status():
    try:
        from portfolio_engine import get_storage_stats
        return {"status": "ok", "stats": get_storage_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/changelog")
def api_get_changelog():
    return {"status": "ok", "changelog": CHANGELOG_DATA}


@app.get("/", response_class=HTMLResponse)
def index_html():
    return """<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>股票每日涨跌与持仓看板 | Portfolio Tracker</title>

  <!-- Early theme initialization to avoid flash -->
  <script>
    (function() {
      const saved = localStorage.getItem('theme');
      if (saved === 'light') {
        document.documentElement.classList.remove('dark');
      } else {
        document.documentElement.classList.add('dark');
      }
    })();
  </script>

  <!-- App Favicons -->
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="alternate icon" type="image/png" href="/favicon.png" />
  <link rel="icon" type="image/x-icon" href="/favicon.ico" />
  <link rel="apple-touch-icon" href="/favicon.png" />

  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 500: '#3b82f6', 600: '#2563eb' },
            gain: '#10b981',
            loss: '#ef4444'
          }
        }
      }
    }
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      transition: background-color 0.2s ease, color 0.2s ease;
    }
    html.dark body {
      background-color: #0b0f19;
      color: #f8fafc;
    }
    html:not(.dark) body {
      background-color: #f8fafc;
      color: #0f172a;
    }

    /* Refined Info Icon & Popover System */
    .popover-container {
      position: relative;
      display: inline-flex;
      align-items: center;
      vertical-align: middle;
    }
    .popover-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 15px;
      height: 15px;
      border-radius: 9999px;
      font-size: 10px;
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      font-weight: 700;
      line-height: 1;
      cursor: pointer;
      user-select: none;
      transition: all 0.15s ease;
      outline: none;
      padding: 0;
    }
    .dark .popover-btn {
      background-color: rgba(51, 65, 85, 0.7);
      color: #94a3b8;
      border: 1px solid rgba(71, 85, 105, 0.7);
    }
    .dark .popover-btn:hover, .dark .popover-container.active .popover-btn {
      background-color: rgba(59, 130, 246, 0.25);
      color: #60a5fa;
      border-color: rgba(96, 165, 250, 0.5);
      transform: scale(1.1);
    }
    html:not(.dark) .popover-btn {
      background-color: #f1f5f9;
      color: #64748b;
      border: 1px solid #cbd5e1;
    }
    html:not(.dark) .popover-btn:hover, html:not(.dark) .popover-container.active .popover-btn {
      background-color: #eff6ff;
      color: #2563eb;
      border-color: #93c5fd;
      transform: scale(1.1);
    }

    .popover-tooltip {
      position: absolute;
      bottom: calc(100% + 7px);
      left: 50%;
      transform: translateX(-50%) translateY(4px);
      width: max-content;
      max-width: 270px;
      padding: 7px 11px;
      border-radius: 10px;
      font-size: 11.5px;
      line-height: 1.45;
      font-weight: 400;
      letter-spacing: normal;
      text-align: left;
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      transition: opacity 0.15s ease, transform 0.15s ease, visibility 0.15s;
      z-index: 100;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.15);
      white-space: normal;
      word-break: break-word;
    }
    .popover-container:hover .popover-tooltip,
    .popover-container.active .popover-tooltip,
    .popover-container:focus-within .popover-tooltip {
      opacity: 1;
      visibility: visible;
      pointer-events: auto;
      transform: translateX(-50%) translateY(0);
    }
    .popover-tooltip::after {
      content: '';
      position: absolute;
      top: 100%;
      left: 50%;
      transform: translateX(-50%);
      border-width: 5px;
      border-style: solid;
    }
    .dark .popover-tooltip {
      background-color: #1e293b;
      color: #e2e8f0;
      border: 1px solid #334155;
    }
    .dark .popover-tooltip::after {
      border-color: #1e293b transparent transparent transparent;
    }
    html:not(.dark) .popover-tooltip {
      background-color: #ffffff;
      color: #334155;
      border: 1px solid #e2e8f0;
    }
    html:not(.dark) .popover-tooltip::after {
      border-color: #ffffff transparent transparent transparent;
    }

    /* Popover bottom alignment */
    .popover-tooltip.pop-bottom {
      bottom: auto;
      top: calc(100% + 8px);
      left: 50%;
      transform: translateX(-50%) translateY(-4px);
    }
    .popover-container:hover .popover-tooltip.pop-bottom,
    .popover-container.active .popover-tooltip.pop-bottom,
    .popover-container:focus-within .popover-tooltip.pop-bottom {
      transform: translateX(-50%) translateY(0);
    }
    .popover-tooltip.pop-bottom::after {
      top: auto;
      bottom: 100%;
      left: 50%;
      transform: translateX(-50%);
    }
    .dark .popover-tooltip.pop-bottom::after {
      border-color: transparent transparent #1e293b transparent;
    }
    html:not(.dark) .popover-tooltip.pop-bottom::after {
      border-color: transparent transparent #ffffff transparent;
    }

    /* Popover left alignment (upwards, left-anchored) */
    .popover-tooltip.pop-left {
      left: -6px;
      right: auto;
      transform: translateY(4px);
    }
    .popover-container:hover .popover-tooltip.pop-left,
    .popover-container.active .popover-tooltip.pop-left,
    .popover-container:focus-within .popover-tooltip.pop-left {
      transform: translateY(0);
    }
    .popover-tooltip.pop-left::after {
      left: 12px;
      transform: none;
    }

    /* Combined: Bottom + Left (anchored to top-left of tooltip, expanding downwards and rightwards) */
    .popover-tooltip.pop-bottom.pop-left {
      bottom: auto;
      top: calc(100% + 8px);
      left: -6px;
      right: auto;
      transform: translateY(-4px);
    }
    .popover-container:hover .popover-tooltip.pop-bottom.pop-left,
    .popover-container.active .popover-tooltip.pop-bottom.pop-left,
    .popover-container:focus-within .popover-tooltip.pop-bottom.pop-left {
      transform: translateY(0);
    }
    .popover-tooltip.pop-bottom.pop-left::after {
      top: auto;
      bottom: 100%;
      left: 12px;
      transform: none;
    }
    .dark .popover-tooltip.pop-bottom.pop-left::after {
      border-color: transparent transparent #1e293b transparent;
    }
    html:not(.dark) .popover-tooltip.pop-bottom.pop-left::after {
      border-color: transparent transparent #ffffff transparent;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col antialiased">
  <!-- Sidebar Backdrop (点击外部遮罩关闭) -->
  <div id="sidebarBackdrop" onclick="closeSidebar()" class="fixed inset-0 bg-black/40 backdrop-blur-xs z-40 hidden transition-opacity duration-300 opacity-0"></div>

  <!-- Gemini-style Left Sidebar (只放置更新日志按钮) -->
  <aside id="appSidebar" class="fixed top-0 left-0 bottom-0 w-64 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-r border-slate-200 dark:border-slate-800 z-50 transform -translate-x-full transition-transform duration-300 ease-in-out flex flex-col shadow-2xl">
    <!-- Sidebar Header -->
    <div class="h-16 px-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
      <div class="flex items-center space-x-2.5">
        <img src="/favicon.svg" alt="App Logo" class="w-7 h-7 rounded-lg shadow-sm" />
        <span class="text-sm font-bold text-slate-900 dark:text-white">功能菜单</span>
      </div>
      <!-- 边栏内部关闭按钮 -->
      <div class="relative flex items-center group">
        <button onclick="closeSidebar()" class="w-8 h-8 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white flex items-center justify-center transition active:scale-95 cursor-pointer" aria-label="关闭边栏">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect width="18" height="18" x="3" y="3" rx="3" ry="3"/>
            <line x1="9" y1="3" x2="9" y2="21"/>
          </svg>
        </button>
        <div class="absolute right-full mr-2 hidden group-hover:block bg-black text-white text-xs px-2.5 py-1 rounded-full whitespace-nowrap shadow-xl font-medium pointer-events-none z-50">
          关闭边栏
        </div>
      </div>
    </div>

    <!-- Sidebar Content: 严格遵从指令，只将更新日志按钮放到边栏内 -->
    <div class="p-3 flex-1 overflow-y-auto space-y-2">
      <div class="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-2 pt-1 pb-0.5">
        版本与记录
      </div>
      <!-- 更新日志专属按钮 -->
      <button onclick="openChangelogModal(); closeSidebar();" class="w-full flex items-center justify-between p-3 rounded-xl bg-gradient-to-r from-blue-50/80 to-indigo-50/40 hover:from-blue-100 hover:to-indigo-100/70 dark:from-slate-800/80 dark:to-blue-950/30 dark:hover:from-slate-800 dark:hover:to-blue-900/50 text-slate-800 dark:text-slate-100 border border-blue-200/70 dark:border-slate-700/80 transition-all duration-150 shadow-sm hover:shadow group text-left cursor-pointer">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center text-sm shadow-sm group-hover:scale-105 transition-transform">
            📜
          </div>
          <div>
            <div class="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
              <span>更新日志</span>
              <span class="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300">v1.4.1</span>
            </div>
            <div class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">版本功能与演进记录</div>
          </div>
        </div>
        <svg class="w-4 h-4 text-slate-400 group-hover:text-blue-600 dark:group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>

    <!-- Sidebar Footer -->
    <div class="p-3 border-t border-slate-200 dark:border-slate-800 text-[11px] text-slate-400 dark:text-slate-500 font-mono flex items-center justify-between">
      <span>Git 分支记录</span>
      <span class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-semibold">feat/db</span>
    </div>
  </aside>

  <!-- Navbar -->
  <header class="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/70 backdrop-blur sticky top-0 z-40 transition-colors">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <img src="/favicon.svg" alt="App Logo" class="w-10 h-10 rounded-xl shadow-lg shadow-blue-500/25 transition hover:scale-105" />
        <div>
          <h1 class="text-base font-bold text-slate-900 dark:text-white leading-tight">每日股票资产分析看板</h1>
          <p class="text-xs text-slate-500 dark:text-slate-400">隐私安全 · 无需券商密码 · 多币种汇率自动折算</p>
        </div>

        <!-- 边栏开关按钮 (Gemini 风格: 位于标题旁，悬浮显示黑色药丸提示) -->
        <div class="relative flex items-center group ml-1">
          <button id="sidebarToggleBtn" onclick="toggleSidebar()" class="w-9 h-9 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white flex items-center justify-center transition active:scale-95 cursor-pointer" aria-label="切换边栏">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect width="18" height="18" x="3" y="3" rx="3" ry="3"/>
              <line x1="9" y1="3" x2="9" y2="21"/>
            </svg>
          </button>
          <div id="sidebarTooltip" class="absolute left-full ml-2 hidden group-hover:block bg-black text-white text-xs px-3 py-1.5 rounded-full whitespace-nowrap shadow-xl font-medium pointer-events-none z-50">
            展开边栏
          </div>
        </div>
      </div>
      <div class="flex items-center space-x-2">
        <!-- 存储引擎状态指示 (SQLite / JSON) -->
        <div class="relative group">
          <div id="storageBadge" class="h-9 px-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 flex items-center gap-1.5 text-xs font-mono font-medium shadow-sm transition">
            <span id="storageIcon">💾</span>
            <span id="storageName">SQLite</span>
          </div>
          <div id="storageTooltip" class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-900 text-white text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            存储引擎: SQLite (portfolio.db)
          </div>
        </div>
        <!-- 切换黑白主题 (新增) -->
        <div class="relative group">
          <button id="themeToggleBtn" onclick="toggleTheme()" title="切换明亮/深色主题" class="w-9 h-9 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 hover:text-amber-500 border border-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 dark:text-slate-200 dark:hover:text-amber-400 dark:border-slate-700 flex items-center justify-center text-base transition shadow-sm hover:scale-105 active:scale-95">
            <span id="themeIcon">☀️</span>
          </button>
          <div id="themeTooltip" class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-900 text-white text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            切换明亮/深色主题
          </div>
        </div>

        <!-- 双向验证 -->
        <div class="relative group">
          <button onclick="runVerification()" title="双向数据交叉核验" class="w-9 h-9 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-300 dark:bg-emerald-950/60 dark:hover:bg-emerald-900/70 dark:text-emerald-400 dark:border-emerald-500/40 flex items-center justify-center text-base transition shadow-sm hover:scale-105 active:scale-95">
            🔍
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-900 text-emerald-400 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            双向数据核验
          </div>
        </div>

        <!-- 记录今日快照 -->
        <div class="relative group">
          <button onclick="recordSnapshot()" title="记录今日收盘快照" class="w-9 h-9 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 dark:text-slate-200 dark:border-slate-700 flex items-center justify-center text-base transition shadow-sm hover:scale-105 active:scale-95">
            📷
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-900 text-slate-200 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            记录今日快照
          </div>
        </div>

        <!-- 调整现金 -->
        <div class="relative group">
          <button onclick="openCashModal()" title="调整可用现金余额" class="w-9 h-9 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 dark:text-slate-200 dark:border-slate-700 flex items-center justify-center text-base transition shadow-sm hover:scale-105 active:scale-95">
            💰
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-900 text-slate-200 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            调整现金余额
          </div>
        </div>

        <!-- 添加/调整股票 -->
        <div class="relative group">
          <button onclick="openStockModal()" title="添加或调整股票持仓" class="w-9 h-9 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold flex items-center justify-center text-lg transition shadow-md shadow-blue-600/20 hover:scale-105 active:scale-95">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"></path></svg>
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-900 text-blue-400 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            添加/调整股票
          </div>
        </div>

        <!-- 刷新行情 -->
        <div class="relative group">
          <button onclick="loadData(true)" title="立即强制向交易所请求最新实时行情" class="w-9 h-9 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 hover:text-slate-900 border border-slate-200 dark:bg-slate-800/80 dark:hover:bg-slate-700 dark:text-slate-300 dark:hover:text-white dark:border-slate-700 flex items-center justify-center transition shadow-sm hover:scale-105 active:scale-95">
            <svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-900 text-slate-200 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            刷新实时行情
          </div>
        </div>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
    <!-- Top KPI Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- Total Value -->
      <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-colors">
        <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold">
          <span>总资产规模 (Total Value)</span>
          <span class="text-xs font-normal text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 px-2 py-0.5 rounded border border-blue-200 dark:border-blue-500/20" id="baseCurrBadge">GBP</span>
        </div>
        <div class="mt-2 text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight" id="totalValue">--</div>
        <div class="mt-2 text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2">
          <span>昨日收盘: <span id="prevTotalValue" class="text-slate-700 dark:text-slate-300">--</span></span>
        </div>
      </div>

      <!-- Today's PnL -->
      <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-colors">
        <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold">
          <span>今日涨跌 (Today's P&L)</span>
          <span class="text-xs font-medium" id="pnlTag">实时</span>
        </div>
        <div class="mt-2 text-3xl font-extrabold" id="todayPnl">--</div>
        <div class="mt-2 text-xs text-slate-500 dark:text-slate-400" id="todayPnlPct">
          --
        </div>
      </div>

      <!-- Asset Allocation -->
      <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-colors">
        <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold">
          <span>资产配置 (Stock vs Cash)</span>
          <span class="text-xs text-slate-400 dark:text-slate-500">权重比例</span>
        </div>
        <div class="mt-2 flex items-baseline gap-2">
          <span class="text-2xl font-bold text-slate-900 dark:text-white" id="stockWeight">--%</span>
          <span class="text-xs text-slate-500 dark:text-slate-400">股票 /</span>
          <span class="text-2xl font-bold text-slate-500 dark:text-slate-400" id="cashWeight">--%</span>
          <span class="text-xs text-slate-500 dark:text-slate-400">现金</span>
        </div>
        <div class="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full mt-3 overflow-hidden flex">
          <div id="stockBar" class="bg-blue-500 h-full transition-all duration-500" style="width: 50%"></div>
          <div id="cashBar" class="bg-emerald-500 h-full transition-all duration-500" style="width: 50%"></div>
        </div>
      </div>

      <!-- Total All-time Return -->
      <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-colors">
        <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider font-semibold">
          <span>累计总回报 (All-Time P&L)</span>
          <span class="text-xs text-slate-400 dark:text-slate-500">相对本金</span>
        </div>
        <div class="mt-2 text-3xl font-extrabold" id="totalReturn">--</div>
        <div class="mt-2 text-xs text-slate-500 dark:text-slate-400">
          成本本金: <span id="totalCost" class="text-slate-700 dark:text-slate-300">--</span>
        </div>
      </div>
    </div>

    <!-- Charts & Allocation Section -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-colors">
        <h3 class="text-sm font-semibold text-slate-900 dark:text-white mb-4 flex items-center justify-between">
          <span>持仓分布 (Holdings Allocation)</span>
          <span class="text-xs text-slate-500">按折算市值</span>
        </h3>
        <div class="h-56 relative flex items-center justify-center">
          <canvas id="allocationChart"></canvas>
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm lg:col-span-2 transition-colors">
        <h3 class="text-sm font-semibold text-slate-900 dark:text-white mb-4 flex items-center justify-between">
          <span>各资产今日涨跌贡献 (Daily P&L by Asset)</span>
          <span class="text-xs text-slate-500" id="lastUpdated">正在获取最新行情...</span>
        </h3>
        <div class="h-56">
          <canvas id="pnlBarChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Holdings Table -->
    <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm transition-colors">
      <div class="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between relative z-20">
        <div class="flex items-center gap-1.5">
          <h2 class="text-base font-bold text-slate-900 dark:text-white">股票持仓明细 (Stock Holdings)</h2>
          <div class="popover-container">
            <button type="button" class="popover-btn" aria-label="查看说明">i</button>
            <div class="popover-tooltip pop-bottom pop-left">每只股票在美股/英股的实时价格、折算英镑价值及当日涨跌幅统计</div>
          </div>
        </div>
        <div class="text-xs text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800/80 px-3 py-1 rounded-lg border border-slate-200 dark:border-slate-700/50">
          共 <span id="holdingsCount" class="font-bold text-slate-900 dark:text-white">0</span> 个持仓标的
        </div>
      </div>

      <div class="overflow-x-auto rounded-b-2xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/50 text-slate-600 dark:text-slate-400 text-xs uppercase tracking-wider border-b border-slate-200 dark:border-slate-800">
              <th class="py-3.5 px-4 font-semibold">标的 / 代码</th>
              <th class="py-3.5 px-4 font-semibold text-right">持有股数</th>
              <th class="py-3.5 px-4 font-semibold text-right">实时现价 (£)</th>
              <th class="py-3.5 px-4 font-semibold text-right">买入均价 (£)</th>
              <th class="py-3.5 px-4 font-semibold text-right">当日涨跌</th>
              <th class="py-3.5 px-4 font-semibold text-right">当前市值 (£)</th>
              <th class="py-3.5 px-4 font-semibold text-right">今日盈亏 (£)</th>
              <th class="py-3.5 px-4 font-semibold text-right">累计盈亏 (£)</th>
              <th class="py-3.5 px-4 font-semibold text-right">仓位</th>
              <th class="py-3.5 px-4 font-semibold text-center">操作</th>
            </tr>
          </thead>
          <tbody id="holdingsTableBody" class="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-800 dark:text-slate-200">
            <tr>
              <td colspan="11" class="py-8 text-center text-slate-500">正在载入行情数据...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Cash Balances Section -->
    <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-colors relative z-10">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-1.5">
          <h2 class="text-sm font-bold text-slate-900 dark:text-white">现金账户 (Cash Balances)</h2>
          <div class="popover-container">
            <button type="button" class="popover-btn" aria-label="查看说明">i</button>
            <div class="popover-tooltip pop-bottom pop-left">多币种现金持有与实时外汇折算，统一以英镑 (GBP) 计价核算</div>
          </div>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="cashCards">
        <!-- populated via JS -->
      </div>
    </div>

    <!-- History Snapshots Table -->
    <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm transition-colors">
      <div class="p-5 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-4 relative z-20">
        <div class="flex items-center gap-2">
          <h2 class="text-base font-bold text-slate-900 dark:text-white">📜 每日历史快照 (Daily Snapshots)</h2>
          <div class="popover-container">
            <button type="button" class="popover-btn" aria-label="查看说明">i</button>
            <div class="popover-tooltip pop-bottom pop-left">精确记录每次快照时刻的系统时间与纽约时间；点击表格中任意一行即可展开当时持仓仓位与英镑估值明细。</div>
          </div>
          <span class="text-[11px] px-2.5 py-0.5 rounded-full bg-cyan-50 dark:bg-cyan-950/80 text-cyan-700 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800/60 font-medium">点击行看明细</span>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="openSnapshotManagerModal()" title="历史快照管理与回收站" class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-200 dark:border-slate-700 text-xs font-semibold shadow-sm transition hover:scale-105 active:scale-95">
            <span>⚙️</span> 快照管理
          </button>
          <button onclick="recordSnapshot()" title="立即记录当前快照" class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md transition hover:scale-105 active:scale-95">
            <span>📷</span> 记录当前快照
          </button>
        </div>
      </div>
      <div class="overflow-x-auto rounded-b-2xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/50 text-slate-600 dark:text-slate-400 text-xs uppercase tracking-wider border-b border-slate-200 dark:border-slate-800">
              <th class="py-3 px-4 font-semibold">系统记录时间</th>
              <th class="py-3 px-4 font-semibold">纽约时间备注</th>
              <th class="py-3 px-4 font-semibold text-right">总资产</th>
              <th class="py-3 px-4 font-semibold text-right">股票市值</th>
              <th class="py-3 px-4 font-semibold text-right">现金余额</th>
              <th class="py-3 px-4 font-semibold text-right">当日涨跌额</th>
              <th class="py-3 px-4 font-semibold text-right">当日涨跌幅</th>
              <th class="py-3 px-4 font-semibold text-center">持仓明细</th>
            </tr>
          </thead>
          <tbody id="historyTableBody" class="divide-y divide-slate-100 dark:divide-slate-800/60 text-slate-800 dark:text-slate-300">
            <tr>
              <td colspan="8" class="py-6 text-center text-slate-500">暂无历史快照</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <!-- Stock Modal -->
  <div id="stockModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 transition-colors">
      <div class="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
        <h3 class="font-bold text-lg text-slate-900 dark:text-white">添加或调整股票持仓</h3>
        <button onclick="closeStockModal()" class="text-slate-400 hover:text-slate-700 dark:hover:text-white text-lg">&times;</button>
      </div>
      <div class="space-y-3 text-sm">
        <div>
          <label class="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">股票代码 (Symbol)</label>
          <input id="modalSymbol" type="text" placeholder="例如: GOOGL, AAPL, NVDA, SHEL.L" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white uppercase focus:outline-none focus:border-blue-500" />
          <p class="text-[11px] text-slate-500 mt-1">美股代码直接输 (GOOGL), 英股带.L (SHEL.L)</p>
        </div>
        
        <div>
          <label class="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">输入方式</label>
          <div class="flex gap-2">
            <button id="modeAmountBtn" onclick="setModalMode('amount')" class="flex-1 py-1.5 text-xs rounded-lg bg-blue-600 text-white font-medium">按金额 (GBP/USD)</button>
            <button id="modeSharesBtn" onclick="setModalMode('shares')" class="flex-1 py-1.5 text-xs rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white">按具体股数</button>
          </div>
        </div>

        <div id="amountSection">
          <label class="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">持仓金额</label>
          <div class="flex gap-2">
            <input id="modalAmount" type="number" step="any" placeholder="例如: 11.7" class="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white focus:outline-none focus:border-blue-500" />
            <select id="modalCurrency" class="bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white focus:outline-none focus:border-blue-500">
              <option value="GBP">GBP (£)</option>
              <option value="USD">USD ($)</option>
            </select>
          </div>
          <p class="text-[11px] text-slate-500 mt-1">系统将自动根据当前实时股价与汇率折算为精准碎股股数并设为买入成本。</p>
        </div>

        <div id="sharesSection" class="hidden space-y-3">
          <div>
            <label class="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">持股数 (Shares)</label>
            <input id="modalShares" type="number" step="any" placeholder="例如: 0.04474" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">买入总成本 (可选)</label>
            <input id="modalCost" type="number" step="any" placeholder="例如: 11.7" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white focus:outline-none focus:border-blue-500" />
          </div>
        </div>
      </div>
      <div class="flex gap-3 pt-2">
        <button onclick="closeStockModal()" class="flex-1 py-2 text-xs rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium">取消</button>
        <button onclick="saveStockHolding()" class="flex-1 py-2 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium shadow-md shadow-blue-600/20">保存持仓</button>
      </div>
    </div>
  </div>

  <!-- Cash Modal -->
  <div id="cashModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4 transition-colors">
      <div class="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
        <h3 class="font-bold text-lg text-slate-900 dark:text-white">设置可用现金余额</h3>
        <button onclick="closeCashModal()" class="text-slate-400 hover:text-slate-700 dark:hover:text-white text-lg">&times;</button>
      </div>
      <div class="space-y-3 text-sm">
        <div>
          <label class="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">GBP 现金 (£)</label>
          <input id="modalCashGbp" type="number" step="any" placeholder="1.0" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">USD 现金 ($)</label>
          <input id="modalCashUsd" type="number" step="any" placeholder="0.0" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white focus:outline-none focus:border-blue-500" />
        </div>
      </div>
      <div class="flex gap-3 pt-2">
        <button onclick="closeCashModal()" class="flex-1 py-2 text-xs rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium">取消</button>
        <button onclick="saveCash()" class="flex-1 py-2 text-xs rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-md shadow-emerald-600/20">保存现金</button>
      </div>
    </div>
  </div>

  <!-- Verify Modal -->
  <div id="verifyModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 transition-colors">
      <div class="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <span class="text-xl">🔍</span>
          <h3 class="font-bold text-lg text-slate-900 dark:text-white">资产数据双向交叉验证</h3>
        </div>
        <button onclick="closeVerifyModal()" class="text-slate-400 hover:text-slate-700 dark:hover:text-white text-lg">&times;</button>
      </div>
      <div id="verifyContent" class="space-y-3 text-sm max-h-[60vh] overflow-y-auto pr-1">
        正在核验数据自洽性...
      </div>
      <div class="flex justify-end pt-2 border-t border-slate-200 dark:border-slate-800">
        <button onclick="closeVerifyModal()" class="py-1.5 px-4 text-xs rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium">关闭</button>
      </div>
    </div>
  </div>

  <!-- Snapshot Detail Modal -->
  <div id="snapshotModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm hidden flex items-center justify-center z-50 p-3 sm:p-5">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-4xl w-full p-5 sm:p-6 shadow-2xl space-y-4 max-h-[92vh] flex flex-col transition-colors">
      <!-- Modal Header -->
      <div class="flex items-start justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
        <div>
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xl">📸</span>
            <h3 class="font-bold text-lg text-slate-900 dark:text-white" id="snapModalTitle">历史快照持仓详情</h3>
            <span id="snapModalStatusBadge" class="text-[11px] px-2.5 py-0.5 rounded-full font-semibold bg-cyan-50 dark:bg-cyan-950/80 text-cyan-700 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800/60"></span>
          </div>
          <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400 mt-1.5" id="snapModalTimeMeta">
            <!-- Populated via JS -->
          </div>
        </div>
        <button onclick="closeSnapshotModal()" class="text-slate-400 hover:text-slate-700 dark:hover:text-white text-2xl p-1 leading-none">&times;</button>
      </div>

      <!-- Modal Scrollable Content -->
      <div class="space-y-4 overflow-y-auto pr-1 flex-1">
        <!-- 4 Stat Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div class="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] text-slate-500 dark:text-slate-400 font-medium">快照总资产 (GBP)</div>
            <div class="text-lg font-bold text-slate-900 dark:text-white font-mono mt-0.5" id="snapTotalVal">-</div>
          </div>
          <div class="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] text-slate-500 dark:text-slate-400 font-medium">股票市值 (GBP)</div>
            <div class="text-lg font-bold text-cyan-700 dark:text-cyan-300 font-mono mt-0.5" id="snapStockVal">-</div>
          </div>
          <div class="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] text-slate-500 dark:text-slate-400 font-medium">现金余额 (GBP)</div>
            <div class="text-lg font-bold text-slate-700 dark:text-slate-200 font-mono mt-0.5" id="snapCashVal">-</div>
          </div>
          <div class="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] text-slate-500 dark:text-slate-400 font-medium">快照日涨跌</div>
            <div class="text-lg font-bold font-mono mt-0.5" id="snapDailyPnl">-</div>
          </div>
        </div>

        <!-- Holdings Breakdown Table -->
        <div class="bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
          <div class="px-4 py-2.5 bg-slate-100 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-sm">📈</span>
              <span class="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">记录时刻股票仓位与估值明细</span>
            </div>
            <span class="text-[11px] text-slate-500 dark:text-slate-400" id="snapHoldingsCount"></span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr class="text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
                  <th class="py-2.5 px-3 font-semibold">股票代码</th>
                  <th class="py-2.5 px-3 font-semibold">持股数</th>
                  <th class="py-2.5 px-3 font-semibold text-right">快照股价</th>
                  <th class="py-2.5 px-3 font-semibold text-right">持仓市值 (£)</th>
                  <th class="py-2.5 px-3 font-semibold text-right">仓位占比</th>
                  <th class="py-2.5 px-3 font-semibold text-right">买入成本/均价</th>
                  <th class="py-2.5 px-3 font-semibold text-right">快照当日涨跌</th>
                  <th class="py-2.5 px-3 font-semibold text-right">快照累计盈亏</th>
                </tr>
              </thead>
              <tbody id="snapHoldingsTableBody" class="divide-y divide-slate-200 dark:divide-slate-800/60 text-slate-800 dark:text-slate-200">
                <!-- Dynamically filled -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- Cash details -->
        <div class="bg-slate-100 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="text-base">💵</span>
            <span class="text-slate-700 dark:text-slate-300 font-medium">记录时刻现金详情:</span>
            <span id="snapCashDetail" class="text-slate-800 dark:text-slate-300 font-mono"></span>
          </div>
          <span class="text-[11px] text-slate-400 dark:text-slate-500 font-mono">始终以 GBP 统一计价核算</span>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="flex items-center justify-between pt-3 border-t border-slate-200 dark:border-slate-800 text-xs">
        <span class="text-slate-400 dark:text-slate-500 font-mono" id="snapModalIdFooter"></span>
        <div class="flex items-center gap-2">
          <button id="snapModalDeleteBtn" onclick="handleDeleteCurrentSnapshot()" type="button" class="py-1.5 px-3.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-600 dark:bg-rose-950/40 dark:hover:bg-rose-900/60 dark:text-rose-400 border border-rose-200 dark:border-rose-900/40 font-medium transition flex items-center gap-1.5 shadow-sm cursor-pointer hover:scale-105 active:scale-95">
            <span id="snapModalDeleteIcon">🗑️</span> <span id="snapModalDeleteText">移入回收站</span>
          </button>
          <button onclick="closeSnapshotModal()" class="py-1.5 px-5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition cursor-pointer">关闭</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Snapshot Manager & Recycle Bin Modal -->
  <div id="snapshotManagerModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4 transition-colors">
      <!-- Modal Header -->
      <div class="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <span class="text-xl">⚙️</span>
          <div class="flex items-center gap-1.5">
            <h3 class="font-bold text-lg text-slate-900 dark:text-white">快照管理与回收站</h3>
            <div class="popover-container">
              <button type="button" class="popover-btn" aria-label="查看说明">i</button>
              <div class="popover-tooltip pop-bottom pop-left">支持按日期范围批量删除快照；已删除快照在回收站安全保留 30 天，支持随时一键还原。</div>
            </div>
          </div>
        </div>
        <button onclick="closeSnapshotManagerModal()" class="text-slate-400 hover:text-slate-700 dark:hover:text-white text-lg">&times;</button>
      </div>

      <!-- Tabs / View Switcher -->
      <div class="flex border-b border-slate-200 dark:border-slate-800 gap-1 pb-1">
        <button id="tabActiveSnapshotsBtn" onclick="switchManagerTab('snapshots')" class="py-2 px-4 text-xs font-bold rounded-lg transition flex items-center gap-1.5 border-b-2 border-blue-600 text-blue-600 dark:text-blue-400 bg-blue-50/60 dark:bg-blue-950/40">
          <span>📅</span> <span>快照管理</span>
          <span id="tabActiveCountBadge" class="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-blue-100 dark:bg-blue-900/80 text-blue-700 dark:text-blue-300 font-mono">0</span>
        </button>
        <button id="tabTrashBtn" onclick="switchManagerTab('trash')" class="py-2 px-4 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white">
          <span>♻️</span> <span>回收站</span>
          <span id="tabTrashCountBadge" class="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono">0</span>
          <span class="popover-container ml-0.5" onclick="event.stopPropagation()">
            <span class="popover-btn" title="查看规则">i</span>
            <span class="popover-tooltip pop-bottom pop-left">已删除快照保留 30 天，到期系统将自动物理清除。保留期间支持一键还原。</span>
          </span>
        </button>
      </div>

      <!-- Tab 1: Snapshots List & Date Range Delete -->
      <div id="tabContentSnapshots" class="space-y-4">
        <!-- Date Range Deletion Box -->
        <div class="p-3.5 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 rounded-xl space-y-2.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5">
              <span class="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1">
                <span>📅</span> 选定日期范围删除
              </span>
              <div class="popover-container">
                <button type="button" class="popover-btn" aria-label="查看说明">i</button>
                <div class="popover-tooltip pop-bottom pop-left">选定区间内的快照将安全移入「回收站」保留 30 天，在此期间支持随时一键全量还原。</div>
              </div>
            </div>
            <div class="flex items-center gap-1.5">
              <button onclick="setDateRangePreset('all')" class="px-2 py-0.5 text-[11px] rounded bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:text-blue-600 transition">全选全部</button>
              <button onclick="setDateRangePreset('today')" class="px-2 py-0.5 text-[11px] rounded bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:text-blue-600 transition">仅今天</button>
              <button onclick="setDateRangePreset('7d')" class="px-2 py-0.5 text-[11px] rounded bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:text-blue-600 transition">近7天</button>
              <button onclick="setDateRangePreset('30d')" class="px-2 py-0.5 text-[11px] rounded bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:text-blue-600 transition">近30天</button>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <div class="flex items-center gap-1">
              <span class="text-slate-500">从:</span>
              <input type="date" id="rangeStartDate" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500" />
            </div>
            <div class="flex items-center gap-1">
              <span class="text-slate-500">至:</span>
              <input type="date" id="rangeEndDate" class="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500" />
            </div>
            <button onclick="confirmDeleteDateRange()" class="ml-auto px-3.5 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-600 text-rose-600 hover:text-white dark:bg-rose-950/40 dark:hover:bg-rose-600 dark:text-rose-400 dark:hover:text-white border border-rose-200 dark:border-rose-900 font-semibold transition flex items-center gap-1 shadow-sm">
              <span>🗑️</span> 删除该范围快照
            </button>
          </div>
        </div>

        <!-- Snapshots List -->
        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-medium px-1">
            <span>有效快照记录列表</span>
            <span id="mgrSnapshotCount" class="font-mono">共 0 条</span>
          </div>
          <div id="mgrSnapshotList" class="space-y-2 max-h-56 overflow-y-auto pr-1">
            <!-- Dynamically populated -->
          </div>
        </div>
      </div>

      <!-- Tab 2: Recycle Bin (30-day Retention) -->
      <div id="tabContentTrash" class="hidden space-y-3">
        <!-- Trash Notice Banner -->
        <div class="p-2.5 bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-900/40 rounded-xl flex items-center justify-between gap-2 text-xs">
          <div class="flex items-center gap-1.5 text-amber-800 dark:text-amber-300">
            <span class="text-base">♻️</span>
            <span class="font-medium">回收站快照（30天自动清理）</span>
            <div class="popover-container">
              <button type="button" class="popover-btn" aria-label="查看说明">i</button>
              <div class="popover-tooltip pop-bottom pop-left">在此安全保留 30 天，到期系统将自动物理清除。保留期间支持一键还原至有效快照列表。</div>
            </div>
          </div>
          <button onclick="confirmPurgeTrash('all')" class="shrink-0 px-2.5 py-1 rounded-lg bg-white dark:bg-slate-800 border border-rose-200 dark:border-rose-900 text-rose-600 dark:text-rose-400 hover:bg-rose-600 hover:text-white dark:hover:bg-rose-600 dark:hover:text-white transition font-medium text-[11px] shadow-sm">
            清空回收站
          </button>
        </div>

        <!-- Trash List -->
        <div id="mgrTrashList" class="space-y-2 max-h-64 overflow-y-auto pr-1">
          <!-- Dynamically populated from /api/trash -->
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="flex items-center justify-between pt-3 border-t border-slate-200 dark:border-slate-800 text-xs">
        <span class="text-slate-400 dark:text-slate-500 font-mono" id="mgrStatusSummary">始终本地私有存储</span>
        <button onclick="closeSnapshotManagerModal()" class="py-1.5 px-5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium transition">关闭</button>
      </div>
    </div>
  </div>

  <!-- Changelog Modal (系统更新日志弹窗) -->
  <div id="changelogModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4 transition-colors max-h-[90vh] flex flex-col">
      <!-- Modal Header -->
      <div class="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800/60 flex items-center justify-center text-xl">
            📜
          </div>
          <div>
            <h3 class="font-bold text-lg text-slate-900 dark:text-white flex items-center gap-2">
              <span>系统版本更新日志</span>
              <span class="text-xs font-mono font-semibold px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300">Changelog</span>
            </h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">结合 Git 提交历史整理 · 当前版本 v1.4.1 (交互体验与回收站优化)</p>
          </div>
        </div>
        <button onclick="closeChangelogModal()" class="text-slate-400 hover:text-slate-700 dark:hover:text-white text-2xl leading-none cursor-pointer">&times;</button>
      </div>

      <!-- Modal Body (Timeline) -->
      <div id="changelogTimelineContainer" class="flex-1 overflow-y-auto pr-1 space-y-4">
        <!-- Dynamically rendered via renderChangelog() from CHANGELOG_DATA -->
      </div>

      <!-- Modal Footer -->
      <div class="flex items-center justify-between pt-3 border-t border-slate-200 dark:border-slate-800 text-xs shrink-0">
        <div class="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 font-mono">
          <span>📦</span>
          <span>本地 Git 同步记录 · 共 8 个版本发布</span>
        </div>
        <button onclick="closeChangelogModal()" class="py-1.5 px-5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium transition cursor-pointer">
          关闭
        </button>
      </div>
    </div>
  </div>

  <!-- Universal In-App Confirmation Modal (全局交互确认弹窗，免疫浏览器原生弹窗拦截) -->
  <div id="appConfirmModal" class="fixed inset-0 bg-black/75 backdrop-blur-sm hidden flex items-center justify-center z-[80] p-4 transition-all">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 transition-colors">
      <div class="flex items-start gap-3">
        <div id="confirmModalIcon" class="w-10 h-10 rounded-xl bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-900/40 flex items-center justify-center text-xl shrink-0">
          🗑️
        </div>
        <div class="space-y-1">
          <h3 id="confirmModalTitle" class="font-bold text-slate-900 dark:text-white text-base">操作确认</h3>
          <p id="confirmModalMsg" class="text-xs text-slate-600 dark:text-slate-300 leading-relaxed"></p>
          <p id="confirmModalSubMsg" class="text-[11px] text-slate-400 dark:text-slate-500 font-mono mt-1"></p>
        </div>
      </div>
      <div class="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
        <button id="confirmModalCancelBtn" type="button" class="py-2 px-4 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium transition cursor-pointer">
          取消
        </button>
        <button id="confirmModalActionBtn" type="button" class="py-2 px-4 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold transition shadow-md cursor-pointer flex items-center gap-1.5">
          <span id="confirmModalActionText">确认</span>
        </button>
      </div>
    </div>
  </div>

  <!-- Floating Toast Notification System (全局轻量提示系统) -->
  <div id="appToast" class="fixed bottom-6 right-6 z-[100] transform transition-all duration-300 ease-out translate-y-12 opacity-0 pointer-events-none max-w-sm">
    <div id="appToastContent" class="flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-xl text-xs font-medium border bg-slate-900/90 text-slate-100 border-slate-700 backdrop-blur-md">
      <span id="appToastIcon" class="text-base">🔔</span>
      <span id="appToastText" class="flex-1">提示信息</span>
      <button onclick="dismissToast()" class="text-slate-400 hover:text-slate-200 ml-1 text-sm font-bold leading-none cursor-pointer">&times;</button>
    </div>
  </div>

  <script>
    let portfolioData = null;
    let historyDataCache = [];
    let currentActiveSnapshotId = null;
    let allocChart = null;
    let pnlChart = null;
    let activeModalMode = 'amount';

    // ===== 全局轻量 Toast 提示系统 =====
    let toastTimeout = null;
    function showToast(message, type = 'info') {
      const toast = document.getElementById('appToast');
      const content = document.getElementById('appToastContent');
      const icon = document.getElementById('appToastIcon');
      const text = document.getElementById('appToastText');
      if (!toast || !content) return;

      if (toastTimeout) clearTimeout(toastTimeout);
      text.innerText = message;

      if (type === 'success') {
        icon.innerText = '✅';
        content.className = 'flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-xl text-xs font-medium border bg-emerald-900/90 text-emerald-100 border-emerald-700/60 backdrop-blur-md';
      } else if (type === 'error') {
        icon.innerText = '❌';
        content.className = 'flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-xl text-xs font-medium border bg-rose-900/90 text-rose-100 border-rose-700/60 backdrop-blur-md';
      } else if (type === 'warn') {
        icon.innerText = '⚠️';
        content.className = 'flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-xl text-xs font-medium border bg-amber-900/90 text-amber-100 border-amber-700/60 backdrop-blur-md';
      } else {
        icon.innerText = 'ℹ️';
        content.className = 'flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-xl text-xs font-medium border bg-slate-900/90 text-slate-100 border-slate-700 backdrop-blur-md';
      }

      toast.classList.remove('translate-y-12', 'opacity-0', 'pointer-events-none');
      toast.classList.add('translate-y-0', 'opacity-100', 'pointer-events-auto');
      toastTimeout = setTimeout(dismissToast, 3500);
    }

    function dismissToast() {
      const toast = document.getElementById('appToast');
      if (toast) {
        toast.classList.add('translate-y-12', 'opacity-0', 'pointer-events-none');
        toast.classList.remove('translate-y-0', 'opacity-100', 'pointer-events-auto');
      }
    }

    // ===== 内置交互式确认弹窗 (解决 window.confirm 浏览器被拦截/失效) =====
    let confirmModalResolver = null;

    function showConfirmModal(opts) {
      return new Promise((resolve) => {
        confirmModalResolver = resolve;
        const iconEl = document.getElementById('confirmModalIcon');
        const titleEl = document.getElementById('confirmModalTitle');
        const msgEl = document.getElementById('confirmModalMsg');
        const subMsgEl = document.getElementById('confirmModalSubMsg');
        const actionBtn = document.getElementById('confirmModalActionBtn');
        const actionText = document.getElementById('confirmModalActionText');

        if (iconEl) iconEl.innerText = opts.icon || '⚠️';
        if (titleEl) titleEl.innerText = opts.title || '操作确认';
        if (msgEl) msgEl.innerText = opts.message || '确定要执行此操作吗？';
        
        if (subMsgEl) {
          if (opts.subMessage) {
            subMsgEl.innerText = opts.subMessage;
            subMsgEl.classList.remove('hidden');
          } else {
            subMsgEl.classList.add('hidden');
          }
        }

        if (actionText) actionText.innerText = opts.confirmText || '确认';

        if (actionBtn) {
          if (opts.confirmClass) {
            actionBtn.className = `py-2 px-4 rounded-xl font-semibold transition shadow-md cursor-pointer flex items-center gap-1.5 ${opts.confirmClass}`;
          } else {
            actionBtn.className = 'py-2 px-4 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold transition shadow-md cursor-pointer flex items-center gap-1.5';
          }
        }

        const modal = document.getElementById('appConfirmModal');
        if (modal) modal.classList.remove('hidden');
      });
    }

    function closeAppConfirmModal(result = false) {
      const modal = document.getElementById('appConfirmModal');
      if (modal) modal.classList.add('hidden');
      if (confirmModalResolver) {
        confirmModalResolver(result);
        confirmModalResolver = null;
      }
    }

    function initTheme() {
      const saved = localStorage.getItem('theme');
      const isDark = saved ? (saved === 'dark') : true;
      setTheme(isDark);
    }

    function toggleTheme() {
      const isCurrentlyDark = document.documentElement.classList.contains('dark');
      setTheme(!isCurrentlyDark);
    }

    function setTheme(dark) {
      const icon = document.getElementById('themeIcon');
      const tooltip = document.getElementById('themeTooltip');
      const btn = document.getElementById('themeToggleBtn');
      if (dark) {
        document.documentElement.classList.add('dark');
        localStorage.setItem('theme', 'dark');
        if (icon) icon.innerText = '☀️';
        if (btn) btn.setAttribute('title', '切换明亮主题');
        if (tooltip) tooltip.innerText = '切换明亮主题';
      } else {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('theme', 'light');
        if (icon) icon.innerText = '🌙';
        if (btn) btn.setAttribute('title', '切换深色主题');
        if (tooltip) tooltip.innerText = '切换深色主题';
      }
      if (portfolioData) {
        renderCharts(portfolioData);
      }
    }

    function setModalMode(mode) {
      activeModalMode = mode;
      const amtBtn = document.getElementById('modeAmountBtn');
      const shrBtn = document.getElementById('modeSharesBtn');
      const amtSec = document.getElementById('amountSection');
      const shrSec = document.getElementById('sharesSection');

      if (mode === 'amount') {
        amtBtn.className = 'flex-1 py-1.5 text-xs rounded-lg bg-blue-600 text-white font-medium';
        shrBtn.className = 'flex-1 py-1.5 text-xs rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white';
        amtSec.classList.remove('hidden');
        shrSec.classList.add('hidden');
      } else {
        shrBtn.className = 'flex-1 py-1.5 text-xs rounded-lg bg-blue-600 text-white font-medium';
        amtBtn.className = 'flex-1 py-1.5 text-xs rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white';
        shrSec.classList.remove('hidden');
        amtSec.classList.add('hidden');
      }
    }

    function openStockModal() {
      document.getElementById('stockModal').classList.remove('hidden');
      document.getElementById('modalSymbol').focus();
    }
    function closeStockModal() {
      document.getElementById('stockModal').classList.add('hidden');
    }
    function openCashModal() {
      if (portfolioData && portfolioData.cash) {
        portfolioData.cash.forEach(c => {
          if (c.currency === 'GBP') document.getElementById('modalCashGbp').value = c.amount;
          if (c.currency === 'USD') document.getElementById('modalCashUsd').value = c.amount;
        });
      }
      document.getElementById('cashModal').classList.remove('hidden');
    }
    function closeCashModal() {
      document.getElementById('cashModal').classList.add('hidden');
    }

    function closeVerifyModal() {
      document.getElementById('verifyModal').classList.add('hidden');
    }

    async function runVerification() {
      document.getElementById('verifyModal').classList.remove('hidden');
      const container = document.getElementById('verifyContent');
      container.innerHTML = '<div class="text-center py-6 text-slate-500 dark:text-slate-400">正在执行交叉验证计算...</div>';
      try {
        const res = await fetch('/api/verify');
        const json = await res.json();
        if (json.status === 'ok') {
          const rep = json.report;
          let html = `
            <div class="p-3 rounded-xl ${rep.all_passed ? 'bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300' : 'bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-500/30 text-rose-700 dark:text-rose-300'} flex items-center gap-2 text-xs font-semibold">
              <span>${rep.all_passed ? '✓ 全部数据双向核验通过：股数、均价、本金、现价与市值 100% 自洽无冲突！' : '⚠️ 存在部分数值偏差，请检查持仓数据！'}</span>
            </div>
          `;
          rep.holdings_checks.forEach(h => {
            html += `
              <div class="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl p-3 space-y-2">
                <div class="font-bold text-slate-900 dark:text-white flex justify-between text-xs">
                  <span class="text-blue-600 dark:text-blue-400">${h.symbol}</span>
                  <span class="text-slate-500 dark:text-slate-400">${h.shares} 股 · 记录本金 £${h.cost_basis.toFixed(2)}</span>
                </div>
                <div class="space-y-1.5 text-xs">
            `;
            h.checks.forEach(c => {
              html += `
                <div class="flex items-start gap-2 ${c.passed ? 'text-slate-700 dark:text-slate-300' : 'text-rose-600 dark:text-rose-400 font-bold'}">
                  <span>${c.passed ? '✅' : '❌'}</span>
                  <div class="flex-1">
                    <span class="font-semibold text-slate-900 dark:text-white">${c.name}:</span>
                    <span class="text-slate-500 dark:text-slate-400 text-[11px] block">${c.msg}</span>
                  </div>
                </div>
              `;
            });
            html += `</div></div>`;
          });
          const b = rep.balance_check;
          html += `
            <div class="bg-slate-100 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/40 rounded-xl p-3 text-xs text-slate-700 dark:text-slate-300 flex justify-between items-center">
              <span>总资产平衡核验: 股票 (£${b.stock_value.toFixed(2)}) + 现金 (£${b.cash_value.toFixed(2)})</span>
              <span class="font-bold text-emerald-600 dark:text-emerald-400">＝ £${b.total_value.toFixed(2)} ✓</span>
            </div>
          `;
          container.innerHTML = html;
        }
      } catch (e) {
        container.innerHTML = `<div class="text-rose-500 py-4">校验失败: ${e}</div>`;
      }
    }

    function formatCurrency(val, sym = '£') {
      return sym + Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function formatPctBadge(pct) {
      const p = Number(pct);
      const sign = p > 0 ? '+' : '';
      const color = p > 0
        ? 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20'
        : (p < 0
          ? 'text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20'
          : 'text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700');
      return `<span class="px-2 py-0.5 rounded text-xs font-semibold border ${color}">${sign}${p.toFixed(2)}%</span>`;
    }

    function formatPnLText(val, pct, sym = '£') {
      const v = Number(val);
      const sign = v > 0 ? '+' : '';
      const color = v > 0 ? 'text-emerald-600 dark:text-emerald-400' : (v < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-600 dark:text-slate-400');
      return `<span class="${color} font-semibold">${sign}${formatCurrency(v, sym)} <span class="text-xs font-normal">(${sign}${Number(pct).toFixed(2)}%)</span></span>`;
    }

    async function loadData(forceRefresh = false) {
      try {
        const url = forceRefresh ? '/api/portfolio?refresh=true' : '/api/portfolio';
        const res = await fetch(url);
        const json = await res.json();
        if (json.status === 'ok') {
          portfolioData = json.data;
          renderDashboard(portfolioData);
          loadHistory();
        }
      } catch (e) {
        console.error("Fetch error:", e);
      }
    }

    async function loadHistory() {
      try {
        const res = await fetch('/api/history');
        const json = await res.json();
        if (json.status === 'ok') {
          historyDataCache = json.history || [];
          renderHistory(historyDataCache);
          if (typeof renderManagerSnapshotList === 'function') renderManagerSnapshotList();
        }
      } catch (e) {
        console.error("History fetch error:", e);
      }
    }

    function renderDashboard(data) {
      const sym = data.base_symbol;
      document.getElementById('baseCurrBadge').innerText = data.base_currency;
      document.getElementById('totalValue').innerText = formatCurrency(data.total_value, sym);
      document.getElementById('prevTotalValue').innerText = formatCurrency(data.prev_total_value, sym);

      // Today PnL
      const todayPnlEl = document.getElementById('todayPnl');
      const todayPnlPctEl = document.getElementById('todayPnlPct');
      const pnlSign = data.daily_pnl > 0 ? '+' : '';
      todayPnlEl.innerText = `${pnlSign}${formatCurrency(data.daily_pnl, sym)}`;
      todayPnlPctEl.innerHTML = `涨跌幅: <span class="font-semibold">${pnlSign}${data.daily_pnl_pct.toFixed(2)}%</span> <span class="popover-container"><span class="popover-btn" title="查看计算口径">i</span><span class="popover-tooltip pop-bottom pop-left">以基准货币英镑 (GBP) 统一计价测算今日持仓涨跌幅度，不计汇率变动干扰。</span></span>`;

      // Weights
      document.getElementById('stockWeight').innerText = data.stock_weight_pct.toFixed(1) + '%';
      document.getElementById('cashWeight').innerText = data.cash_weight_pct.toFixed(1) + '%';
      document.getElementById('stockBar').style.width = `${data.stock_weight_pct}%`;
      document.getElementById('cashBar').style.width = `${data.cash_weight_pct}%`;

      // Total Return
      const retEl = document.getElementById('totalReturn');
      const retSign = data.total_return > 0 ? '+' : '';
      retEl.innerText = `${retSign}${formatCurrency(data.total_return, sym)}`;
      retEl.className = `mt-2 text-3xl font-extrabold ${data.total_return > 0 ? 'text-emerald-600 dark:text-emerald-400' : (data.total_return < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-white')}`;
      document.getElementById('totalCost').innerText = formatCurrency(data.total_invested_cost, sym);

      document.getElementById('lastUpdated').innerText = `已更新: ${new Date(data.timestamp).toLocaleTimeString()}`;
      document.getElementById('holdingsCount').innerText = data.holdings.length;

      // Table Render
      const tbody = document.getElementById('holdingsTableBody');
      tbody.innerHTML = '';
      if (data.holdings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="py-8 text-center text-slate-500">暂无股票持仓。请点击右上角 "+ 添加股票" 开始跟踪。</td></tr>';
      } else {
        data.holdings.forEach(h => {
          const row = document.createElement('tr');
          row.className = 'hover:bg-slate-50 dark:hover:bg-slate-800/40 transition group border-b border-slate-100 dark:border-slate-800/60';
          const nativeSym = h.stock_currency === 'USD' ? '$' : (h.stock_currency + ' ');
          const sharesStr = Number(h.shares).toFixed(7).replace(/\\.?0+$/, '');
          const avgPriceGbp = h.avg_price_base ? formatCurrency(h.avg_price_base, sym) : '--';
          const avgPriceSub = h.avg_price_native ? `<div class="text-[11px] text-slate-400 dark:text-slate-500">$${h.avg_price_native.toFixed(2)}</div>` : '';
          const currentPriceNativeSub = h.stock_currency !== 'GBP' ? `<div class="text-[11px] text-slate-400 dark:text-slate-500">${nativeSym}${h.price_native.toFixed(2)}</div>` : '';

          row.innerHTML = `
            <td class="py-3 px-4">
              <div class="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <span class="text-blue-600 dark:text-blue-400">${h.symbol}</span>
                <span class="text-xs font-normal text-slate-500 dark:text-slate-400 truncate max-w-[120px]">${h.name}</span>
              </div>
              <div class="text-[11px] text-slate-400 dark:text-slate-500">${h.exchange || ''} · ${h.stock_currency}</div>
            </td>
            <td class="py-3 px-4 text-right font-mono text-slate-700 dark:text-slate-300">${sharesStr}</td>
            <td class="py-3 px-4 text-right font-mono text-slate-700 dark:text-slate-300">
              <div>${formatCurrency(h.price_base, sym)}</div>
              ${currentPriceNativeSub}
            </td>
            <td class="py-3 px-4 text-right font-mono text-slate-700 dark:text-slate-300">
              <div>${avgPriceGbp}</div>
              ${avgPriceSub}
            </td>
            <td class="py-3 px-4 text-right">${formatPctBadge(h.stock_change_pct)}</td>
            <td class="py-3 px-4 text-right font-mono font-bold text-slate-900 dark:text-white">${formatCurrency(h.current_value_base, sym)}</td>
            <td class="py-3 px-4 text-right">${formatPnLText(h.daily_pnl_base, h.daily_pnl_pct, sym)}</td>
            <td class="py-3 px-4 text-right">${formatPnLText(h.total_pnl_base, h.total_pnl_pct, sym)}</td>
            <td class="py-3 px-4 text-right font-mono text-slate-500 dark:text-slate-400">${h.weight_pct.toFixed(1)}%</td>
            <td class="py-3 px-4 text-center">
              <button onclick="removeHolding('${h.symbol}')" title="删除持仓" class="text-slate-400 hover:text-rose-500 p-1 rounded transition opacity-0 group-hover:opacity-100">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
              </button>
            </td>
          `;
          tbody.appendChild(row);
        });
      }

      // Cash Cards
      const cashContainer = document.getElementById('cashCards');
      cashContainer.innerHTML = '';
      data.cash.forEach(c => {
        const card = document.createElement('div');
        card.className = 'bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl p-4 flex items-center justify-between transition-colors';
        const cSym = c.currency === 'GBP' ? '£' : (c.currency === 'USD' ? '$' : c.currency + ' ');
        card.innerHTML = `
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400 font-semibold">${c.currency} 可用现金</div>
            <div class="text-xl font-bold text-slate-900 dark:text-white mt-1">${formatCurrency(c.amount, cSym)}</div>
            <div class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">折合: ${formatCurrency(c.value_base, sym)}</div>
          </div>
          <div class="text-2xl opacity-80">${c.currency === 'GBP' ? '💷' : '💵'}</div>
        `;
        cashContainer.appendChild(card);
      });

      renderCharts(data);
    }

    function renderCharts(data) {
      const sym = data.base_symbol;
      const isDark = document.documentElement.classList.contains('dark');
      const tickColor = isDark ? '#94a3b8' : '#64748b';
      const gridColor = isDark ? '#1e293b' : '#e2e8f0';

      // Donut chart
      const allocLabels = data.holdings.map(h => h.symbol).concat(data.cash.filter(c => c.amount > 0).map(c => `${c.currency} 现金`));
      const allocValues = data.holdings.map(h => h.current_value_base).concat(data.cash.filter(c => c.amount > 0).map(c => c.value_base));
      const allocColors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#64748b'];

      if (allocChart) allocChart.destroy();
      const ctx1 = document.getElementById('allocationChart').getContext('2d');
      allocChart = new Chart(ctx1, {
        type: 'doughnut',
        data: {
          labels: allocLabels,
          datasets: [{
            data: allocValues,
            backgroundColor: allocColors.slice(0, allocValues.length),
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom', labels: { color: tickColor, boxWidth: 12, font: { size: 11 } } }
          },
          cutout: '70%'
        }
      });

      // PnL Bar Chart
      const pnlLabels = data.holdings.map(h => h.symbol);
      const pnlValues = data.holdings.map(h => h.daily_pnl_base);
      const pnlColors = pnlValues.map(v => v >= 0 ? '#10b981' : '#ef4444');

      if (pnlChart) pnlChart.destroy();
      const ctx2 = document.getElementById('pnlBarChart').getContext('2d');
      pnlChart = new Chart(ctx2, {
        type: 'bar',
        data: {
          labels: pnlLabels,
          datasets: [{
            label: `今日涨跌额 (${sym})`,
            data: pnlValues,
            backgroundColor: pnlColors,
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: tickColor } },
            y: { grid: { color: gridColor }, ticks: { color: tickColor } }
          }
        }
      });
    }

    function renderHistory(history) {
      const tbody = document.getElementById('historyTableBody');
      tbody.innerHTML = '';
      if (!history || history.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="py-6 text-center text-slate-500">暂无快照记录，请点击右上角"记录当前快照"。</td></tr>';
        return;
      }
      history.slice().reverse().forEach((item, idx) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-800/60 cursor-pointer transition text-sm group border-b border-slate-100 dark:border-slate-800/60';
        const targetId = item.id || item.timestamp || item.date;
        tr.onclick = () => openSnapshotModal(targetId);

        const sym = item.base_currency === 'GBP' ? '£' : '$';
        const sysTime = item.system_time || item.timestamp || item.date;
        const nyNote = item.ny_note;

        let nyBadge = '<span class="text-slate-400 dark:text-slate-500 text-xs">—</span>';
        if (nyNote) {
          nyBadge = `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 dark:bg-amber-950/70 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60 shadow-sm">
            <span>🗽</span> <span>${nyNote}</span>
          </span>`;
        }

        tr.innerHTML = `
          <td class="py-3.5 px-4 font-mono">
            <div class="text-slate-900 dark:text-white font-semibold flex items-center gap-1.5">
              <span class="text-cyan-600 dark:text-cyan-400">🕒</span>
              <span class="text-slate-700 dark:text-slate-200">${sysTime}</span>
            </div>
          </td>
          <td class="py-3.5 px-4">
            ${nyBadge}
          </td>
          <td class="py-3.5 px-4 text-right font-mono font-bold text-slate-900 dark:text-white">${formatCurrency(item.total_value, sym)}</td>
          <td class="py-3.5 px-4 text-right font-mono text-cyan-700 dark:text-cyan-300 font-semibold">${formatCurrency(item.stock_value, sym)}</td>
          <td class="py-3.5 px-4 text-right font-mono text-slate-700 dark:text-slate-300">${formatCurrency(item.cash_value, sym)}</td>
          <td class="py-3.5 px-4 text-right font-mono">${formatPnLText(item.daily_pnl, item.daily_pnl_pct, sym)}</td>
          <td class="py-3.5 px-4 text-right">${formatPctBadge(item.daily_pnl_pct)}</td>
          <td class="py-3.5 px-4 text-center">
            <button onclick="event.stopPropagation(); openSnapshotModal('${targetId}')" class="px-2.5 py-1 text-xs font-semibold rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-600/20 dark:text-blue-400 hover:bg-blue-600 hover:text-white transition flex items-center gap-1 mx-auto shadow-sm">
              <span>🔍</span> <span>明细</span>
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function openSnapshotModal(identifier) {
      if (!identifier) return;
      let snap = historyDataCache.find(x => x.id === identifier || x.timestamp === identifier || x.date === identifier);
      if (!snap) {
        // Fallback fetch from api
        fetch(`/api/snapshot/${encodeURIComponent(identifier)}`)
          .then(r => r.json())
          .then(res => {
            if (res.status === 'ok') renderSnapshotDetail(res.snapshot);
            else alert('未找到该快照详情');
          })
          .catch(e => alert('获取快照详情失败: ' + e));
        return;
      }
      renderSnapshotDetail(snap);
    }

    function renderSnapshotDetail(snap) {
      const sym = snap.base_currency === 'GBP' ? '£' : '$';

      // Title & badges
      document.getElementById('snapModalTitle').innerText = `历史快照持仓详情 (${snap.date})`;
      const badge = document.getElementById('snapModalStatusBadge');
      if (snap.session_status) {
        badge.innerText = snap.session_status;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }

      const metaEl = document.getElementById('snapModalTimeMeta');
      metaEl.innerHTML = `
        <span class="flex items-center gap-1.5 text-cyan-700 dark:text-cyan-300">
          <span>🕒 系统时间:</span> <strong class="font-mono text-slate-900 dark:text-white">${snap.system_time || snap.timestamp}</strong>
        </span>
        <span class="text-slate-300 dark:text-slate-600">|</span>
        <span class="flex items-center gap-1.5 text-amber-700 dark:text-amber-300">
          <span>🗽 纽约时间备注:</span> <strong class="font-mono text-amber-800 dark:text-amber-200">${snap.ny_note || snap.ny_time || '无备注'}</strong>
        </span>
      `;

      // 4 Stat Cards
      document.getElementById('snapTotalVal').innerText = formatCurrency(snap.total_value, sym);
      document.getElementById('snapStockVal').innerText = formatCurrency(snap.stock_value, sym);
      document.getElementById('snapCashVal').innerText = formatCurrency(snap.cash_value, sym);

      const pnlEl = document.getElementById('snapDailyPnl');
      const pnlSign = snap.daily_pnl > 0 ? '+' : '';
      pnlEl.innerText = `${pnlSign}${formatCurrency(snap.daily_pnl, sym)} (${pnlSign}${Number(snap.daily_pnl_pct).toFixed(2)}%)`;
      pnlEl.className = `text-lg font-bold font-mono mt-0.5 ${snap.daily_pnl > 0 ? 'text-emerald-600 dark:text-emerald-400' : (snap.daily_pnl < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-white')}`;

      // Holdings table
      const tbody = document.getElementById('snapHoldingsTableBody');
      tbody.innerHTML = '';

      const holdings = snap.holdings || [];
      document.getElementById('snapHoldingsCount').innerText = `共 ${holdings.length} 只股票持仓`;

      if (holdings.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="8" class="py-8 px-4 text-center text-slate-400 bg-slate-50/50 dark:bg-slate-900/40">
              <div class="max-w-md mx-auto space-y-1.5">
                <p class="font-semibold text-amber-600 dark:text-amber-300 text-sm">ℹ️ 此快照为早期记录（未包含个股持仓明细）</p>
                <p class="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">系统已升级快照引擎，后续记录的每一次快照均会自动永久记录个股精确股数、英镑估值、买入成本与单日盈亏明细。</p>
              </div>
            </td>
          </tr>
        `;
      } else {
        holdings.forEach(h => {
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-slate-100 dark:hover:bg-slate-800/60 transition border-b border-slate-100 dark:border-slate-800/60';

          let priceStr = formatCurrency(h.price_base, sym);
          if (h.stock_currency && h.stock_currency !== snap.base_currency && h.price_native) {
            priceStr += `<div class="text-[10px] text-slate-400 dark:text-slate-500 font-mono">($${Number(h.price_native).toFixed(2)})</div>`;
          }

          let costStr = formatCurrency(h.cost_basis_base, sym);
          if (h.avg_price_base) {
            costStr += `<div class="text-[10px] text-slate-400 dark:text-slate-500 font-mono">@${formatCurrency(h.avg_price_base, sym)}</div>`;
          }

          const dailyPnlSign = h.daily_pnl_base > 0 ? '+' : '';
          const dailyClass = h.daily_pnl_base > 0 ? 'text-emerald-600 dark:text-emerald-400' : (h.daily_pnl_base < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-600 dark:text-slate-400');

          const totPnlSign = h.total_pnl_base > 0 ? '+' : '';
          const totClass = h.total_pnl_base > 0 ? 'text-emerald-600 dark:text-emerald-400' : (h.total_pnl_base < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-600 dark:text-slate-400');

          tr.innerHTML = `
            <td class="py-3 px-3">
              <div class="font-bold text-slate-900 dark:text-white font-mono text-sm">${h.symbol}</div>
              <div class="text-[11px] text-slate-500 dark:text-slate-400 truncate max-w-[150px]">${h.name || ''}</div>
            </td>
            <td class="py-3 px-3 font-mono text-cyan-700 dark:text-cyan-300 font-semibold text-sm">${h.shares}</td>
            <td class="py-3 px-3 text-right font-mono text-slate-700 dark:text-slate-200">${priceStr}</td>
            <td class="py-3 px-3 text-right font-mono font-bold text-slate-900 dark:text-white text-sm">${formatCurrency(h.current_value_base, sym)}</td>
            <td class="py-3 px-3 text-right font-mono text-slate-600 dark:text-slate-300">${h.weight_pct}%</td>
            <td class="py-3 px-3 text-right font-mono">${costStr}</td>
            <td class="py-3 px-3 text-right font-mono ${dailyClass}">
              ${dailyPnlSign}${formatCurrency(h.daily_pnl_base, sym)}
              <div class="text-[10px]">${dailyPnlSign}${Number(h.daily_pnl_pct).toFixed(2)}%</div>
            </td>
            <td class="py-3 px-3 text-right font-mono ${totClass}">
              ${totPnlSign}${formatCurrency(h.total_pnl_base, sym)}
              <div class="text-[10px]">${totPnlSign}${Number(h.total_pnl_pct).toFixed(2)}%</div>
            </td>
          `;
          tbody.appendChild(tr);
        });
      }

      // Cash breakdown
      const cashEl = document.getElementById('snapCashDetail');
      if (snap.cash && snap.cash.length > 0) {
        cashEl.innerText = snap.cash.map(c => `${c.currency}: ${Number(c.amount).toFixed(2)} (折合 ${formatCurrency(c.value_base, sym)})`).join(' · ');
      } else {
        cashEl.innerText = `现金余额: ${formatCurrency(snap.cash_value, sym)}`;
      }

      currentActiveSnapshotId = snap.id || snap.timestamp || snap.date;
      document.getElementById('snapModalIdFooter').innerText = `快照唯一标识: ${currentActiveSnapshotId || 'N/A'}`;
      
      const snapDelBtn = document.getElementById('snapModalDeleteBtn');
      const delText = document.getElementById('snapModalDeleteText');
      const delIcon = document.getElementById('snapModalDeleteIcon');
      if (snapDelBtn) snapDelBtn.disabled = false;
      if (delText) delText.innerText = '移入回收站';
      if (delIcon) delIcon.innerText = '🗑️';

      document.getElementById('snapshotModal').classList.remove('hidden');
    }

    function closeSnapshotModal() {
      document.getElementById('snapshotModal').classList.add('hidden');
    }

    async function handleDeleteCurrentSnapshot() {
      if (!currentActiveSnapshotId) {
        showToast('未找到有效快照标识', 'error');
        return;
      }
      await confirmDeleteSnapshot(currentActiveSnapshotId);
    }

    async function saveStockHolding() {
      const symbol = document.getElementById('modalSymbol').value.trim();
      if (!symbol) return alert('请输入股票代码');

      let payload = { symbol };
      if (activeModalMode === 'amount') {
        const amount = parseFloat(document.getElementById('modalAmount').value);
        if (isNaN(amount) || amount <= 0) return alert('请输入有效金额');
        payload.amount = amount;
        payload.currency = document.getElementById('modalCurrency').value;
      } else {
        const shares = parseFloat(document.getElementById('modalShares').value);
        if (isNaN(shares) || shares <= 0) return alert('请输入有效持股数');
        payload.shares = shares;
        const cost = parseFloat(document.getElementById('modalCost').value);
        if (!isNaN(cost)) payload.cost_basis = cost;
      }

      try {
        const res = await fetch('/api/holding', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === 'ok') {
          closeStockModal();
          loadData();
        } else {
          alert('保存失败: ' + json.detail);
        }
      } catch (e) {
        alert('请求失败: ' + e);
      }
    }

    async function removeHolding(symbol) {
      const confirmed = await showConfirmModal({
        title: '移除股票持仓',
        message: `确定要从当前持仓列表中移除股票 ${symbol} 吗？`,
        subMessage: '移除后系统将不再追踪此股票的实时行情与估值。',
        confirmText: '确认移除',
        confirmClass: 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-500/30',
        icon: '📉'
      });
      if (!confirmed) return;
      try {
        const res = await fetch(`/api/holding/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
        const json = await res.json();
        if (json.status === 'ok') {
          loadData();
          showToast(`股票 ${symbol} 持仓已移除`, 'success');
        } else {
          showToast('移除失败: ' + (json.detail || '未知错误'), 'error');
        }
      } catch (e) {
        showToast('删除失败: ' + e, 'error');
      }
    }

    async function saveCash() {
      const gbp = parseFloat(document.getElementById('modalCashGbp').value);
      const usd = parseFloat(document.getElementById('modalCashUsd').value);
      try {
        await fetch('/api/cash', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            gbp: isNaN(gbp) ? null : gbp,
            usd: isNaN(usd) ? null : usd
          })
        });
        closeCashModal();
        loadData();
      } catch (e) {
        alert('保存现金失败: ' + e);
      }
    }

    async function recordSnapshot() {
      try {
        const res = await fetch('/api/snapshot', { method: 'POST' });
        const json = await res.json();
        if (json.status === 'ok') {
          const s = json.snapshot;
          alert(`✅ 持仓快照已成功保存！\n\n• 系统时间: ${s.system_time || s.timestamp}\n• 纽约时间备注: ${s.ny_note || '无'}\n• 组合总值: £${s.total_value}\n\n已更新下方快照历史，点击该行即可查看当时持仓明细。`);
          loadHistory();
        } else {
          alert('记录快照失败: ' + (json.detail || '未知错误'));
        }
      } catch (e) {
        alert('记录快照网络错误: ' + e);
      }
    }

    let currentManagerTab = 'snapshots';
    let trashDataCache = [];

    function openSnapshotManagerModal() {
      switchManagerTab('snapshots');
      fetchTrashData();
      renderManagerSnapshotList();
      document.getElementById('snapshotManagerModal').classList.remove('hidden');
    }

    function closeSnapshotManagerModal() {
      document.getElementById('snapshotManagerModal').classList.add('hidden');
    }

    function switchManagerTab(tab) {
      currentManagerTab = tab;
      const snapBtn = document.getElementById('tabActiveSnapshotsBtn');
      const trashBtn = document.getElementById('tabTrashBtn');
      const snapContent = document.getElementById('tabContentSnapshots');
      const trashContent = document.getElementById('tabContentTrash');

      if (tab === 'snapshots') {
        snapBtn.className = 'py-2 px-4 text-xs font-bold rounded-lg transition flex items-center gap-1.5 border-b-2 border-blue-600 text-blue-600 dark:text-blue-400 bg-blue-50/60 dark:bg-blue-950/40';
        trashBtn.className = 'py-2 px-4 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white';
        snapContent.classList.remove('hidden');
        trashContent.classList.add('hidden');
        renderManagerSnapshotList();
      } else {
        trashBtn.className = 'py-2 px-4 text-xs font-bold rounded-lg transition flex items-center gap-1.5 border-b-2 border-amber-600 text-amber-700 dark:text-amber-400 bg-amber-50/60 dark:bg-amber-950/40';
        snapBtn.className = 'py-2 px-4 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white';
        trashContent.classList.remove('hidden');
        snapContent.classList.add('hidden');
        fetchTrashData();
      }
    }

    async function fetchTrashData() {
      try {
        const res = await fetch('/api/trash');
        const json = await res.json();
        if (json.status === 'ok') {
          trashDataCache = json.trash || [];
          const countBadge = document.getElementById('tabTrashCountBadge');
          if (countBadge) countBadge.innerText = trashDataCache.length;
          renderTrashList();
        }
      } catch (e) {
        console.error("Trash fetch error:", e);
      }
    }

    function renderManagerSnapshotList() {
      const listEl = document.getElementById('mgrSnapshotList');
      const countEl = document.getElementById('mgrSnapshotCount');
      const tabBadge = document.getElementById('tabActiveCountBadge');
      if (!listEl) return;

      if (countEl) countEl.innerText = `共 ${historyDataCache.length} 条`;
      if (tabBadge) tabBadge.innerText = historyDataCache.length;
      listEl.innerHTML = '';

      if (historyDataCache.length === 0) {
        listEl.innerHTML = `
          <div class="py-8 text-center text-slate-400 text-xs bg-slate-50 dark:bg-slate-800/40 rounded-xl">
            暂无有效快照记录
          </div>
        `;
        return;
      }

      const sorted = [...historyDataCache].sort((a, b) => (b.timestamp || b.date || '').localeCompare(a.timestamp || a.date || ''));

      sorted.forEach((item, idx) => {
        const sym = item.base_currency === 'GBP' ? '£' : '$';
        const targetId = item.id || item.timestamp || item.date;
        const isLatest = idx === 0;

        const row = document.createElement('div');
        row.className = 'flex items-center justify-between p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition';

        const pnlSign = item.daily_pnl > 0 ? '+' : '';
        const pnlClass = item.daily_pnl > 0 ? 'text-emerald-600 dark:text-emerald-400' : (item.daily_pnl < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500');

        row.innerHTML = `
          <div class="flex items-center gap-2.5 min-w-0">
            <span class="text-base shrink-0">${isLatest ? '⭐' : '📄'}</span>
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-mono text-xs font-semibold text-slate-900 dark:text-white">${item.system_time || item.timestamp || item.date}</span>
                ${isLatest ? '<span class="text-[10px] px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-600 dark:bg-emerald-950/80 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 font-medium">最新</span>' : ''}
                ${item.ny_note ? `<span class="text-[10px] text-slate-400 dark:text-slate-500">(${item.ny_note})</span>` : ''}
              </div>
              <div class="text-[11px] text-slate-500 dark:text-slate-400 font-mono mt-0.5">
                总值: <strong class="text-slate-700 dark:text-slate-200">${formatCurrency(item.total_value, sym)}</strong>
                <span class="mx-1">·</span>
                单日: <span class="${pnlClass}">${pnlSign}${formatCurrency(item.daily_pnl, sym)} (${pnlSign}${Number(item.daily_pnl_pct).toFixed(2)}%)</span>
              </div>
            </div>
          </div>
          <button onclick="confirmDeleteSnapshot('${targetId}')" class="px-2.5 py-1 text-xs font-semibold rounded-lg bg-rose-50 hover:bg-rose-600 text-rose-600 hover:text-white dark:bg-rose-950/50 dark:hover:bg-rose-600 dark:text-rose-400 dark:hover:text-white border border-rose-200 dark:border-rose-900/50 transition shrink-0 ml-2 shadow-sm flex items-center gap-1">
            <span>🗑️</span> 移入回收站
          </button>
        `;
        listEl.appendChild(row);
      });
    }

    function renderTrashList() {
      const listEl = document.getElementById('mgrTrashList');
      if (!listEl) return;
      listEl.innerHTML = '';

      if (trashDataCache.length === 0) {
        listEl.innerHTML = `
          <div class="py-10 text-center text-slate-400 text-xs bg-slate-50 dark:bg-slate-800/40 rounded-xl space-y-1">
            <div class="text-2xl">📭</div>
            <div class="font-medium text-slate-600 dark:text-slate-300">回收站是空的</div>
            <div class="text-[11px] text-slate-400">所有被删除的快照会在此保留 30 天，支持一键随时还原</div>
          </div>
        `;
        return;
      }

      trashDataCache.forEach(item => {
        const snap = item.snapshot || {};
        const sym = snap.base_currency === 'GBP' ? '£' : '$';
        const row = document.createElement('div');
        row.className = 'flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition gap-2';

        const pnlSign = snap.daily_pnl > 0 ? '+' : '';
        const pnlClass = snap.daily_pnl > 0 ? 'text-emerald-600 dark:text-emerald-400' : (snap.daily_pnl < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500');

        row.innerHTML = `
          <div class="min-w-0 space-y-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-mono text-xs font-semibold text-slate-900 dark:text-white">${snap.system_time || snap.timestamp || snap.date}</span>
              <span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800 font-medium">
                ⏳ 还有 ${item.days_remaining} 天自动清除 (删除于 ${item.deleted_at})
              </span>
            </div>
            <div class="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
              当时总值: <strong class="text-slate-700 dark:text-slate-200">${formatCurrency(snap.total_value, sym)}</strong>
              <span class="mx-1">·</span>
              单日盈亏: <span class="${pnlClass}">${pnlSign}${formatCurrency(snap.daily_pnl, sym)}</span>
              ${snap.holdings_count ? `<span class="mx-1">·</span>包含 ${snap.holdings_count} 只持仓` : ''}
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0 self-end sm:self-center">
            <button onclick="restoreTrashItem('${item.trash_id}')" class="px-2.5 py-1 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-600 hover:text-white dark:bg-emerald-950/40 dark:text-emerald-300 dark:hover:bg-emerald-600 dark:hover:text-white border border-emerald-200 dark:border-emerald-800 transition flex items-center gap-1 shadow-sm">
              <span>↩️</span> 还原快照
            </button>
            <button onclick="confirmPurgeTrash('${item.trash_id}')" class="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-100 text-slate-600 hover:bg-rose-600 hover:text-white dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-rose-600 dark:hover:text-white border border-slate-200 dark:border-slate-700 transition">
              彻底删除
            </button>
          </div>
        `;
        listEl.appendChild(row);
      });
    }

    async function restoreTrashItem(trashId) {
      try {
        const res = await fetch(`/api/trash/restore/${encodeURIComponent(trashId)}`, { method: 'POST' });
        const json = await res.json();
        if (json.status === 'ok') {
          await loadHistory();
          await fetchTrashData();
          if (typeof updateStorageUI === 'function') updateStorageUI();
          showToast(json.message || '快照已成功还原至有效历史列表', 'success');
        } else {
          showToast('还原失败: ' + (json.detail || '未知错误'), 'error');
        }
      } catch (e) {
        showToast('网络错误: ' + e, 'error');
      }
    }

    async function confirmPurgeTrash(trashId) {
      const isAll = trashId === 'all';
      const confirmed = await showConfirmModal({
        title: isAll ? '清空回收站' : '彻底清除快照',
        message: isAll 
          ? '确定要清空整个回收站吗？所有快照将被永久彻底抹去，无法再还原！' 
          : '确定要彻底删除此快照吗？删除后将无法恢复。',
        subMessage: '此操作为永久物理删除，无法恢复，请谨慎操作。',
        confirmText: isAll ? '确认清空全部' : '彻底删除',
        confirmClass: 'bg-rose-700 hover:bg-rose-600 text-white shadow-rose-600/30',
        icon: '⚠️'
      });
      if (!confirmed) return;

      try {
        const url = isAll ? '/api/trash' : `/api/trash/${encodeURIComponent(trashId)}`;
        const res = await fetch(url, { method: 'DELETE' });
        const json = await res.json();
        if (json.status === 'ok') {
          await fetchTrashData();
          if (typeof updateStorageUI === 'function') updateStorageUI();
          showToast(json.message || '回收站已成功清理', 'success');
        } else {
          showToast('彻底删除失败: ' + (json.detail || '未知错误'), 'error');
        }
      } catch (e) {
        showToast('网络错误: ' + e, 'error');
      }
    }

    function setDateRangePreset(preset) {
      const today = new Date().toISOString().slice(0, 10);
      const startEl = document.getElementById('rangeStartDate');
      const endEl = document.getElementById('rangeEndDate');

      if (preset === 'all') {
        if (historyDataCache.length > 0) {
          const dates = historyDataCache.map(x => x.date).filter(Boolean).sort();
          startEl.value = dates[0] || today;
          endEl.value = dates[dates.length - 1] || today;
        } else {
          startEl.value = '';
          endEl.value = '';
        }
      } else if (preset === 'today') {
        startEl.value = today;
        endEl.value = today;
      } else if (preset === '7d') {
        const d = new Date();
        d.setDate(d.getDate() - 7);
        startEl.value = d.toISOString().slice(0, 10);
        endEl.value = today;
      } else if (preset === '30d') {
        const d = new Date();
        d.setDate(d.getDate() - 30);
        startEl.value = d.toISOString().slice(0, 10);
        endEl.value = today;
      }
    }

    async function confirmDeleteDateRange() {
      const startDate = document.getElementById('rangeStartDate').value;
      const endDate = document.getElementById('rangeEndDate').value;
      if (!startDate && !endDate) {
        showToast('请选择起始日期或结束日期', 'warn');
        return;
      }

      const label = (startDate && endDate) 
        ? `${startDate} 至 ${endDate}` 
        : (startDate ? `从 ${startDate} 起的所有快照` : `截至 ${endDate} 的所有快照`);

      const confirmed = await showConfirmModal({
        title: '按日期范围移入回收站',
        message: `确定要将【${label}】范围内的快照移入回收站吗？`,
        subMessage: '已删除快照将在回收站中保留 30 天，支持随时一键还原。',
        confirmText: '删除该范围快照',
        confirmClass: 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-500/30',
        icon: '📅'
      });
      if (!confirmed) return;

      try {
        const res = await fetch('/api/snapshots/delete-range', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ start_date: startDate || null, end_date: endDate || null })
        });
        const json = await res.json();
        if (json.status === 'ok') {
          closeSnapshotModal();
          await loadHistory();
          await fetchTrashData();
          if (typeof updateStorageUI === 'function') updateStorageUI();
          showToast(`✅ ${json.message || '选定范围快照已成功移入回收站'}`, 'success');
        } else {
          showToast('删除失败: ' + (json.detail || '未知错误'), 'error');
        }
      } catch (e) {
        showToast('网络请求失败: ' + e, 'error');
      }
    }

    async function confirmDeleteSnapshot(identifier) {
      if (!identifier) return;
      const confirmed = await showConfirmModal({
        title: '移入快照回收站',
        message: `确定要将此快照记录 (${identifier}) 移入回收站吗？`,
        subMessage: '快照将在回收站中安全保留 30 天，到期前可随时一键恢复。',
        confirmText: '移入回收站',
        confirmClass: 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-500/30',
        icon: '🗑️'
      });
      if (!confirmed) return;

      const delBtn = document.getElementById('snapModalDeleteBtn');
      const delText = document.getElementById('snapModalDeleteText');
      if (delBtn) delBtn.disabled = true;
      if (delText) delText.innerText = '移入中...';

      try {
        const res = await fetch(`/api/snapshot/${encodeURIComponent(identifier)}`, { method: 'DELETE' });
        const json = await res.json();
        if (json.status === 'ok') {
          closeSnapshotModal();
          await loadHistory();
          await fetchTrashData();
          if (typeof updateStorageUI === 'function') updateStorageUI();
          showToast(json.message || '快照已成功移入回收站 (保留30天)', 'success');
        } else {
          showToast('移入回收站失败: ' + (json.detail || '未知错误'), 'error');
        }
      } catch (e) {
        showToast('网络请求错误: ' + e, 'error');
      } finally {
        if (delBtn) delBtn.disabled = false;
        if (delText) delText.innerText = '移入回收站';
      }
    }

    // Modal dismiss listeners
    document.getElementById('snapshotModal').addEventListener('click', (e) => {
      if (e.target.id === 'snapshotModal') closeSnapshotModal();
    });
    document.getElementById('snapshotManagerModal').addEventListener('click', (e) => {
      if (e.target.id === 'snapshotManagerModal') closeSnapshotManagerModal();
    });
    document.getElementById('verifyModal').addEventListener('click', (e) => {
      if (e.target.id === 'verifyModal') closeVerifyModal();
    });
    document.getElementById('stockModal').addEventListener('click', (e) => {
      if (e.target.id === 'stockModal') closeStockModal();
    });
    document.getElementById('cashModal').addEventListener('click', (e) => {
      if (e.target.id === 'cashModal') closeCashModal();
    });
    document.getElementById('changelogModal').addEventListener('click', (e) => {
      if (e.target.id === 'changelogModal') closeChangelogModal();
    });
    document.getElementById('appConfirmModal').addEventListener('click', (e) => {
      if (e.target.id === 'appConfirmModal') closeAppConfirmModal(false);
    });
    document.getElementById('confirmModalCancelBtn').addEventListener('click', () => {
      closeAppConfirmModal(false);
    });
    document.getElementById('confirmModalActionBtn').addEventListener('click', () => {
      closeAppConfirmModal(true);
    });

    // ===== Sidebar (边栏) 交互逻辑 =====
    let isSidebarOpen = false;

    function toggleSidebar() {
      isSidebarOpen = !isSidebarOpen;
      updateSidebarUI();
    }

    function openSidebar() {
      isSidebarOpen = true;
      updateSidebarUI();
    }

    function closeSidebar() {
      isSidebarOpen = false;
      updateSidebarUI();
    }

    function updateSidebarUI() {
      const sidebar = document.getElementById('appSidebar');
      const backdrop = document.getElementById('sidebarBackdrop');
      const tooltip = document.getElementById('sidebarTooltip');
      if (!sidebar) return;

      if (isSidebarOpen) {
        sidebar.classList.remove('-translate-x-full');
        sidebar.classList.add('translate-x-0');
        if (backdrop) {
          backdrop.classList.remove('hidden');
          requestAnimationFrame(() => {
            backdrop.classList.remove('opacity-0');
            backdrop.classList.add('opacity-100');
          });
        }
        if (tooltip) tooltip.innerText = '关闭边栏';
      } else {
        sidebar.classList.remove('translate-x-0');
        sidebar.classList.add('-translate-x-full');
        if (backdrop) {
          backdrop.classList.remove('opacity-100');
          backdrop.classList.add('opacity-0');
          setTimeout(() => {
            if (!isSidebarOpen) backdrop.classList.add('hidden');
          }, 300);
        }
        if (tooltip) tooltip.innerText = '展开边栏';
      }
    }

    // ===== 更新日志 (Changelog) 数据与逻辑 =====
    const CHANGELOG_DATA = [
      {
        version: "v1.4.1",
        date: "2026-09-19",
        commit: "fix/trash",
        title: "交互体验升级：彻底修复移入回收站失效问题，引入内置交互确认弹窗与全局 Toast",
        is_latest: true,
        items: [
          { type: "fix", icon: "🐛", tag: "按钮修复", text: "彻底修复快照详情弹窗中「移入回收站」按钮在内嵌环境或特定浏览器下因 window.confirm 被静默屏蔽而点击无响应的问题" },
          { type: "feat", icon: "🛡️", tag: "内置弹窗", text: "封装 showConfirmModal 全局交互确认弹窗，采用 z-[80] backdrop-blur 高层级遮罩与双主题适配，免疫任何浏览器原生弹窗拦截" },
          { type: "feat", icon: "🔔", tag: "全局Toast", text: "引入现代化浮动 Toast 消息通知系统，快照移入回收站、还原、彻底清理等均呈现即时丝滑的状态与错误反馈" },
          { type: "arch", icon: "⚡", tag: "状态绑定", text: "重构快照详情弹窗的事件绑定机制，解绑匿名闭包，采用明确的全局活跃快照标识、加载状态指示与防重复提交保护" }
        ]
      },
      {
        version: "v1.4.0",
        date: "2026-09-19",
        commit: "feat/db",
        title: "存储架构升级：引入存储适配器模式与 SQLite 数据库支持 (兼容 Cloudflare D1)",
        is_latest: false,
        items: [
          { type: "arch", icon: "💾", tag: "存储解耦", text: "设计抽象存储适配器基类 BaseStorage，使业务计算引擎、快照归档与底层持久化彻底解耦" },
          { type: "feat", icon: "📄", tag: "保留纯JSON", text: "通过 JSONStorage 适配器 100% 完整保留原有 portfolio.json / history.json 纯文本运行模式，向下完全兼容" },
          { type: "feat", icon: "🚀", tag: "SQLite引擎", text: "新增 SQLiteStorage 适配器，零额外依赖运行于本地 portfolio.db 单文件数据库，开启 WAL 高性能并发模式" },
          { type: "cloud", icon: "☁️", tag: "Cloudflare D1", text: "数据库表结构与 SQL 100% 同构契合 Cloudflare D1，内置 REST API 适配器支持随时直连边缘云端数据库" },
          { type: "tool", icon: "🔄", tag: "双向迁移CLI", text: "提供 python main.py migrate 与 python main.py storage 指令，支持 JSON 与 SQLite 之间随时双向自由无损迁移" },
          { type: "feat", icon: "🔀", tag: "环境平滑切换", text: "支持通过 STORAGE_BACKEND 环境变量（json / sqlite / cloudflare_d1）自由无缝切换活动存储引擎" }
        ]
      },
      {
        version: "v1.3.1",
        date: "2026-09-19",
        commit: "1303df6",
        title: "卡片边界无裁切优化与 Popover 定位对齐",
        is_latest: false,
        items: [
          { type: "fix", icon: "🐛", tag: "边界修复", text: "解绑外层资产卡片的 overflow-hidden，彻底解决标题 Popover 提示向上弹出时被卡片边框切断的问题" },
          { type: "feat", icon: "📐", tag: "定位体系", text: "引入 .pop-bottom.pop-left 定位规则与专用向上指示三角，卡片及弹窗标题说明统一向下自然延展并对准图标中心" },
          { type: "ui", icon: "🎨", tag: "视觉一致", text: "卡片表头独立增设 relative z-20 堆叠层级，横向滚动表格采用 rounded-b-2xl 保持圆角美观与平滑滚动" }
        ]
      },
      {
        version: "v1.3.0",
        date: "2026-09-18",
        commit: "1c3422a",
        title: "引入信息图标 ⓘ 与精简 Popover 交互",
        is_latest: false,
        items: [
          { type: "ui", icon: "ℹ️", tag: "文案精简", text: "精简持仓明细、现金账户、历史快照、日期范围删除等超长辅助文案，以统一精致的圆形 i 图标呈现" },
          { type: "feat", icon: "👆", tag: "触控友好", text: "支持鼠标悬停（Hover）及移动端触控点击常驻，点击外部空白区域自动优雅收起" },
          { type: "ui", icon: "🌓", tag: "主题适配", text: "双配色高对比度适配：深色模式使用 #1e293b 背景与发光边框，浅色模式采用纯净白底与柔和阴影" }
        ]
      },
      {
        version: "v1.2.0",
        date: "2026-09-18",
        commit: "363fa12",
        title: "快照回收站机制与日期范围批量删除",
        is_latest: false,
        items: [
          { type: "feat", icon: "♻️", tag: "安全回收站", text: "废弃物理直接删除机制，被删快照安全转入回收站暂存，支持随时一键全量还原，杜绝误操作风险" },
          { type: "feat", icon: "⏳", tag: "30天生命周期", text: "底层集成 TTL 自动过期引擎，进入回收站超过 30 天的废弃快照由系统自动执行安全物理抹除" },
          { type: "feat", icon: "📅", tag: "范围批量删除", text: "支持任意选定起止日期的快照批量删除，并提供「全选全部、仅今天、近7天、近30天」一键预设筛选" }
        ]
      },
      {
        version: "v1.1.0",
        date: "2026-09-18",
        commit: "14d6703",
        title: "历史快照管理面板与持仓穿透透视",
        is_latest: false,
        items: [
          { type: "feat", icon: "⚙️", tag: "管理弹窗", text: "历史快照卡片头部新增「快照管理」与「记录当前快照」双入口，大幅提升资产记录管理效率" },
          { type: "feat", icon: "🔍", tag: "明细穿透", text: "点击历史记录行任意位置，即刻弹出记录时刻的完整股票代码、每股现价、持仓市值与现金详情" },
          { type: "feat", icon: "🗑️", tag: "单条管理", text: "在明细穿透弹窗底部提供快捷安全删除操作，便于迅速剔除脏数据与异常快照" }
        ]
      },
      {
        version: "v1.0.1",
        date: "2026-09-18",
        commit: "0ad63ff",
        title: "黑白双配色主题一键切换与全局适配",
        is_latest: false,
        items: [
          { type: "ui", icon: "☀️/🌙", tag: "双主题切换", text: "顶部导航栏新增纯图标切换按钮（☀️/🌙），带防误触悬浮 Tooltip 提示" },
          { type: "ui", icon: "🎨", tag: "全量适配", text: "覆盖指标卡、饼图/柱状图容器、持仓明细表、历史快照表及所有模态弹窗的双主题配色深度调优" },
          { type: "perf", icon: "⚡", tag: "无感持久化", text: "基于 localStorage 与 HTML 根节点预执行脚本，刷新页面瞬时应用主题，告别白屏刺眼闪烁" }
        ]
      },
      {
        version: "v1.0.0",
        date: "2026-09-18",
        commit: "7576f09",
        title: "股票每日涨跌统计与资产分析小助手初始发布",
        is_latest: false,
        items: [
          { type: "security", icon: "🔒", tag: "本地隐私", text: "零券商绑定、免券商密码与 API Key，纯本地配置文件 portfolio.json 计算，保障绝对资金隐私安全" },
          { type: "feat", icon: "💷", tag: "GBP基准统一", text: "多币种股票与多币种现金实时汇率折算，剥离汇率波动干扰，真实追踪股票组合内生涨跌" },
          { type: "feat", icon: "📊", tag: "双模式看板", text: "同时提供 Terminal 终端实时彩色看板与现代化 Web 交互看板 (FastAPI + Tailwind + Chart.js, Port 26212)" },
          { type: "feat", icon: "📷", tag: "自动化快照", text: "自动化收盘快照记录与纽约交易时段智能识别备注，提供历史估值追溯与双向交叉核验对账" }
        ]
      }
    ];

    function renderChangelog() {
      const container = document.getElementById('changelogTimelineContainer');
      if (!container) return;
      container.innerHTML = CHANGELOG_DATA.map((ver, idx) => `
        <div class="relative pl-6 pb-2 before:absolute before:left-2 before:top-2.5 before:bottom-0 before:w-0.5 ${idx === CHANGELOG_DATA.length - 1 ? 'before:hidden' : 'before:bg-slate-200 dark:before:bg-slate-800'}">
          <div class="absolute left-0 top-1.5 w-4 h-4 rounded-full border-2 ${ver.is_latest ? 'border-blue-500 bg-blue-500 shadow-sm shadow-blue-500/50' : 'border-slate-400 dark:border-slate-600 bg-white dark:bg-slate-900'}"></div>
          <div class="bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-2.5 shadow-xs">
            <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/60 dark:border-slate-800/80 pb-2">
              <div class="flex items-center gap-2">
                <span class="text-sm font-bold text-slate-900 dark:text-white font-mono">${ver.version}</span>
                ${ver.is_latest ? '<span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300/40 font-semibold">当前最新</span>' : ''}
                <span class="text-xs font-semibold text-slate-800 dark:text-slate-200">${ver.title}</span>
              </div>
              <div class="flex items-center gap-2 text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                <span>${ver.date}</span>
                <span>·</span>
                <span class="bg-slate-200 dark:bg-slate-700/80 px-1.5 py-0.5 rounded text-slate-700 dark:text-slate-300 font-mono">${ver.commit}</span>
              </div>
            </div>
            <ul class="space-y-1.5 text-xs text-slate-600 dark:text-slate-300">
              ${ver.items.map(item => `
                <li class="flex items-start gap-2">
                  <span class="shrink-0 mt-0.5">${item.icon}</span>
                  <div>
                    <strong class="font-semibold text-slate-900 dark:text-slate-100">[${item.tag}]</strong>
                    <span>${item.text}</span>
                  </div>
                </li>
              `).join('')}
            </ul>
          </div>
        </div>
      `).join('');
    }

    function openChangelogModal() {
      renderChangelog();
      document.getElementById('changelogModal').classList.remove('hidden');
    }

    function closeChangelogModal() {
      document.getElementById('changelogModal').classList.add('hidden');
    }

    // Popover click-outside / toggle listener for touch & desktop
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.popover-btn');
      const allContainers = document.querySelectorAll('.popover-container.active');
      if (btn) {
        const container = btn.closest('.popover-container');
        const isActive = container.classList.contains('active');
        allContainers.forEach(c => c.classList.remove('active'));
        if (!isActive) container.classList.add('active');
        e.stopPropagation();
      } else if (!e.target.closest('.popover-tooltip')) {
        allContainers.forEach(c => c.classList.remove('active'));
      }
    });

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        document.querySelectorAll('.popover-container.active').forEach(c => c.classList.remove('active'));
        if (isSidebarOpen) closeSidebar();
        closeAppConfirmModal(false);
        closeChangelogModal();
        closeSnapshotModal();
        closeSnapshotManagerModal();
        closeVerifyModal();
        closeStockModal();
        closeCashModal();
      }
    });

    async function updateStorageUI() {
      try {
        const res = await fetch('/api/storage/status');
        const json = await res.json();
        if (json.status === 'ok') {
          const stats = json.stats;
          const iconEl = document.getElementById('storageIcon');
          const nameEl = document.getElementById('storageName');
          const tipEl = document.getElementById('storageTooltip');
          if (stats.backend === 'sqlite') {
            if (iconEl) iconEl.innerText = '💾';
            if (nameEl) nameEl.innerText = 'SQLite';
            if (tipEl) tipEl.innerText = `活动存储: SQLite (${stats.db_file}) · ${stats.counts.snapshots}条快照`;
          } else if (stats.backend === 'cloudflare_d1') {
            if (iconEl) iconEl.innerText = '☁️';
            if (nameEl) nameEl.innerText = 'CF D1';
            if (tipEl) tipEl.innerText = '活动存储: Cloudflare D1 边缘云数据库';
          } else {
            if (iconEl) iconEl.innerText = '📄';
            if (nameEl) nameEl.innerText = 'JSON';
            if (tipEl) tipEl.innerText = `活动存储: 纯文本 JSON (${stats.portfolio_file}) · ${stats.counts.snapshots}条快照`;
          }
        }
      } catch (e) {
        console.warn('Storage status fetch error:', e);
      }
    }

    // Theme initialization and periodic refresh every 60s
    initTheme();
    loadData();
    updateStorageUI();
    setInterval(loadData, 60000);
    setInterval(updateStorageUI, 60000);
  </script>
</body>
</html>
"""
