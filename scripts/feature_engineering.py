"""
Feature Engineering — Week 2, Step 2
======================================
Reads historical OHLCV data from all_tickers.csv and computes:

  Price Trend:
    - SMA_20, SMA_50          Simple Moving Averages
    - EMA_12, EMA_26          Exponential Moving Averages

  Momentum:
    - RSI_14                  Relative Strength Index (0-100)
    - MACD, MACD_signal,      Moving Average Convergence Divergence
      MACD_hist
    - Momentum_20             20-day price rate of change
    - Stoch_K                 Stochastic Oscillator %K

  Volatility:
    - BB_upper, BB_lower,     Bollinger Bands (20-day, 2σ)
      BB_mid, BB_pct
    - ATR_14                  Average True Range
    - Volatility_20           20-day annualised rolling volatility

  Volume:
    - Volume_SMA_20           20-day average volume
    - Volume_ratio            today's volume / 20-day avg
    - Volume_spike            True if volume > 2x average
    - OBV                     On-Balance Volume

  Composite:
    - VWAP_signal             1 if close > rolling VWAP proxy, else 0
    - Price_vs_SMA50          % distance from 50-day MA
    - BB_position             where close sits in Bollinger band (0-1)

Run:
  python scripts/feature_engineering.py
Output:
  scripts/output/features/all_features.csv
  scripts/output/features/{TICKER}_features.csv
"""

import os
import pandas as pd
import numpy as np

INPUT_FILE  = os.path.join(os.path.dirname(__file__), "output", "historical", "all_tickers.csv")
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "output", "features")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Individual indicator functions
# ─────────────────────────────────────────────────────────────

def compute_sma(series, window):
    return series.rolling(window=window).mean()

def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def compute_rsi(series, period=14):
    delta  = series.diff()
    gain   = delta.clip(lower=0)
    loss   = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.round(2)

def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast   = compute_ema(series, fast)
    ema_slow   = compute_ema(series, slow)
    macd       = ema_fast - ema_slow
    macd_sig   = macd.ewm(span=signal, adjust=False).mean()
    macd_hist  = macd - macd_sig
    return macd.round(4), macd_sig.round(4), macd_hist.round(4)

def compute_bollinger(series, window=20, num_std=2):
    mid   = series.rolling(window).mean()
    std   = series.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    # BB% = how far price is within the band (0 = lower, 1 = upper)
    bb_pct = ((series - lower) / (upper - lower)).round(4)
    return upper.round(4), lower.round(4), mid.round(4), bb_pct

def compute_atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean().round(4)

def compute_volatility(daily_return, window=20):
    return (daily_return.rolling(window).std() * np.sqrt(252)).round(4)

def compute_momentum(series, period=20):
    return (series / series.shift(period) - 1).round(4)

def compute_stoch_k(high, low, close, period=14):
    low_min  = low.rolling(period).min()
    high_max = high.rolling(period).max()
    k = ((close - low_min) / (high_max - low_min) * 100).round(2)
    return k

def compute_obv(close, volume):
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum().astype(int)

def compute_vwap_signal(close, volume):
    """Rolling 20-day VWAP proxy: cumulative(price*vol) / cumulative(vol)"""
    tp = close  # true price proxy (we don't have intraday H+L+C/3)
    cum_pv = (tp * volume).rolling(20).sum()
    cum_v  = volume.rolling(20).sum()
    vwap   = cum_pv / cum_v
    return (close > vwap).fillna(False)

# ─────────────────────────────────────────────────────────────
# Per-ticker feature computation
# ─────────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().sort_values("date").reset_index(drop=True)

    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]
    r = df["daily_return"]

    # ── Price Trend ──────────────────────────────────────────
    df["SMA_20"]  = compute_sma(c, 20).round(4)
    df["SMA_50"]  = compute_sma(c, 50).round(4)
    df["EMA_12"]  = compute_ema(c, 12).round(4)
    df["EMA_26"]  = compute_ema(c, 26).round(4)

    # ── Momentum ─────────────────────────────────────────────
    df["RSI_14"]          = compute_rsi(c)
    df["MACD"], df["MACD_signal"], df["MACD_hist"] = compute_macd(c)
    df["Momentum_20"]     = compute_momentum(c, 20)
    df["Stoch_K"]         = compute_stoch_k(h, l, c)

    # ── Volatility ───────────────────────────────────────────
    df["BB_upper"], df["BB_lower"], df["BB_mid"], df["BB_pct"] = compute_bollinger(c)
    df["ATR_14"]          = compute_atr(h, l, c)
    df["Volatility_20"]   = compute_volatility(r)

    # ── Volume ───────────────────────────────────────────────
    df["Volume_SMA_20"]   = compute_sma(v, 20).round(0).astype("Int64")
    df["Volume_ratio"]    = (v / df["Volume_SMA_20"]).round(4)
    df["Volume_spike"]    = (df["Volume_ratio"] > 2.0).fillna(False).astype(int)
    df["OBV"]             = compute_obv(c, v)

    # ── Composite ────────────────────────────────────────────
    df["VWAP_signal"]     = compute_vwap_signal(c, v).fillna(0).astype(int)
    df["Price_vs_SMA50"]  = ((c - df["SMA_50"]) / df["SMA_50"]).round(4)
    df["BB_position"]     = df["BB_pct"]   # alias for clarity

    # RSI labels for human readability
    df["RSI_signal"] = pd.cut(
        df["RSI_14"],
        bins=[0, 30, 50, 70, 100],
        labels=["Oversold", "Neutral-Low", "Neutral-High", "Overbought"]
    ).astype(str)

    # MACD crossover signal
    df["MACD_cross"] = np.where(
        (df["MACD"] > df["MACD_signal"]) & (df["MACD"].shift(1) <= df["MACD_signal"].shift(1)),
        "Bullish Cross",
        np.where(
            (df["MACD"] < df["MACD_signal"]) & (df["MACD"].shift(1) >= df["MACD_signal"].shift(1)),
            "Bearish Cross",
            "None"
        )
    )

    return df

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    print(f"Loading historical data from {INPUT_FILE}...\n")
    raw = pd.read_csv(INPUT_FILE)
    print(f"  {len(raw):,} rows · {raw['ticker'].nunique()} tickers\n")

    all_features = []
    summary = []

    for ticker in sorted(raw["ticker"].unique()):
        df_ticker = raw[raw["ticker"] == ticker].copy()
        df_feat   = engineer_features(df_ticker)

        # Save per-ticker CSV
        out_path = os.path.join(OUTPUT_DIR, f"{ticker}_features.csv")
        df_feat.to_csv(out_path, index=False)
        all_features.append(df_feat)

        # Latest row stats for summary
        latest = df_feat.dropna(subset=["RSI_14", "MACD"]).iloc[-1]
        spikes = df_feat["Volume_spike"].sum()
        crosses = df_feat[df_feat["MACD_cross"] != "None"]["MACD_cross"].value_counts()

        summary.append({
            "ticker":       ticker,
            "latest_date":  latest["date"],
            "close":        round(latest["close"], 2),
            "RSI_14":       round(latest["RSI_14"], 1),
            "RSI_signal":   latest["RSI_signal"],
            "MACD":         round(latest["MACD"], 4),
            "MACD_signal":  round(latest["MACD_signal"], 4),
            "BB_pct":       round(latest["BB_pct"], 3),
            "Volatility":   f"{latest['Volatility_20']*100:.1f}%",
            "Momentum_20":  f"{latest['Momentum_20']*100:.1f}%",
            "Vol_spikes":   int(spikes),
            "Bullish_X":    crosses.get("Bullish Cross", 0),
            "Bearish_X":    crosses.get("Bearish Cross", 0),
        })

        print(f"  ✅ {ticker}: RSI={latest['RSI_14']:.1f} ({latest['RSI_signal']}) | "
              f"MACD={'▲' if latest['MACD'] > latest['MACD_signal'] else '▼'} | "
              f"BB%={latest['BB_pct']:.2f} | Vol spikes={int(spikes)}")

    # Save combined features
    combined = pd.concat(all_features, ignore_index=True)
    combined_path = os.path.join(OUTPUT_DIR, "all_features.csv")
    combined.to_csv(combined_path, index=False)

    # Print summary table
    print(f"\n{'='*90}")
    print(f"  FEATURE SUMMARY — Latest values as of most recent trading day")
    print(f"{'='*90}")
    print(f"\n{'Ticker':<8} {'Close':>8} {'RSI':>6} {'RSI Label':<14} {'MACD':>8} {'BB%':>6} {'Volatility':>10} {'Mom20':>8} {'VolSpikes':>10}")
    print("-"*90)
    for r in summary:
        print(f"{r['ticker']:<8} ${r['close']:>7} {r['RSI_14']:>6.1f} {r['RSI_signal']:<14} "
              f"{r['MACD']:>8.4f} {r['BB_pct']:>6.3f} {r['Volatility']:>10} "
              f"{r['Momentum_20']:>8} {r['Vol_spikes']:>10}")

    print(f"\n✅ Saved {len(summary)} feature files to {OUTPUT_DIR}/")
    print(f"   Combined: all_features.csv ({len(combined):,} rows × {len(combined.columns)} columns)")
    print(f"\nFeature columns: {[c for c in combined.columns if c not in ['ticker','date','open','high','low','close','volume','daily_return']]}")

if __name__ == "__main__":
    main()
