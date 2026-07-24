"""
seed_dynamodb.py — Seed DynamoDB from local CSV outputs
========================================================
Reads from scripts/output/ and writes to:
  - StockScores     (AlphaScore, RSI, MACD, BB, anomaly)
  - StockSummaries  (SocialScore, sentiment)
  - StockPredictions (XGBoost UP/DOWN/NEUTRAL)

Run from alphalens/ directory:
  python scripts/seed_dynamodb.py
"""

import boto3
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
import os, json

# ── Config ────────────────────────────────────────────────────────────────────

SCORES_TABLE      = "StockScores"
SUMMARIES_TABLE   = "StockSummaries"
PREDICTIONS_TABLE = "StockPredictions"
REGION            = "us-east-1"

TICKER_META = {
    "AAPL":  {"name": "Apple Inc.",             "sector": "Technology"},
    "MSFT":  {"name": "Microsoft Corporation",  "sector": "Technology"},
    "NVDA":  {"name": "NVIDIA Corporation",     "sector": "Semiconductors"},
    "TSLA":  {"name": "Tesla Inc.",             "sector": "Automotive"},
    "GOOGL": {"name": "Alphabet Inc.",          "sector": "Technology"},
    "AMZN":  {"name": "Amazon.com Inc.",        "sector": "Consumer Cyclical"},
    "META":  {"name": "Meta Platforms Inc.",    "sector": "Technology"},
    "NFLX":  {"name": "Netflix Inc.",           "sector": "Entertainment"},
    "AMD":   {"name": "Advanced Micro Devices", "sector": "Semiconductors"},
    "INTC":  {"name": "Intel Corporation",      "sector": "Semiconductors"},
}

BASE = os.path.dirname(__file__)

def d(val):
    """Convert float to Decimal for DynamoDB."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return Decimal("0")
    return Decimal(str(round(float(val), 4)))

def load_latest_prices():
    """Get latest close, volume from historical CSVs."""
    prices = {}
    hist_dir = os.path.join(BASE, "output", "historical")
    for ticker in TICKER_META:
        path = os.path.join(hist_dir, f"{ticker}.csv")
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        df = df.dropna(subset=["close"])
        if df.empty:
            continue
        last = df.iloc[-1]
        prev = df.iloc[-21] if len(df) > 21 else df.iloc[0]
        prices[ticker] = {
            "close":          float(last["close"]),
            "volume":         float(last["volume"]),
            "change_pct_20d": round((float(last["close"]) - float(prev["close"])) / float(prev["close"]) * 100, 2),
            "date":           str(last["date"])[:10],
        }
    return prices

# ── Load CSVs ─────────────────────────────────────────────────────────────────

print("Loading CSVs...")
scores_df   = pd.read_csv(os.path.join(BASE, "output", "alpha_scores_latest.csv"))
finbert_df  = pd.read_csv(os.path.join(BASE, "output", "finbert_scores.csv"))
anomaly_df  = pd.read_csv(os.path.join(BASE, "output", "anomaly_flags_latest.csv"))
predict_df  = pd.read_csv(os.path.join(BASE, "output", "xgb_predictions.csv"))
prices      = load_latest_prices()

scores_df   = scores_df.set_index("ticker")
finbert_df  = finbert_df.set_index("ticker")
anomaly_df  = anomaly_df.set_index("ticker")
predict_df  = predict_df.set_index("ticker")

# ── DynamoDB ──────────────────────────────────────────────────────────────────

dynamo = boto3.resource("dynamodb", region_name=REGION)
scores_tbl   = dynamo.Table(SCORES_TABLE)
summary_tbl  = dynamo.Table(SUMMARIES_TABLE)
predict_tbl  = dynamo.Table(PREDICTIONS_TABLE)

tickers = list(TICKER_META.keys())
today   = scores_df["date"].iloc[0] if "date" in scores_df.columns else "2026-06-18"

print(f"Seeding {len(tickers)} tickers for date={today}\n")

for ticker in tickers:
    meta = TICKER_META[ticker]
    price_info = prices.get(ticker, {})
    date_str = price_info.get("date", today)

    # ── Scores row ──────────────────────────────────────────────────────────
    s   = scores_df.loc[ticker]
    an  = anomaly_df.loc[ticker]
    fb  = finbert_df.loc[ticker]

    close         = d(price_info.get("close", 0))
    volume        = d(price_info.get("volume", 0))
    change_pct    = d(price_info.get("change_pct_20d", 0))
    alpha_score   = d(s["alpha_score"])
    rsi           = d(s["rsi"])
    bb_pct        = d(s["bb_pct"])
    volatility    = d(s["volatility"])
    vol_ratio     = d(s["vol_ratio"])
    macd_dir      = str(s["macd_dir"])
    anomaly_flag  = int(an["anomaly_flag"])
    social_score  = d(fb["finbert_score"])
    discovery     = d(float(alpha_score) * 0.6 + float(social_score) * 10 * 0.4)
    rsi_signal    = "Oversold" if float(rsi) < 30 else "Overbought" if float(rsi) > 70 else "Neutral"
    vol_spikes    = d(an["volume_ratio"])

    scores_tbl.put_item(Item={
        "PK": f"TICKER#{ticker}",
        "SK": f"SCORE#{date_str}",
        "ticker":         ticker,
        "name":           meta["name"],
        "sector":         meta["sector"],
        "date":           date_str,
        "close":          close,
        "volume":         volume,
        "change_pct":     change_pct,
        "alpha_score":    alpha_score,
        "social_score":   social_score,
        "discovery_score":discovery,
        "rsi":            rsi,
        "rsi_signal":     rsi_signal,
        "macd":           macd_dir,
        "bb_pct":         bb_pct,
        "volatility":     volatility,
        "vol_ratio":      vol_ratio,
        "vol_spikes":     vol_spikes,
        "anomaly_flag":   anomaly_flag,
        "in_watchlist":   ticker in ["AAPL", "NVDA", "MSFT"],
    })
    print(f"  ✅ StockScores: {ticker} | alpha={float(alpha_score):.1f} rsi={float(rsi):.1f} anomaly={anomaly_flag}")

    # ── Summaries row ────────────────────────────────────────────────────────
    summary_tbl.put_item(Item={
        "PK": f"TICKER#{ticker}",
        "SK": f"SUMMARY#{date_str}",
        "ticker":       ticker,
        "date":         date_str,
        "social_score": social_score,
        "finbert_score":d(fb["finbert_score"]),
        "keyword_score":d(fb["keyword_score"]),
        "pos_avg":      d(fb["pos_avg"]),
        "neg_avg":      d(fb["neg_avg"]),
        "neu_avg":      d(fb["neu_avg"]),
    })
    print(f"  ✅ StockSummaries: {ticker} | social={float(social_score):.1f}")

    # ── Predictions row ──────────────────────────────────────────────────────
    if ticker in predict_df.index:
        p = predict_df.loc[ticker]
        prediction = str(p["prediction"])
        confidence = d(p["confidence"])
        icon = "↑" if prediction == "UP" else "↓" if prediction == "DOWN" else "→"

        predict_tbl.put_item(Item={
            "PK": f"TICKER#{ticker}",
            "SK": f"PRED#{date_str}",
            "ticker":       ticker,
            "date":         date_str,
            "prediction":   prediction,
            "confidence":   confidence,
            "prob_up":      d(p["prob_up"]),
            "prob_down":    d(p["prob_down"]),
            "prob_neutral": d(p["prob_neutral"]),
            "anomaly_flag": anomaly_flag,
            "display": {
                "icon":  icon,
                "label": f"{prediction} ({float(confidence)*100:.0f}% conf)",
            },
        })
        print(f"  ✅ StockPredictions: {ticker} | {prediction} {float(confidence)*100:.0f}%")

    print()

print("=" * 50)
print(f"✅ Seeded {len(tickers)} tickers into DynamoDB")
print("Now test the API:")
print("  curl https://8ptxnd1uoi.execute-api.us-east-1.amazonaws.com/scores")
