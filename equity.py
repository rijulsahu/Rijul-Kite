# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv", "yfinance"]
# ///
import os
import yfinance as yf
from api_setup_auth import kite
from concurrent.futures import ThreadPoolExecutor

# India 10-year G-Sec approximate risk-free rate
RISK_FREE_RATE = 0.07


def _fetch_nifty_1y_return() -> float:
    """Fetch trailing 1-year total return for Nifty 50 (^NSEI)."""
    try:
        nifty = yf.Ticker("^NSEI").history(period="1y")
        if len(nifty) < 2:
            return 0.0
        return (nifty["Close"].iloc[-1] / nifty["Close"].iloc[0]) - 1
    except Exception:
        return 0.0


_SKIP_YFINANCE = {"TVSMNCRPS-P1"}  # non-tradeable entitlements with no yfinance data

def get_stock_metadata(symbol, r_market: float = 0.0):
    """Fetch market-cap category plus fundamental data (sector, PE, dividend yield, beta, 52W range, alpha)."""
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
    try:
        holding = kite.holdings()
        return holding
    except Exception as e:
        print("Error fetching equity holdings:", e)
        return None

def fetch_stock_metadata(symbols):
    r_market = _fetch_nifty_1y_return()
    print(f"  Nifty 1Y return (^NSEI): {r_market:.2%}")

    def _fetch(symbol):
        return get_stock_metadata(symbol, r_market)

    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(_fetch, symbols)
    return dict(zip(symbols, results))

def format_holdings(holdings):
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