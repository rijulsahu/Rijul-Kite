# /// script
# requires-python = ">=3.13"
# dependencies = ["kiteconnect", "python-dotenv", "yfinance"]
# ///
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