# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv", "yfinance"]
# ///

from equity import (
    fetch_equity_holdings, format_holdings, print_holdings,
    save_to_csv as save_equity_csv,
)
from mf import (
    fetch_mf_holdings, fetch_amfi_categories, format_mf_holdings,
    print_mf_holdings, save_to_csv as save_mf_csv,
    fetch_mf_sips, format_mf_sips, print_mf_sips, save_sips_to_csv,
)

print("=== EQUITY HOLDINGS ===")
equity_holdings = fetch_equity_holdings()
if equity_holdings is not None:
    rows = format_holdings(equity_holdings)
    print_holdings(rows)
    save_equity_csv(rows)

print("\n=== MUTUAL FUND HOLDINGS ===")
mf_holdings = fetch_mf_holdings()
if mf_holdings is not None:
    print("Fetching AMFI categories...")
    categories = fetch_amfi_categories()
    rows = format_mf_holdings(mf_holdings, categories)
    print_mf_holdings(rows)
    save_mf_csv(rows)

print("\n=== MUTUAL FUND SIPS ===")
sips = fetch_mf_sips()
if sips is not None:
    sip_rows = format_mf_sips(sips)
    if sip_rows:
        print_mf_sips(sip_rows)
        save_sips_to_csv(sip_rows)