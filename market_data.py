"""Market data provider using yfinance with in-memory caching and currency normalization."""

from __future__ import annotations
import time
from typing import Dict, Any, Optional
import yfinance as yf

# In-memory quote cache with TTL (seconds)
_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 90  # 90 seconds cache


def get_fx_rate(from_curr: str, to_curr: str, force_refresh: bool = False) -> Dict[str, float]:
    """
    Get exchange rate from from_curr to to_curr.
    Returns dict: {'rate': float, 'prev_close': float, 'change_pct': float}
    """
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()

    if from_curr == to_curr:
        return {"rate": 1.0, "prev_close": 1.0, "change_pct": 0.0}

    pair_key = f"FX_{from_curr}_{to_curr}"
    now = time.time()
    if not force_refresh and pair_key in _CACHE and (now - _CACHE[pair_key]["ts"] < CACHE_TTL):
        return _CACHE[pair_key]["data"]

    rate = 1.0
    prev_close = 1.0

    try:
        # Try direct pair first: e.g. USDGBP=X
        direct_symbol = f"{from_curr}{to_curr}=X"
        ticker = yf.Ticker(direct_symbol)
        last_price = getattr(ticker.fast_info, 'last_price', None)
        ticker_prev = getattr(ticker.fast_info, 'previous_close', None)
        
        if last_price and last_price > 0:
            rate = float(last_price)
            prev_close = float(ticker_prev) if ticker_prev else rate
        else:
            # Try inverted pair: e.g. GBPUSD=X
            inverted_symbol = f"{to_curr}{from_curr}=X"
            inv_ticker = yf.Ticker(inverted_symbol)
            inv_last = getattr(inv_ticker.fast_info, 'last_price', None)
            inv_prev = getattr(inv_ticker.fast_info, 'previous_close', None)
            if inv_last and inv_last > 0:
                rate = 1.0 / float(inv_last)
                prev_close = (1.0 / float(inv_prev)) if inv_prev else rate
    except Exception as e:
        # Fallback common rates if offline or API error
        if from_curr == "USD" and to_curr == "GBP":
            rate, prev_close = 1.0 / 1.33, 1.0 / 1.33
        elif from_curr == "GBP" and to_curr == "USD":
            rate, prev_close = 1.33, 1.33

    change_pct = ((rate - prev_close) / prev_close * 100) if prev_close else 0.0
    res = {"rate": rate, "prev_close": prev_close, "change_pct": change_pct}
    _CACHE[pair_key] = {"ts": now, "data": res}
    return res


def get_stock_quote(symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch quote for symbol.
    Returns:
      symbol, name, currency, price, prev_close, change, change_pct,
      day_high, day_low, market_cap, exchange
    """
    symbol = symbol.strip().upper()
    cache_key = f"QUOTE_{symbol}"
    now = time.time()
    if not force_refresh and cache_key in _CACHE and (now - _CACHE[cache_key]["ts"] < CACHE_TTL):
        return _CACHE[cache_key]["data"]

    ticker = yf.Ticker(symbol)
    fast_info = ticker.fast_info

    price = getattr(fast_info, 'last_price', None)
    prev_close = getattr(fast_info, 'previous_close', None)
    currency = getattr(fast_info, 'currency', 'USD') or 'USD'
    currency = currency.upper()

    # Handle UK pence (GBp / GBX) -> normalise to GBP
    is_pence = currency in ('GBP', 'GBX') and currency != 'GBP'
    if currency == 'GBP' and hasattr(ticker, 'info'):
        # Check if actually pence (Yahoo Finance sometimes labels LSE as GBP but price is in pence)
        pass

    if currency in ('GBP_PENCE', 'GBX'):
        scale = 0.01
        currency = 'GBP'
    elif currency == 'GBP':
        scale = 1.0
    else:
        scale = 1.0

    if price is not None:
        price = float(price) * scale
    if prev_close is not None:
        prev_close = float(prev_close) * scale
    else:
        prev_close = price

    change = (price - prev_close) if (price and prev_close) else 0.0
    change_pct = (change / prev_close * 100) if (prev_close and prev_close > 0) else 0.0

    day_high = getattr(fast_info, 'day_high', None)
    day_low = getattr(fast_info, 'day_low', None)

    # Get clean company name
    name = symbol
    try:
        info = ticker.info
        name = info.get('shortName') or info.get('longName') or symbol
    except Exception:
        name = symbol

    res = {
        "symbol": symbol,
        "name": name,
        "currency": currency,
        "price": price or 0.0,
        "prev_close": prev_close or 0.0,
        "change": change,
        "change_pct": change_pct,
        "day_high": (float(day_high) * scale) if day_high else None,
        "day_low": (float(day_low) * scale) if day_low else None,
        "exchange": getattr(fast_info, 'exchange', 'UNKNOWN'),
    }

    _CACHE[cache_key] = {"ts": now, "data": res}
    return res
