# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv", "yfinance"]
# ///
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