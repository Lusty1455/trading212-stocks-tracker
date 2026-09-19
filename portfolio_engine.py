"""Portfolio calculations engine for multi-currency stock tracking without account credentials."""

from __future__ import annotations
import json
import os
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from market_data import get_stock_quote, get_fx_rate

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")


def get_default_portfolio() -> Dict[str, Any]:
    """Default initial portfolio as described by user: 1 GBP cash + 11.7 GBP of GOOGL."""
    return {
        "base_currency": "GBP",
        "cash": {
            "GBP": 1.0,
            "USD": 0.0
        },
        "holdings": [
            {
                "symbol": "GOOGL",
                "name": "Alphabet Inc. (Class A)",
                # Will be calculated if shares is None or 0
                "shares": None,
                "initial_amount": 11.7,
                "initial_currency": "GBP",
                "cost_basis": 11.7,
                "cost_currency": "GBP",
                "added_at": datetime.now().strftime("%Y-%m-%d")
            }
        ]
    }


def load_portfolio() -> Dict[str, Any]:
    """Load portfolio from portfolio.json, or initialize default if not present."""
    if not os.path.exists(PORTFOLIO_FILE):
        data = get_default_portfolio()
        save_portfolio(data)
        return data
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        data = get_default_portfolio()
        save_portfolio(data)
        return data


def save_portfolio(data: Dict[str, Any]) -> None:
    """Save portfolio data atomically to portfolio.json."""
    tmp_file = f"{PORTFOLIO_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, PORTFOLIO_FILE)


def add_or_update_holding(
    symbol: str,
    amount: Optional[float] = None,
    currency: str = "GBP",
    shares: Optional[float] = None,
    cost_basis: Optional[float] = None,
    cost_currency: str = "GBP",
    avg_price_usd: Optional[float] = None,
    avg_price_gbp: Optional[float] = None
) -> Dict[str, Any]:
    """
    Add or update a holding.
    If amount is given (e.g. 10.5 GBP), calculates shares using current market price and FX.
    Supports exact shares + average purchase prices.
    """
    symbol = symbol.strip().upper()
    quote = get_stock_quote(symbol)
    stock_curr = quote["currency"]
    portfolio = load_portfolio()
    base_curr = portfolio.get("base_currency", "GBP")

    if shares is None or shares <= 0:
        if amount is None or amount <= 0:
            raise ValueError("Must specify either shares or monetary amount")
        fx = get_fx_rate(currency, stock_curr)["rate"]
        amount_in_stock_curr = amount * fx
        if quote["price"] <= 0:
            raise ValueError(f"Could not fetch valid price for {symbol}")
        calculated_shares = amount_in_stock_curr / quote["price"]
        actual_shares = round(calculated_shares, 7)
        effective_cost = amount if cost_basis is None else cost_basis
        effective_cost_curr = currency if cost_basis is None else cost_currency
    else:
        actual_shares = round(shares, 7)
        if cost_basis is not None:
            effective_cost = cost_basis
            effective_cost_curr = cost_currency
        elif avg_price_gbp is not None:
            effective_cost = round(actual_shares * avg_price_gbp, 2)
            effective_cost_curr = "GBP"
        elif avg_price_usd is not None:
            fx_usd_to_base = get_fx_rate("USD", base_curr)["rate"]
            effective_cost = round(actual_shares * avg_price_usd * fx_usd_to_base, 2)
            effective_cost_curr = base_curr
        else:
            effective_cost = 0.0
            effective_cost_curr = cost_currency

    # Update or append in holdings
    holdings = portfolio.get("holdings", [])
    found = False
    for h in holdings:
        if h["symbol"].upper() == symbol:
            h["shares"] = actual_shares
            h["name"] = quote.get("name") or symbol
            h["cost_basis"] = effective_cost
            h["cost_currency"] = effective_cost_curr
            if avg_price_usd is not None:
                h["average_price_usd"] = avg_price_usd
            if avg_price_gbp is not None:
                h["average_price_gbp"] = avg_price_gbp
            found = True
            break

    if not found:
        entry = {
            "symbol": symbol,
            "name": quote.get("name") or symbol,
            "shares": actual_shares,
            "cost_basis": effective_cost,
            "cost_currency": effective_cost_curr,
            "added_at": datetime.now().strftime("%Y-%m-%d")
        }
        if avg_price_usd is not None:
            entry["average_price_usd"] = avg_price_usd
        if avg_price_gbp is not None:
            entry["average_price_gbp"] = avg_price_gbp
        holdings.append(entry)

    portfolio["holdings"] = holdings
    save_portfolio(portfolio)
    return portfolio


def remove_holding(symbol: str) -> Dict[str, Any]:
    """Remove a holding by symbol."""
    symbol = symbol.strip().upper()
    portfolio = load_portfolio()
    holdings = [h for h in portfolio.get("holdings", []) if h["symbol"].upper() != symbol]
    portfolio["holdings"] = holdings
    save_portfolio(portfolio)
    return portfolio


def set_cash(currency: str, amount: float) -> Dict[str, Any]:
    """Set cash balance for given currency."""
    portfolio = load_portfolio()
    cash = portfolio.get("cash", {})
    cash[currency.upper()] = round(float(amount), 2)
    portfolio["cash"] = cash
    save_portfolio(portfolio)
    return portfolio


def calculate_portfolio(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Run full financial calculations for the portfolio:
    - Real-time stock quotes
    - FX conversions to base currency (both current and yesterday's close)
    - Daily Gain/Loss (£ and %)
    - Total Return (£ and %)
    - Allocation breakdown
    """
    portfolio = load_portfolio()
    base_curr = portfolio.get("base_currency", "GBP").upper()
    holdings_raw = portfolio.get("holdings", [])
    cash_raw = portfolio.get("cash", {})

    holdings_calc: List[Dict[str, Any]] = []
    total_stock_value = 0.0
    prev_stock_value = 0.0
    total_stock_cost = 0.0

    needs_save = False

    for item in holdings_raw:
        symbol = item["symbol"].upper()
        quote = get_stock_quote(symbol, force_refresh=force_refresh)
        stock_curr = quote["currency"]
        
        # If shares was not computed yet (e.g. initial setup with initial_amount)
        shares = item.get("shares")
        if shares is None:
            initial_amt = item.get("initial_amount", 0.0)
            initial_curr = item.get("initial_currency", "GBP")
            fx_to_stock = get_fx_rate(initial_curr, stock_curr, force_refresh=force_refresh)["rate"]
            amt_in_stock_curr = initial_amt * fx_to_stock
            shares = round(amt_in_stock_curr / quote["price"], 6) if quote["price"] > 0 else 0.0
            item["shares"] = shares
            needs_save = True

        # Exchange rate from stock_curr to base_curr (fixed at current rate, ignoring FX fluctuation)
        fx_info = get_fx_rate(stock_curr, base_curr, force_refresh=force_refresh)
        fx_current = fx_info["rate"]

        # Current & Prev stock price in Base Currency (GBP)
        price_native = quote["price"]
        prev_price_native = quote["prev_close"]
        stock_change_pct = quote["change_pct"]

        price_base = price_native * fx_current
        prev_price_base = prev_price_native * fx_current

        # Valuation in GBP
        curr_val_base = shares * price_base
        prev_val_base = shares * prev_price_base

        # Daily Gain/Loss for this holding in GBP (driven purely by stock price change, ignoring FX)
        daily_pnl = curr_val_base - prev_val_base
        daily_pnl_pct = stock_change_pct

        # Cost basis in GBP
        cost_basis = float(item.get("cost_basis", 0.0))
        cost_curr = item.get("cost_currency", base_curr).upper()
        fx_cost = get_fx_rate(cost_curr, base_curr)["rate"] if cost_curr != base_curr else 1.0
        cost_basis_base = cost_basis * fx_cost

        total_pnl = curr_val_base - cost_basis_base if cost_basis_base > 0 else 0.0
        total_pnl_pct = ((total_pnl / cost_basis_base) * 100) if cost_basis_base > 0 else 0.0

        # Average buy price (cost per share in GBP and native currency)
        avg_price_base = item.get("average_price_gbp") or ((cost_basis_base / shares) if (shares and shares > 0 and cost_basis_base > 0) else None)
        avg_price_native = item.get("average_price_usd") or ((cost_basis / shares) if (shares and shares > 0 and cost_basis > 0) else None)

        holding_res = {
            "symbol": symbol,
            "name": quote.get("name") or item.get("name") or symbol,
            "shares": shares,
            "stock_currency": stock_curr,
            "price_native": price_native,
            "prev_price_native": prev_price_native,
            "avg_price_native": avg_price_native,
            "avg_price_base": avg_price_base,
            "stock_change_pct": stock_change_pct,
            "fx_rate_to_base": fx_current,
            "price_base": price_base,
            "prev_price_base": prev_price_base,
            "current_value_base": curr_val_base,
            "prev_value_base": prev_val_base,
            "daily_pnl_base": daily_pnl,
            "daily_pnl_pct": daily_pnl_pct,
            "cost_basis_base": cost_basis_base,
            "total_pnl_base": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "exchange": quote.get("exchange", "")
        }
        holdings_calc.append(holding_res)

        total_stock_value += curr_val_base
        prev_stock_value += prev_val_base
        total_stock_cost += cost_basis_base

    if needs_save:
        save_portfolio(portfolio)

    # Cash calculations (all converted to GBP at current rate, 0 daily FX fluctuation)
    cash_calc: List[Dict[str, Any]] = []
    total_cash_base = 0.0

    for c_curr, c_amt in cash_raw.items():
        c_amt = float(c_amt)
        fx_info = get_fx_rate(c_curr, base_curr)
        c_val_current = c_amt * fx_info["rate"]
        cash_calc.append({
            "currency": c_curr,
            "amount": c_amt,
            "fx_rate_to_base": fx_info["rate"],
            "value_base": c_val_current,
            "daily_pnl_base": 0.0
        })
        total_cash_base += c_val_current

    prev_cash_base = total_cash_base

    # Overall Portfolio Summary
    total_portfolio_value = total_stock_value + total_cash_base
    prev_portfolio_value = prev_stock_value + prev_cash_base
    daily_pnl_total = total_portfolio_value - prev_portfolio_value
    daily_pnl_total_pct = (
        (daily_pnl_total / prev_portfolio_value) * 100
    ) if prev_portfolio_value > 0 else 0.0

    total_invested_cost = total_stock_cost + total_cash_base
    total_return_amount = total_portfolio_value - total_invested_cost
    total_return_pct = (
        (total_return_amount / total_invested_cost) * 100
    ) if total_invested_cost > 0 else 0.0

    # Weights
    for h in holdings_calc:
        h["weight_pct"] = (
            (h["current_value_base"] / total_portfolio_value) * 100
        ) if total_portfolio_value > 0 else 0.0

    stock_weight_pct = (
        (total_stock_value / total_portfolio_value) * 100
    ) if total_portfolio_value > 0 else 0.0
    cash_weight_pct = (
        (total_cash_base / total_portfolio_value) * 100
    ) if total_portfolio_value > 0 else 0.0

    # Currency symbol
    curr_symbols = {"GBP": "£", "USD": "$", "EUR": "€", "CNY": "¥", "JPY": "¥"}
    base_symbol = curr_symbols.get(base_curr, base_curr + " ")

    return {
        "timestamp": datetime.now().isoformat(),
        "base_currency": base_curr,
        "base_symbol": base_symbol,
        "total_value": total_portfolio_value,
        "prev_total_value": prev_portfolio_value,
        "daily_pnl": daily_pnl_total,
        "daily_pnl_pct": daily_pnl_total_pct,
        "total_invested_cost": total_invested_cost,
        "total_return": total_return_amount,
        "total_return_pct": total_return_pct,
        "stock_value": total_stock_value,
        "stock_weight_pct": stock_weight_pct,
        "cash_value": total_cash_base,
        "cash_weight_pct": cash_weight_pct,
        "holdings": holdings_calc,
        "cash": cash_calc
    }


def get_ny_time_info() -> Dict[str, str]:
    """Calculate system local time and New York time with market session status."""
    from zoneinfo import ZoneInfo
    now_local = datetime.now().astimezone()
    ny_tz = ZoneInfo("America/New_York")
    now_ny = datetime.now(ny_tz)

    sys_time_str = now_local.strftime("%Y-%m-%d %H:%M:%S")
    sys_hour_str = now_local.strftime("%H:%M")
    sys_tz_name = now_local.strftime("%Z") or "Local"

    ny_time_str = now_ny.strftime("%Y-%m-%d %H:%M:%S")
    ny_hour_str = now_ny.strftime("%H:%M")
    ny_tz_name = now_ny.strftime("%Z") or "EDT"

    # Regular trading hours: 09:30 - 16:00 Mon-Fri (New York time)
    weekday = now_ny.weekday()
    minute_of_day = now_ny.hour * 60 + now_ny.minute
    market_open_min = 9 * 60 + 30
    market_close_min = 16 * 60

    if weekday >= 5:
        session_status = "周末休市"
    elif minute_of_day < market_open_min:
        session_status = "美股盘前"
    elif minute_of_day <= market_close_min:
        session_status = "盘中交易"
    else:
        session_status = "已收盘/盘后"

    ny_note = f"纽约时间 {ny_hour_str} {ny_tz_name} ({session_status})"
    return {
        "system_time": f"{sys_time_str} {sys_tz_name}",
        "system_hour": sys_hour_str,
        "ny_time": f"{ny_time_str} {ny_tz_name}",
        "ny_hour": ny_hour_str,
        "ny_note": ny_note,
        "session_status": session_status
    }


def record_daily_snapshot() -> Dict[str, Any]:
    """Record current portfolio metrics with exact system time, NY time note, and full holdings details."""
    calc = calculate_portfolio(force_refresh=True)
    time_info = get_ny_time_info()
    today_str = date.today().isoformat()
    now_dt = datetime.now()
    snap_id = f"snap_{now_dt.strftime('%Y%m%d_%H%M%S')}"

    # Detailed holdings at this snapshot moment
    holdings_snapshot = []
    for h in calc["holdings"]:
        holdings_snapshot.append({
            "symbol": h["symbol"],
            "name": h["name"],
            "shares": h["shares"],
            "stock_currency": h["stock_currency"],
            "price_base": round(h["price_base"], 2),
            "price_native": round(h["price_native"], 2),
            "current_value_base": round(h["current_value_base"], 2),
            "daily_pnl_base": round(h["daily_pnl_base"], 2),
            "daily_pnl_pct": round(h["daily_pnl_pct"], 2),
            "cost_basis_base": round(h["cost_basis_base"], 2),
            "total_pnl_base": round(h["total_pnl_base"], 2),
            "total_pnl_pct": round(h["total_pnl_pct"], 2),
            "weight_pct": round(h["weight_pct"], 1),
            "avg_price_base": round(h["avg_price_base"], 2) if h.get("avg_price_base") else None,
            "avg_price_native": round(h["avg_price_native"], 2) if h.get("avg_price_native") else None
        })

    cash_snapshot = []
    for c in calc["cash"]:
        cash_snapshot.append({
            "currency": c["currency"],
            "amount": c["amount"],
            "value_base": round(c["value_base"], 2)
        })

    snapshot = {
        "id": snap_id,
        "date": today_str,
        "timestamp": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "system_time": time_info["system_time"],
        "system_hour": time_info["system_hour"],
        "ny_time": time_info["ny_time"],
        "ny_hour": time_info["ny_hour"],
        "ny_note": time_info["ny_note"],
        "session_status": time_info["session_status"],
        "base_currency": calc["base_currency"],
        "total_value": round(calc["total_value"], 2),
        "stock_value": round(calc["stock_value"], 2),
        "cash_value": round(calc["cash_value"], 2),
        "daily_pnl": round(calc["daily_pnl"], 2),
        "daily_pnl_pct": round(calc["daily_pnl_pct"], 2),
        "holdings_count": len(calc["holdings"]),
        "holdings": holdings_snapshot,
        "cash": cash_snapshot
    }

    history: List[Dict[str, Any]] = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    # If recorded within last 3 minutes, update last entry to avoid rapid spam, otherwise append
    replaced = False
    if history:
        last = history[-1]
        try:
            last_ts = datetime.strptime(last.get("timestamp", ""), "%Y-%m-%d %H:%M:%S")
            if abs((now_dt - last_ts).total_seconds()) < 180:
                history[-1] = snapshot
                replaced = True
        except Exception:
            pass

    if not replaced:
        history.append(snapshot)

    # Sort by timestamp
    history.sort(key=lambda x: x.get("timestamp", x.get("date", "")))

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    return snapshot


def get_history() -> List[Dict[str, Any]]:
    """Load historical snapshots."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def get_snapshot_detail(identifier: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve snapshot details by ID, timestamp, date, or index (1-based from newest or 0-based).
    """
    history = get_history()
    if not history:
        return None

    # Check by id, timestamp, or date
    for item in reversed(history):
        if (
            item.get("id") == identifier
            or item.get("timestamp") == identifier
            or item.get("date") == identifier
        ):
            return item

    # Check by integer index if provided (support 1-based from table or 0-based)
    try:
        num = int(identifier)
        if 1 <= num <= len(history):
            return history[num - 1]
        elif 0 <= num < len(history):
            return history[num]
        elif -len(history) <= num < 0:
            return history[num]
    except ValueError:
        pass

    return None


def delete_snapshot(identifier: str) -> bool:
    """
    Delete a snapshot by ID, timestamp, date, or index (or 'latest').
    Saves the updated history atomically to history.json.
    """
    history = get_history()
    if not history:
        return False

    target_idx = None
    if identifier == "latest":
        target_idx = len(history) - 1
    else:
        for i, item in enumerate(history):
            if (
                item.get("id") == identifier
                or item.get("timestamp") == identifier
                or item.get("date") == identifier
            ):
                target_idx = i
                break
        if target_idx is None:
            try:
                num = int(identifier)
                if 1 <= num <= len(history):
                    target_idx = num - 1
                elif 0 <= num < len(history):
                    target_idx = num
                elif -len(history) <= num < 0:
                    target_idx = len(history) + num
            except ValueError:
                pass

    if target_idx is not None and 0 <= target_idx < len(history):
        history.pop(target_idx)
        tmp_file = f"{HISTORY_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, HISTORY_FILE)
        return True

    return False


def clear_all_snapshots() -> bool:
    """Clear all historical snapshots."""
    tmp_file = f"{HISTORY_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump([], f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, HISTORY_FILE)
    return True


def verify_portfolio_integrity() -> Dict[str, Any]:
    """
    Run bidirectional cross-verification on all holdings and cash:
    1. Check: Shares * Avg Price GBP == Cost Basis (GBP)
    2. Check: Shares * Current Price GBP == Market Value
    3. Check: Market Value - Cost Basis == Unrealized Return
    4. Check: Stock Value + Cash == Total Portfolio Value
    Returns detailed audit report with status, passed checks, and any warning discrepancies.
    """
    data = calculate_portfolio()
    results = []
    all_passed = True

    for h in data["holdings"]:
        sym = h["symbol"]
        shares = h["shares"]
        cost_basis = h["cost_basis_base"]
        avg_price = h.get("avg_price_base")
        curr_val = h["current_value_base"]
        pnl = h["total_pnl_base"]
        
        checks = []
        
        # Check 1: 股数与均价推算本金
        if avg_price and shares:
            calc_cost = shares * avg_price
            diff_cost = abs(calc_cost - cost_basis)
            if diff_cost <= 0.05:  # within 5 pence rounding
                checks.append({
                    "name": "本金与均价闭环校验",
                    "passed": True,
                    "msg": f"{shares:.7f}股 × £{avg_price:.2f} = £{calc_cost:.2f} (与记录本金 £{cost_basis:.2f} 吻合)"
                })
            else:
                all_passed = False
                checks.append({
                    "name": "本金与均价闭环校验",
                    "passed": False,
                    "msg": f"偏差警告: 股数×均价为 £{calc_cost:.2f}，而本金记录为 £{cost_basis:.2f}，相差 £{diff_cost:.2f}"
                })
        
        # Check 2: 现价与市值逻辑校验
        calc_val = shares * h["price_base"]
        diff_val = abs(calc_val - curr_val)
        if diff_val <= 0.02:
            checks.append({
                "name": "实时市值测算校验",
                "passed": True,
                "msg": f"{shares:.7f}股 × 现价£{h['price_base']:.2f} = £{curr_val:.2f} (计算一致)"
            })
        else:
            all_passed = False
            checks.append({
                "name": "实时市值测算校验",
                "passed": False,
                "msg": f"市值偏差 £{diff_val:.2f}"
            })

        # Check 3: 盈亏计算校验 (市值 - 本金 == 浮动盈亏)
        expected_pnl = curr_val - cost_basis
        diff_pnl = abs(expected_pnl - pnl)
        if diff_pnl <= 0.02:
            checks.append({
                "name": "浮盈计算自洽校验",
                "passed": True,
                "msg": f"市值 £{curr_val:.2f} - 本金 £{cost_basis:.2f} = 回报 £{pnl:+.2f} (自洽)"
            })
        else:
            all_passed = False
            checks.append({
                "name": "浮盈计算自洽校验",
                "passed": False,
                "msg": f"浮盈偏差 £{diff_pnl:.2f}"
            })

        results.append({
            "symbol": sym,
            "shares": shares,
            "cost_basis": cost_basis,
            "current_value": curr_val,
            "total_pnl": pnl,
            "checks": checks
        })

    # Balance check:
    total_val = data["total_value"]
    sum_components = data["stock_value"] + data["cash_value"]
    balance_ok = abs(total_val - sum_components) <= 0.01

    return {
        "status": "passed" if all_passed and balance_ok else "warning",
        "all_passed": all_passed and balance_ok,
        "holdings_checks": results,
        "balance_check": {
            "passed": balance_ok,
            "total_value": total_val,
            "stock_value": data["stock_value"],
            "cash_value": data["cash_value"]
        }
    }
