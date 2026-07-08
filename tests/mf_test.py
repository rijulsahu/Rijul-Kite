# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv", "yfinance"]
# ///
"""Manual integration test for the Kite mutual fund holdings API.

Fetches raw MF holdings via the Kite Connect client from
``api_setup_auth`` and prints each holding dict to stdout.  Intended for
quick sanity-checks during development; not part of an automated test suite.

Usage::

    uv run tests/mf_test.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import os
import yfinance as yf
from api_setup_auth import kite

def fetch_mf_holdings():
    try:
        holding = kite.mf_holdings()
        return holding
    except Exception as e:
        print("Error fetching mutual fund holdings:", e)
        return None

if __name__ == "__main__":
    mf_holdings = fetch_mf_holdings()
    if mf_holdings is not None:
        for holding in mf_holdings:
            print(holding)