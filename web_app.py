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
      top: calc(100% + 7px);
      transform: translateX(-50%) translateY(-4px);
    }
    .popover-container:hover .popover-tooltip.pop-bottom,
    .popover-container.active .popover-tooltip.pop-bottom {
      transform: translateX(-50%) translateY(0);
    }
    .popover-tooltip.pop-bottom::after {
      top: auto;
      bottom: 100%;
    }
    .dark .popover-tooltip.pop-bottom::after {
      border-color: transparent transparent #1e293b transparent;
    }
    html:not(.dark) .popover-tooltip.pop-bottom::after {
      border-color: transparent transparent #ffffff transparent;
    }

    /* Popover left alignment */
    .popover-tooltip.pop-left {
      left: 0;
      transform: translateY(4px);
    }
    .popover-container:hover .popover-tooltip.pop-left,
    .popover-container.active .popover-tooltip.pop-left {
      transform: translateY(0);
    }
    .popover-tooltip.pop-left::after {
      left: 10px;
      transform: none;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col antialiased">
  <!-- Navbar -->
  <header class="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/70 backdrop-blur sticky top-0 z-40 transition-colors">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <img src="/favicon.svg" alt="App Logo" class="w-10 h-10 rounded-xl shadow-lg shadow-blue-500/25 transition hover:scale-105" />
        <div>
          <h1 class="text-base font-bold text-slate-900 dark:text-white leading-tight">每日股票资产分析看板</h1>
          <p class="text-xs text-slate-500 dark:text-slate-400">隐私安全 · 无需券商密码 · 多币种汇率自动折算</p>
        </div>
      </div>
      <div class="flex items-center space-x-2">
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
    <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm transition-colors">
      <div class="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-1.5">
          <h2 class="text-base font-bold text-slate-900 dark:text-white">股票持仓明细 (Stock Holdings)</h2>
          <div class="popover-container">
            <button type="button" class="popover-btn" aria-label="查看说明">i</button>
            <div class="popover-tooltip pop-left">每只股票在美股/英股的实时价格、折算英镑价值及当日涨跌幅统计</div>
          </div>
        </div>
        <div class="text-xs text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800/80 px-3 py-1 rounded-lg border border-slate-200 dark:border-slate-700/50">
          共 <span id="holdingsCount" class="font-bold text-slate-900 dark:text-white">0</span> 个持仓标的
        </div>
      </div>

      <div class="overflow-x-auto">
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
    <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm transition-colors">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-1.5">
          <h2 class="text-sm font-bold text-slate-900 dark:text-white">现金账户 (Cash Balances)</h2>
          <div class="popover-container">
            <button type="button" class="popover-btn" aria-label="查看说明">i</button>
            <div class="popover-tooltip pop-left">多币种现金持有与实时外汇折算，统一以英镑 (GBP) 计价核算</div>
          </div>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="cashCards">
        <!-- populated via JS -->
      </div>
    </div>

    <!-- History Snapshots Table -->
    <div class="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm transition-colors">
      <div class="p-5 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-2">
          <h2 class="text-base font-bold text-slate-900 dark:text-white">📜 每日历史快照 (Daily Snapshots)</h2>
          <div class="popover-container">
            <button type="button" class="popover-btn" aria-label="查看说明">i</button>
            <div class="popover-tooltip pop-left">精确记录每次快照时刻的系统时间与纽约时间；点击表格中任意一行即可展开当时持仓仓位与英镑估值明细。</div>
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
      <div class="overflow-x-auto">
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
          <button id="snapModalDeleteBtn" class="py-1.5 px-3.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-600 dark:bg-rose-950/40 dark:hover:bg-rose-900/60 dark:text-rose-400 border border-rose-200 dark:border-rose-900/40 font-medium transition flex items-center gap-1 shadow-sm">
            <span>🗑️</span> 移入回收站
          </button>
          <button onclick="closeSnapshotModal()" class="py-1.5 px-5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition">关闭</button>
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
              <div class="popover-tooltip pop-bottom">支持按日期范围批量删除快照；已删除快照在回收站安全保留 30 天，支持随时一键还原。</div>
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
            <span class="popover-tooltip pop-bottom">已删除快照保留 30 天，到期系统将自动物理清除。保留期间支持一键还原。</span>
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
                <div class="popover-tooltip pop-left">选定区间内的快照将安全移入「回收站」保留 30 天，在此期间支持随时一键全量还原。</div>
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
              <div class="popover-tooltip pop-bottom">在此安全保留 30 天，到期系统将自动物理清除。保留期间支持一键还原至有效快照列表。</div>
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

  <script>
    let portfolioData = null;
    let historyDataCache = [];
    let allocChart = null;
    let pnlChart = null;
    let activeModalMode = 'amount';

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
      todayPnlPctEl.innerHTML = `涨跌幅: <span class="font-semibold">${pnlSign}${data.daily_pnl_pct.toFixed(2)}%</span> <span class="popover-container"><span class="popover-btn" title="查看计算口径">i</span><span class="popover-tooltip">以基准货币英镑 (GBP) 统一计价测算今日持仓涨跌幅度，不计汇率变动干扰。</span></span>`;

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

      document.getElementById('snapModalIdFooter').innerText = `快照唯一标识: ${snap.id || snap.timestamp || 'N/A'}`;
      const snapDelBtn = document.getElementById('snapModalDeleteBtn');
      if (snapDelBtn) {
        snapDelBtn.onclick = () => confirmDeleteSnapshot(snap.id || snap.timestamp || snap.date);
      }
      document.getElementById('snapshotModal').classList.remove('hidden');
    }

    function closeSnapshotModal() {
      document.getElementById('snapshotModal').classList.add('hidden');
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
      if (!confirm(`确定要移除股票 ${symbol} 的持仓吗？`)) return;
      try {
        await fetch(`/api/holding/${symbol}`, { method: 'DELETE' });
        loadData();
      } catch (e) {
        alert('删除失败: ' + e);
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
        } else {
          alert('还原失败: ' + (json.detail || '未知错误'));
        }
      } catch (e) {
        alert('网络错误: ' + e);
      }
    }

    async function confirmPurgeTrash(trashId) {
      const isAll = trashId === 'all';
      const promptText = isAll 
        ? '⚠️ 警告：确定要清空整个回收站吗？所有快照将被永久彻底抹去，无法再还原！' 
        : '确定要彻底删除此快照吗？删除后将无法恢复。';
      if (!confirm(promptText)) return;

      try {
        const url = isAll ? '/api/trash' : `/api/trash/${encodeURIComponent(trashId)}`;
        const res = await fetch(url, { method: 'DELETE' });
        const json = await res.json();
        if (json.status === 'ok') {
          await fetchTrashData();
        } else {
          alert('彻底删除失败: ' + (json.detail || '未知错误'));
        }
      } catch (e) {
        alert('网络错误: ' + e);
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
        alert('请选择起始日期或结束日期');
        return;
      }

      const label = (startDate && endDate) 
        ? `${startDate} 至 ${endDate}` 
        : (startDate ? `从 ${startDate} 起的所有快照` : `截至 ${endDate} 的所有快照`);

      if (!confirm(`确定要将【${label}】范围内的快照移入回收站吗？\n\n已删除快照将在回收站中保留 30 天，支持随时一键还原。`)) {
        return;
      }

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
          alert(`✅ ${json.message || '选定范围快照已成功移入回收站'}`);
        } else {
          alert('删除失败: ' + (json.detail || '未知错误'));
        }
      } catch (e) {
        alert('网络请求失败: ' + e);
      }
    }

    async function confirmDeleteSnapshot(identifier) {
      if (!identifier) return;
      if (!confirm(`确定要将此快照记录移入回收站吗？\n\n快照将在回收站中保留 30 天，到期前可随时一键恢复。`)) return;

      try {
        const res = await fetch(`/api/snapshot/${encodeURIComponent(identifier)}`, { method: 'DELETE' });
        const json = await res.json();
        if (json.status === 'ok') {
          closeSnapshotModal();
          await loadHistory();
          await fetchTrashData();
        } else {
          alert('删除失败: ' + (json.detail || '未知错误'));
        }
      } catch (e) {
        alert('网络错误: ' + e);
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
        closeSnapshotModal();
        closeSnapshotManagerModal();
        closeVerifyModal();
        closeStockModal();
        closeCashModal();
      }
    });

    // Theme initialization and periodic refresh every 60s
    initTheme();
    loadData();
    setInterval(loadData, 60000);
  </script>
</body>
</html>
"""
