# /// script
# requires-python = ">=3.13"
# dependencies = ["matplotlib"]
# ///

"""
portfolio_summary.py

Reads the equity holdings CSV exported from Kite and prints a summary of the
Finology 30 portfolio — i.e., only stocks that are actively tracked as part of
the F30 bucket. Also generates four charts:

  1. Horizontal bar chart  — P&L per stock (green = profit, red = loss).
  2. Allocation bar chart  — Portfolio allocation by invested amount (target vs actual).
  3. Grouped bar chart     — Invested vs Current Value per stock.
  4. Overall summary bar   — F30 vs Excluded totals side-by-side.
  5. Portfolio details table — Full equity breakdown with colour-coded P&L.
  6. MF Gain bar chart     — Gain (₹) per mutual fund with % annotation.
  7. MF Category breakdown — Invested vs Current Value grouped by fund category.
  8. MF details table      — Full mutual fund table grouped by category.

Excluded categories (printed separately for reference):
  - GOLD_ETF         : Gold ETFs — tracked separately, not equity stocks.
  - CASES            : Smallcase baskets — managed as index-like instruments.
  - F30_NOT_TRACKING : Stocks that Finology no longer tracks (e.g. delisted/removed).
  - IPO              : Allotted via IPO; not part of the F30 buy-list.
  - BONUS_SHARES     : Bonus shares credited by the company; cost basis is zero
                       and they will be formally credited in September 2026.
"""

import csv
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages

# Path to the equity holdings CSV exported from Kite
EQ_CSV_PATH = os.path.join(os.path.dirname(__file__), "output", "equity.csv")

# Output PDF path for all portfolio charts (date-stamped so each day produces a new file)
import datetime as _dt
PDF_PATH = os.path.join(
    os.path.dirname(__file__), "output",
    f"portfolio_summary_{_dt.date.today().strftime('%d_%B_%Y')}.pdf",
)

# Path to the mutual fund holdings CSV exported from Kite
MF_CSV_PATH = os.path.join(os.path.dirname(__file__), "output", "mf.csv")

# Path to the SIP data CSV exported by mf.py
SIP_CSV_PATH = os.path.join(os.path.dirname(__file__), "output", "sip.csv")

# Gold ETFs — excluded because they track gold prices, not equity performance
GOLD_ETF = ['GOLD1', 'GOLDIETF', 'HDFCGOLD', 'SETFGOLD', 'GOLDBEES']

# Smallcase baskets — excluded because they are index/theme instruments, not individual stocks
CASES = ['TOP100CASE', 'MID150CASE']

# Stocks that Finology no longer tracks in their F30 universe
F30_NOT_TRACKING = ['KWIL']

# Stocks received via IPO allotment — not part of the F30 buy-list
IPO = ['TATATECH']

# Bonus shares allotted by the company; cost basis is ₹0 and
# they will be formally credited to the demat in September 2026
BONUS_SHARES = ['TVSMNCRPS']

# Combined set of all symbols to exclude from the F30 portfolio summary
EXCLUDED: set = set(GOLD_ETF + CASES + F30_NOT_TRACKING + IPO + BONUS_SHARES)


def _print_section(title: str, rows: list, show_totals: bool = True) -> None:
    """Print a formatted table section for a group of holdings.

    Args:
        title: Section heading to display above the table.
        rows: List of (symbol, invested, cur_value, pnl) tuples.
        show_totals: Whether to print a totals row and summary footer.
    """
    if not rows:
        return

    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")
    print(f"{'Symbol':<15} {'Cap':<12} {'Invested':>12} {'Cur Value':>12} {'PnL':>12}")
    print("-" * 70)

    total_invested = total_cur_value = total_pnl = 0.0
    for symbol, invested, cur_value, pnl, cap in rows:
        print(f"{symbol:<15} {cap:<12} {invested:>12.2f} {cur_value:>12.2f} {pnl:>12.2f}")
        total_invested += invested
        total_cur_value += cur_value
        total_pnl += pnl

    if show_totals:
        print("-" * 70)
        print(f"{'TOTAL':<15} {'':12} {total_invested:>12.2f} {total_cur_value:>12.2f} {total_pnl:>12.2f}")
        pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0
        print()
        print(f"  Total Invested  : ₹{total_invested:>12,.2f}")
        print(f"  Total Cur Value : ₹{total_cur_value:>12,.2f}")
        print(f"  Total P&L       : ₹{total_pnl:>12,.2f}  ({pnl_pct:.2f}%)")


def summarize_portfolio(eq_csv_path: str = EQ_CSV_PATH) -> None:
    """Read the Kite equity CSV and print a categorised portfolio summary.

    The function splits holdings into two groups:
      1. **F30 Portfolio** — stocks actively tracked by Finology 30.
      2. **Excluded holdings** — gold ETFs, smallcases, IPO allotments,
         bonus shares, and stocks no longer tracked by Finology.

    Args:
        eq_csv_path: Absolute path to the equity holdings CSV file.
    """
    f30_rows: list = []       # Stocks in the active F30 portfolio
    excluded_rows: list = []  # Everything else (gold, cases, IPO, bonus, etc.)

    with open(eq_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row["Symbol"]
            invested = float(row["Invested"]) if row["Invested"] else 0.0
            cur_value = float(row["Cur Value"]) if row["Cur Value"] else 0.0
            pnl = float(row["PnL"]) if row["PnL"] else 0.0
            cap = row.get("Cap") or "Unknown"
            entry = (symbol, invested, cur_value, pnl, cap)

            if symbol in EXCLUDED:
                excluded_rows.append(entry)
            else:
                f30_rows.append(entry)

    # Print active F30 holdings with full totals
    _print_section("Finology 30 Portfolio", f30_rows, show_totals=True)

    # Print excluded holdings for reference (no meaningful totals needed)
    _print_section(
        "Excluded (Gold ETFs / Cases / IPO / Bonus / Not Tracked)",
        excluded_rows,
        show_totals=True,
    )


def summarize_mf(mf_csv_path: str = MF_CSV_PATH) -> None:
    """Read the Kite mutual fund CSV and print a categorised MF summary.

    Holdings are grouped by fund category and printed with subtotals per
    category followed by a grand total.

    Args:
        mf_csv_path: Absolute path to the mutual fund holdings CSV file.
    """
    mf_rows: list = []
    with open(mf_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fund = row["Fund"]
            for suffix in (" - DIRECT  PLAN", " - DIRECT PLAN"):
                fund = fund.replace(suffix, "")
            mf_rows.append((
                fund[:42],
                float(row["Invested"])  if row["Invested"]  else 0.0,
                float(row["Cur Value"]) if row["Cur Value"] else 0.0,
                float(row["Gain"])      if row["Gain"]      else 0.0,
                float(row["Gain%"])     if row["Gain%"]     else 0.0,
                row.get("Category") or "Unknown",
            ))

    # Group by short category name, sorted by total invested descending
    cat_groups: dict = {}
    for row in mf_rows:
        cat = row[5].split(" - ", 1)[-1] if " - " in row[5] else row[5]
        cat_groups.setdefault(cat, []).append(row)

    sorted_cats = sorted(cat_groups, key=lambda c: sum(r[1] for r in cat_groups[c]), reverse=True)

    W = 84
    total_invested = total_cur = total_gain = 0.0

    for cat in sorted_cats:
        rows = cat_groups[cat]
        print(f"\n{'=' * W}")
        print(f"  {cat}")
        print(f"{'=' * W}")
        print(f"{'Fund':<44} {'Invested':>12} {'Cur Value':>12} {'Gain':>12} {'Gain%':>7}")
        print("-" * W)

        cat_inv = cat_cur = cat_gain = 0.0
        for fund, invested, cur_value, gain, gain_pct, _ in rows:
            print(f"{fund:<44} {invested:>12.2f} {cur_value:>12.2f} {gain:>12.2f} {gain_pct:>6.2f}%")
            cat_inv  += invested
            cat_cur  += cur_value
            cat_gain += gain

        cat_pct = (cat_gain / cat_inv * 100) if cat_inv else 0.0
        print("-" * W)
        print(f"{'SUBTOTAL':<44} {cat_inv:>12.2f} {cat_cur:>12.2f} {cat_gain:>12.2f} {cat_pct:>6.2f}%")
        total_invested += cat_inv
        total_cur      += cat_cur
        total_gain     += cat_gain

    total_pct = (total_gain / total_invested * 100) if total_invested else 0.0
    print(f"\n{'=' * W}")
    print(f"{'GRAND TOTAL':<44} {total_invested:>12.2f} {total_cur:>12.2f} {total_gain:>12.2f} {total_pct:>6.2f}%")
    print()
    print(f"  Total Invested  : \u20b9{total_invested:>14,.2f}")
    print(f"  Total Cur Value : \u20b9{total_cur:>14,.2f}")
    print(f"  Total Gain      : \u20b9{total_gain:>14,.2f}  ({total_pct:.2f}%)")


def summarize_sips(sip_csv_path: str = SIP_CSV_PATH) -> None:
    """Print a summary of MF SIPs from the saved CSV.

    Args:
        sip_csv_path: Absolute path to the SIP CSV saved by mf.py.
    """
    if not os.path.exists(sip_csv_path):
        print("\nNo SIP data found. Run mf.py first to generate sip.csv.")
        return

    with open(sip_csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return

    W = 110
    print(f"\n{'=' * W}")
    print("  SIP Summary")
    print(f"{'=' * W}")
    print(f"{'Fund':<48} {'Amount (₹)':>12} {'Freq':<12} {'Done/Total':>12} {'Next Date':>12} {'Status':<10}")
    print("-" * W)

    monthly_total = 0.0
    for r in rows:
        fund = r.get("Fund", "")
        for sfx in (" - DIRECT  PLAN", " - DIRECT PLAN"):
            fund = fund.replace(sfx, "")
        amount = float(r["Amount"]) if r.get("Amount") else 0.0
        done_total = f"{r.get('Completed','0')}/{r.get('Instalments','0')}"
        next_date = str(r.get("Next Instalment", ""))[:10]
        status = r.get("Status", "")
        print(f"{fund[:47]:<48} {amount:>12,.0f} {r.get('Frequency',''):<12} {done_total:>12} {next_date:>12} {status:<10}")
        if status.lower() == "active" and r.get("Frequency", "").lower() == "monthly":
            monthly_total += amount

    print("-" * W)
    print(f"  Monthly SIP commitment (active): ₹{monthly_total:>10,.0f}")


if __name__ == "__main__":
    summarize_portfolio(EQ_CSV_PATH)
    summarize_mf(MF_CSV_PATH)
    summarize_sips(SIP_CSV_PATH)


# ---------------------------------------------------------------------------
# Visualisation helpers
# ---------------------------------------------------------------------------

def _fmt_inr(value: float, _pos=None) -> str:
    """Matplotlib tick formatter that displays values in ₹ with K/L suffix."""
    if abs(value) >= 1_00_000:
        return f"₹{value/1_00_000:.1f}L"
    if abs(value) >= 1_000:
        return f"₹{value/1_000:.0f}K"
    return f"₹{value:.0f}"


def _short_fund_name(name: str) -> str:
    """Strip the ' - DIRECT PLAN' suffix and truncate to 36 chars for chart labels."""
    for suffix in (" - DIRECT  PLAN", " - DIRECT PLAN"):
        name = name.replace(suffix, "")
    return name[:36]


def plot_pnl_bar(rows: list, title: str) -> None:
    """Horizontal bar chart showing P&L per stock (green = profit, red = loss).

    Args:
        rows: List of (symbol, invested, cur_value, pnl) tuples.
        title: Chart title string.
    """
    # Sort by PnL descending so best performers appear at top
    sorted_rows = sorted(rows, key=lambda r: r[3], reverse=True)
    symbols = [r[0] for r in sorted_rows]
    pnls    = [r[3] for r in sorted_rows]
    colors  = ["#2ecc71" if p >= 0 else "#e74c3c" for p in pnls]

    fig, ax = plt.subplots(figsize=(10, max(6, len(symbols) * 0.35)))
    bars = ax.barh(symbols, pnls, color=colors, edgecolor="white", linewidth=0.5)

    # Annotate each bar with the ₹ value
    pnl_range = (max(pnls) - min(pnls)) or 1
    offset = pnl_range * 0.01
    for bar, val in zip(bars, pnls):
        x = bar.get_width()
        if val >= 0:
            x_pos, ha = x + offset, "left"
        else:
            # Place label just to the right of the zero line so it doesn't
            # crowd against the left axis.
            x_pos, ha = offset, "left"
        ax.text(
            x_pos, bar.get_y() + bar.get_height() / 2,
            _fmt_inr(val), va="center", ha=ha, fontsize=8,
            color="#2ecc71" if val >= 0 else "#e74c3c",
        )

    ax.axvline(0, color="grey", linewidth=0.8, linestyle="--")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Profit / Loss (₹)")
    ax.invert_yaxis()  # highest P&L at top
    fig.tight_layout()


def plot_allocation_bar(rows: list, title: str) -> None:
    """Chart 2: Insights-style bar chart of allocation by invested amount.

    Shows each stock's invested amount against equal-weight target thresholds,
    plus a right-side summary block and colour guide.

    Args:
        rows: List of (symbol, invested, cur_value, pnl, cap, ... ) tuples.
        title: Chart title string.
    """
    if not rows:
        return

    target_total = 15_00_000.0  # ₹15L target corpus
    total_invested = sum(r[1] for r in rows)
    n_stocks = len(rows)
    target_per_stock = target_total / n_stocks if n_stocks else 0.0
    equal_weight_pct = (100.0 / n_stocks) if n_stocks else 0.0

    # Sort by invested amount so under-allocated names are grouped at top.
    sorted_rows = sorted(rows, key=lambda r: r[1])
    symbols = [r[0] for r in sorted_rows]
    invested = [r[1] for r in sorted_rows]
    alloc_pct = [(v / total_invested * 100) if total_invested else 0.0 for v in invested]

    # Colour by distance to equal-weight target.
    def _alloc_color(v: float) -> str:
        ratio = (v / target_per_stock) if target_per_stock else 0.0
        if ratio < 0.50:
            return "#e74c3c"  # < 50% of target
        if ratio < 0.85:
            return "#f39c12"  # 50-85%
        if ratio <= 1.15:
            return "#27ae60"  # 85-115% (on target)
        return "#2980b9"      # > 115% (overweight)

    colors = [_alloc_color(v) for v in invested]

    fig, (ax, ax_info) = plt.subplots(
        1, 2, figsize=(17, max(7.5, n_stocks * 0.28 + 2.0)),
        gridspec_kw={"width_ratios": [4.9, 1.45]},
    )

    gap_to_target = [target_per_stock - v for v in invested]

    bars = ax.barh(symbols, invested, color=colors, edgecolor="white", linewidth=0.5)
    # Cap x-axis just past the target line — bars rarely exceed target, so
    # 1.40× of target_per_stock gives enough room for both inline labels
    # without leaving a wide empty zone to the right of the dotted line.
    x_max = max(max(invested) * 1.18, target_per_stock * 1.40 if target_per_stock else 1.0)
    ax.set_xlim(0, x_max)

    # Equal-weight target marker
    ax.axvline(target_per_stock, color="#34495e", linestyle="--", linewidth=1.0,
               label=f"Equal-weight target  {_fmt_inr(target_per_stock)}  ({equal_weight_pct:.1f}%)")

    for bar, v, pct, gap in zip(bars, invested, alloc_pct, gap_to_target):
        y_mid = bar.get_y() + bar.get_height() / 2

        # Invested % + amount label, anchored just past bar end
        ax.text(
            bar.get_width() + x_max * 0.008,
            y_mid,
            f"{pct:>4.1f}%  {_fmt_inr(v)}",
            va="center", ha="left", fontsize=8, color="#2c3e50",
        )

        # Compact "Need ₹X" label only for under-target stocks, anchored just
        # past the target dotted line so it doesn't crowd the invested label.
        if gap > 0:
            ax.text(
                target_per_stock + x_max * 0.012,
                y_mid,
                f"−{_fmt_inr(gap)}",
                va="center", ha="left", fontsize=7.5,
                color="#c0392b", fontweight="bold",
            )

    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax.set_xlabel("Invested Amount (₹)")
    ax.tick_params(axis="y", labelsize=8)
    ax.invert_yaxis()

    subtitle = (
        f"Target ₹15L total  ·  {_fmt_inr(target_per_stock)} per stock  ·  "
        f"{equal_weight_pct:.1f}% equal weight  ·  Current invested {_fmt_inr(total_invested)}"
    )
    ax.set_title(f"{title}\n{subtitle}", fontsize=12.5, fontweight="bold", pad=10)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)

    # Right-side summary + colour guide panel
    ratios = [(v / target_per_stock) if target_per_stock else 0.0 for v in invested]
    on_target = sum(1 for r in ratios if 0.85 <= r <= 1.15)
    over_weight = sum(1 for r in ratios if r > 1.15)
    under_weight = sum(1 for r in ratios if r < 0.85)
    total_deficit = sum(max(target_per_stock - v, 0.0) for v in invested)
    min_pct = min(alloc_pct) if alloc_pct else 0.0
    max_pct = max(alloc_pct) if alloc_pct else 0.0

    ax_info.axis("off")
    ax_info.text(0.02, 0.96, "SUMMARY", fontsize=10, fontweight="bold", ha="left", va="top")

    lines = [
        ("Target total", "₹15L"),
        ("Current invested", _fmt_inr(total_invested)),
        ("Still needed", _fmt_inr(max(target_total - total_invested, 0.0))),
        ("Total stocks", str(n_stocks)),
        ("Target per stock", _fmt_inr(target_per_stock)),
        ("Equal weight", f"{equal_weight_pct:.1f}%"),
        ("On target  ↔", str(on_target)),
        ("Over-weight  ↑", str(over_weight)),
        ("Under-weight  ↓", str(under_weight)),
        ("Total deficit", _fmt_inr(total_deficit)),
        ("Current range", f"{min_pct:.1f}% - {max_pct:.1f}%"),
    ]

    y = 0.90
    for label, value in lines:
        ax_info.text(0.02, y, label, fontsize=8, color="#555", ha="left", va="top")
        ax_info.text(0.98, y, value, fontsize=8, color="#111", ha="right", va="top", fontweight="bold")
        y -= 0.065

    ax_info.text(0.02, y - 0.02, "COLOUR GUIDE", fontsize=8.5, fontweight="bold", ha="left", va="top")
    # Render as 2x2 so both right-side categories stay visible.
    guide_grid = [
        (("#e74c3c", "< 50% of target"), ("#27ae60", "85 - 115% (on target)")),
        (("#f39c12", "50 - 85% of target"), ("#2980b9", "> 115% (over-weight)")),
    ]
    y -= 0.08
    row_h = 0.07
    left_x, right_x = 0.02, 0.52
    for left_item, right_item in guide_grid:
        for (box_x, (c, txt)) in ((left_x, left_item), (right_x, right_item)):
            ax_info.add_patch(plt.Rectangle(
                (box_x, y - 0.03), 0.06, 0.04,
                transform=ax_info.transAxes,
                facecolor=c,
                edgecolor="#999",
                linewidth=0.4,
            ))
            ax_info.text(
                box_x + 0.09,
                y - 0.01,
                txt,
                fontsize=7.3,
                color="#444",
                ha="left",
                va="center",
            )
        y -= row_h

    fig.tight_layout()


def plot_invested_vs_current(rows: list, title: str) -> None:
    """Grouped bar chart comparing Invested vs Current Value per stock.

    The Current Value bar is annotated with the P&L percentage so it is
    immediately visible whether each holding is up or down and by how much.

    Args:
        rows: List of (symbol, invested, cur_value, pnl) tuples.
        title: Chart title string.
    """
    symbols   = [r[0] for r in rows]
    invested  = [r[1] for r in rows]
    cur_value = [r[2] for r in rows]
    pnl       = [r[3] for r in rows]

    x = range(len(symbols))
    width = 0.4

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar([i - width / 2 for i in x], invested,  width, label="Invested",      color="#3498db", alpha=0.85)
    bars_cur = ax.bar([i + width / 2 for i in x], cur_value, width, label="Current Value", color="#9b59b6", alpha=0.85)

    # Annotate each Current Value bar with P&L % above the bar
    y_max = max(max(invested), max(cur_value)) if invested and cur_value else 1
    offset = y_max * 0.008
    for bar, inv, p in zip(bars_cur, invested, pnl):
        pnl_pct = (p / inv * 100) if inv else 0.0
        sign    = "+" if pnl_pct >= 0 else ""
        color   = "#1a7a3a" if pnl_pct >= 0 else "#c0392b"
        # Use the taller of the two bars so the label never overlaps either bar
        y_pos = max(bar.get_height(), inv) + offset
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y_pos,
            f"{sign}{pnl_pct:.1f}%",
            ha="center", va="bottom", fontsize=7.5, fontweight="bold", color=color,
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels(symbols, rotation=45, ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Amount (₹)")
    ax.legend()
    fig.tight_layout()


def plot_totals_table(f30_rows: list, excluded_rows: list) -> None:
    """Render a full detail + summary table for F30 and Excluded sections.

    Each section lists its individual stocks followed by a section-total row.
    A Grand Total row appears at the bottom.  P&L cells are colour-coded
    green (profit) or red (loss).

    Args:
        f30_rows: F30 portfolio rows.
        excluded_rows: Excluded holdings rows.
    """
    col_labels = ["#", "Symbol", "Cap", "Qty", "Invested (₹)", "Cur Value (₹)", "P&L (₹)", "P&L %"]
    n_cols = len(col_labels)

    table_rows: list  = []
    row_colors: list  = []
    bold_rows:  list  = []   # 1-based indices (header = 0) that need bold text
    white_text: list  = []   # section-header rows whose text should be white
    serial: list      = [0]  # mutable counter shared across sections

    # Cap-tier sort order and background colours
    _CAP_RANK   = {"Large": 0, "Mid": 1, "Small": 2}
    _CAP_COLORS = {
        "Large": "#d6eaf8",   # soft blue
        "Mid":   "#e8daef",   # soft lavender
        "Small": "#fdebd0",   # soft peach
    }
    _CAP_FALLBACK = "#eaecee"  # light grey for Unknown / anything else

    def _pnl_color(pnl: float) -> str:
        return "#d5f5e3" if pnl >= 0 else "#fadbd8"

    def _add_section(label: str, rows: list, base_color: str, hdr_color: str):
        """Append one section (header + stock rows + totals) to the table."""
        # Section header row — no serial number
        table_rows.append(["", label, "", "", "", "", "", ""])
        row_colors.append([hdr_color] * n_cols)
        white_text.append(len(table_rows))  # 1-based after header offset

        # Sort by cap tier (Large → Mid → Small → other), then alphabetically
        sorted_rows = sorted(rows, key=lambda r: (_CAP_RANK.get(r[4], 3), r[0]))

        sec_inv = sec_cur = sec_pnl = 0.0
        for symbol, invested, cur_value, pnl, cap, qty in sorted_rows:
            serial[0] += 1
            pnl_pct = (pnl / invested * 100) if invested else 0.0
            pc = _pnl_color(pnl)
            row_base = _CAP_COLORS.get(cap, _CAP_FALLBACK)
            table_rows.append([
                str(serial[0]),
                symbol,
                cap,
                f"{qty:.0f}",
                f"{invested:,.2f}",
                f"{cur_value:,.2f}",
                f"{pnl:,.2f}",
                f"{pnl_pct:.2f}%",
            ])
            row_colors.append([row_base] * 6 + [pc, pc])   # 8 cols now
            sec_inv += invested
            sec_cur += cur_value
            sec_pnl += pnl

        sec_pct = (sec_pnl / sec_inv * 100) if sec_inv else 0.0
        pc = _pnl_color(sec_pnl)
        tint = "#aed6f1" if base_color == "#d6eaf8" else "#fad7a0"
        table_rows.append([
            "",
            "TOTAL",
            "",
            "",
            f"{sec_inv:,.2f}",
            f"{sec_cur:,.2f}",
            f"{sec_pnl:,.2f}",
            f"{sec_pct:.2f}%",
        ])
        row_colors.append([tint] * 6 + [pc, pc])
        bold_rows.append(len(table_rows))

        return sec_inv, sec_cur, sec_pnl

    f30_inv, f30_cur, f30_pnl = _add_section(
        "── Finology 30 Portfolio ──", f30_rows, "#d6eaf8", "#2980b9"
    )
    serial[0] = 0  # restart numbering for the excluded section
    exc_inv, exc_cur, exc_pnl = _add_section(
        "── Excluded (Gold / Cases / IPO / Bonus) ──", excluded_rows, "#fef9e7", "#e67e22"
    )

    # Grand Total row
    all_inv = f30_inv + exc_inv
    all_cur = f30_cur + exc_cur
    all_pnl = f30_pnl + exc_pnl
    all_pct = (all_pnl / all_inv * 100) if all_inv else 0.0
    pc = _pnl_color(all_pnl)
    table_rows.append([
        "",
        "GRAND TOTAL",
        "",
        "",
        f"{all_inv:,.2f}",
        f"{all_cur:,.2f}",
        f"{all_pnl:,.2f}",
        f"{all_pct:.2f}%",
    ])
    row_colors.append(["#d5d8dc"] * 6 + [pc, pc])
    bold_rows.append(len(table_rows))

    # Figure height scales with number of rows
    fig_height = max(5, len(table_rows) * 0.38 + 1.2)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    ax.axis("off")

    tbl = ax.table(
        cellText=table_rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        cellColours=row_colors,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(12)
    tbl.auto_set_column_width(col=list(range(n_cols)))  # size each column to its widest content
    tbl.scale(1, 1.45)  # xscale=1 keeps column widths; only row heights change

    # Style column header (row index 0)
    for col in range(n_cols):
        tbl[(0, col)].set_facecolor("#2c3e50")
        tbl[(0, col)].set_text_props(color="white", fontweight="bold")

    # White text on coloured section-header rows
    for idx in white_text:
        for col in range(n_cols):
            tbl[(idx, col)].set_text_props(color="white", fontweight="bold")

    # Bold section-total and grand-total rows
    for idx in bold_rows:
        for col in range(n_cols):
            tbl[(idx, col)].set_text_props(fontweight="bold")

    ax.set_title(
        "Equity Portfolio Details & Totals Summary",
        fontsize=20, fontweight="bold", pad=14, loc="center",
    )

    # Add small colour patches to make the legend readable
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor="#d6eaf8", edgecolor="#999", label="Large cap"),
        Patch(facecolor="#e8daef", edgecolor="#999", label="Mid cap"),
        Patch(facecolor="#fdebd0", edgecolor="#999", label="Small cap"),
        Patch(facecolor="#eaecee", edgecolor="#999", label="Other / Unknown"),
        Patch(facecolor="#d5f5e3", edgecolor="#999", label="Profit (P&L)"),
        Patch(facecolor="#fadbd8", edgecolor="#999", label="Loss (P&L)"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.02),
        ncol=6,
        fontsize=16,
        framealpha=0.9,
        edgecolor="#cccccc",
    )
    fig.tight_layout()


def plot_summary_overview(f30_rows: list, excluded_rows: list) -> None:
    """Side-by-side grouped bar chart comparing F30 vs Excluded portfolio totals.

    Shows Invested, Current Value, and P&L for both groups.

    Args:
        f30_rows: F30 portfolio rows.
        excluded_rows: Excluded holdings rows which are not part of the F30 portfolio.
    """
    def totals(rows):
        return (
            sum(r[1] for r in rows),   # invested
            sum(r[2] for r in rows),   # cur_value
            sum(r[3] for r in rows),   # pnl
        )

    f30_inv, f30_cur, f30_pnl         = totals(f30_rows)
    exc_inv, exc_cur, exc_pnl         = totals(excluded_rows)

    categories = ["Invested", "Current Value", "P&L"]
    f30_vals   = [f30_inv, f30_cur, f30_pnl]
    exc_vals   = [exc_inv, exc_cur, exc_pnl]

    x = range(len(categories))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - width / 2 for i in x], f30_vals, width, label="F30 Portfolio",     color="#2980b9", alpha=0.9)
    ax.bar([i + width / 2 for i in x], exc_vals, width, label="GoldETF + Others Holdings", color="#f39c12", alpha=0.9)

    # Annotate bars
    for i, (fv, ev) in enumerate(zip(f30_vals, exc_vals)):
        ax.text(i - width / 2, fv + max(f30_vals) * 0.01, _fmt_inr(fv), ha="center", fontsize=9)
        ax.text(i + width / 2, ev + max(f30_vals) * 0.01, _fmt_inr(ev), ha="center", fontsize=9)

    ax.set_xticks(list(x))
    ax.set_xticklabels(categories)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax.set_title("Portfolio Overview: F30 vs GoldETF + Others Holdings", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Amount (₹)")
    ax.legend()
    fig.tight_layout()


# ---------------------------------------------------------------------------
# Mutual Fund visualisation helpers
# ---------------------------------------------------------------------------

def plot_mf_gain_bar(mf_rows: list, title: str) -> None:
    """Chart 6: Horizontal bar showing absolute Gain (₹) per fund, annotated with Gain %.

    Sorted by absolute gain descending so the best-performing fund appears at the top.

    Args:
        mf_rows: List of (fund, qty, avg, nav, invested, cur_value, gain, gain_pct, category).
        title: Chart title string.
    """
    sorted_rows = sorted(mf_rows, key=lambda r: r[6], reverse=True)
    labels    = [_short_fund_name(r[0]) for r in sorted_rows]
    gains     = [r[6] for r in sorted_rows]
    gain_pcts = [r[7] for r in sorted_rows]
    colors    = ["#2ecc71" if g >= 0 else "#e74c3c" for g in gains]

    fig, ax = plt.subplots(figsize=(12, max(6, len(labels) * 0.45)))
    bars = ax.barh(labels, gains, color=colors, edgecolor="white", linewidth=0.5)

    gain_range = (max(gains) - min(gains)) or 1
    offset = gain_range * 0.01
    for bar, val, pct in zip(bars, gains, gain_pcts):
        x = bar.get_width()
        if val >= 0:
            x_pos, ha = x + offset, "left"
        else:
            # Place label just to the right of the zero line so it doesn't
            # overlap with the bar or the dotted axis line.
            x_pos, ha = offset, "left"
        ax.text(
            x_pos, bar.get_y() + bar.get_height() / 2,
            f"{_fmt_inr(val)}  ({pct:+.1f}%)", va="center", ha=ha, fontsize=8,
            color="#1a7a3a" if val >= 0 else "#c0392b",
        )

    ax.axvline(0, color="grey", linewidth=0.8, linestyle="--")
    ax.set_xlim(right=max(gains) * 1.55)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Gain / Loss (₹)")
    ax.invert_yaxis()
    fig.tight_layout()


def plot_mf_category_breakdown(mf_rows: list, title: str) -> None:
    """Chart 7: Grouped bar showing Invested vs Current Value per MF category.

    Bars are annotated with category-level gain % above the Current Value bar.

    Args:
        mf_rows: List of (fund, qty, avg, nav, invested, cur_value, gain, gain_pct, category).
        title: Chart title string.
    """
    cat_data: dict = {}
    for _, _, _, _, invested, cur_value, *_, category in mf_rows:
        short_cat = category.split(" - ", 1)[-1] if " - " in category else category
        if short_cat not in cat_data:
            cat_data[short_cat] = [0.0, 0.0]
        cat_data[short_cat][0] += invested
        cat_data[short_cat][1] += cur_value

    cats     = sorted(cat_data, key=lambda c: cat_data[c][0], reverse=True)
    inv_vals = [cat_data[c][0] for c in cats]
    cur_vals = [cat_data[c][1] for c in cats]

    x = range(len(cats))
    width = 0.4

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar([i - width / 2 for i in x], inv_vals, width, label="Invested",      color="#3498db", alpha=0.85)
    bars_cur = ax.bar([i + width / 2 for i in x], cur_vals, width, label="Current Value", color="#27ae60", alpha=0.85)

    y_max = max(max(inv_vals), max(cur_vals)) if inv_vals and cur_vals else 1
    offset = y_max * 0.008
    for bar, inv, cur in zip(bars_cur, inv_vals, cur_vals):
        gain_pct = ((cur - inv) / inv * 100) if inv else 0.0
        sign  = "+" if gain_pct >= 0 else ""
        color = "#1a7a3a" if gain_pct >= 0 else "#c0392b"
        y_pos = max(bar.get_height(), inv) + offset
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y_pos,
            f"{sign}{gain_pct:.1f}%",
            ha="center", va="bottom", fontsize=8, fontweight="bold", color=color,
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels([c[:22] for c in cats], rotation=30, ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Amount (₹)")
    ax.legend()
    fig.tight_layout()


def plot_mf_table(mf_rows: list) -> None:
    """Chart 8: Detailed MF table grouped by fund category with colour-coded gain cells.

    Each category section lists its funds followed by a subtotal row.
    A Grand Total row appears at the bottom.

    Args:
        mf_rows: List of (fund, qty, avg, nav, invested, cur_value, gain, gain_pct, category).
    """
    col_labels = ["#", "Fund", "Invested (₹)", "Cur Value (₹)", "Gain (₹)", "Gain %"]
    n_cols = len(col_labels)

    table_rows: list = []
    row_colors: list = []
    bold_rows:  list = []
    white_text: list = []

    def _gain_color(gain: float) -> str:
        return "#d5f5e3" if gain >= 0 else "#fadbd8"

    # Group rows by short category name
    cat_groups: dict = {}
    for row in mf_rows:
        cat = row[8].split(" - ", 1)[-1] if " - " in row[8] else row[8]
        cat_groups.setdefault(cat, []).append(row)

    # Sort categories by total invested descending
    sorted_cats = sorted(cat_groups, key=lambda c: sum(r[4] for r in cat_groups[c]), reverse=True)

    hdr_palette = [
        "#2980b9", "#27ae60", "#8e44ad", "#c0392b",
        "#16a085", "#d35400", "#2c3e50", "#7f8c8d",
    ]
    base_palette = ["#eaf4fb", "#eafaf1", "#f5eef8", "#fdedec",
                    "#e8f8f5", "#fef5e7", "#eaecee", "#f2f3f4"]

    total_all_inv = total_all_cur = total_all_gain = 0.0
    serial = 0

    for cat_idx, cat in enumerate(sorted_cats):
        rows      = cat_groups[cat]
        hdr_color  = hdr_palette[cat_idx % len(hdr_palette)]
        base_color = base_palette[cat_idx % len(base_palette)]

        # Category header row
        table_rows.append(["", f"── {cat} ──", "", "", "", ""])
        row_colors.append([hdr_color] * n_cols)
        white_text.append(len(table_rows))

        cat_inv = cat_cur = cat_gain = 0.0
        for fund, qty, avg, nav, invested, cur_value, gain, gain_pct, category in rows:
            serial += 1
            pc = _gain_color(gain)
            table_rows.append([
                str(serial),
                _short_fund_name(fund),
                f"{invested:,.2f}",
                f"{cur_value:,.2f}",
                f"{gain:,.2f}",
                f"{gain_pct:.2f}%",
            ])
            row_colors.append([base_color] * 4 + [pc, pc])
            cat_inv  += invested
            cat_cur  += cur_value
            cat_gain += gain

        cat_gain_pct = (cat_gain / cat_inv * 100) if cat_inv else 0.0
        pc = _gain_color(cat_gain)
        tint = hdr_palette[cat_idx % len(hdr_palette)] + "44"  # unused; use fixed tints below
        tint_colors = ["#aed6f1", "#a9dfbf", "#d2b4de", "#f1948a",
                       "#76d7c4", "#f0b27a", "#abb2b9", "#bfc9ca"]
        tint = tint_colors[cat_idx % len(tint_colors)]
        table_rows.append(["", "SUBTOTAL", f"{cat_inv:,.2f}", f"{cat_cur:,.2f}", f"{cat_gain:,.2f}", f"{cat_gain_pct:.2f}%"])
        row_colors.append([tint] * 4 + [pc, pc])
        bold_rows.append(len(table_rows))

        total_all_inv  += cat_inv
        total_all_cur  += cat_cur
        total_all_gain += cat_gain

    # Grand Total
    all_gain_pct = (total_all_gain / total_all_inv * 100) if total_all_inv else 0.0
    pc = _gain_color(total_all_gain)
    table_rows.append(["", "GRAND TOTAL", f"{total_all_inv:,.2f}", f"{total_all_cur:,.2f}", f"{total_all_gain:,.2f}", f"{all_gain_pct:.2f}%"])
    row_colors.append(["#d5d8dc"] * 4 + [pc, pc])
    bold_rows.append(len(table_rows))

    fig_height = max(5, len(table_rows) * 0.38 + 1.2)
    fig, ax = plt.subplots(figsize=(15, fig_height))
    ax.axis("off")

    tbl = ax.table(
        cellText=table_rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        cellColours=row_colors,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.auto_set_column_width(col=list(range(n_cols)))
    tbl.scale(1, 1.45)

    for col in range(n_cols):
        tbl[(0, col)].set_facecolor("#2c3e50")
        tbl[(0, col)].set_text_props(color="white", fontweight="bold")

    for idx in white_text:
        for col in range(n_cols):
            tbl[(idx, col)].set_text_props(color="white", fontweight="bold")

    for idx in bold_rows:
        for col in range(n_cols):
            tbl[(idx, col)].set_text_props(fontweight="bold")

    ax.set_title("Mutual Fund Portfolio — Details by Category", fontsize=13, fontweight="bold", pad=14, loc="center")
    fig.tight_layout()


# ---------------------------------------------------------------------------
# New insight chart functions (Charts 9–15)
# ---------------------------------------------------------------------------

def plot_winners_losers_panel(f30_rows: list) -> None:
    """Chart 9: Strike rate stats panel + top-5 winners and top-5 losers bars.

    Args:
        f30_rows: List of (symbol, invested, cur_value, pnl, cap) tuples.
    """
    winners = sorted([(r[0], r[3]) for r in f30_rows if r[3] >= 0], key=lambda x: x[1], reverse=True)
    losers  = sorted([(r[0], r[3]) for r in f30_rows if r[3] < 0],  key=lambda x: x[1])

    strike_rate  = len(winners) / len(f30_rows) * 100 if f30_rows else 0
    total_profit = sum(p for _, p in winners)
    total_loss   = sum(p for _, p in losers)
    best  = winners[0] if winners else ("—", 0)
    worst = losers[0]  if losers  else ("—", 0)

    fig, axes = plt.subplots(1, 3, figsize=(17, max(5, len(winners[:5]) * 0.55 + 2)))

    # Panel 1 — stats table
    ax0 = axes[0]
    ax0.axis("off")
    net_pnl = total_profit + total_loss
    stats = [
        ("Total Stocks",  str(len(f30_rows))),
        ("Winners  ↑",    str(len(winners))),
        ("Losers   ↓",    str(len(losers))),
        ("Strike Rate",   f"{strike_rate:.1f}%"),
        ("Total Profit",  _fmt_inr(total_profit)),
        ("Total Loss",    _fmt_inr(total_loss)),
        ("Net P&L",       _fmt_inr(net_pnl)),
        ("Best Stock",    f"{best[0]}  {_fmt_inr(best[1])}"),
        ("Worst Stock",   f"{worst[0]}  {_fmt_inr(worst[1])}"),
    ]

    cell_text   = [[label, val] for label, val in stats]
    cell_colors = []
    for label, _ in stats:
        if label == "Total Profit":
            cell_colors.append(["#eafaf1", "#d5f5e3"])
        elif label == "Total Loss":
            cell_colors.append(["#fef9e7", "#fadbd8"])
        elif label == "Net P&L":
            cell_colors.append(["#eaf4fb", "#d5f5e3" if net_pnl >= 0 else "#fadbd8"])
        elif label == "Winners  ↑":
            cell_colors.append(["#eafaf1", "#eafaf1"])
        elif label == "Losers   ↓":
            cell_colors.append(["#fef5e7", "#fef5e7"])
        else:
            cell_colors.append(["#f2f3f4", "#f8f9fa"])

    tbl = ax0.table(
        cellText=cell_text,
        cellLoc="center",
        loc="center",
        cellColours=cell_colors,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 2.0)

    # Style each cell: left-align labels, right-align values, bold values
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#bdc3c7")
        cell.set_linewidth(0.6)
        if col == 0:
            cell.get_text().set_ha("left")
            cell.get_text().set_fontweight("bold")
            cell.PAD = 0.08
        else:
            cell.get_text().set_ha("right")
            cell.PAD = 0.08

    ax0.set_title("F30 Portfolio Stats", fontsize=12, fontweight="bold", pad=10)

    # Panel 2 — top 5 winners
    ax1 = axes[1]
    top5_w = winners[:5]
    syms_w = [r[0] for r in top5_w]
    vals_w = [r[1] for r in top5_w]
    ax1.barh(syms_w, vals_w, color="#2ecc71", edgecolor="white")
    for bar, val in zip(ax1.patches, vals_w):
        ax1.text(val / 2, bar.get_y() + bar.get_height() / 2,
                 _fmt_inr(val), va="center", ha="center", fontsize=9,
                 color="white", fontweight="bold")
    ax1.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax1.invert_yaxis()
    ax1.set_title("Top 5 Winners", fontsize=11, fontweight="bold")

    # Panel 3 — top 5 losers
    ax2 = axes[2]
    top5_l = losers[:5]
    syms_l = [r[0] for r in top5_l]
    vals_l = [r[1] for r in top5_l]
    ax2.barh(syms_l, vals_l, color="#e74c3c", edgecolor="white")
    for bar, val in zip(ax2.patches, vals_l):
        ax2.text(val / 2, bar.get_y() + bar.get_height() / 2,
                 _fmt_inr(val), va="center", ha="center", fontsize=9,
                 color="white", fontweight="bold")
    ax2.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax2.axvline(0, color="grey", linewidth=0.8, linestyle="--")
    ax2.invert_yaxis()
    ax2.set_title("Top 5 Losers", fontsize=11, fontweight="bold")

    fig.suptitle("F30 Portfolio — Winners & Losers Analysis", fontsize=13, fontweight="bold")
    fig.tight_layout()


def plot_cap_tier_bar(f30_rows: list, title: str) -> None:
    """Chart 10: Grouped bar comparing Invested vs Current Value by market cap tier.

    Args:
        f30_rows: List of (symbol, invested, cur_value, pnl, cap) tuples.
        title: Chart title string.
    """
    cap_data: dict = {}
    for symbol, invested, cur_value, pnl, cap, *_ in f30_rows:
        cap_data.setdefault(cap, [0.0, 0.0])
        cap_data[cap][0] += invested
        cap_data[cap][1] += cur_value

    order = [c for c in ["Large", "Mid", "Small", "Unknown"] if c in cap_data]
    inv_vals = [cap_data[c][0] for c in order]
    cur_vals = [cap_data[c][1] for c in order]

    x = range(len(order))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - width / 2 for i in x], inv_vals, width, label="Invested",      color="#3498db", alpha=0.85)
    bars = ax.bar([i + width / 2 for i in x], cur_vals, width, label="Current Value", color="#2ecc71", alpha=0.85)

    y_max = max(max(inv_vals), max(cur_vals)) if inv_vals and cur_vals else 1
    for bar, inv, cur in zip(bars, inv_vals, cur_vals):
        gain_pct = ((cur - inv) / inv * 100) if inv else 0.0
        color = "#1a7a3a" if gain_pct >= 0 else "#c0392b"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + y_max * 0.01,
                f"{gain_pct:+.1f}%", ha="center", fontsize=10, fontweight="bold", color=color)

    ax.set_xticks(list(x))
    ax.set_xticklabels(order)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Amount (₹)")
    ax.legend()
    fig.tight_layout()


def plot_sector_pie(eq_full_rows: list, title: str) -> None:
    """Chart 11: Pie chart of F30 portfolio allocation by GICS sector (invested ₹).

    Args:
        eq_full_rows: List of dicts with keys Symbol, Invested, Sector.
        title: Chart title string.
    """
    sector_inv: dict = {}
    for r in eq_full_rows:
        sec = r.get("Sector") or "Unknown"
        sector_inv[sec] = sector_inv.get(sec, 0.0) + r["Invested"]

    if not sector_inv:
        return

    labels = list(sector_inv.keys())
    values = list(sector_inv.values())
    total  = sum(values)

    fig, ax = plt.subplots(figsize=(10, 9))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.1f%%",
        startangle=140, pctdistance=0.80,
        wedgeprops={"linewidth": 0.6, "edgecolor": "white"},
    )
    for t in autotexts:
        t.set_fontsize(8)
    ax.set_title(
        f"{title}\n(Total Invested ₹{total:,.0f})",
        fontsize=13, fontweight="bold", pad=16,
    )
    fig.tight_layout()


def plot_52w_range(eq_full_rows: list, title: str) -> None:
    """Chart 12: Normalised 52-week range chart — LTP shown as % position within range.

    Each bar spans 0 % (52W Low) to 100 % (52W High). The diamond marks the LTP
    and the vertical bar marks the average buy price.  Sorted by LTP % position
    (lowest first) to highlight the most beaten-down stocks at the top.

    Args:
        eq_full_rows: List of dicts with keys Symbol, LTP, Avg, 52W High, 52W Low.
        title: Chart title string.
    """
    valid = [
        (r["Symbol"], r["LTP"], r["Avg"], r["52W Low"], r["52W High"])
        for r in eq_full_rows
        if r.get("52W High", 0) > 0 and r.get("52W Low", 0) > 0 and r["52W High"] > r["52W Low"]
    ]
    if not valid:
        return

    def _pct(val, lo, hi):
        return (val - lo) / (hi - lo) * 100 if hi > lo else 50.0

    valid.sort(key=lambda r: _pct(r[1], r[3], r[4]))

    fig, ax = plt.subplots(figsize=(13, max(6, len(valid) * 0.44)))

    for i, (sym, ltp, avg, lo, hi) in enumerate(valid):
        ltp_pct      = _pct(ltp, lo, hi)
        avg_pct      = _pct(avg, lo, hi)
        pct_from_hi  = (ltp - hi) / hi * 100
        fill_color   = "#2ecc71" if ltp >= avg else "#e74c3c"

        ax.barh(i, 100, left=0, height=0.55, color="#ecf0f1",
                edgecolor="#bdc3c7", linewidth=0.5, zorder=1)
        ax.barh(i, ltp_pct, left=0, height=0.55, color=fill_color,
                alpha=0.45, zorder=2)
        ax.scatter(ltp_pct, i, color=fill_color, zorder=4, s=60, marker="D")
        ax.scatter(avg_pct, i, color="#2c3e50",  zorder=3, s=50, marker="|", linewidths=2)
        ax.text(103, i, f"₹{ltp:,.1f}  ({pct_from_hi:+.1f}% from 52W H)",
                va="center", fontsize=7.5)

    ax.set_yticks(range(len(valid)))
    ax.set_yticklabels([r[0] for r in valid], fontsize=8.5)
    ax.set_xlim(0, 150)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["52W Low", "25%", "Mid", "75%", "52W High"])
    ax.axvline(50, color="#bdc3c7", linewidth=0.7, linestyle="--")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Position in 52-Week Range  (◆ LTP  |  ▌ Avg Cost)")

    legend_els = [
        mpatches.Patch(facecolor="#2ecc71", alpha=0.6, label="LTP ≥ Avg Cost (above water)"),
        mpatches.Patch(facecolor="#e74c3c", alpha=0.6, label="LTP < Avg Cost (in loss)"),
    ]
    ax.legend(handles=legend_els, loc="lower right", fontsize=9)
    fig.tight_layout()


def plot_annual_dividend(eq_full_rows: list, title: str) -> None:
    """Chart 13: Estimated annual dividend income per F30 stock (Invested × DivYield%).

    Args:
        eq_full_rows: List of dicts with keys Symbol, Invested, DivYield%.
        title: Chart title string.
    """
    rows = [
        (r["Symbol"], round(r["Invested"] * r.get("DivYield%", 0) / 100, 2))
        for r in eq_full_rows
        if r.get("DivYield%", 0) > 0
    ]
    if not rows:
        return

    rows.sort(key=lambda r: r[1], reverse=True)
    symbols = [r[0] for r in rows]
    income  = [r[1] for r in rows]
    total   = sum(income)

    fig, ax = plt.subplots(figsize=(10, max(4, len(symbols) * 0.42)))
    bars = ax.barh(symbols, income, color="#3498db", edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, income):
        ax.text(val + total * 0.004, bar.get_y() + bar.get_height() / 2,
                _fmt_inr(val), va="center", fontsize=9)

    ax.set_xlim(right=max(income) * 1.40)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_inr))
    ax.set_title(f"{title}  —  Est. Total: {_fmt_inr(total)}/yr",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Estimated Annual Dividend Income (₹)")
    ax.invert_yaxis()
    fig.tight_layout()


def plot_asset_allocation_overview(f30_rows: list, excluded_rows: list, mf_rows: list) -> None:
    """Chart 14: Full-portfolio asset allocation pie across all asset classes.

    Groups investments into: F30 Equity, Gold ETFs, Smallcases, Other Equity,
    MF Equity, MF Index Funds, MF Debt, and MF Other.

    Args:
        f30_rows:       List of (symbol, invested, cur_value, pnl, cap) for F30 stocks.
        excluded_rows:  List of (symbol, invested, cur_value, pnl, cap) for excluded holdings.
        mf_rows:        MF rows tuple (fund, qty, avg, nav, invested, cur_value, gain, gain_pct, category).
    """
    gold_syms  = set(GOLD_ETF)
    cases_syms = set(CASES)

    f30_invested   = sum(r[1] for r in f30_rows)
    gold_invested  = sum(r[1] for r in excluded_rows if r[0] in gold_syms)
    cases_invested = sum(r[1] for r in excluded_rows if r[0] in cases_syms)
    other_equity   = sum(r[1] for r in excluded_rows
                         if r[0] not in gold_syms and r[0] not in cases_syms)

    debt_kw   = ("liquid", "ultra short", "short duration", "money market", "overnight", "debt")
    index_kw  = ("index", "sensex", "nifty")
    equity_kw = ("large cap", "mid cap", "small cap", "flexi cap", "large & mid", "multi cap")

    mf_equity = mf_index = mf_debt = mf_other = 0.0
    for row in mf_rows:
        cat_lower = row[8].lower()
        invested  = row[4]
        if any(k in cat_lower for k in debt_kw):
            mf_debt   += invested
        elif any(k in cat_lower for k in index_kw):
            mf_index  += invested
        elif any(k in cat_lower for k in equity_kw):
            mf_equity += invested
        else:
            mf_other  += invested

    asset_classes = [
        ("F30 Equity",   f30_invested,   "#2980b9"),
        ("Gold ETFs",    gold_invested,  "#f1c40f"),
        ("Smallcases",   cases_invested, "#e67e22"),
        ("Other Equity", other_equity,   "#8e44ad"),
        ("MF — Equity",  mf_equity,      "#27ae60"),
        ("MF — Index",   mf_index,       "#16a085"),
        ("MF — Debt",    mf_debt,        "#2c3e50"),
        ("MF — Other",   mf_other,       "#95a5a6"),
    ]
    labels = [a[0] for a in asset_classes if a[1] > 0]
    values = [a[1] for a in asset_classes if a[1] > 0]
    colors = [a[2] for a in asset_classes if a[1] > 0]
    total  = sum(values)

    fig, ax = plt.subplots(figsize=(11, 9))
    # Use labels=None to prevent crowded inline text; legend handles labels instead.
    wedges, _, autotexts = ax.pie(
        values,
        labels=None,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 4 else "",
        startangle=140,
        pctdistance=0.72,
        wedgeprops={"linewidth": 0.6, "edgecolor": "white"},
        colors=colors,
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_fontweight("bold")

    # Build an informative legend: colour patch + label + invested amount + %
    legend_labels = [
        f"{lbl}  —  ₹{val:,.0f}  ({val / total * 100:.1f}%)"
        for lbl, val in zip(labels, values)
    ]
    ax.legend(
        wedges, legend_labels,
        title="Asset Class",
        title_fontsize=9,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=9,
        framealpha=0.9,
    )
    ax.set_title(
        f"Full Portfolio Asset Allocation\n(Total Invested ₹{total:,.0f})",
        fontsize=13, fontweight="bold", pad=16,
    )
    fig.tight_layout(rect=[0, 0, 0.78, 1])


def plot_sip_dashboard(sip_rows: list) -> None:
    """Chart 15: Table chart showing all SIPs with key details.

    Args:
        sip_rows: List of dicts with keys Fund, Amount, Frequency, Completed,
                  Instalments, Pending, Next Instalment, Status.
    """
    if not sip_rows:
        return

    col_labels = ["Fund", "Amount (₹)", "Frequency", "Done / Total", "Pending", "Next Date", "Status"]
    n_cols = len(col_labels)

    table_rows: list = []
    row_colors: list = []
    monthly_total = 0.0

    for r in sip_rows:
        fund = r.get("Fund", "")
        for sfx in (" - DIRECT  PLAN", " - DIRECT PLAN"):
            fund = fund.replace(sfx, "")
        fund = fund[:42]

        status     = str(r.get("Status", "")).lower()
        frequency  = str(r.get("Frequency", "")).lower()
        base_color = "#eafaf1" if status == "active" else "#fef9e7"
        amount     = float(r["Amount"]) if r.get("Amount") else 0.0

        table_rows.append([
            fund,
            f"{amount:,.0f}",
            str(r.get("Frequency", "")).capitalize(),
            f"{r.get('Completed','0')} / {r.get('Instalments','0')}",
            str(r.get("Pending", "")),
            str(r.get("Next Instalment", ""))[:10],
            str(r.get("Status", "")).upper(),
        ])
        row_colors.append([base_color] * n_cols)

        if status == "active" and frequency == "monthly":
            monthly_total += amount

    # Summary row
    table_rows.append([f"Monthly SIP Total (Active)", f"₹{monthly_total:,.0f}", "", "", "", "", ""])
    row_colors.append(["#d6eaf8"] * n_cols)

    fig_height = max(4, len(table_rows) * 0.48 + 1.5)
    fig, ax = plt.subplots(figsize=(15, fig_height))
    ax.axis("off")

    tbl = ax.table(
        cellText=table_rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        cellColours=row_colors,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.auto_set_column_width(col=list(range(n_cols)))
    tbl.scale(1, 1.55)

    for col in range(n_cols):
        tbl[(0, col)].set_facecolor("#2c3e50")
        tbl[(0, col)].set_text_props(color="white", fontweight="bold")

    # Bold the summary row
    for col in range(n_cols):
        tbl[(len(table_rows), col)].set_text_props(fontweight="bold")

    ax.set_title("Mutual Fund SIP Dashboard", fontsize=13, fontweight="bold", pad=14)
    fig.tight_layout()


def plot_weighted_beta(eq_full_rows: list) -> None:
    """Chart 16: Weighted portfolio beta panel.

    Displays each F30 stock's beta alongside a summary showing the
    portfolio-level weighted-average beta (weight = invested ₹).
    Stocks with beta > 1 are high-volatility (amplify market moves);
    beta < 1 dampens them.

    Args:
        eq_full_rows: List of dicts with keys Symbol, Invested, Beta.
    """
    valid = [(r["Symbol"], r["Invested"], r.get("Beta", 0))
             for r in eq_full_rows if r.get("Beta", 0) != 0]
    if not valid:
        return

    total_invested = sum(r[1] for r in valid)
    weighted_beta  = sum(r[1] * r[2] for r in valid) / total_invested if total_invested else 0.0

    # Sort by beta descending
    valid.sort(key=lambda r: r[2], reverse=True)
    symbols = [r[0] for r in valid]
    betas   = [r[2] for r in valid]
    weights = [r[1] / total_invested * 100 for r in valid]
    colors  = ["#e74c3c" if b > 1.2 else "#f39c12" if b > 1.0 else "#2ecc71" for b in betas]

    fig, (ax_bar, ax_info) = plt.subplots(1, 2, figsize=(16, max(7, len(valid) * 0.45 + 1)),
                                           gridspec_kw={"width_ratios": [3, 1]})

    bars = ax_bar.barh(symbols, betas, color=colors, edgecolor="white", linewidth=0.5)

    # Compute axis limits first so label offset is proportional to the data range
    max_beta   = max(betas)
    min_beta   = min(betas)
    beta_range = (max_beta - min_beta) or 1.0
    offset     = beta_range * 0.015          # small gap between bar end and label
    right_lim  = max_beta + beta_range * 0.50  # room for label text on the right
    left_lim   = min(0.0, min_beta) - beta_range * 0.08  # show negative bars

    for bar, b, w in zip(bars, betas, weights):
        # Always anchor label just right of bar end (positive) or just right of
        # x=0 (negative), so EIHOTEL/ITC/WONDERLA labels never crowd each other.
        x_pos = (b + offset) if b >= 0 else offset
        ax_bar.text(x_pos, bar.get_y() + bar.get_height() / 2,
                    f"β={b:.2f}  ({w:.1f}%)", va="center", ha="left", fontsize=8)

    ax_bar.axvline(1.0, color="#2c3e50", linewidth=1.2, linestyle="--", label="Market β = 1")
    ax_bar.axvline(weighted_beta, color="#8e44ad", linewidth=1.5, linestyle="-",
                   label=f"Portfolio β = {weighted_beta:.2f}")
    ax_bar.set_xlim(left=left_lim, right=right_lim)
    ax_bar.set_title("F30 Portfolio — Stock Betas (weight = invested ₹)",
                     fontsize=12, fontweight="bold", pad=10)
    ax_bar.set_xlabel("Beta")
    ax_bar.invert_yaxis()
    ax_bar.legend(fontsize=9)

    # Summary info panel
    ax_info.axis("off")
    high_beta  = [(s, b) for s, _, b in valid if b > 1.2]
    low_beta   = [(s, b) for s, _, b in valid if b < 0.8]
    lines = [
        ("Portfolio β",   f"{weighted_beta:.2f}"),
        ("Market β",      "1.00"),
        ("High β (>1.2)", str(len(high_beta))),
        ("Low β (<0.8)",  str(len(low_beta))),
    ]
    ax_info.text(0.5, 1.0, "Beta Summary", ha="center", va="top",
                 fontsize=11, fontweight="bold", transform=ax_info.transAxes)
    y = 0.85
    for label, val in lines:
        ax_info.text(0.05, y, label, ha="left",  va="top", fontsize=10, transform=ax_info.transAxes)
        ax_info.text(0.95, y, val,   ha="right", va="top", fontsize=10, transform=ax_info.transAxes)
        y -= 0.13
    if high_beta:
        ax_info.text(0.05, y - 0.03, "High β stocks:",
                     ha="left", va="top", fontsize=9, fontweight="bold",
                     transform=ax_info.transAxes, color="#c0392b")
        y -= 0.14
        for sym, b in high_beta:
            ax_info.text(0.08, y, f"{sym}  β={b:.2f}",
                         ha="left", va="top", fontsize=8.5, transform=ax_info.transAxes)
            y -= 0.10
    ax_info.set_facecolor("#f8f9fa")
    fig.tight_layout()


def plot_portfolio_insights(
    f30_rows: list,
    excluded_rows: list,
    mf_rows: list,
    f30_full: list,
    sip_rows: list | None = None,
) -> None:
    """Final PDF page: executive-summary Portfolio Insights sheet."""
    import datetime
    import matplotlib.gridspec as gridspec

    # ── Derived metrics ──────────────────────────────────────────────────
    def _s(v: float) -> str:
        return "+" if v >= 0 else ""

    f30_inv  = sum(r[1] for r in f30_rows)
    f30_cur  = sum(r[2] for r in f30_rows)
    f30_pnl  = sum(r[3] for r in f30_rows)
    f30_pct  = (f30_pnl / f30_inv * 100) if f30_inv else 0.0

    mf_inv   = sum(r[4] for r in mf_rows)
    mf_cur   = sum(r[5] for r in mf_rows)
    mf_gain  = sum(r[6] for r in mf_rows)
    mf_pct   = (mf_gain / mf_inv * 100) if mf_inv else 0.0

    gold_syms = set(GOLD_ETF)
    gold_inv  = sum(r[1] for r in excluded_rows if r[0] in gold_syms)
    gold_cur  = sum(r[2] for r in excluded_rows if r[0] in gold_syms)
    gold_pnl  = gold_cur - gold_inv
    gold_pct  = (gold_pnl / gold_inv * 100) if gold_inv else 0.0

    exc_inv   = sum(r[1] for r in excluded_rows)
    exc_cur   = sum(r[2] for r in excluded_rows)
    exc_pnl   = exc_cur - exc_inv
    total_inv = f30_inv + exc_inv + mf_inv
    total_cur = f30_cur + exc_cur + mf_cur
    total_pnl = f30_pnl + exc_pnl + mf_gain
    total_pct = (total_pnl / total_inv * 100) if total_inv else 0.0

    # F30 analysis
    winners    = [r for r in f30_rows if r[3] >= 0]
    strike_rt  = len(winners) / len(f30_rows) * 100 if f30_rows else 0
    best       = max(f30_rows, key=lambda r: r[3]) if f30_rows else ("—", 0, 0, 0, "")
    worst      = min(f30_rows, key=lambda r: r[3]) if f30_rows else ("—", 0, 0, 0, "")
    top3_pct   = (
        sum(r[1] for r in sorted(f30_rows, key=lambda r: r[1], reverse=True)[:3])
        / f30_inv * 100
    ) if f30_inv else 0

    # Portfolio beta
    bv         = [(r["Invested"], r.get("Beta", 0)) for r in f30_full if r.get("Beta", 0) != 0]
    b_inv_tot  = sum(x[0] for x in bv)
    w_beta     = sum(x[0] * x[1] for x in bv) / b_inv_tot if b_inv_tot else 0.0
    high_b_cnt = sum(1 for _, b in bv if b > 1.2)
    neg_b_cnt  = sum(1 for _, b in bv if b < 0)

    # Sectors
    sec_set    = {r.get("Sector") or "Unknown" for r in f30_full}
    sec_set.discard("Unknown")
    n_sectors  = len(sec_set)

    # Cap mix
    cap_cnt: dict = {}
    for r in f30_rows:
        cap_cnt[r[4]] = cap_cnt.get(r[4], 0) + 1

    # SIP
    monthly_sip = 0.0
    if sip_rows:
        for r in sip_rows:
            if (
                str(r.get("Status", "")).lower() == "active"
                and str(r.get("Frequency", "")).lower() == "monthly"
            ):
                monthly_sip += float(r.get("Amount") or 0)

    # Asset allocation buckets
    cases_set   = set(CASES)
    cases_inv   = sum(r[1] for r in excluded_rows if r[0] in cases_set)
    other_eq    = sum(
        r[1] for r in excluded_rows
        if r[0] not in gold_syms and r[0] not in cases_set
    )
    alloc_raw   = [
        ("F30 Equity",   f30_inv,  "#2980b9"),
        ("Mutual Funds", mf_inv,   "#27ae60"),
        ("Gold ETFs",    gold_inv, "#d4ac0d"),
        ("Smallcases",   cases_inv,"#e67e22"),
        ("Other Equity", other_eq, "#8e44ad"),
    ]
    alloc        = [(l, v, c) for l, v, c in alloc_raw if v > 0]
    total_assets = sum(v for _, v, _ in alloc)

    # ── Figure ───────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(17, 11))
    fig.patch.set_facecolor("#eef2f7")

    gs = gridspec.GridSpec(
        3, 4, figure=fig,
        height_ratios=[0.55, 1.5, 4.5],
        top=0.97, bottom=0.04,
        left=0.025, right=0.975,
        hspace=0.28, wspace=0.22,
    )

    def _bg(ax, fc, ec="#e0e0e0", lw=0.5):
        """Rounded-rectangle background filling the axes."""
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.01, 0.01), 0.98, 0.98,
            boxstyle="round,pad=0.01",
            facecolor=fc, edgecolor=ec, linewidth=lw,
            transform=ax.transAxes, zorder=0, clip_on=False,
        ))

    # ── Header ───────────────────────────────────────────────────────────
    ax_h = fig.add_subplot(gs[0, :])
    ax_h.axis("off")
    _bg(ax_h, "#1a252f", ec="none")
    ax_h.text(0.018, 0.70, "PORTFOLIO INSIGHTS",
              transform=ax_h.transAxes,
              fontsize=15, fontweight="bold", color="white", va="center")
    ax_h.text(0.018, 0.22, "Executive Summary  \u00b7  F30 Equity + Mutual Funds + Gold",
              transform=ax_h.transAxes,
              fontsize=8.5, color="#aab7c4", va="center")
    ax_h.text(0.984, 0.50,
              datetime.date.today().strftime("%d %b %Y"),
              transform=ax_h.transAxes,
              fontsize=9, color="#7fb3d3", va="center", ha="right", fontweight="bold")

    # ── Metric Cards ─────────────────────────────────────────────────────
    card_specs = [
        ("#17202a", "#5dade2",
         "TOTAL PORTFOLIO",
         f"\u20b9{total_cur/1e5:.2f}L",
         f"Invested \u20b9{total_inv/1e5:.2f}L  \u00b7  {_s(total_pnl)}\u20b9{total_pnl/1e3:.0f}K  ({_s(total_pct)}{total_pct:.1f}%)"),
        ("#1b4f72", "#7fb3d3",
         "F30 EQUITY",
         f"\u20b9{f30_cur/1e5:.2f}L",
         f"Invested \u20b9{f30_inv/1e5:.2f}L  \u00b7  {_s(f30_pnl)}\u20b9{f30_pnl/1e3:.0f}K  ({_s(f30_pct)}{f30_pct:.1f}%)"),
        ("#145a32", "#58d68d",
         "MUTUAL FUNDS",
         f"\u20b9{mf_cur/1e5:.2f}L",
         f"Invested \u20b9{mf_inv/1e5:.2f}L  \u00b7  {_s(mf_gain)}\u20b9{mf_gain/1e3:.0f}K  ({_s(mf_pct)}{mf_pct:.1f}%)"),
        ("#6e2f00", "#f0b27a",
         "GOLD ETFs",
         f"\u20b9{gold_cur/1e5:.2f}L",
         f"Invested \u20b9{gold_inv/1e5:.2f}L  \u00b7  {_s(gold_pnl)}\u20b9{gold_pnl/1e3:.0f}K  ({_s(gold_pct)}{gold_pct:.1f}%)"),
    ]
    for col, (bg, tc, title, val, sub) in enumerate(card_specs):
        ax_c = fig.add_subplot(gs[1, col])
        ax_c.axis("off")
        _bg(ax_c, bg, ec="none")
        ax_c.text(0.09, 0.83, title,  transform=ax_c.transAxes,
                  fontsize=7.5, fontweight="bold", color=tc, va="top")
        ax_c.text(0.09, 0.52, val,    transform=ax_c.transAxes,
                  fontsize=15, fontweight="bold", color="white", va="center")
        ax_c.text(0.09, 0.13, sub,    transform=ax_c.transAxes,
                  fontsize=7, color=tc, va="bottom", alpha=0.9)

    # ── Key Observations (row 2, col 0-1) ────────────────────────────────
    ax_obs = fig.add_subplot(gs[2, 0:2])
    ax_obs.axis("off")
    _bg(ax_obs, "white")
    ax_obs.text(0.04, 0.964, "KEY OBSERVATIONS",
                transform=ax_obs.transAxes,
                fontsize=10, fontweight="bold", color="#1a252f", va="top")
    ax_obs.plot([0.04, 0.96], [0.930, 0.930], transform=ax_obs.transAxes,
                color="#dee2e6", linewidth=1.0, solid_capstyle="round")

    beta_desc = (
        "Defensive \u2014 dampens market swings" if w_beta < 0.9 else
        "Market-neutral \u2014 tracks index closely" if w_beta < 1.05 else
        "Aggressive \u2014 amplifies market moves"
    )
    conc_note = (
        "High concentration \u2014 monitor top-3 exposure"
        if top3_pct > 40 else
        "Reasonably distributed across holdings"
    )
    obs_lines = [
        (f"{len(winners)}/{len(f30_rows)} F30 stocks profitable  \u2014  {strike_rt:.0f}% strike rate",
         "#27ae60" if strike_rt >= 50 else "#e74c3c"),
        (f"Best: {best[0]}  ({_s(best[3])}\u20b9{best[3]/1e3:.1f}K)   \u00b7   Worst: {worst[0]}  (\u20b9{worst[3]/1e3:.1f}K)",
         "#2c3e50"),
        (f"Top-3 holdings = {top3_pct:.0f}% of F30 weight  \u00b7  {conc_note}",
         "#e67e22" if top3_pct > 40 else "#27ae60"),
        (f"Portfolio \u03b2 = {w_beta:.2f}  \u00b7  {beta_desc}",
         "#27ae60" if w_beta < 0.9 else "#f39c12" if w_beta < 1.1 else "#e74c3c"),
        (f"{high_b_cnt} high-\u03b2 stocks (>1.2)  \u00b7  {neg_b_cnt} negative-\u03b2 stocks hedge downside",
         "#8e44ad"),
        (f"{n_sectors} GICS sectors covered  \u00b7  {len(f30_rows)} active F30 positions",
         "#2980b9"),
        (f"Gold ETFs  {_s(gold_pct)}{gold_pct:.1f}% return on \u20b9{gold_inv/1e5:.2f}L  \u00b7  Inflation hedge",
         "#d4ac0d"),
        (f"Mutual Funds: {len(mf_rows)} funds  \u00b7  {mf_pct:.1f}% avg gain on \u20b9{mf_inv/1e5:.2f}L",
         "#16a085"),
    ]
    y = 0.906
    for text, color in obs_lines:
        ax_obs.add_patch(mpatches.FancyBboxPatch(
            (0.025, y - 0.052), 0.012, 0.050,
            boxstyle="round,pad=0.005",
            facecolor=color, edgecolor="none",
            transform=ax_obs.transAxes, zorder=1,
        ))
        ax_obs.text(0.055, y - 0.027, text,
                    transform=ax_obs.transAxes,
                    fontsize=8.8, color="#1a1a2e", va="center")
        y -= 0.090
        if y < 0.06:
            break

    # ── Risk Profile (row 2, col 2) ──────────────────────────────────────
    ax_risk = fig.add_subplot(gs[2, 2])
    ax_risk.axis("off")
    _bg(ax_risk, "white")
    ax_risk.text(0.5, 0.962, "RISK PROFILE",
                 transform=ax_risk.transAxes,
                 fontsize=10, fontweight="bold", color="#1a252f", va="top", ha="center")
    ax_risk.plot([0.06, 0.94], [0.928, 0.928],
                 transform=ax_risk.transAxes, color="#dee2e6", linewidth=1.0)

    beta_col   = "#27ae60" if w_beta < 0.9 else "#f39c12" if w_beta < 1.1 else "#e74c3c"
    risk_label = (
        "LOW VOLATILITY" if w_beta < 0.9 else
        "MODERATE" if w_beta < 1.1 else
        "HIGH VOLATILITY"
    )
    ax_risk.text(0.5, 0.880, f"\u03b2 = {w_beta:.2f}",
                 transform=ax_risk.transAxes,
                 fontsize=22, fontweight="bold", color=beta_col, va="top", ha="center")
    ax_risk.text(0.5, 0.818, "Weighted Portfolio Beta",
                 transform=ax_risk.transAxes,
                 fontsize=7.5, color="#7f8c8d", va="top", ha="center")
    ax_risk.add_patch(mpatches.FancyBboxPatch(
        (0.10, 0.718), 0.80, 0.072,
        boxstyle="round,pad=0.01",
        facecolor=beta_col, edgecolor=beta_col, alpha=0.22, linewidth=0.8,
        transform=ax_risk.transAxes, zorder=1,
    ))
    ax_risk.text(0.5, 0.754, risk_label,
                 transform=ax_risk.transAxes,
                 fontsize=8.5, fontweight="bold", color=beta_col, ha="center", va="center")

    # Beta scale bar
    bar_y = 0.630
    ax_risk.add_patch(mpatches.FancyBboxPatch(
        (0.08, bar_y), 0.84, 0.040,
        boxstyle="round,pad=0.005",
        facecolor="#ecf0f1", edgecolor="none",
        transform=ax_risk.transAxes, zorder=1,
    ))
    fw = min(w_beta / 2.0, 1.0) * 0.84
    if fw > 0.005:
        ax_risk.add_patch(mpatches.FancyBboxPatch(
            (0.08, bar_y), fw, 0.040,
            boxstyle="round,pad=0.005",
            facecolor=beta_col, edgecolor="none",
            transform=ax_risk.transAxes, zorder=2,
        ))
    ax_risk.plot([0.50, 0.50], [bar_y - 0.01, bar_y + 0.050],
                 transform=ax_risk.transAxes,
                 color="#2c3e50", linewidth=1.2, linestyle="--", zorder=3)
    for xp, lb in [(0.08, "0"), (0.50, "1"), (0.92, "2")]:
        ax_risk.text(xp, bar_y - 0.054, lb,
                     transform=ax_risk.transAxes,
                     fontsize=6.5, ha="center", color="#aab7c4")

    # Stats grid
    y2 = 0.545
    ax_risk.plot([0.06, 0.94], [y2 + 0.02, y2 + 0.02],
                 transform=ax_risk.transAxes, color="#dee2e6", linewidth=0.6)
    for lbl, val, col in [
        ("High \u03b2 stocks  (>1.2)", str(high_b_cnt),   "#e74c3c"),
        ("Negative \u03b2 hedges",     str(neg_b_cnt),     "#8e44ad"),
        ("Active F30 positions",  str(len(f30_rows)), "#2980b9"),
        ("Sectors covered",       str(n_sectors),     "#27ae60"),
    ]:
        ax_risk.text(0.08, y2, lbl, transform=ax_risk.transAxes,
                     fontsize=8, color="#555555", va="top")
        ax_risk.text(0.92, y2, val, transform=ax_risk.transAxes,
                     fontsize=9, fontweight="bold", color=col, va="top", ha="right")
        y2 -= 0.075

    # Cap tier badges
    y3 = 0.19
    ax_risk.plot([0.06, 0.94], [y3 + 0.025, y3 + 0.025],
                 transform=ax_risk.transAxes, color="#dee2e6", linewidth=0.6)
    ax_risk.text(0.5, y3 - 0.01, "MARKET CAP MIX",
                 transform=ax_risk.transAxes,
                 fontsize=8, fontweight="bold", color="#1a252f", va="top", ha="center")
    cap_colors_map = {"Large": "#2980b9", "Mid": "#27ae60", "Small": "#f39c12"}
    xb = 0.06
    for cap in ["Large", "Mid", "Small"]:
        cnt = cap_cnt.get(cap, 0)
        if cnt:
            c = cap_colors_map[cap]
            ax_risk.add_patch(mpatches.FancyBboxPatch(
                (xb, 0.070), 0.26, 0.068,
                boxstyle="round,pad=0.01",
                facecolor=c, edgecolor="none",
                transform=ax_risk.transAxes, zorder=1,
            ))
            ax_risk.text(xb + 0.13, 0.104, f"{cap}  {cnt}",
                         transform=ax_risk.transAxes,
                         fontsize=8, fontweight="bold", color="white",
                         ha="center", va="center")
            xb += 0.30

    # ── Asset Allocation (row 2, col 3) ──────────────────────────────────
    ax_alloc = fig.add_subplot(gs[2, 3])
    ax_alloc.axis("off")
    _bg(ax_alloc, "white")
    ax_alloc.text(0.5, 0.962, "ASSET ALLOCATION",
                  transform=ax_alloc.transAxes,
                  fontsize=10, fontweight="bold", color="#1a252f", va="top", ha="center")
    ax_alloc.plot([0.06, 0.94], [0.928, 0.928],
                  transform=ax_alloc.transAxes, color="#dee2e6", linewidth=1.0)
    ax_alloc.text(0.5, 0.910, f"Total Invested  \u20b9{total_assets/1e5:.2f}L",
                  transform=ax_alloc.transAxes,
                  fontsize=8.0, color="#7f8c8d", ha="center", va="top")

    bar_start = 0.38
    bar_max   = 0.52
    yb        = 0.800
    bh        = 0.068
    for lbl, val, col in alloc:
        pct = (val / total_assets * 100) if total_assets else 0
        bw  = (pct / 100) * bar_max
        ax_alloc.text(bar_start - 0.03, yb + bh / 2, lbl,
                      transform=ax_alloc.transAxes,
                      fontsize=7.5, color=col, va="center", ha="right", fontweight="bold")
        ax_alloc.add_patch(mpatches.FancyBboxPatch(
            (bar_start, yb), bar_max, bh,
            boxstyle="round,pad=0.005",
            facecolor="#ecf0f1", edgecolor="none",
            transform=ax_alloc.transAxes, zorder=1,
        ))
        if bw > 0.004:
            ax_alloc.add_patch(mpatches.FancyBboxPatch(
                (bar_start, yb), bw, bh,
                boxstyle="round,pad=0.005",
                facecolor=col, edgecolor="none",
                transform=ax_alloc.transAxes, zorder=2,
            ))
        bar_end = bar_start + bw
        if bar_end > 0.76:
            # Bar is wide — place label inside, right-aligned, white text
            ax_alloc.text(bar_end - 0.015, yb + bh / 2,
                          f"{pct:.0f}%  \u20b9{val/1e5:.2f}L",
                          transform=ax_alloc.transAxes,
                          fontsize=7.5, fontweight="bold", color="white",
                          va="center", ha="right")
        else:
            # Bar is narrow — place label outside, left-aligned, colored text
            ax_alloc.text(bar_end + 0.018, yb + bh / 2,
                          f"{pct:.0f}%  \u20b9{val/1e5:.2f}L",
                          transform=ax_alloc.transAxes,
                          fontsize=7.5, fontweight="bold", color=col,
                          va="center", ha="left")
        yb -= 0.118

    if monthly_sip > 0:
        ax_alloc.plot([0.06, 0.94], [0.13, 0.13],
                      transform=ax_alloc.transAxes, color="#dee2e6", linewidth=0.6)
        ax_alloc.text(0.5, 0.105, f"SIP  \u20b9{monthly_sip:,.0f} / month",
                      transform=ax_alloc.transAxes,
                      fontsize=9, fontweight="bold", color="#1a5276",
                      ha="center", va="top")
        ax_alloc.text(0.5, 0.058, "Systematic monthly investment active",
                      transform=ax_alloc.transAxes,
                      fontsize=7.5, color="#7f8c8d", ha="center", va="top")

    # ── Footer ───────────────────────────────────────────────────────────
    fig.text(
        0.5, 0.014,
        "Auto-generated from Kite holdings data  \u00b7  Not investment advice  \u00b7  For personal reference only",
        ha="center", fontsize=7, color="#aab7c4",
    )


def visualize_portfolio(
    eq_csv_path: str = EQ_CSV_PATH,
    mf_csv_path: str = MF_CSV_PATH,
    sip_csv_path: str = SIP_CSV_PATH,
) -> None:
    """Load holdings data and render all portfolio charts into a single PDF.

    Args:
        eq_csv_path:  Absolute path to the equity holdings CSV file.
        mf_csv_path:  Absolute path to the mutual fund holdings CSV file.
        sip_csv_path: Absolute path to the SIP CSV file (optional; skipped if absent).
    """
    f30_rows: list      = []
    excluded_rows: list = []
    eq_full_rows: list  = []   # extended rows including new columns from equity.py

    with open(eq_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol    = row["Symbol"]
            invested  = float(row["Invested"])   if row.get("Invested")   else 0.0
            cur_value = float(row["Cur Value"])  if row.get("Cur Value")  else 0.0
            pnl       = float(row["PnL"])        if row.get("PnL")        else 0.0
            cap       = row.get("Cap") or "Unknown"
            ltp       = float(row["LTP"])        if row.get("LTP")        else 0.0
            avg       = float(row["Avg"])        if row.get("Avg")        else 0.0
            sector    = row.get("Sector") or "Unknown"
            pe        = float(row["PE"])         if row.get("PE")         else 0.0
            div_yield = float(row["DivYield%"])  if row.get("DivYield%")  else 0.0
            beta      = float(row["Beta"])       if row.get("Beta")       else 0.0
            w52_high  = float(row["52W High"])   if row.get("52W High")   else 0.0
            w52_low   = float(row["52W Low"])    if row.get("52W Low")    else 0.0
            qty       = float(row["Qty"])         if row.get("Qty")         else 0.0

            entry = (symbol, invested, cur_value, pnl, cap, qty)
            (excluded_rows if symbol in EXCLUDED else f30_rows).append(entry)

            eq_full_rows.append({
                "Symbol": symbol, "Invested": invested, "Cur Value": cur_value,
                "PnL": pnl, "Cap": cap, "LTP": ltp, "Avg": avg,
                "Sector": sector, "PE": pe, "DivYield%": div_yield,
                "Beta": beta, "52W High": w52_high, "52W Low": w52_low,
                "_excluded": symbol in EXCLUDED,
            })

    # F30-only extended rows (for sector/52W/dividend charts)
    f30_full = [r for r in eq_full_rows if not r["_excluded"]]

    # Chart 1 — F30 P&L per stock
    plot_pnl_bar(f30_rows, "F30 Portfolio — P&L per Stock")

    # Chart 2 — F30 allocation by invested amount
    plot_allocation_bar(f30_rows, "F30 Portfolio — Allocation by Invested Amount")

    # Chart 3 — Invested vs Current Value per F30 stock
    plot_invested_vs_current(f30_rows, "F30 Portfolio — Invested vs Current Value")

    # Chart 4 — High-level overview: F30 vs Excluded
    plot_summary_overview(f30_rows, excluded_rows)

    # Chart 5 — Totals summary table
    plot_totals_table(f30_rows, excluded_rows)

    # Chart 9 — Winners & Losers analysis
    plot_winners_losers_panel(f30_rows)

    # Chart 10 — Cap tier breakdown (Large / Mid / Small)
    plot_cap_tier_bar(f30_rows, "F30 Portfolio — Invested vs Current Value by Cap Tier")

    # Chart 11 — Sector allocation pie (F30 stocks only)
    plot_sector_pie(f30_full, "F30 Portfolio — Sector Allocation by Invested Amount")

    # Chart 12 — 52-week range chart (F30 stocks only)
    plot_52w_range(f30_full, "F30 Portfolio — 52-Week Price Range  (◆ LTP  |  ▌ Avg Cost)")

    # Chart 13 — Estimated annual dividend income (F30 stocks only)
    plot_annual_dividend(f30_full, "F30 Portfolio — Estimated Annual Dividend Income")

    # Chart 16 — Weighted portfolio beta (F30 stocks only)
    plot_weighted_beta(f30_full)

    # -----------------------------------------------------------------------
    # Mutual fund charts
    # -----------------------------------------------------------------------
    mf_rows: list = []
    with open(mf_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mf_rows.append((
                row["Fund"],
                float(row["Qty"])       if row.get("Qty")       else 0.0,
                float(row["Avg"])       if row.get("Avg")       else 0.0,
                float(row["NAV"])       if row.get("NAV")       else 0.0,
                float(row["Invested"])  if row.get("Invested")  else 0.0,
                float(row["Cur Value"]) if row.get("Cur Value") else 0.0,
                float(row["Gain"])      if row.get("Gain")      else 0.0,
                float(row["Gain%"])     if row.get("Gain%")     else 0.0,
                row.get("Category") or "Unknown",
            ))

    # Chart 14 — Full portfolio asset allocation overview (equity + MF + gold)
    plot_asset_allocation_overview(f30_rows, excluded_rows, mf_rows)

    # Chart 6 — MF gain per fund
    plot_mf_gain_bar(mf_rows, "Mutual Fund Portfolio — Gain per Fund")

    # Chart 7 — MF category breakdown
    plot_mf_category_breakdown(mf_rows, "Mutual Fund Portfolio — Invested vs Current Value by Category")

    # Chart 8 — MF detailed table
    plot_mf_table(mf_rows)

    # Chart 15 — SIP dashboard (only if sip.csv exists)
    sip_rows: list = []
    if os.path.exists(sip_csv_path):
        with open(sip_csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sip_rows.append({
                    "Fund":            row.get("Fund", ""),
                    "Amount":          float(row["Amount"]) if row.get("Amount") else 0.0,
                    "Frequency":       row.get("Frequency", ""),
                    "Completed":       row.get("Completed", "0"),
                    "Instalments":     row.get("Instalments", "0"),
                    "Pending":         row.get("Pending", "0"),
                    "Next Instalment": row.get("Next Instalment", ""),
                    "Status":          row.get("Status", ""),
                })
        if sip_rows:
            plot_sip_dashboard(sip_rows)

    # Final page — Portfolio Insights executive summary
    plot_portfolio_insights(f30_rows, excluded_rows, mf_rows, f30_full,
                            sip_rows if sip_rows else None)

    # Save all open figures to a single PDF
    with PdfPages(PDF_PATH) as pdf:
        for fig in map(plt.figure, plt.get_fignums()):
            pdf.savefig(fig, bbox_inches="tight")
    plt.close("all")
    print(f"\nPDF saved → {PDF_PATH}")


if __name__ == "__main__":
    summarize_portfolio(EQ_CSV_PATH)
    summarize_mf(MF_CSV_PATH)
    summarize_sips(SIP_CSV_PATH)
    visualize_portfolio(EQ_CSV_PATH, MF_CSV_PATH, SIP_CSV_PATH)
