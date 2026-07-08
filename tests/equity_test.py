# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv", "yfinance"]
# ///
"""Manual integration test for the Kite equity holdings API.

Fetches raw equity holdings via the Kite Connect client from
``api_setup_auth`` and prints each holding dict to stdout.  Intended for
quick sanity-checks during development; not part of an automated test suite.

Usage::

    uv run tests/equity_test.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import os
import yfinance as yf
from api_setup_auth import kite

def fetch_equity_holdings():
    try:
        holding = kite.holdings()
        return holding
    except Exception as e:
        print("Error fetching equity holdings:", e)
        return None

if __name__ == "__main__":
    equity_holdings = fetch_equity_holdings()
    if equity_holdings is not None:
        for holding in equity_holdings:
            print(holding)