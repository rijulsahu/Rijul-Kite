# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv"]
# ///
import os
from api_setup_auth import kite

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "output")

def fetch_amfi_categories():
    import urllib.request
    import re
    url = "https://www.amfiindia.com/spages/NAVAll.txt"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            lines = r.read().decode("utf-8").splitlines()
    except Exception as e:
        print(f"Warning: Could not fetch AMFI categories (network error): {e}")
        return {}
    isin_to_category = {}
    current_category = ""
    for line in lines:
        line = line.strip()
        if line.startswith("Open Ended") or line.startswith("Close Ended"):
            m = re.search(r'\((.+)\)', line)
            current_category = m.group(1) if m else line
            continue
        parts = line.split(";")
        if len(parts) >= 3:
            for isin in (parts[1], parts[2]):
                if isin.startswith("INF") or isin.startswith("IN1"):
                    isin_to_category[isin] = current_category
    return isin_to_category

def fetch_mf_holdings():
    try:
        return kite.mf_holdings()
    except Exception as e:
        print("Error fetching mutual fund holdings:", e)
        return None

def format_mf_holdings(holdings, categories=None):
    rows = []
    for h in holdings:
        fund_name = h['fund'].replace('u0026', '&')
        invested = round(h['average_price'] * h['quantity'], 2)
        current_value = round(h['last_price'] * h['quantity'], 2)
        gain = round(current_value - invested, 2)
        gain_pct = round((gain / invested) * 100, 2) if invested else 0.0
        category = ""
        if categories:
            category = categories.get(h['tradingsymbol'], "Unknown")
        rows.append({
            'Fund':        fund_name,
            'Qty':         h['quantity'],
            'Avg':         h['average_price'],
            'NAV':         h['last_price'],
            'Invested':    invested,
            'Cur Value':   current_value,
            'Gain':        gain,
            'Gain%':       gain_pct,
            'Category':    category,
        })
    return rows

def print_mf_holdings(rows):
    widths = [46, 12, 10, 10, 14, 14, 12, 9, 32]
    headers = list(rows[0].keys())
    sep = "=" * sum(widths)
    print(f"\n{sep}")
    print("".join(f"{h:<{w}}" for h, w in zip(headers, widths)))
    print(sep)
    for row in rows:
        vals = list(row.values())
        vals[0] = str(vals[0])[:45]    # truncate long fund names
        vals[-2] = f"{vals[-2]}%"      # append % to Gain%
        vals[-1] = str(vals[-1])[:31]  # truncate long category
        print("".join(f"{str(v):<{w}}" for v, w in zip(vals, widths)))
    # totals row
    total_invested = sum(r['Invested'] for r in rows)
    total_value = sum(r['Cur Value'] for r in rows)
    total_gain = round(total_value - total_invested, 2)
    total_gain_pct = round((total_gain / total_invested) * 100, 2) if total_invested else 0.0
    print(sep)
    summary = ['TOTAL', '', '', '', round(total_invested, 2), round(total_value, 2), total_gain, f"{total_gain_pct}%", '']
    print("".join(f"{str(v):<{w}}" for v, w in zip(summary, widths)))

def save_to_csv(rows):
    import csv
    os.makedirs(EXPORT_DIR, exist_ok=True)
    filepath = os.path.join(EXPORT_DIR, "mf.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved to {filepath}")


# ---------------------------------------------------------------------------
# SIP helpers
# ---------------------------------------------------------------------------

def fetch_mf_sips():
    try:
        return kite.mf_sips()
    except Exception as e:
        print("Error fetching MF SIPs:", e)
        return None


def format_mf_sips(sips):
    rows = []
    for s in sips:
        rows.append({
            'Fund':            s.get('fund') or s.get('tradingsymbol', ''),
            'SIP ID':          s.get('sip_id', ''),
            'Amount':          s.get('instalment_amount', 0),
            'Frequency':       s.get('frequency', ''),
            'Instalments':     s.get('instalments', 0),
            'Completed':       s.get('completed_instalments', 0),
            'Pending':         s.get('pending_instalments', 0),
            'Next Instalment': s.get('next_instalment', ''),
            'Status':          s.get('status', ''),
        })
    return rows


def print_mf_sips(rows):
    widths = [46, 14, 12, 12, 12, 12, 10, 16, 10]
    headers = list(rows[0].keys())
    sep = "=" * sum(widths)
    print(f"\n{sep}")
    print("  Active SIPs")
    print(sep)
    print("".join(f"{h:<{w}}" for h, w in zip(headers, widths)))
    print("-" * sum(widths))
    for row in rows:
        vals = list(row.values())
        vals[0] = str(vals[0])[:45]
        print("".join(f"{str(v):<{w}}" for v, w in zip(vals, widths)))
    active_monthly = sum(
        r['Amount'] for r in rows
        if str(r['Status']).lower() == 'active' and str(r['Frequency']).lower() == 'monthly'
    )
    print("-" * sum(widths))
    print(f"  Monthly SIP commitment (active): ₹{active_monthly:,.0f}")


def save_sips_to_csv(rows):
    import csv
    os.makedirs(EXPORT_DIR, exist_ok=True)
    filepath = os.path.join(EXPORT_DIR, "sip.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved to {filepath}")


if __name__ == "__main__":
    mf_holdings = fetch_mf_holdings()
    if mf_holdings is not None:
        print("Fetching AMFI categories...")
        categories = fetch_amfi_categories()
        rows = format_mf_holdings(mf_holdings, categories)
        print_mf_holdings(rows)
        save_to_csv(rows)

    print("\nFetching SIPs...")
    sips = fetch_mf_sips()
    if sips is not None:
        sip_rows = format_mf_sips(sips)
        if sip_rows:
            print_mf_sips(sip_rows)
            save_sips_to_csv(sip_rows)
 