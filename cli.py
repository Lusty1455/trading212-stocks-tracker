"""Rich-powered Command Line Interface for Stock Daily Tracking & Portfolio Analysis."""

from __future__ import annotations
import argparse
import sys
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box

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

import shutil

terminal_width = shutil.get_terminal_size(fallback=(100, 24)).columns
console = Console(width=max(terminal_width, 100))


def format_money(amount: float, symbol: str = "£") -> str:
    return f"{symbol}{amount:,.2f}"


def format_pnl(amount: float, pct: float, symbol: str = "£") -> Text:
    if amount > 0.0001:
        return Text(f"+{symbol}{amount:,.2f} (+{pct:,.2f}%)", style="bold green")
    elif amount < -0.0001:
        return Text(f"-{symbol}{abs(amount):,.2f} ({pct:,.2f}%)", style="bold red")
    else:
        return Text(f"{symbol}0.00 (0.00%)", style="dim")


def format_pct(pct: float) -> Text:
    if pct > 0.0001:
        return Text(f"+{pct:,.2f}%", style="bold green")
    elif pct < -0.0001:
        return Text(f"{pct:,.2f}%", style="bold red")
    else:
        return Text("0.00%", style="dim")


def cmd_status(force_refresh: bool = False) -> None:
    """Display the full portfolio status and daily statistics."""
    refresh_msg = "正在强制获取最新实时行情..." if force_refresh else "正在获取最新行情与数据..."
    with console.status(f"[bold cyan]{refresh_msg}", spinner="dots"):
        data = calculate_portfolio(force_refresh=force_refresh)

    sym = data["base_symbol"]
    tot_val = data["total_value"]
    daily_pnl = data["daily_pnl"]
    daily_pnl_pct = data["daily_pnl_pct"]
    tot_cost = data["total_invested_cost"]
    tot_ret = data["total_return"]
    tot_ret_pct = data["total_return_pct"]
    stock_val = data["stock_value"]
    cash_val = data["cash_value"]
    stock_wt = data["stock_weight_pct"]
    cash_wt = data["cash_weight_pct"]

    # Header Card
    pnl_style = "bold green" if daily_pnl > 0 else ("bold red" if daily_pnl < 0 else "dim")
    sign = "+" if daily_pnl > 0 else ""

    summary_text = (
        f"[bold white]总资产 (Total Value):[/] [bold yellow]{sym}{tot_val:,.2f}[/]   "
        f"[bold white]今日涨跌 (Today P&L):[/] [{pnl_style}]{sign}{sym}{daily_pnl:,.2f} ({sign}{daily_pnl_pct:,.2f}%)[/]\n"
        f"[dim white]股票市值:[/] {sym}{stock_val:,.2f} ({stock_wt:.1f}%)   "
        f"[dim white]可用现金:[/] {sym}{cash_val:,.2f} ({cash_wt:.1f}%)   "
        f"[dim white]累计回报:[/] {sym}{tot_ret:+,.2f} ({tot_ret_pct:+,.2f}%)"
    )

    console.print()
    console.print(
        Panel(
            summary_text,
            title=f"📊 [bold cyan]每日股票持仓与涨跌统计 ({data['base_currency']})[/]",
            subtitle=f"[dim]更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]",
            box=box.ROUNDED,
            border_style="cyan"
        )
    )

    # Stock Holdings Table (Adaptive for terminal width)
    is_narrow = console.width < 100

    table = Table(
        title="📈 股票持仓明细 (Stock Holdings)",
        box=box.ROUNDED,
        header_style="bold magenta",
        title_justify="left"
    )

    if is_narrow:
        table.add_column("标的 / 均价", style="bold cyan")
        table.add_column("市值 / 股数", justify="right")
        table.add_column("实时现价(£)", justify="right")
        table.add_column("今日盈亏", justify="right")
        table.add_column("累计回报", justify="right")

        for h in data["holdings"]:
            avg_usd = h.get("avg_price_native")
            avg_gbp = h.get("avg_price_base")
            avg_sub = ""
            if avg_gbp and avg_usd:
                avg_sub = f"\n[dim]均:£{avg_gbp:.2f}[/]\n[dim](${avg_usd:.2f})[/]"
            elif avg_gbp:
                avg_sub = f"\n[dim]均:£{avg_gbp:.2f}[/]"

            symbol_cell = f"{h['symbol']}{avg_sub}"
            share_str = f"{h['shares']:.7f}".rstrip('0').rstrip('.')
            val_base = f"{sym}{h['current_value_base']:,.2f}"
            share_and_val = f"[bold white]{val_base}[/]\n[dim]{share_str}股[/]"

            day_pnl = format_pnl(h["daily_pnl_base"], h["daily_pnl_pct"], sym)
            tot_pnl = format_pnl(h["total_pnl_base"], h["total_pnl_pct"], sym)
            stock_chg = format_pct(h["stock_change_pct"])
            
            # Pure GBP price with USD in subtitle
            native_curr_tag = "$" if h["stock_currency"] == "USD" else ""
            price_cell = f"£{h['price_base']:,.2f}\n{stock_chg}"
            if h["stock_currency"] != "GBP":
                price_cell = f"£{h['price_base']:,.2f}\n[dim]{native_curr_tag}{h['price_native']:,.2f}[/] {stock_chg}"

            table.add_row(
                symbol_cell,
                share_and_val,
                price_cell,
                day_pnl,
                tot_pnl
            )
    else:
        table.add_column("标的代码", style="bold cyan", no_wrap=True)
        table.add_column("公司名称", style="white", no_wrap=True)
        table.add_column("持股数", justify="right", no_wrap=True)
        table.add_column("现价(£)", justify="right", no_wrap=True)
        table.add_column("买入均价(£)", justify="right", no_wrap=True)
        table.add_column("当日涨跌", justify="right", no_wrap=True)
        table.add_column(f"当前市值({sym})", justify="right", style="bold white", no_wrap=True)
        table.add_column("今日盈亏", justify="right", no_wrap=True)
        table.add_column("累计回报", justify="right", no_wrap=True)
        table.add_column("仓位", justify="right", no_wrap=True)

        for h in data["holdings"]:
            val_base = f"{sym}{h['current_value_base']:,.2f}"
            day_pnl = format_pnl(h["daily_pnl_base"], h["daily_pnl_pct"], sym)
            tot_pnl = format_pnl(h["total_pnl_base"], h["total_pnl_pct"], sym)
            stock_chg = format_pct(h["stock_change_pct"])
            wt = f"{h['weight_pct']:.1f}%"
            avg_usd = h.get("avg_price_native")
            avg_gbp = h.get("avg_price_base")
            avg_str = f"£{avg_gbp:,.2f}" if avg_gbp else "--"
            if avg_gbp and avg_usd:
                avg_str = f"£{avg_gbp:,.2f} (${avg_usd:,.2f})"

            native_curr_tag = "$" if h["stock_currency"] == "USD" else ""
            price_str = f"£{h['price_base']:,.2f}"
            if h["stock_currency"] != "GBP":
                price_str = f"£{h['price_base']:,.2f} ({native_curr_tag}{h['price_native']:,.2f})"

            table.add_row(
                h["symbol"],
                h["name"][:18],
                f"{h['shares']:.7f}".rstrip('0').rstrip('.'),
                price_str,
                avg_str,
                stock_chg,
                val_base,
                day_pnl,
                tot_pnl,
                wt
            )

    console.print(table)

    # Cash Details Table
    cash_table = Table(
        title="💰 现金账户 (Cash Balances)",
        box=box.SIMPLE_HEAD,
        header_style="bold green",
        title_justify="left"
    )
    cash_table.add_column("币种", style="bold", justify="left")
    cash_table.add_column("原币金额", justify="right")
    cash_table.add_column("折算汇率", justify="right")
    cash_table.add_column(f"折合总额 ({sym})", justify="right", style="bold")

    for c in data["cash"]:
        curr = c["currency"]
        amt = c["amount"]
        fx = c["fx_rate_to_base"]
        v_base = c["value_base"]
        c_tag = "£" if curr == "GBP" else ("$" if curr == "USD" else curr)
        cash_table.add_row(
            curr,
            f"{c_tag}{amt:,.2f}",
            f"{fx:.4f}" if curr != data["base_currency"] else "1.0000",
            f"{sym}{v_base:,.2f}"
        )

    console.print(cash_table)
    console.print()


def cmd_add(args: argparse.Namespace) -> None:
    """Add or update a holding position."""
    symbol = args.symbol.upper()
    amount = args.amount
    currency = args.currency.upper()
    shares = args.shares
    cost = args.cost
    avg_usd = getattr(args, "avg_usd", None)
    avg_gbp = getattr(args, "avg_gbp", None)

    with console.status(f"[bold cyan]正在添加/更新 {symbol} 持仓...", spinner="dots"):
        add_or_update_holding(
            symbol=symbol,
            amount=amount,
            currency=currency,
            shares=shares,
            cost_basis=cost,
            cost_currency=currency,
            avg_price_usd=avg_usd,
            avg_price_gbp=avg_gbp
        )
    console.print(f"[bold green]✓ 成功更新持仓: {symbol}[/]")
    cmd_status()


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a holding."""
    symbol = args.symbol.upper()
    remove_holding(symbol)
    console.print(f"[bold yellow]✓ 已移除股票持仓: {symbol}[/]")
    cmd_status()


def cmd_cash(args: argparse.Namespace) -> None:
    """Update cash balances."""
    if args.gbp is not None:
        set_cash("GBP", args.gbp)
        console.print(f"[bold green]✓ 已设置 GBP 现金: £{args.gbp:,.2f}[/]")
    if args.usd is not None:
        set_cash("USD", args.usd)
        console.print(f"[bold green]✓ 已设置 USD 现金: ${args.usd:,.2f}[/]")
    cmd_status()


def cmd_snapshot() -> None:
    """Record current portfolio snapshot with exact system time, NY time remark, and full holdings."""
    with console.status("[bold cyan]正在记录持仓快照 (含系统时间与纽约时间)...", spinner="dots"):
        snap = record_daily_snapshot()
    curr = snap.get("base_currency", "GBP")
    sym = "£" if curr == "GBP" else "$"
    console.print(
        Panel(
            f"✅ [bold green]持仓快照已成功保存至历史记录！[/]\n\n"
            f"  • 快照标识: [cyan]{snap.get('id', 'N/A')}[/]\n"
            f"  • 系统记录时间: [bold white]{snap.get('system_time', snap.get('timestamp'))}[/]\n"
            f"  • 纽约时间备注: [bold yellow]{snap.get('ny_note', 'N/A')}[/]\n"
            f"  • 投资组合总值: [bold white]{sym}{snap['total_value']:,.2f}[/] "
            f"(股票 {sym}{snap.get('stock_value', 0.0):,.2f} + 现金 {sym}{snap.get('cash_value', 0.0):,.2f})\n"
            f"  • 当日盈亏变化: {format_pnl(snap.get('daily_pnl', 0.0), snap.get('daily_pnl_pct', 0.0), sym)}\n"
            f"  • 包含持仓数量: [bold]{snap.get('holdings_count', 0)} 只股票[/]\n\n"
            f"[dim cyan]💡 提示: 执行 'python cli.py history {snap.get('id', '1')}' 或在 Web 看板点击快照，可查看当时具体股票仓位。[/]",
            box=box.ROUNDED,
            border_style="green"
        )
    )


def cmd_snapshot_detail(target: str) -> None:
    """Display in-depth breakdown of holdings and valuation at a specific historical snapshot moment."""
    snap = get_snapshot_detail(target)
    if not snap:
        console.print(f"[bold red]❌ 未找到标识为 '{target}' 的历史快照。运行 'history' 可查看所有有效快照列表。[/]")
        return

    curr = snap.get("base_currency", "GBP")
    sym = "£" if curr == "GBP" else "$"

    sys_time = snap.get("system_time", snap.get("timestamp", snap.get("date", "未知")))
    ny_note = snap.get("ny_note", "无备注")
    status = snap.get("session_status", "历史快照")

    header_text = (
        f"📸 [bold white]历史快照持仓详情[/] [cyan]({snap.get('id', snap.get('date'))})[/]\n"
        f"  • 系统记录时间: [bold cyan]{sys_time}[/]\n"
        f"  • 纽约时间备注: [bold yellow]{ny_note}[/]\n"
        f"  • 投资组合总值: [bold white]{sym}{snap['total_value']:,.2f}[/] "
        f"(股票市值: {sym}{snap.get('stock_value', 0.0):,.2f} | 现金: {sym}{snap.get('cash_value', 0.0):,.2f})\n"
        f"  • 快照当日涨跌: {format_pnl(snap.get('daily_pnl', 0.0), snap.get('daily_pnl_pct', 0.0), sym)}"
    )
    console.print(Panel(header_text, box=box.ROUNDED, border_style="cyan"))

    holdings = snap.get("holdings", [])
    if not holdings:
        console.print(
            Panel(
                "[dim yellow]此条历史快照为早期版本记录，未包含个股持仓明细。\n"
                "后续新生成的快照均完整包含每只股票的股数、现价、买入成本与单日盈亏明细。[/]",
                box=box.ROUNDED,
                title="持仓明细"
            )
        )
    else:
        table = Table(
            title=f"📈 快照记录时刻股票仓位与估值明细 (共 {len(holdings)} 只持仓)",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        table.add_column("代码", style="bold yellow")
        table.add_column("股票名称", style="dim")
        table.add_column("快照持股数", justify="right")
        table.add_column(f"快照股价 ({sym})", justify="right")
        table.add_column(f"持仓市值 ({sym})", justify="right", style="bold")
        table.add_column("仓位占比", justify="right")
        table.add_column(f"买入成本/均价 ({sym})", justify="right")
        table.add_column("快照当日涨跌", justify="right")
        table.add_column("快照累计盈亏", justify="right")

        for h in holdings:
            daily_pnl = h.get("daily_pnl_base", 0.0)
            daily_pct = h.get("daily_pnl_pct", 0.0)
            tot_pnl = h.get("total_pnl_base", 0.0)
            tot_pct = h.get("total_pnl_pct", 0.0)

            price_str = f"{sym}{h.get('price_base', 0.0):,.2f}"
            if h.get("stock_currency") != curr and h.get("price_native"):
                price_str += f"\n[dim](${h.get('price_native'):,.2f})[/]"

            cost_str = f"{sym}{h.get('cost_basis_base', 0.0):,.2f}"
            if h.get("avg_price_base"):
                cost_str += f"\n[dim]@{sym}{h.get('avg_price_base'):,.2f}[/]"

            table.add_row(
                h["symbol"],
                h.get("name", "N/A"),
                f"{h['shares']:g}",
                price_str,
                f"{sym}{h.get('current_value_base', 0.0):,.2f}",
                f"{h.get('weight_pct', 0.0):.1f}%",
                cost_str,
                format_pnl(daily_pnl, daily_pct, sym),
                format_pnl(tot_pnl, tot_pct, sym)
            )
        console.print(table)

    # Cash breakdown
    cash_list = snap.get("cash", [])
    if cash_list:
        cash_items = [f"{c['currency']}: {c['amount']:,.2f} (折合 {sym}{c['value_base']:,.2f})" for c in cash_list]
        console.print(Panel(f"💵 [bold]记录时刻现金余额:[/] {' · '.join(cash_items)}", box=box.ROUNDED, border_style="dim"))


def cmd_history(target: Optional[str] = None) -> None:
    """Show recorded snapshots or inspect a specific snapshot if target is provided."""
    if target:
        cmd_snapshot_detail(target)
        return

    history = get_history()
    if not history:
        console.print("[dim yellow]暂无历史快照记录。运行 'snapshot' 命令即可记录今日持仓。[/]")
        return

    table = Table(
        title="📜 每日历史持仓快照 (Daily History)",
        caption="💡 提示: 运行 'python cli.py history <序号或ID>' 可深入查看该快照时刻的具体股票持仓明细",
        box=box.ROUNDED,
        header_style="bold cyan"
    )
    table.add_column("#", justify="center", style="dim")
    table.add_column("系统记录时间", style="cyan")
    table.add_column("纽约时间备注", style="yellow")
    table.add_column("总资产", justify="right", style="bold")
    table.add_column("股票市值", justify="right")
    table.add_column("现金金额", justify="right")
    table.add_column("当日涨跌额", justify="right")
    table.add_column("当日涨跌幅", justify="right")
    table.add_column("持仓只数", justify="center")

    for i, item in enumerate(history[-15:], start=1):  # show last 15
        curr = item.get("base_currency", "GBP")
        sym = "£" if curr == "GBP" else "$"
        pnl = item.get("daily_pnl", 0.0)
        pnl_pct = item.get("daily_pnl_pct", 0.0)
        pnl_text = format_pnl(pnl, pnl_pct, sym)

        sys_time_str = item.get("system_time") or item.get("timestamp") or item.get("date")
        ny_note_str = item.get("ny_note") or "—"
        holdings_cnt = str(item.get("holdings_count", len(item.get("holdings", []))))

        table.add_row(
            str(i),
            sys_time_str,
            ny_note_str,
            f"{sym}{item['total_value']:,.2f}",
            f"{sym}{item['stock_value']:,.2f}",
            f"{sym}{item['cash_value']:,.2f}",
            pnl_text,
            format_pct(pnl_pct),
            holdings_cnt
        )
    console.print(table)


def cmd_watch(args: argparse.Namespace) -> None:
    """Live watch mode, refreshing status periodically."""
    import time
    interval = args.interval if hasattr(args, "interval") and args.interval else 15
    console.print(f"[bold cyan]正在启动实时盯盘模式 (每 {interval} 秒向交易所请求最新报价)... 按 Ctrl+C 退出[/]")
    try:
        while True:
            console.clear()
            cmd_status(force_refresh=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]已退出实时盯盘模式。[/]")


def cmd_interactive() -> None:
    """Interactive wizard to update holdings or cash without memorizing arguments."""
    console.print(
        Panel("🛠️ [bold cyan]持仓与资金快速更新向导[/]\n[dim]请选择序号并回车：[/]", box=box.ROUNDED)
    )
    console.print("  [bold cyan]1.[/] 更新/添加股票 (输入代码、股数、均价)")
    console.print("  [bold cyan]2.[/] 调整现金余额 (GBP / USD)")
    console.print("  [bold cyan]3.[/] 移除股票持仓")
    console.print("  [bold cyan]4.[/] 保存今日收盘快照")
    console.print("  [bold cyan]5.[/] 退出\n")
    
    try:
        choice = input("请选择操作 (1-5): ").strip()
    except (KeyboardInterrupt, EOFError):
        return

    if choice == "1":
        symbol = input("请输入股票代码 (例如 GOOGL): ").strip().upper()
        if not symbol:
            return
        mode = input("录入方式: 1-按持股数(推荐), 2-按金额折算 [默认 1]: ").strip()
        if mode == "2":
            amt_str = input("持有金额 (£): ").strip()
            if amt_str:
                add_or_update_holding(symbol=symbol, amount=float(amt_str), currency="GBP")
        else:
            shares_str = input("精确持股数 (例如 0.0412197): ").strip()
            if not shares_str:
                return
            shares = float(shares_str)
            gbp_str = input("买入英镑均价 (£, 可回车跳过): ").strip()
            usd_str = input("买入美元均价 ($, 可回车跳过): ").strip()
            avg_gbp = float(gbp_str) if gbp_str else None
            avg_usd = float(usd_str) if usd_str else None
            add_or_update_holding(
                symbol=symbol,
                shares=shares,
                avg_price_gbp=avg_gbp,
                avg_price_usd=avg_usd
            )
        console.print(f"[bold green]✓ 成功更新持仓: {symbol}[/]")
        cmd_status()
    elif choice == "2":
        gbp_str = input("GBP 现金余额 (£, 留空不改): ").strip()
        usd_str = input("USD 现金余额 ($, 留空不改): ").strip()
        if gbp_str:
            set_cash("GBP", float(gbp_str))
        if usd_str:
            set_cash("USD", float(usd_str))
        console.print("[bold green]✓ 现金余额已更新[/]")
        cmd_status()
    elif choice == "3":
        symbol = input("请输入要移除的股票代码: ").strip().upper()
        if symbol:
            remove_holding(symbol)
            console.print(f"[bold yellow]✓ 已移除持仓: {symbol}[/]")
            cmd_status()
    elif choice == "4":
        cmd_snapshot()


def cmd_verify() -> None:
    """Run cross-verification check on all portfolio holdings and cash."""
    with console.status("[bold cyan]正在执行资产数据双向交叉验证...", spinner="dots"):
        report = verify_portfolio_integrity()

    status_style = "bold green" if report["all_passed"] else "bold yellow"
    status_text = "✓ 全部数据双向验证通过 (100% 自洽无偏差)" if report["all_passed"] else "⚠️ 存在部分数据校验偏差，请检查"

    console.print()
    console.print(Panel(f"[{status_style}]{status_text}[/]", title="🔍 [bold cyan]资产数据双向交叉验证报告 (Two-Way Verification)[/]", box=box.ROUNDED))

    for h in report["holdings_checks"]:
        t = Table(title=f"标的: {h['symbol']} (持仓 {h['shares']} 股 | 记录本金 £{h['cost_basis']:.2f})", box=box.SIMPLE_HEAD)
        t.add_column("校验项", style="bold white")
        t.add_column("结论", justify="center")
        t.add_column("详细核验信息", style="dim white")

        for c in h["checks"]:
            mark = "[bold green]通过 ✓[/]" if c["passed"] else "[bold red]异常 ✗[/]"
            t.add_row(c["name"], mark, c["msg"])
        console.print(t)

    b = report["balance_check"]
    bal_mark = "[bold green]通过 ✓[/]" if b["passed"] else "[bold red]不平 ✗[/]"
    console.print(f"[bold cyan]总资产平衡核验:[/] {bal_mark} 股票 (£{b['stock_value']:.2f}) + 现金 (£{b['cash_value']:.2f}) = 总规模 £{b['total_value']:.2f}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="股票每日涨跌统计与资产追踪小工具 (无需关联券商账户)"
    )
    parser.add_argument("-r", "--refresh", action="store_true", help="强制穿透缓存，立即向交易所请求最新实时价格")
    subparsers = parser.add_subparsers(dest="command")

    # status
    p_status = subparsers.add_parser("status", help="显示当前持仓统计与当日涨跌 (默认)")
    p_status.add_argument("-r", "--refresh", action="store_true", help="强制向交易所请求最新实时价格")

    # verify / check
    subparsers.add_parser("verify", help="双向交叉验证：核验股数、均价、本金与市值一致性")
    subparsers.add_parser("check", help="双向交叉验证：核验股数、均价、本金与市值一致性")

    # watch
    p_watch = subparsers.add_parser("watch", help="实时盯盘模式 (自动定时刷新)")
    p_watch.add_argument("--interval", type=int, default=15, help="刷新间隔秒数 (默认 15 秒)")

    # update / edit
    subparsers.add_parser("update", help="交互式向导：快速修改持仓与现金")
    subparsers.add_parser("edit", help="交互式向导：快速修改持仓与现金")

    # add
    p_add = subparsers.add_parser("add", help="添加或更新股票持仓")
    p_add.add_argument("symbol", type=str, help="股票代码，例如 GOOGL, AAPL, TSLA, SHEL.L")
    p_add.add_argument("--amount", type=float, default=None, help="持有金额，如 11.7")
    p_add.add_argument("--currency", type=str, default="GBP", help="金额币种 (GBP / USD)")
    p_add.add_argument("--shares", type=float, default=None, help="精确持股数 (例如 0.0412197)")
    p_add.add_argument("--cost", type=float, default=None, help="买入总成本 (例如 10.50)")
    p_add.add_argument("--avg-usd", type=float, default=None, help="买入美元均价 (例如 343.28)")
    p_add.add_argument("--avg-gbp", type=float, default=None, help="买入英镑均价 (例如 254.73)")

    # remove
    p_rem = subparsers.add_parser("remove", help="移除股票持仓")
    p_rem.add_argument("symbol", type=str, help="股票代码")

    # cash
    p_cash = subparsers.add_parser("cash", help="设置可用现金余额")
    p_cash.add_argument("--gbp", type=float, default=None, help="GBP 现金余额")
    p_cash.add_argument("--usd", type=float, default=None, help="USD 现金余额")

    # snapshot
    subparsers.add_parser("snapshot", help="保存今日收盘/当前市值快照至历史")

    # history
    p_hist = subparsers.add_parser("history", help="查看每日历史市值变化记录与快照持仓详情")
    p_hist.add_argument("target", nargs="?", default=None, help="快照ID、时间或序号(如 1 或 snap_xxx)，查看当时股票仓位明细")

    args = parser.parse_args()

    if args.command in ("verify", "check"):
        cmd_verify()
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "cash":
        cmd_cash(args)
    elif args.command in ("update", "edit"):
        cmd_interactive()
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "snapshot":
        cmd_snapshot()
    elif args.command == "history":
        cmd_history(args.target)
    else:
        # Default action is status
        force_ref = getattr(args, "refresh", False)
        cmd_status(force_refresh=force_ref)


if __name__ == "__main__":
    main()
