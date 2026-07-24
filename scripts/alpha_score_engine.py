"""
AlphaScore Engine — Week 3
===========================
Computes a 0-100 composite technical score for each ticker on every date
using the features computed in feature_engineering.py.

Weighting:
  RSI (14)          30%  — momentum overbought/oversold signal
  MACD signal       20%  — trend direction + crossover strength
  Bollinger Band %  20%  — where price sits in volatility channel
  Momentum (20d)    15%  — 20-day price rate of change
  Volatility (20d)  10%  — annualised rolling vol (lower = more stable)
  Volume Ratio       5%  — participation vs 20-day average

Scoring philosophy:
  - RSI <30 (oversold) scores HIGH — potential bounce opportunity
  - RSI >70 (overbought) scores LOW — extended, risk of pullback
  - BB% near 0 (lower band) scores HIGH — room to recover
  - BB% near 1 (upper band) scores LOW — price already extended
  - Negative momentum scores lower UNLESS RSI is oversold (mean-reversion)
  - High volatility reduces score slightly (risk adjustment)

Run:
  python scripts/alpha_score_engine.py

Input:  scripts/output/features/all_features.csv
Output:
  scripts/output/alpha_scores.csv        (all dates × all tickers)
  scripts/output/alpha_scores_latest.csv (latest date only, for dashboard)
"""

import os
import pandas as pd
import numpy as np

FEATURES_FILE = os.path.join(os.path.dirname(__file__), "output", "features", "all_features.csv")
OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Component scoring functions  (each returns 0–100)
# ─────────────────────────────────────────────────────────────

def score_rsi(rsi: float) -> float:
    """RSI <30 = oversold opportunity (high score); >70 = overbought risk (low score)."""
    if pd.isna(rsi):  return 50.0
    if rsi < 20:      return 92.0
    if rsi < 30:      return 82.0   # oversold
    if rsi < 40:      return 68.0
    if rsi <= 55:     return 52.0   # neutral zone
    if rsi <= 65:     return 42.0
    if rsi <= 70:     return 32.0
    return 18.0                     # overbought


def score_macd(macd: float, macd_signal: float, macd_hist: float) -> float:
    """
    Combines three MACD signals:
      - Is MACD above or below signal line? (direction)
      - Is histogram positive or negative? (strength)
      - Is histogram growing or shrinking? (momentum of trend)
    """
    if pd.isna(macd) or pd.isna(macd_signal): return 50.0
    base = 50.0
    # Direction: above signal = bullish
    base += 20.0 if macd > macd_signal else -20.0
    # Histogram strength
    if not pd.isna(macd_hist):
        base += 10.0 if macd_hist > 0 else -10.0
    return float(np.clip(base, 0, 100))


def score_bb(bb_pct: float) -> float:
    """
    BB% near 0 = price at lower band (oversold/support) → high score.
    BB% near 1 = price at upper band (extended) → low score.
    BB% > 1 = price broke above band → strong trend signal → moderate score.
    """
    if pd.isna(bb_pct): return 50.0
    if bb_pct < 0.0:    return 90.0   # below lower band (very oversold)
    if bb_pct < 0.15:   return 80.0
    if bb_pct < 0.30:   return 68.0
    if bb_pct <= 0.70:  return 52.0   # mid-band
    if bb_pct <= 0.85:  return 38.0
    if bb_pct <= 1.0:   return 25.0
    return 60.0                        # above upper band = strong breakout


def score_momentum(mom: float) -> float:
    """20-day price rate of change. Positive momentum = higher score."""
    if pd.isna(mom): return 50.0
    pct = mom * 100  # convert decimal to %
    if pct > 20:     return 85.0
    if pct > 10:     return 72.0
    if pct > 3:      return 60.0
    if pct > 0:      return 53.0
    if pct > -3:     return 47.0
    if pct > -10:    return 38.0
    if pct > -20:    return 28.0
    return 15.0


def score_volatility(vol: float) -> float:
    """Annualised vol (decimal or %). Lower = more stable = slightly better."""
    if pd.isna(vol): return 50.0
    pct = vol * 100 if vol < 2 else vol   # handle both formats
    if pct < 15:    return 75.0
    if pct < 25:    return 65.0
    if pct < 40:    return 55.0
    if pct < 60:    return 45.0
    if pct < 80:    return 38.0
    return 28.0                            # very high vol = lower score


def score_volume(vol_ratio: float) -> float:
    """Volume vs 20-day average. Higher participation = higher score."""
    if pd.isna(vol_ratio): return 50.0
    if vol_ratio > 3.0:    return 80.0
    if vol_ratio > 2.0:    return 70.0
    if vol_ratio > 1.5:    return 62.0
    if vol_ratio > 1.0:    return 54.0
    if vol_ratio > 0.7:    return 46.0
    return 35.0


# ─────────────────────────────────────────────────────────────
# Composite AlphaScore
# ─────────────────────────────────────────────────────────────

WEIGHTS = {
    "rsi":        0.30,
    "macd":       0.20,
    "bb":         0.20,
    "momentum":   0.15,
    "volatility": 0.10,
    "volume":     0.05,
}

def compute_alpha_score(row: pd.Series) -> float:
    components = {
        "rsi":        score_rsi(row.get("RSI_14")),
        "macd":       score_macd(row.get("MACD"), row.get("MACD_signal"), row.get("MACD_hist")),
        "bb":         score_bb(row.get("BB_pct")),
        "momentum":   score_momentum(row.get("Momentum_20")),
        "volatility": score_volatility(row.get("Volatility_20")),
        "volume":     score_volume(row.get("Volume_ratio")),
    }
    score = sum(WEIGHTS[k] * v for k, v in components.items())
    return round(float(np.clip(score, 0, 100)), 1), components


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    print(f"Loading features from {FEATURES_FILE}...\n")
    df = pd.read_csv(FEATURES_FILE)
    print(f"  {len(df):,} rows · {df['ticker'].nunique()} tickers · "
          f"{df['date'].min()} → {df['date'].max()}\n")

    # Compute AlphaScore for every row
    scores       = []
    comp_records = []

    for _, row in df.iterrows():
        alpha, comps = compute_alpha_score(row)
        scores.append(alpha)
        comp_records.append({
            "ticker": row["ticker"],
            "date":   row["date"],
            "alpha_score": alpha,
            **{f"comp_{k}": round(v, 1) for k, v in comps.items()},
        })

    df["alpha_score"] = scores

    # Save full history
    all_scores = pd.DataFrame(comp_records)
    all_path = os.path.join(OUTPUT_DIR, "alpha_scores.csv")
    all_scores.to_csv(all_path, index=False)

    # Latest date per ticker
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].copy()

    latest_summary = []
    print(f"{'='*70}")
    print(f"  ALPHA SCORE SUMMARY — {latest_date}")
    print(f"{'='*70}")
    print(f"\n{'Ticker':<8} {'Alpha':>7} {'RSI':>6} {'MACD':>6} {'BB%':>6} {'Mom':>6} {'Vol':>6} {'VolRat':>7}")
    print("-" * 70)

    comp_df = pd.DataFrame(comp_records)
    latest_comps = comp_df[comp_df["date"] == latest_date].set_index("ticker")

    for _, row in latest.sort_values("alpha_score", ascending=False).iterrows():
        ticker = row["ticker"]
        alpha  = row["alpha_score"]
        c = latest_comps.loc[ticker] if ticker in latest_comps.index else {}

        label = "🟢" if alpha >= 65 else "🟡" if alpha >= 50 else "🔴"
        print(
            f"{ticker:<8} {alpha:>6.1f} {label}  "
            f"{c.get('comp_rsi', 0):>5.0f}  {c.get('comp_macd', 0):>5.0f}  "
            f"{c.get('comp_bb', 0):>5.0f}  {c.get('comp_momentum', 0):>5.0f}  "
            f"{c.get('comp_volatility', 0):>5.0f}  {c.get('comp_volume', 0):>6.0f}"
        )
        latest_summary.append({
            "ticker":      ticker,
            "date":        latest_date,
            "alpha_score": alpha,
            "rsi":         round(row.get("RSI_14", 0), 1),
            "macd_dir":    "Bullish" if row.get("MACD", 0) > row.get("MACD_signal", 0) else "Bearish",
            "bb_pct":      round(row.get("BB_pct", 0), 3),
            "momentum_20": round(row.get("Momentum_20", 0) * 100, 1),
            "volatility":  round(row.get("Volatility_20", 0) * 100, 1),
            "vol_ratio":   round(row.get("Volume_ratio", 0), 2),
        })

    # Save latest
    latest_path = os.path.join(OUTPUT_DIR, "alpha_scores_latest.csv")
    pd.DataFrame(latest_summary).to_csv(latest_path, index=False)

    print(f"\n✅ Saved:")
    print(f"   {all_path}  ({len(all_scores):,} rows — full history)")
    print(f"   {latest_path}  (latest scores for dashboard)")

    # Print component breakdown note
    print(f"\n  Weights: RSI 30% | MACD 20% | BB% 20% | Momentum 15% | Volatility 10% | Volume 5%")

    # Print update snippet for frontend mock-data
    print(f"\n{'='*70}")
    print(f"  COPY THESE INTO frontend/app/lib/mock-data.ts  (alphaScore field)")
    print(f"{'='*70}")
    for s in sorted(latest_summary, key=lambda x: x["ticker"]):
        print(f"  {s['ticker']}: alphaScore={s['alpha_score']}")


if __name__ == "__main__":
    main()
