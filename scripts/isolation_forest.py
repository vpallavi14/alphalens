"""
Isolation Forest Anomaly Detector — Week 3
===========================================
Trains a per-ticker Isolation Forest model on 2 years of historical data
to learn what "normal" looks like for each stock, then flags days that
deviate significantly from that baseline.

Why per-ticker? NVDA's normal daily move is ±3%. INTC's normal is ±1.5%.
A shared model would flag NVDA as anomalous every other day. Training
separately means anomalies are relative to each stock's own history.

Features used:
  - daily_return      : % price change (captures price anomalies)
  - Volume_ratio      : volume vs 20-day average (captures activity spikes)
  - Volatility_20     : rolling annualised vol (captures vol regime shifts)
  - ATR_14            : average true range (captures intraday range expansion)
  - BB_pct            : Bollinger Band position (captures channel breaks)
  - abs_return        : |daily_return| (magnitude without direction)

contamination=0.05 means we expect ~5% of days to be anomalous.
That gives us roughly 25 flagged days per ticker over 2 years — enough
to be meaningful without flooding the signal.

Output:
  scripts/output/anomaly_flags.csv         — all dates, all tickers
  scripts/output/anomaly_flags_latest.csv  — latest date per ticker
  scripts/output/models/iso_forest_{ticker}.pkl  — per-ticker models

Run:
  python scripts/isolation_forest.py  (scikit-learn already installed)
"""

import os
import pickle
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

FEATURES_FILE = os.path.join(os.path.dirname(__file__), "output", "features", "all_features.csv")
HIST_FILE     = os.path.join(os.path.dirname(__file__), "output", "historical", "all_tickers.csv")
MODEL_DIR     = os.path.join(os.path.dirname(__file__), "output", "models")
OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(MODEL_DIR, exist_ok=True)

CONTAMINATION = 0.05   # expect 5% anomalous days
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
           "AMZN", "META", "NFLX", "AMD",  "INTC"]

FEATURE_COLS = [
    "daily_return",
    "Volume_ratio",
    "Volatility_20",
    "ATR_14",
    "BB_pct",
    "abs_return",
]

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def prepare_ticker(df_feat: pd.DataFrame, df_hist: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extract one ticker from features CSV and add abs_return."""
    df = df_feat[df_feat["ticker"] == ticker].copy()

    # daily_return is already in features CSV (passed through from historical)
    # If missing for any reason, pull it from the historical file
    if "daily_return" not in df.columns:
        hist = df_hist[df_hist["ticker"] == ticker][["date", "daily_return"]].copy()
        df = df.merge(hist, on="date", how="inner")

    df["abs_return"] = df["daily_return"].abs()
    df = df.sort_values("date").dropna(subset=FEATURE_COLS)
    return df


def train_iso_forest(X: pd.DataFrame):
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=CONTAMINATION,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)
    return model, scaler


def score_anomaly(model, scaler, X: pd.DataFrame):
    """
    Returns:
      anomaly_flag   : 1 = anomalous, 0 = normal
      anomaly_score  : raw score (more negative = more anomalous)
    """
    X_scaled = scaler.transform(X)
    flags  = model.predict(X_scaled)          # -1 = anomaly, 1 = normal
    scores = model.decision_function(X_scaled) # negative = more anomalous

    return (flags == -1).astype(int), scores


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    from sklearn.ensemble import IsolationForest

    print(f"\nIsolation Forest Anomaly Detector")
    print("=" * 60)

    # Load data
    print(f"\nLoading data...")
    df_feat = pd.read_csv(FEATURES_FILE)
    df_hist = pd.read_csv(HIST_FILE)
    print(f"  Features: {len(df_feat):,} rows")
    print(f"  History:  {len(df_hist):,} rows\n")

    all_results  = []
    latest_rows  = []
    ticker_stats = []

    for ticker in TICKERS:
        df = prepare_ticker(df_feat, df_hist, ticker)
        if len(df) < 50:
            print(f"  {ticker}: not enough data — skipping")
            continue

        X = df[FEATURE_COLS]

        # Train
        model, scaler = train_iso_forest(X)

        # Score all dates
        flags, scores = score_anomaly(model, scaler, X)
        df["anomaly_flag"]  = flags
        df["anomaly_score"] = scores.round(4)

        # Save model
        model_path = os.path.join(MODEL_DIR, f"iso_forest_{ticker}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump({"model": model, "scaler": scaler}, f)

        # Stats
        n_anomalies = flags.sum()
        anomaly_pct = n_anomalies / len(df) * 100

        # Most extreme anomaly dates
        top_anomalies = df[df["anomaly_flag"] == 1].nsmallest(3, "anomaly_score")

        print(f"  {ticker}: {n_anomalies} anomalies / {len(df)} days ({anomaly_pct:.1f}%)  "
              f"| Most extreme: {', '.join(top_anomalies['date'].tolist())}")

        ticker_stats.append({
            "ticker":       ticker,
            "total_days":   len(df),
            "anomalies":    int(n_anomalies),
            "anomaly_pct":  round(anomaly_pct, 1),
            "top_dates":    ", ".join(top_anomalies["date"].tolist()),
        })

        # Collect results
        result_cols = ["ticker", "date", "close", "daily_return", "Volume_ratio",
                       "Volatility_20", "ATR_14", "BB_pct", "abs_return",
                       "anomaly_flag", "anomaly_score"]
        available = [c for c in result_cols if c in df.columns]
        all_results.append(df[available])

        # Latest row
        latest = df.iloc[-1]
        latest_rows.append({
            "ticker":        ticker,
            "date":          latest["date"],
            "anomaly_flag":  int(latest["anomaly_flag"]),
            "anomaly_score": float(latest["anomaly_score"]),
            "daily_return":  round(float(latest["daily_return"]), 4),
            "volume_ratio":  round(float(latest["Volume_ratio"]), 2),
            "volatility":    round(float(latest["Volatility_20"]) * 100, 1),
        })

    # ── Summary ───────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ANOMALY SUMMARY — Latest Date Status")
    print(f"{'='*60}")
    print(f"\n{'Ticker':<8} {'Flag':>6} {'Score':>8} {'DailyRet':>10} {'VolRatio':>9} {'Vol%':>7}")
    print("-" * 60)

    for r in latest_rows:
        flag_icon = "🚨" if r["anomaly_flag"] else "✅"
        print(f"{r['ticker']:<8} {flag_icon} {'ANOMALY' if r['anomaly_flag'] else 'normal':>6}  "
              f"{r['anomaly_score']:>8.4f}  {r['daily_return']*100:>8.2f}%  "
              f"{r['volume_ratio']:>8.2f}x  {r['volatility']:>6.1f}%")

    # ── Top anomaly days across all tickers ───────────────────
    combined = pd.concat(all_results, ignore_index=True)
    top_ever = (combined[combined["anomaly_flag"] == 1]
                .nsmallest(10, "anomaly_score")[["ticker", "date", "anomaly_score",
                                                  "daily_return", "Volume_ratio"]])
    print(f"\n  Top 10 Most Extreme Anomalies (all time):")
    print(f"  {'Ticker':<8} {'Date':<12} {'Score':>8} {'Return':>9} {'VolRatio':>9}")
    print("  " + "-" * 50)
    for _, row in top_ever.iterrows():
        ret_pct = row["daily_return"] * 100
        print(f"  {row['ticker']:<8} {row['date']:<12} {row['anomaly_score']:>8.4f} "
              f"{ret_pct:>+8.2f}%  {row['Volume_ratio']:>8.2f}x")

    # ── Save ──────────────────────────────────────────────────
    all_path    = os.path.join(OUTPUT_DIR, "anomaly_flags.csv")
    latest_path = os.path.join(OUTPUT_DIR, "anomaly_flags_latest.csv")
    combined.to_csv(all_path, index=False)
    pd.DataFrame(latest_rows).to_csv(latest_path, index=False)

    print(f"\n✅ Saved:")
    print(f"   {all_path}  ({len(combined):,} rows)")
    print(f"   {latest_path}")
    print(f"   {MODEL_DIR}/iso_forest_{{ticker}}.pkl  (10 models)")
    print(f"\n🔄 Next: wire AlphaScore + XGBoost + Anomaly into nightly Lambda pipeline")


if __name__ == "__main__":
    main()
