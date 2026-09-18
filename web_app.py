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
    body { font-family: 'Inter', system-ui, -apple-system, sans-serif; background-color: #0b0f19; }
  </style>
</head>
<body class="text-slate-100 min-h-screen flex flex-col antialiased">
  <!-- Navbar -->
  <header class="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-40">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <img src="/favicon.svg" alt="App Logo" class="w-10 h-10 rounded-xl shadow-lg shadow-blue-500/25 transition hover:scale-105" />
        <div>
          <h1 class="text-base font-bold text-white leading-tight">每日股票资产分析看板</h1>
          <p class="text-xs text-slate-400">隐私安全 · 无需券商密码 · 多币种汇率自动折算</p>
        </div>
      </div>
      <div class="flex items-center space-x-2">
        <!-- 双向验证 -->
        <div class="relative group">
          <button onclick="runVerification()" title="双向数据交叉核验" class="w-9 h-9 rounded-xl bg-emerald-950/60 hover:bg-emerald-900/70 text-emerald-400 border border-emerald-500/40 flex items-center justify-center text-base transition shadow-sm hover:scale-105 active:scale-95">
            🔍
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-800 text-emerald-400 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            双向数据核验
          </div>
        </div>

        <!-- 记录今日快照 -->
        <div class="relative group">
          <button onclick="recordSnapshot()" title="记录今日收盘快照" class="w-9 h-9 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center justify-center text-base transition shadow-sm hover:scale-105 active:scale-95">
            📷
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-800 text-slate-200 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            记录今日快照
          </div>
        </div>

        <!-- 调整现金 -->
        <div class="relative group">
          <button onclick="openCashModal()" title="调整可用现金余额" class="w-9 h-9 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center justify-center text-base transition shadow-sm hover:scale-105 active:scale-95">
            💰
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-800 text-slate-200 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            调整现金余额
          </div>
        </div>

        <!-- 添加/调整股票 -->
        <div class="relative group">
          <button onclick="openStockModal()" title="添加或调整股票持仓" class="w-9 h-9 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold flex items-center justify-center text-lg transition shadow-md shadow-blue-600/20 hover:scale-105 active:scale-95">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"></path></svg>
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-800 text-blue-400 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
            添加/调整股票
          </div>
        </div>

        <!-- 刷新行情 -->
        <div class="relative group">
          <button onclick="loadData(true)" title="立即强制向交易所请求最新实时行情" class="w-9 h-9 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 flex items-center justify-center transition shadow-sm hover:scale-105 active:scale-95">
            <svg class="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          </button>
          <div class="absolute -bottom-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-slate-800 text-slate-200 text-[11px] px-2.5 py-1 rounded-md shadow-xl border border-slate-700 whitespace-nowrap pointer-events-none z-50 font-medium">
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
      <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between text-xs text-slate-400 uppercase tracking-wider font-semibold">
          <span>总资产规模 (Total Value)</span>
          <span class="text-xs font-normal text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20" id="baseCurrBadge">GBP</span>
        </div>
        <div class="mt-2 text-3xl font-extrabold text-white tracking-tight" id="totalValue">--</div>
        <div class="mt-2 text-xs text-slate-400 flex items-center gap-2">
          <span>昨日收盘: <span id="prevTotalValue" class="text-slate-300">--</span></span>
        </div>
      </div>

      <!-- Today's PnL -->
      <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between text-xs text-slate-400 uppercase tracking-wider font-semibold">
          <span>今日涨跌 (Today's P&L)</span>
          <span class="text-xs font-medium" id="pnlTag">实时</span>
        </div>
        <div class="mt-2 text-3xl font-extrabold" id="todayPnl">--</div>
        <div class="mt-2 text-xs text-slate-400" id="todayPnlPct">
          --
        </div>
      </div>

      <!-- Asset Allocation -->
      <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between text-xs text-slate-400 uppercase tracking-wider font-semibold">
          <span>资产配置 (Stock vs Cash)</span>
          <span class="text-xs text-slate-500">权重比例</span>
        </div>
        <div class="mt-2 flex items-baseline gap-2">
          <span class="text-2xl font-bold text-white" id="stockWeight">--%</span>
          <span class="text-xs text-slate-400">股票 /</span>
          <span class="text-2xl font-bold text-slate-400" id="cashWeight">--%</span>
          <span class="text-xs text-slate-400">现金</span>
        </div>
        <div class="w-full bg-slate-800 h-2 rounded-full mt-3 overflow-hidden flex">
          <div id="stockBar" class="bg-blue-500 h-full transition-all duration-500" style="width: 50%"></div>
          <div id="cashBar" class="bg-emerald-500 h-full transition-all duration-500" style="width: 50%"></div>
        </div>
      </div>

      <!-- Total All-time Return -->
      <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between text-xs text-slate-400 uppercase tracking-wider font-semibold">
          <span>累计总回报 (All-Time P&L)</span>
          <span class="text-xs text-slate-500">相对本金</span>
        </div>
        <div class="mt-2 text-3xl font-extrabold" id="totalReturn">--</div>
        <div class="mt-2 text-xs text-slate-400">
          成本本金: <span id="totalCost" class="text-slate-300">--</span>
        </div>
      </div>
    </div>

    <!-- Charts & Allocation Section -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <h3 class="text-sm font-semibold text-white mb-4 flex items-center justify-between">
          <span>持仓分布 (Holdings Allocation)</span>
          <span class="text-xs text-slate-500">按折算市值</span>
        </h3>
        <div class="h-56 relative flex items-center justify-center">
          <canvas id="allocationChart"></canvas>
        </div>
      </div>

      <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-sm lg:col-span-2">
        <h3 class="text-sm font-semibold text-white mb-4 flex items-center justify-between">
          <span>各资产今日涨跌贡献 (Daily P&L by Asset)</span>
          <span class="text-xs text-slate-500" id="lastUpdated">正在获取最新行情...</span>
        </h3>
        <div class="h-56">
          <canvas id="pnlBarChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Holdings Table -->
    <div class="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
      <div class="p-5 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h2 class="text-base font-bold text-white">股票持仓明细 (Stock Holdings)</h2>
          <p class="text-xs text-slate-400 mt-0.5">每只股票在美股/英股的实时价格、折算英镑价值及当日涨跌幅统计</p>
        </div>
        <div class="text-xs text-slate-400 bg-slate-800/80 px-3 py-1 rounded-lg border border-slate-700/50">
          共 <span id="holdingsCount" class="font-bold text-white">0</span> 个持仓标的
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-slate-800/50 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
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
          <tbody id="holdingsTableBody" class="divide-y divide-slate-800/60 text-slate-200">
            <tr>
              <td colspan="11" class="py-8 text-center text-slate-500">正在载入行情数据...</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Cash Balances Section -->
    <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-sm">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-sm font-bold text-white">现金账户 (Cash Balances)</h2>
          <p class="text-xs text-slate-400 mt-0.5">多币种现金持有与实时外汇折算</p>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="cashCards">
        <!-- populated via JS -->
      </div>
    </div>

    <!-- History Snapshots Table -->
    <div class="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
      <div class="p-5 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-base font-bold text-white">📜 每日历史快照 (Daily Snapshots)</h2>
            <span class="text-[11px] px-2.5 py-0.5 rounded-full bg-cyan-950/80 text-cyan-300 border border-cyan-800/60 font-medium">精确系统小时 · 纽约时间备注 · 点击行看仓位</span>
          </div>
          <p class="text-xs text-slate-400 mt-1">精确记录每次快照时刻的系统时间与纽约时间，点击表格中任意一行即可展开当时持仓仓位与英镑估值明细</p>
        </div>
        <button onclick="recordSnapshot()" title="立即记录当前快照" class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600/80 hover:bg-blue-600 text-white text-xs font-semibold shadow-md transition hover:scale-105 active:scale-95">
          <span>📷</span> 记录当前快照
        </button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-slate-800/50 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
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
          <tbody id="historyTableBody" class="divide-y divide-slate-800/60 text-slate-300">
            <tr>
              <td colspan="8" class="py-6 text-center text-slate-500">暂无历史快照</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <!-- Stock Modal -->
  <div id="stockModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 class="font-bold text-lg text-white">添加或调整股票持仓</h3>
        <button onclick="closeStockModal()" class="text-slate-400 hover:text-white text-lg">&times;</button>
      </div>
      <div class="space-y-3 text-sm">
        <div>
          <label class="block text-xs font-semibold text-slate-400 mb-1">股票代码 (Symbol)</label>
          <input id="modalSymbol" type="text" placeholder="例如: GOOGL, AAPL, NVDA, SHEL.L" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white uppercase focus:outline-none focus:border-blue-500" />
          <p class="text-[11px] text-slate-500 mt-1">美股代码直接输 (GOOGL), 英股带.L (SHEL.L)</p>
        </div>
        
        <div>
          <label class="block text-xs font-semibold text-slate-400 mb-1">输入方式</label>
          <div class="flex gap-2">
            <button id="modeAmountBtn" onclick="setModalMode('amount')" class="flex-1 py-1.5 text-xs rounded-lg bg-blue-600 text-white font-medium">按金额 (GBP/USD)</button>
            <button id="modeSharesBtn" onclick="setModalMode('shares')" class="flex-1 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-400 hover:text-white">按具体股数</button>
          </div>
        </div>

        <div id="amountSection">
          <label class="block text-xs font-semibold text-slate-400 mb-1">持仓金额</label>
          <div class="flex gap-2">
            <input id="modalAmount" type="number" step="any" placeholder="例如: 11.7" class="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" />
            <select id="modalCurrency" class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
              <option value="GBP">GBP (£)</option>
              <option value="USD">USD ($)</option>
            </select>
          </div>
          <p class="text-[11px] text-slate-500 mt-1">系统将自动根据当前实时股价与汇率折算为精准碎股股数并设为买入成本。</p>
        </div>

        <div id="sharesSection" class="hidden space-y-3">
          <div>
            <label class="block text-xs font-semibold text-slate-400 mb-1">持股数 (Shares)</label>
            <input id="modalShares" type="number" step="any" placeholder="例如: 0.04474" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-400 mb-1">买入总成本 (可选)</label>
            <input id="modalCost" type="number" step="any" placeholder="例如: 11.7" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" />
          </div>
        </div>
      </div>
      <div class="flex gap-3 pt-2">
        <button onclick="closeStockModal()" class="flex-1 py-2 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium">取消</button>
        <button onclick="saveStockHolding()" class="flex-1 py-2 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium shadow-md shadow-blue-600/20">保存持仓</button>
      </div>
    </div>
  </div>

  <!-- Cash Modal -->
  <div id="cashModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 class="font-bold text-lg text-white">设置可用现金余额</h3>
        <button onclick="closeCashModal()" class="text-slate-400 hover:text-white text-lg">&times;</button>
      </div>
      <div class="space-y-3 text-sm">
        <div>
          <label class="block text-xs font-semibold text-slate-400 mb-1">GBP 现金 (£)</label>
          <input id="modalCashGbp" type="number" step="any" placeholder="1.0" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-400 mb-1">USD 现金 ($)</label>
          <input id="modalCashUsd" type="number" step="any" placeholder="0.0" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500" />
        </div>
      </div>
      <div class="flex gap-3 pt-2">
        <button onclick="closeCashModal()" class="flex-1 py-2 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium">取消</button>
        <button onclick="saveCash()" class="flex-1 py-2 text-xs rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-md shadow-emerald-600/20">保存现金</button>
      </div>
    </div>
  </div>

  <!-- Verify Modal -->
  <div id="verifyModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm hidden flex items-center justify-center z-50 p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <span class="text-xl">🔍</span>
          <h3 class="font-bold text-lg text-white">资产数据双向交叉验证</h3>
        </div>
        <button onclick="closeVerifyModal()" class="text-slate-400 hover:text-white text-lg">&times;</button>
      </div>
      <div id="verifyContent" class="space-y-3 text-sm max-h-[60vh] overflow-y-auto pr-1">
        正在核验数据自洽性...
      </div>
      <div class="flex justify-end pt-2 border-t border-slate-800">
        <button onclick="closeVerifyModal()" class="py-1.5 px-4 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium">关闭</button>
      </div>
    </div>
  </div>

  <!-- Snapshot Detail Modal -->
  <div id="snapshotModal" class="fixed inset-0 bg-black/75 backdrop-blur-sm hidden flex items-center justify-center z-50 p-3 sm:p-5">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-4xl w-full p-5 sm:p-6 shadow-2xl space-y-4 max-h-[92vh] flex flex-col">
      <!-- Modal Header -->
      <div class="flex items-start justify-between border-b border-slate-800 pb-3">
        <div>
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xl">📸</span>
            <h3 class="font-bold text-lg text-white" id="snapModalTitle">历史快照持仓详情</h3>
            <span id="snapModalStatusBadge" class="text-[11px] px-2.5 py-0.5 rounded-full font-semibold bg-cyan-950/80 text-cyan-300 border border-cyan-800/60"></span>
          </div>
          <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 mt-1.5" id="snapModalTimeMeta">
            <!-- Populated via JS -->
          </div>
        </div>
        <button onclick="closeSnapshotModal()" class="text-slate-400 hover:text-white text-2xl p-1 leading-none">&times;</button>
      </div>

      <!-- Modal Scrollable Content -->
      <div class="space-y-4 overflow-y-auto pr-1 flex-1">
        <!-- 4 Stat Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] text-slate-400 font-medium">快照总资产 (GBP)</div>
            <div class="text-lg font-bold text-white font-mono mt-0.5" id="snapTotalVal">-</div>
          </div>
          <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] text-slate-400 font-medium">股票市值 (GBP)</div>
            <div class="text-lg font-bold text-cyan-300 font-mono mt-0.5" id="snapStockVal">-</div>
          </div>
          <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] text-slate-400 font-medium">现金余额 (GBP)</div>
            <div class="text-lg font-bold text-slate-200 font-mono mt-0.5" id="snapCashVal">-</div>
          </div>
          <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-3">
            <div class="text-[11px] text-slate-400 font-medium">快照日涨跌</div>
            <div class="text-lg font-bold font-mono mt-0.5" id="snapDailyPnl">-</div>
          </div>
        </div>

        <!-- Holdings Breakdown Table -->
        <div class="bg-slate-800/40 border border-slate-800 rounded-xl overflow-hidden">
          <div class="px-4 py-2.5 bg-slate-800/80 border-b border-slate-800 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-sm">📈</span>
              <span class="text-xs font-bold text-white uppercase tracking-wider">记录时刻股票仓位与估值明细</span>
            </div>
            <span class="text-[11px] text-slate-400" id="snapHoldingsCount"></span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr class="text-slate-400 bg-slate-800/50 border-b border-slate-800">
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
              <tbody id="snapHoldingsTableBody" class="divide-y divide-slate-800/60 text-slate-200">
                <!-- Dynamically filled -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- Cash details -->
        <div class="bg-slate-800/30 border border-slate-800 rounded-xl p-3 text-xs flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="text-base">💵</span>
            <span class="text-slate-300 font-medium">记录时刻现金详情:</span>
            <span id="snapCashDetail" class="text-slate-300 font-mono"></span>
          </div>
          <span class="text-[11px] text-slate-500 font-mono">始终以 GBP 统一计价核算</span>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="flex items-center justify-between pt-3 border-t border-slate-800 text-xs">
        <span class="text-slate-500 font-mono" id="snapModalIdFooter"></span>
        <button onclick="closeSnapshotModal()" class="py-1.5 px-5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition">关闭</button>
      </div>
    </div>
  </div>

  <script>
    let portfolioData = null;
    let historyDataCache = [];
    let allocChart = null;
    let pnlChart = null;
    let activeModalMode = 'amount';

    function setModalMode(mode) {
      activeModalMode = mode;
      const amtBtn = document.getElementById('modeAmountBtn');
      const shrBtn = document.getElementById('modeSharesBtn');
      const amtSec = document.getElementById('amountSection');
      const shrSec = document.getElementById('sharesSection');

      if (mode === 'amount') {
        amtBtn.className = 'flex-1 py-1.5 text-xs rounded-lg bg-blue-600 text-white font-medium';
        shrBtn.className = 'flex-1 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-400 hover:text-white';
        amtSec.classList.remove('hidden');
        shrSec.classList.add('hidden');
      } else {
        shrBtn.className = 'flex-1 py-1.5 text-xs rounded-lg bg-blue-600 text-white font-medium';
        amtBtn.className = 'flex-1 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-400 hover:text-white';
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
      container.innerHTML = '<div class="text-center py-6 text-slate-400">正在执行交叉验证计算...</div>';
      try {
        const res = await fetch('/api/verify');
        const json = await res.json();
        if (json.status === 'ok') {
          const rep = json.report;
          let html = `
            <div class="p-3 rounded-xl ${rep.all_passed ? 'bg-emerald-950/40 border border-emerald-500/30 text-emerald-300' : 'bg-rose-950/40 border border-rose-500/30 text-rose-300'} flex items-center gap-2 text-xs font-semibold">
              <span>${rep.all_passed ? '✓ 全部数据双向核验通过：股数、均价、本金、现价与市值 100% 自洽无冲突！' : '⚠️ 存在部分数值偏差，请检查持仓数据！'}</span>
            </div>
          `;
          rep.holdings_checks.forEach(h => {
            html += `
              <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-3 space-y-2">
                <div class="font-bold text-white flex justify-between text-xs">
                  <span class="text-blue-400">${h.symbol}</span>
                  <span class="text-slate-400">${h.shares} 股 · 记录本金 £${h.cost_basis.toFixed(2)}</span>
                </div>
                <div class="space-y-1.5 text-xs">
            `;
            h.checks.forEach(c => {
              html += `
                <div class="flex items-start gap-2 ${c.passed ? 'text-slate-300' : 'text-rose-400 font-bold'}">
                  <span>${c.passed ? '✅' : '❌'}</span>
                  <div class="flex-1">
                    <span class="font-semibold text-white">${c.name}:</span>
                    <span class="text-slate-400 text-[11px] block">${c.msg}</span>
                  </div>
                </div>
              `;
            });
            html += `</div></div>`;
          });
          const b = rep.balance_check;
          html += `
            <div class="bg-slate-800/40 border border-slate-700/40 rounded-xl p-3 text-xs text-slate-300 flex justify-between items-center">
              <span>总资产平衡核验: 股票 (£${b.stock_value.toFixed(2)}) + 现金 (£${b.cash_value.toFixed(2)})</span>
              <span class="font-bold text-emerald-400">＝ £${b.total_value.toFixed(2)} ✓</span>
            </div>
          `;
          container.innerHTML = html;
        }
      } catch (e) {
        container.innerHTML = `<div class="text-rose-400 py-4">校验失败: ${e}</div>`;
      }
    }

    function formatCurrency(val, sym = '£') {
      return sym + Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function formatPctBadge(pct) {
      const p = Number(pct);
      const sign = p > 0 ? '+' : '';
      const color = p > 0 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : (p < 0 ? 'text-rose-400 bg-rose-500/10 border-rose-500/20' : 'text-slate-400 bg-slate-800');
      return `<span class="px-2 py-0.5 rounded text-xs font-semibold border ${color}">${sign}${p.toFixed(2)}%</span>`;
    }

    function formatPnLText(val, pct, sym = '£') {
      const v = Number(val);
      const sign = v > 0 ? '+' : '';
      const color = v > 0 ? 'text-emerald-400' : (v < 0 ? 'text-rose-400' : 'text-slate-400');
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
      todayPnlEl.className = `mt-2 text-3xl font-extrabold ${data.daily_pnl > 0 ? 'text-emerald-400' : (data.daily_pnl < 0 ? 'text-rose-400' : 'text-white')}`;
      todayPnlPctEl.innerHTML = `涨跌幅: <span class="font-semibold">${pnlSign}${data.daily_pnl_pct.toFixed(2)}%</span> (以英镑计价，不计汇率波动)`;

      // Weights
      document.getElementById('stockWeight').innerText = data.stock_weight_pct.toFixed(1) + '%';
      document.getElementById('cashWeight').innerText = data.cash_weight_pct.toFixed(1) + '%';
      document.getElementById('stockBar').style.width = `${data.stock_weight_pct}%`;
      document.getElementById('cashBar').style.width = `${data.cash_weight_pct}%`;

      // Total Return
      const retEl = document.getElementById('totalReturn');
      const retSign = data.total_return > 0 ? '+' : '';
      retEl.innerText = `${retSign}${formatCurrency(data.total_return, sym)}`;
      retEl.className = `mt-2 text-3xl font-extrabold ${data.total_return > 0 ? 'text-emerald-400' : (data.total_return < 0 ? 'text-rose-400' : 'text-white')}`;
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
          row.className = 'hover:bg-slate-800/40 transition group';
          const nativeSym = h.stock_currency === 'USD' ? '$' : (h.stock_currency + ' ');
          const sharesStr = Number(h.shares).toFixed(7).replace(/\\.?0+$/, '');
          const avgPriceGbp = h.avg_price_base ? formatCurrency(h.avg_price_base, sym) : '--';
          const avgPriceSub = h.avg_price_native ? `<div class="text-[11px] text-slate-500">$${h.avg_price_native.toFixed(2)}</div>` : '';
          const currentPriceNativeSub = h.stock_currency !== 'GBP' ? `<div class="text-[11px] text-slate-500">${nativeSym}${h.price_native.toFixed(2)}</div>` : '';

          row.innerHTML = `
            <td class="py-3 px-4">
              <div class="font-bold text-white flex items-center gap-2">
                <span class="text-blue-400">${h.symbol}</span>
                <span class="text-xs font-normal text-slate-400 truncate max-w-[120px]">${h.name}</span>
              </div>
              <div class="text-[11px] text-slate-500">${h.exchange || ''} · ${h.stock_currency}</div>
            </td>
            <td class="py-3 px-4 text-right font-mono text-slate-300">${sharesStr}</td>
            <td class="py-3 px-4 text-right font-mono text-slate-300">
              <div>${formatCurrency(h.price_base, sym)}</div>
              ${currentPriceNativeSub}
            </td>
            <td class="py-3 px-4 text-right font-mono text-slate-300">
              <div>${avgPriceGbp}</div>
              ${avgPriceSub}
            </td>
            <td class="py-3 px-4 text-right">${formatPctBadge(h.stock_change_pct)}</td>
            <td class="py-3 px-4 text-right font-mono font-bold text-white">${formatCurrency(h.current_value_base, sym)}</td>
            <td class="py-3 px-4 text-right">${formatPnLText(h.daily_pnl_base, h.daily_pnl_pct, sym)}</td>
            <td class="py-3 px-4 text-right">${formatPnLText(h.total_pnl_base, h.total_pnl_pct, sym)}</td>
            <td class="py-3 px-4 text-right font-mono text-slate-400">${h.weight_pct.toFixed(1)}%</td>
            <td class="py-3 px-4 text-center">
              <button onclick="removeHolding('${h.symbol}')" title="删除持仓" class="text-slate-500 hover:text-rose-400 p-1 rounded transition opacity-0 group-hover:opacity-100">
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
        card.className = 'bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 flex items-center justify-between';
        const cSym = c.currency === 'GBP' ? '£' : (c.currency === 'USD' ? '$' : c.currency + ' ');
        card.innerHTML = `
          <div>
            <div class="text-xs text-slate-400 font-semibold">${c.currency} 可用现金</div>
            <div class="text-xl font-bold text-white mt-1">${formatCurrency(c.amount, cSym)}</div>
            <div class="text-xs text-slate-500 mt-0.5">折合: ${formatCurrency(c.value_base, sym)}</div>
          </div>
          <div class="text-2xl opacity-70">${c.currency === 'GBP' ? '💷' : '💵'}</div>
        `;
        cashContainer.appendChild(card);
      });

      renderCharts(data);
    }

    function renderCharts(data) {
      const sym = data.base_symbol;

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
            legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 12, font: { size: 11 } } }
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
            x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
            y: { grid: { color: '#1e293b' }, ticks: { color: '#94a3b8' } }
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
        tr.className = 'hover:bg-slate-800/60 cursor-pointer transition text-sm group';
        const targetId = item.id || item.timestamp || item.date;
        tr.onclick = () => openSnapshotModal(targetId);

        const sym = item.base_currency === 'GBP' ? '£' : '$';
        const sysTime = item.system_time || item.timestamp || item.date;
        const nyNote = item.ny_note;

        let nyBadge = '<span class="text-slate-500 text-xs">—</span>';
        if (nyNote) {
          nyBadge = `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60 shadow-sm">
            <span>🗽</span> <span>${nyNote}</span>
          </span>`;
        }

        tr.innerHTML = `
          <td class="py-3.5 px-4 font-mono">
            <div class="text-white font-semibold flex items-center gap-1.5">
              <span class="text-cyan-400">🕒</span>
              <span class="text-slate-200">${sysTime}</span>
            </div>
          </td>
          <td class="py-3.5 px-4">
            ${nyBadge}
          </td>
          <td class="py-3.5 px-4 text-right font-mono font-bold text-white">${formatCurrency(item.total_value, sym)}</td>
          <td class="py-3.5 px-4 text-right font-mono text-cyan-300 font-semibold">${formatCurrency(item.stock_value, sym)}</td>
          <td class="py-3.5 px-4 text-right font-mono text-slate-300">${formatCurrency(item.cash_value, sym)}</td>
          <td class="py-3.5 px-4 text-right font-mono">${formatPnLText(item.daily_pnl, item.daily_pnl_pct, sym)}</td>
          <td class="py-3.5 px-4 text-right">${formatPctBadge(item.daily_pnl_pct)}</td>
          <td class="py-3.5 px-4 text-center">
            <button onclick="event.stopPropagation(); openSnapshotModal('${targetId}')" class="px-2.5 py-1 text-xs font-semibold rounded-lg bg-blue-600/20 text-blue-400 group-hover:bg-blue-600 group-hover:text-white transition flex items-center gap-1 mx-auto shadow-sm">
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
        <span class="flex items-center gap-1.5 text-cyan-300">
          <span>🕒 系统时间:</span> <strong class="font-mono text-white">${snap.system_time || snap.timestamp}</strong>
        </span>
        <span class="text-slate-600">|</span>
        <span class="flex items-center gap-1.5 text-amber-300">
          <span>🗽 纽约时间备注:</span> <strong class="font-mono text-amber-200">${snap.ny_note || snap.ny_time || '无备注'}</strong>
        </span>
      `;

      // 4 Stat Cards
      document.getElementById('snapTotalVal').innerText = formatCurrency(snap.total_value, sym);
      document.getElementById('snapStockVal').innerText = formatCurrency(snap.stock_value, sym);
      document.getElementById('snapCashVal').innerText = formatCurrency(snap.cash_value, sym);

      const pnlEl = document.getElementById('snapDailyPnl');
      const pnlSign = snap.daily_pnl > 0 ? '+' : '';
      pnlEl.innerText = `${pnlSign}${formatCurrency(snap.daily_pnl, sym)} (${pnlSign}${Number(snap.daily_pnl_pct).toFixed(2)}%)`;
      pnlEl.className = `text-lg font-bold font-mono mt-0.5 ${snap.daily_pnl > 0 ? 'text-emerald-400' : (snap.daily_pnl < 0 ? 'text-rose-400' : 'text-white')}`;

      // Holdings table
      const tbody = document.getElementById('snapHoldingsTableBody');
      tbody.innerHTML = '';

      const holdings = snap.holdings || [];
      document.getElementById('snapHoldingsCount').innerText = `共 ${holdings.length} 只股票持仓`;

      if (holdings.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="8" class="py-8 px-4 text-center text-slate-400 bg-slate-900/40">
              <div class="max-w-md mx-auto space-y-1.5">
                <p class="font-semibold text-amber-300 text-sm">ℹ️ 此快照为早期记录（未包含个股持仓明细）</p>
                <p class="text-xs text-slate-400 leading-relaxed">系统已升级快照引擎，后续记录的每一次快照均会自动永久记录个股精确股数、英镑估值、买入成本与单日盈亏明细。</p>
              </div>
            </td>
          </tr>
        `;
      } else {
        holdings.forEach(h => {
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-slate-800/60 transition';

          let priceStr = formatCurrency(h.price_base, sym);
          if (h.stock_currency && h.stock_currency !== snap.base_currency && h.price_native) {
            priceStr += `<div class="text-[10px] text-slate-500 font-mono">($${Number(h.price_native).toFixed(2)})</div>`;
          }

          let costStr = formatCurrency(h.cost_basis_base, sym);
          if (h.avg_price_base) {
            costStr += `<div class="text-[10px] text-slate-500 font-mono">@${formatCurrency(h.avg_price_base, sym)}</div>`;
          }

          const dailyPnlSign = h.daily_pnl_base > 0 ? '+' : '';
          const dailyClass = h.daily_pnl_base > 0 ? 'text-emerald-400' : (h.daily_pnl_base < 0 ? 'text-rose-400' : 'text-slate-400');

          const totPnlSign = h.total_pnl_base > 0 ? '+' : '';
          const totClass = h.total_pnl_base > 0 ? 'text-emerald-400' : (h.total_pnl_base < 0 ? 'text-rose-400' : 'text-slate-400');

          tr.innerHTML = `
            <td class="py-3 px-3">
              <div class="font-bold text-white font-mono text-sm">${h.symbol}</div>
              <div class="text-[11px] text-slate-400 truncate max-w-[150px]">${h.name || ''}</div>
            </td>
            <td class="py-3 px-3 font-mono text-cyan-300 font-semibold text-sm">${h.shares}</td>
            <td class="py-3 px-3 text-right font-mono text-slate-200">${priceStr}</td>
            <td class="py-3 px-3 text-right font-mono font-bold text-white text-sm">${formatCurrency(h.current_value_base, sym)}</td>
            <td class="py-3 px-3 text-right font-mono text-slate-300">${h.weight_pct}%</td>
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

    // Modal dismiss listeners
    document.getElementById('snapshotModal').addEventListener('click', (e) => {
      if (e.target.id === 'snapshotModal') closeSnapshotModal();
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

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeSnapshotModal();
        closeVerifyModal();
        closeStockModal();
        closeCashModal();
      }
    });

    // Initial load and periodic refresh every 60s
    loadData();
    setInterval(loadData, 60000);
  </script>
</body>
</html>
"""
