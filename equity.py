# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv", "yfinance"]
# ///
"""Equity holdings module for the Rijul-Kite portfolio tracker.

Fetches live equity holdings from the Zerodha Kite Connect API, enriches
each position with fundamental and technical metadata from Yahoo Finance
(sector, trailing PE, dividend yield, beta, 52-week high/low, and
Jensen's Alpha), and exports the results to ``output/equity.csv``.

Typical usage::

    uv run equity.py

Or import into ``run.py`` for the combined pipeline::

    from equity import fetch_equity_holdings, format_holdings, save_to_csv

The Nifty 50 index (``^NSEI``) is used as the market benchmark when
computing Jensen's Alpha.  The risk-free rate is fixed at the approximate
India 10-year G-Sec yield (``RISK_FREE_RATE``).

Author: Rijul Sahu
Portfolio: https://rijul.cloud
"""
import os
import yfinance as yf
from api_setup_auth import kite
from concurrent.futures import ThreadPoolExecutor

# India 10-year G-Sec approximate risk-free rate
RISK_FREE_RATE = 0.07


def _fetch_nifty_1y_return() -> float:
    """Fetch the trailing 1-year total return for the Nifty 50 index.

    Downloads price history for ``^NSEI`` via yfinance and computes the
    simple price return from the first to the last available close.

    Returns:
        float: Fractional 1-year return (e.g. ``0.15`` for 15 %). Returns
        ``0.0`` on any error or when fewer than two data points are available.
    """
    try:
        nifty = yf.Ticker("^NSEI").history(period="1y")
        if len(nifty) < 2:
            return 0.0
        return (nifty["Close"].iloc[-1] / nifty["Close"].iloc[0]) - 1
    except Exception:
        return 0.0


_SKIP_YFINANCE = {"TVSMNCRPS-P1"}  # non-tradeable entitlements with no yfinance data

def get_stock_metadata(symbol, r_market: float = 0.0):
    """Fetch yfinance metadata and compute Jensen's Alpha for a single stock.

    Classifies the stock by market-cap tier (Large / Mid / Small) using
    ``marketCap`` in crore INR (≥ 20 000 → Large, ≥ 5 000 → Mid, else Small),
    then retrieves sector, trailing PE, dividend yield, beta, and the
    52-week high/low from ``yf.Ticker.info``.

    Jensen's Alpha is computed as::

        α = r_stock − (r_f + β × (r_market − r_f))

    where ``r_f`` is ``RISK_FREE_RATE`` and ``r_stock`` is the trailing
    1-year price return from yfinance history.

    Args:
        symbol (str): NSE trading symbol (e.g. ``"INFY"``). ``.NS`` is
            appended automatically for the Yahoo Finance ticker.
        r_market (float): Trailing 1-year market return used in the alpha
            calculation.  Pass the value returned by
            ``_fetch_nifty_1y_return()``.  Defaults to ``0.0``, in which
            case alpha is not calculated.

    Returns:
        dict: Keys ``Cap``, ``Sector``, ``PE``, ``DivYield%``, ``Beta``,
        ``52W High``, ``52W Low``, ``Alpha``.
        Falls back to zeroed-out defaults on any fetch error.
    """
    if symbol in _SKIP_YFINANCE:
        return {"Cap": "Small", "Sector": "Unknown", "PE": 0,
                "DivYield%": 0, "Beta": 0, "52W High": 0, "52W Low": 0, "Alpha": 0.0}
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info
        crore = (info.get("marketCap") or 0) / 1e7
        if crore >= 20000:
            cap = "Large"
        elif crore >= 5000:
            cap = "Mid"
        else:
            cap = "Small"
        beta = round(info.get("beta") or 0, 2)

        # Trailing 1Y return for Jensen's Alpha
        hist = ticker.history(period="1y")
        if len(hist) >= 2 and r_market != 0.0:
            r_stock = (hist["Close"].iloc[-1] / hist["Close"].iloc[0]) - 1
            alpha = round(r_stock - (RISK_FREE_RATE + beta * (r_market - RISK_FREE_RATE)), 4)
        else:
            alpha = 0.0

        return {
            "Cap":       cap,
            "Sector":    info.get("sector") or "Unknown",
            "PE":        round(info.get("trailingPE") or 0, 2),
            "DivYield%": round(info.get("dividendYield") or 0, 2),
            "Beta":      beta,
            "52W High":  round(info.get("fiftyTwoWeekHigh") or 0, 2),
            "52W Low":   round(info.get("fiftyTwoWeekLow") or 0, 2),
            "Alpha":     alpha,
        }
    except Exception:
        return {"Cap": "Unknown", "Sector": "Unknown", "PE": 0,
                "DivYield%": 0, "Beta": 0, "52W High": 0, "52W Low": 0, "Alpha": 0.0}

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "output")

def fetch_equity_holdings():
    """Fetch raw equity holdings from the Kite Connect API.

    Returns:
        list[dict] | None: A list of holding dictionaries as returned by
        ``KiteConnect.holdings()``, or ``None`` if the API call fails.
    """
    try:
        holding = kite.holdings()
        return holding
    except Exception as e:
        print("Error fetching equity holdings:", e)
        return None

def fetch_stock_metadata(symbols):
    """Fetch yfinance metadata for a list of symbols in parallel.

    Retrieves the current Nifty 1-year return first (used as the market
    benchmark for alpha), then dispatches ``get_stock_metadata`` for all
    symbols concurrently using a ``ThreadPoolExecutor``.

    Args:
        symbols (list[str]): NSE trading symbols to enrich.

    Returns:
        dict[str, dict]: Mapping of symbol → metadata dict as returned by
        ``get_stock_metadata``.
    """
    r_market = _fetch_nifty_1y_return()
    print(f"  Nifty 1Y return (^NSEI): {r_market:.2%}")

    def _fetch(symbol):
        return get_stock_metadata(symbol, r_market)

    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(_fetch, symbols)
    return dict(zip(symbols, results))

def format_holdings(holdings):
    """Enrich raw Kite holdings with yfinance metadata and return formatted rows.

    Filters out symbols listed in ``_SKIP_YFINANCE``, fetches yfinance
    metadata for the remaining symbols in parallel, then combines Kite
    fields (quantity, average price, last/close price, P&L, day change)
    with the enriched metadata (cap tier, sector, PE, dividend yield, beta,
    52-week range, alpha) into a list of row dictionaries.

    Args:
        holdings (list[dict]): Raw holdings as returned by
            ``fetch_equity_holdings()``.

    Returns:
        list[dict]: One dict per holding with keys: ``Symbol``, ``Qty``,
        ``Avg``, ``LTP``, ``Close``, ``Invested``, ``Cur Value``, ``PnL``,
        ``Day Chg``, ``Day Chg%``, ``Cap``, ``Sector``, ``PE``,
        ``DivYield%``, ``Beta``, ``52W High``, ``52W Low``, ``Alpha``.
    """
    holdings = [h for h in holdings if h['tradingsymbol'] not in _SKIP_YFINANCE]
    symbols = [h['tradingsymbol'] for h in holdings]
    meta_map = fetch_stock_metadata(symbols)   # all calls fire in parallel

    rows = []
    for h in holdings:
        invested = round(h['average_price'] * h['quantity'], 2)
        current_value = round(h['last_price'] * h['quantity'], 2)
        meta = meta_map[h['tradingsymbol']]
        rows.append({
            'Symbol':     h['tradingsymbol'],
            'Qty':        h['quantity'],
            'Avg':        h['average_price'],
            'LTP':        h['last_price'],
            'Close':      h['close_price'],
            'Invested':   invested,
            'Cur Value':  current_value,
            'PnL':        round(h['pnl'], 2),
            'Day Chg':    round(h['day_change'], 2),
            'Day Chg%':   round(h['day_change_percentage'], 2),
            'Cap':        meta['Cap'],
            'Sector':     meta['Sector'],
            'PE':         meta['PE'],
            'DivYield%':  meta['DivYield%'],
            'Beta':       meta['Beta'],
            '52W High':   meta['52W High'],
            '52W Low':    meta['52W Low'],
            'Alpha':      meta['Alpha'],
        })
    return rows

def print_holdings(rows):
    """Print equity holdings to stdout in a fixed-width tabular format.

    Args:
        rows (list[dict]): Formatted holding rows as returned by
            ``format_holdings()``.
    """
    widths = [16, 6, 12, 12, 12, 14, 14, 12, 10, 10, 8, 20, 8, 10, 7, 10, 10, 10]
    headers = list(rows[0].keys())
    sep = "=" * sum(widths)
    print(f"\n{sep}")
    print("".join(f"{h:<{w}}" for h, w in zip(headers, widths)))
    print(sep)
    for row in rows:
        vals = list(row.values())
        vals[9] = f"{vals[9]}%"   # Day Chg%
        print("".join(f"{str(v):<{w}}" for v, w in zip(vals, widths)))

def save_to_csv(rows):
    """Export equity holding rows to ``output/equity.csv``.

    Creates the ``output/`` directory if it does not exist, then writes a
    CSV file with a header row derived from the first row's keys.

    Args:
        rows (list[dict]): Formatted holding rows as returned by
            ``format_holdings()``.

    Side effects:
        Creates or overwrites ``output/equity.csv``.
    """
    import csv
    os.makedirs(EXPORT_DIR, exist_ok=True)
    filepath = os.path.join(EXPORT_DIR, "equity.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved to {filepath}")

if __name__ == "__main__":
    equity_holdings = fetch_equity_holdings()
    if equity_holdings is not None:
        rows = format_holdings(equity_holdings)
        print_holdings(rows)
        save_to_csv(rows)