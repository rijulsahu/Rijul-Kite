# Rijul-Kite

A personal portfolio tracker built on top of the [Zerodha Kite Connect API](https://kite.trade/docs/connect/v3/). Fetches live equity and mutual fund holdings, enriches them with yfinance data (sector, PE, beta, alpha, 52W range), and exports clean CSVs plus a full PDF visual summary.

---

## Features

- **Equity holdings** — quantity, average cost, current value, P&L, day change, cap category, sector, PE, dividend yield, beta, alpha
- **Mutual fund holdings** — NAV, current value, P&L, AMFI fund category
- **SIP tracker** — active SIP details
- **Portfolio PDF summary** — P&L bar charts, allocation charts, MF breakdowns, colour-coded tables
- **Session caching** — Kite access tokens are cached locally and reused until the 6 AM IST daily expiry; no repeated browser logins

---

## Requirements

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv/) (dependency runner)
- A Zerodha Kite Connect app — API key and secret from [developers.kite.trade](https://developers.kite.trade)

---

## Setup

### 1. Clone

```bash
git clone https://github.com/<your-username>/Rijul-Kite.git
cd Rijul-Kite
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env`:

```env
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
```

> `.env` is gitignored and will never be committed.

---

## Usage

All scripts are run with `uv run` — no manual `pip install` or venv activation needed. `uv` reads the inline `# dependencies` block from each script and installs on first run.

### Fetch holdings and export CSVs

```bash
uv run run.py
```

Outputs to `output/equity.csv`, `output/mf.csv`, `output/sip.csv`.

### Generate PDF portfolio summary

```bash
uv run portfolio_summary.py
```

Reads `output/equity.csv` and `output/mf.csv` and produces a multi-page PDF with charts and tables.

### Run individual modules

```bash
uv run equity.py           # equity holdings only
uv run mf.py               # mutual fund holdings only
```

### Auth flow

On first run (or after token expiry), a browser window opens to the Kite login page. After login, the access token is cached in `.kite_session.json` (gitignored) and reused for subsequent runs until 6 AM IST the next day.

---

## Project Structure

```
Rijul-Kite/
├── api_setup_auth.py      # Kite auth, session caching, token refresh
├── equity.py              # Equity holdings fetch + yfinance enrichment
├── mf.py                  # Mutual fund holdings + AMFI category mapping
├── portfolio_summary.py   # PDF chart/table generation (reads CSVs)
├── run.py                 # Entry point — runs equity + MF + SIP pipeline
├── .env.example           # Credential template
├── output/                # CSV exports (gitignored)
└── tests/                 # Manual integration tests
```

---

## Security

- API credentials are loaded from `.env` via `python-dotenv` — never hardcoded
- `.env`, `.kite_session.json`, and `output/` are all gitignored
- Session file is written with restrictive OS permissions (user-only read/write)
