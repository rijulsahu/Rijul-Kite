# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv"]
# ///
"""Mutual fund holdings and SIP module for the Rijul-Kite portfolio tracker.

Fetches live mutual fund holdings and active SIP details from the Zerodha
Kite Connect API.  Fund categories are enriched via the AMFI NAVAll feed
(``https://www.amfiindia.com/spages/NAVAll.txt``) which maps ISINs to
AMFI category strings (e.g. *Large Cap Fund*, *ELSS*, *Liquid Fund*).

Exports:
    - ``output/mf.csv``  — mutual fund holdings with gain/loss and category.
    - ``output/sip.csv`` — active SIP details including instalment schedule.

Typical usage::

    uv run mf.py

Or import into ``run.py`` for the combined pipeline::

    from mf import fetch_mf_holdings, format_mf_holdings, save_to_csv

Notes:
    The AMFI category fetch is a best-effort network call; a warning is
    printed and an empty dict is returned on failure so the rest of the
    pipeline continues unaffected.

Author: Rijul Sahu, https://rijul.cloud
"""
import os
from api_setup_auth import kite

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "output")

def fetch_amfi_categories():
    """Fetch ISIN-to-category mappings from the AMFI NAVAll text feed.

    Downloads ``https://www.amfiindia.com/spages/NAVAll.txt``, parses the
    pipe-delimited file, and returns a dict mapping each fund ISIN to its
    AMFI category string (extracted from parenthesised text in
    ``Open Ended ...`` and ``Close Ended ...`` section headers).

    Returns:
        dict[str, str]: Mapping of ISIN → category string.  Returns an empty
        dict on any network or parse error.
    """
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
    """Fetch raw mutual fund holdings from the Kite Connect API.

    Returns:
        list[dict] | None: A list of MF holding dictionaries as returned by
        ``KiteConnect.mf_holdings()``, or ``None`` if the API call fails.
    """
    try:
        return kite.mf_holdings()
    except Exception as e:
        print("Error fetching mutual fund holdings:", e)
        return None

def format_mf_holdings(holdings, categories=None):
    """Format raw Kite MF holdings into display-ready row dicts.

    Computes invested amount, current value, absolute gain, and gain
    percentage for each fund.  Optionally maps each holding's
    ``tradingsymbol`` (which is the fund ISIN) to an AMFI category string.

    Args:
        holdings (list[dict]): Raw MF holdings from ``fetch_mf_holdings()``.
        categories (dict[str, str] | None): ISIN-to-category mapping from
            ``fetch_amfi_categories()``.  Pass ``None`` to skip category
            enrichment.

    Returns:
        list[dict]: One dict per fund with keys: ``Fund``, ``Qty``,
        ``Avg``, ``NAV``, ``Invested``, ``Cur Value``, ``Gain``,
        ``Gain%``, ``Category``.
    """
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
    """Print mutual fund holdings to stdout with a subtotals footer.

    Renders a fixed-width table and appends a TOTAL row showing aggregate
    invested amount, current value, gain, and gain percentage.

    Args:
        rows (list[dict]): Formatted MF rows from ``format_mf_holdings()``.
    """
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
    """Export mutual fund holding rows to ``output/mf.csv``.

    Creates the ``output/`` directory if it does not exist, then writes a
    CSV file with a header derived from the first row's keys.

    Args:
        rows (list[dict]): Formatted MF rows from ``format_mf_holdings()``.

    Side effects:
        Creates or overwrites ``output/mf.csv``.
    """
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
    """Fetch active and scheduled SIP details from the Kite Connect API.

    Returns:
        list[dict] | None: A list of SIP dictionaries as returned by
        ``KiteConnect.mf_sips()``, or ``None`` if the API call fails.
    """
    try:
        return kite.mf_sips()
    except Exception as e:
        print("Error fetching MF SIPs:", e)
        return None


def format_mf_sips(sips):
    """Format raw Kite SIP records into display-ready row dicts.

    Args:
        sips (list[dict]): Raw SIP records from ``fetch_mf_sips()``.

    Returns:
        list[dict]: One dict per SIP with keys: ``Fund``, ``SIP ID``,
        ``Amount``, ``Frequency``, ``Instalments``, ``Completed``,
        ``Pending``, ``Next Instalment``, ``Status``.
    """
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
    """Print SIP details to stdout with a monthly commitment summary.

    Renders a fixed-width table and appends a footer line showing the total
    monthly SIP commitment for all active monthly SIPs.

    Args:
        rows (list[dict]): Formatted SIP rows from ``format_mf_sips()``.
    """
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
    """Export SIP rows to ``output/sip.csv``.

    Creates the ``output/`` directory if it does not exist, then writes a
    CSV file with a header derived from the first row's keys.

    Args:
        rows (list[dict]): Formatted SIP rows from ``format_mf_sips()``.

    Side effects:
        Creates or overwrites ``output/sip.csv``.
    """
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
 