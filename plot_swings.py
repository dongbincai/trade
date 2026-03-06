#!/usr/bin/env python3
"""
Swing Point Visualization — 3 charts for any ticker

Usage:
    python plot_swings.py TICKER [DAYS]

    TICKER  Stock symbol, e.g. PONY, SPY, OXY  (must have data/history/{TICKER}.csv)
    DAYS    Lookback days (default: 90)

Examples:
    python plot_swings.py PONY
    python plot_swings.py SPY 120
    python plot_swings.py OXY 60
"""

import sys
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np


# ═══════════════════════════════════════════
# Config
# ═══════════════════════════════════════════

WINDOW = 5  # swing detection: highest/lowest in +/- WINDOW days

# Colors
BG = "#1a1a2e"
PRICE_COLOR = "#8892b0"
HIGH_COLOR = "#ff6b6b"
LOW_COLOR = "#51cf66"
HH_COLOR = "#ff6b6b"
LH_COLOR = "#ffa94d"
HL_COLOR = "#51cf66"
LL_COLOR = "#845ef7"
LINE_HIGH = "#ff8787"
LINE_LOW = "#69db7c"
NOW_COLOR = "#ffd43b"

LABEL_COLORS = {"HH": HH_COLOR, "LH": LH_COLOR, "HL": HL_COLOR, "LL": LL_COLOR, "--": "#666"}


# ═══════════════════════════════════════════
# Core logic
# ═══════════════════════════════════════════

def find_swings(closes, window=5):
    """Find swing highs and lows. Returns list of (index, price)."""
    highs, lows = [], []
    for i in range(window, len(closes) - window):
        seg = closes[i - window : i + window + 1]
        if closes[i] == max(seg):
            highs.append((i, closes[i]))
        if closes[i] == min(seg):
            lows.append((i, closes[i]))
    return highs, lows


def dedup(points, tol=0.01):
    """Remove consecutive same-price swing points."""
    if not points:
        return []
    result = [points[0]]
    for p in points[1:]:
        if abs(p[1] - result[-1][1]) > tol:
            result.append(p)
    return result


def label_sequence(points, direction="high"):
    """Label each point as HH/LH or HL/LL relative to its predecessor."""
    labels = []
    for i in range(len(points)):
        if i == 0:
            labels.append("--")
        else:
            curr, prev = points[i][1], points[i - 1][1]
            if direction == "high":
                labels.append("HH" if curr > prev else "LH")
            else:
                labels.append("HL" if curr > prev else "LL")
    return labels


# ═══════════════════════════════════════════
# Plotting
# ═══════════════════════════════════════════

def plot_swings(ticker, days=90):
    csv_path = f"data/history/{ticker.upper()}.csv"
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found. Run: PYTHONPATH=src python -m src.cli sync {ticker}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df["Date"] = pd.to_datetime(df["Date"])
    cutoff = df["Date"].max() - timedelta(days=days)
    df = df[df["Date"] >= cutoff].copy().sort_values("Date").reset_index(drop=True)

    if len(df) < WINDOW * 2 + 5:
        print(f"ERROR: Not enough data ({len(df)} rows). Need at least {WINDOW * 2 + 5}.")
        sys.exit(1)

    dates = df["Date"].values
    closes = df["Close"].values

    # Find & label swing points
    raw_highs, raw_lows = find_swings(closes, WINDOW)
    swing_highs = dedup(raw_highs)
    swing_lows = dedup(raw_lows)
    high_labels = label_sequence(swing_highs, "high")
    low_labels = label_sequence(swing_lows, "low")

    # Extract plotting arrays
    h_dates = [dates[h[0]] for h in swing_highs]
    h_prices = [h[1] for h in swing_highs]
    l_dates = [dates[l[0]] for l in swing_lows]
    l_prices = [l[1] for l in swing_lows]

    # ── Style ──
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG,
        "axes.edgecolor": "#444", "axes.labelcolor": "#ccc",
        "xtick.color": "#999", "ytick.color": "#999",
        "text.color": "#ddd", "grid.color": "#333", "grid.alpha": 0.5,
        "font.size": 11, "font.family": "DejaVu Sans",
    })

    fig, axes = plt.subplots(3, 1, figsize=(16, 18), sharex=True)
    fig.suptitle(f"{ticker.upper()} Swing Analysis  ({days}d lookback)", 
                 fontsize=16, fontweight="bold", color="white", y=0.95)

    # ── Chart 1: Raw price ──
    ax1 = axes[0]
    ax1.plot(dates, closes, color=PRICE_COLOR, linewidth=1.8, alpha=0.9)
    ax1.fill_between(dates, closes, closes.min() - (closes.max() - closes.min()) * 0.05,
                     alpha=0.06, color=PRICE_COLOR)
    ax1.set_title("Step 1: Raw Closing Price", fontsize=13, pad=10)
    ax1.set_ylabel("Price ($)")
    ax1.grid(True, alpha=0.3)

    # ── Chart 2: Swing points marked ──
    ax2 = axes[1]
    ax2.plot(dates, closes, color=PRICE_COLOR, linewidth=1.2, alpha=0.4)

    ax2.scatter(h_dates, h_prices, color=HIGH_COLOR, s=140, zorder=5,
                marker="v", edgecolors="white", linewidths=0.8, label="Swing High")
    for d, p in zip(h_dates, h_prices):
        ax2.annotate(f"${p:.2f}", xy=(d, p), xytext=(0, 14), textcoords="offset points",
                     ha="center", fontsize=9, color=HIGH_COLOR, fontweight="bold")

    ax2.scatter(l_dates, l_prices, color=LOW_COLOR, s=140, zorder=5,
                marker="^", edgecolors="white", linewidths=0.8, label="Swing Low")
    for d, p in zip(l_dates, l_prices):
        ax2.annotate(f"${p:.2f}", xy=(d, p), xytext=(0, -20), textcoords="offset points",
                     ha="center", fontsize=9, color=LOW_COLOR, fontweight="bold")

    ax2.annotate(f"window={WINDOW}: highest/lowest\nin {WINDOW*2+1}-day neighborhood",
                 xy=(0.02, 0.95), xycoords="axes fraction", fontsize=9, va="top", color="#888",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#222", edgecolor="#444"))

    ax2.set_title(f"Step 2: Find Swing Points (highest/lowest in +/-{WINDOW} days)", fontsize=13, pad=10)
    ax2.set_ylabel("Price ($)")
    ax2.legend(loc="upper right", fontsize=10, facecolor="#222", edgecolor="#444")
    ax2.grid(True, alpha=0.3)

    # ── Chart 3: Connected + labels ──
    ax3 = axes[2]
    ax3.plot(dates, closes, color=PRICE_COLOR, linewidth=1.0, alpha=0.25)

    ax3.plot(h_dates, h_prices, color=LINE_HIGH, linewidth=2.2, linestyle="--", alpha=0.8,
             marker="v", markersize=9, markerfacecolor=HIGH_COLOR,
             markeredgecolor="white", markeredgewidth=0.5, label="Swing Highs connected")

    ax3.plot(l_dates, l_prices, color=LINE_LOW, linewidth=2.2, linestyle="--", alpha=0.8,
             marker="^", markersize=9, markerfacecolor=LOW_COLOR,
             markeredgecolor="white", markeredgewidth=0.5, label="Swing Lows connected")

    # HH / LH labels
    for i, (sh, lbl) in enumerate(zip(swing_highs, high_labels)):
        color = LABEL_COLORS.get(lbl, "#888")
        if lbl == "--":
            txt = f"${sh[1]:.2f}"
        else:
            prev_p = swing_highs[i - 1][1]
            arrow = ">" if sh[1] > prev_p else "<"
            txt = f"{lbl}\n${sh[1]:.2f}\n({arrow} ${prev_p:.2f})"
        ax3.annotate(txt, xy=(dates[sh[0]], sh[1]), xytext=(0, 22),
                     textcoords="offset points", ha="center", fontsize=8,
                     color=color, fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor=BG, edgecolor=color, alpha=0.9))

    # HL / LL labels
    for i, (sl, lbl) in enumerate(zip(swing_lows, low_labels)):
        color = LABEL_COLORS.get(lbl, "#888")
        if lbl == "--":
            txt = f"${sl[1]:.2f}"
        else:
            prev_p = swing_lows[i - 1][1]
            arrow = ">" if sl[1] > prev_p else "<"
            txt = f"{lbl}\n${sl[1]:.2f}\n({arrow} ${prev_p:.2f})"
        ax3.annotate(txt, xy=(dates[sl[0]], sl[1]), xytext=(0, -40),
                     textcoords="offset points", ha="center", fontsize=8,
                     color=color, fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor=BG, edgecolor=color, alpha=0.9))

    # Current price
    current_price = closes[-1]
    ax3.axhline(y=current_price, color=NOW_COLOR, linewidth=0.8, linestyle=":", alpha=0.5)
    ax3.annotate(f"NOW ${current_price:.2f}", xy=(dates[-1], current_price),
                 xytext=(5, 8), textcoords="offset points", fontsize=10,
                 color=NOW_COLOR, fontweight="bold")

    # Legend box
    trend_text = (
        "HOW TO READ:\n"
        "HH (red)    = Higher High: peak > prev peak\n"
        "LH (orange) = Lower High:  peak < prev peak\n"
        "HL (green)  = Higher Low:  dip > prev dip\n"
        "LL (purple) = Lower Low:   dip < prev dip\n"
        "---\n"
        "HH+HL = UPTREND    LH+LL = DOWNTREND"
    )
    ax3.annotate(trend_text, xy=(0.02, 0.97), xycoords="axes fraction", fontsize=8.5,
                 va="top", color="#ddd", family="monospace",
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#222", edgecolor="#555"))

    ax3.set_title("Step 3: Compare each high vs prev high, each low vs prev low", fontsize=13, pad=10)
    ax3.set_ylabel("Price ($)")
    ax3.set_xlabel("Date")
    ax3.legend(loc="upper right", fontsize=10, facecolor="#222", edgecolor="#444")
    ax3.grid(True, alpha=0.3)

    # X-axis formatting — adapt tick density to date range
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        if days <= 90:
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        elif days <= 180:
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
        else:
            ax.xaxis.set_major_locator(mdates.MonthLocator())

    plt.tight_layout(rect=[0, 0, 1, 0.93])

    out_file = f"{ticker.lower()}_swings.png"
    plt.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close()

    # ── Console summary ──
    print(f"Saved: {out_file}")
    print(f"\n{ticker.upper()} Swing Summary ({pd.Timestamp(dates[0]).date()} to {pd.Timestamp(dates[-1]).date()}):")
    print(f"  Swing Highs ({len(swing_highs)}):")
    for i, (sh, lbl) in enumerate(zip(swing_highs, high_labels)):
        d = pd.Timestamp(dates[sh[0]]).date()
        prev = f"  vs ${swing_highs[i-1][1]:.2f}" if i > 0 else ""
        print(f"    {d}  ${sh[1]:.2f}  {lbl}{prev}")
    print(f"  Swing Lows ({len(swing_lows)}):")
    for i, (sl, lbl) in enumerate(zip(swing_lows, low_labels)):
        d = pd.Timestamp(dates[sl[0]]).date()
        prev = f"  vs ${swing_lows[i-1][1]:.2f}" if i > 0 else ""
        print(f"    {d}  ${sl[1]:.2f}  {lbl}{prev}")


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ticker = sys.argv[1].upper()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90

    plot_swings(ticker, days)
