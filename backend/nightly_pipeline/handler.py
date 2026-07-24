"""
AlphaLens Nightly Pipeline Lambda — Week 4
==========================================
Triggered by EventBridge at 6pm ET (23:00 UTC) Mon–Fri after market close.

Steps:
  1. Fetch latest OHLCV for all 10 tickers from yfinance (2yr window)
  2. Compute technical features (RSI, MACD, BB%, ATR, etc.)
  3. Compute AlphaScore (weighted composite of 6 technical signals)
  4. Fetch Finnhub news → keyword sentiment → Social Score (1–10)
  5. Run Isolation Forest models (loaded from S3) → anomaly flag
  6. Run XGBoost classifier (loaded from S3) → UP/DOWN/NEUTRAL prediction
  7. Write all results to DynamoDB (StockScores, StockSummaries, StockPredictions)
  8. Archive latest OHLCV CSV to S3 (for /history API)

FinBERT is NOT used in the Lambda — the model is 440MB and exceeds Lambda's
unzipped package limit. The nightly pipeline uses fast keyword sentiment instead.
FinBERT scoring happens offline via scripts/finbert_social_score.py.

Lambda Layer requirements (in requirements-layer.txt):
  pandas, numpy, scikit-learn, xgboost, yfinance, requests, boto3

Environment variables (set by CDK):
  SCORES_TABLE      = StockScores
  SUMMARIES_TABLE   = StockSummaries
  PREDICTIONS_TABLE = StockPredictions
  DATA_BUCKET       = alphalens-raw-data
  MODEL_BUCKET      = alphalens-model-artifacts
  FINNHUB_API_KEY   = (set via AWS Secrets Manager or env var)
"""

import json
import os
import io
import pickle
import time
import warnings
import logging
from datetime import datetime, date, timedelta

# Redirect yfinance cache to /tmp (Lambda's only writable directory)
os.environ["XDG_CACHE_HOME"] = "/tmp"

import boto3
import numpy as np
import pandas as pd
import yfinance as yf

# Set yfinance cache to /tmp
try:
    yf.set_tz_cache_location("/tmp")
except Exception:
    pass

from boto3.dynamodb.conditions import Key
from decimal import Decimal

warnings.filterwarnings("ignore")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ─── Config ──────────────────────────────────────────────────────────────────

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
           "AMZN", "META", "NFLX", "AMD",  "INTC"]

TICKER_META = {
    "AAPL":  {"name": "Apple Inc.",            "sector": "Technology"},
    "MSFT":  {"name": "Microsoft Corporation", "sector": "Technology"},
    "NVDA":  {"name": "NVIDIA Corporation",    "sector": "Semiconductors"},
    "TSLA":  {"name": "Tesla Inc.",            "sector": "Automotive"},
    "GOOGL": {"name": "Alphabet Inc.",         "sector": "Technology"},
    "AMZN":  {"name": "Amazon.com Inc.",       "sector": "Consumer Cyclical"},
    "META":  {"name": "Meta Platforms Inc.",   "sector": "Technology"},
    "NFLX":  {"name": "Netflix Inc.",          "sector": "Entertainment"},
    "AMD":   {"name": "Advanced Micro Devices","sector": "Semiconductors"},
    "INTC":  {"name": "Intel Corporation",     "sector": "Semiconductors"},
}

SCORES_TABLE      = os.environ.get("SCORES_TABLE",      "StockScores")
SUMMARIES_TABLE   = os.environ.get("SUMMARIES_TABLE",   "StockSummaries")
PREDICTIONS_TABLE = os.environ.get("PREDICTIONS_TABLE", "StockPredictions")
DATA_BUCKET       = os.environ.get("DATA_BUCKET",       "alphalens-raw-data")
MODEL_BUCKET      = os.environ.get("MODEL_BUCKET",      "alphalens-model-artifacts")
FINNHUB_KEY       = os.environ.get("FINNHUB_API_KEY",   "")

dynamodb = boto3.resource("dynamodb")
s3       = boto3.client("s3")

today = date.today().isoformat()


# ─── Step 1: Fetch OHLCV ────────────────────────────────────────────────────

def fetch_prices() -> dict[str, pd.DataFrame]:
    """Download 2yr daily OHLCV for all tickers via yfinance (one at a time)."""
    logger.info("Fetching OHLCV from yfinance...")
    end   = datetime.today()
    start = end - timedelta(days=730)

    frames = {}
    for ticker in TICKERS:
        for attempt in range(3):
            try:
                t = yf.Ticker(ticker)
                df = t.history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    interval="1d",
                    auto_adjust=True,
                )
                if df.empty:
                    raise ValueError("Empty dataframe returned")
                df.index = df.index.strftime("%Y-%m-%d")
                df.index.name = "date"
                df.columns = [c.lower() for c in df.columns]
                df["ticker"]       = ticker
                df["daily_return"] = df["close"].pct_change()
                frames[ticker] = df.dropna(subset=["close"])
                logger.info(f"  {ticker}: {len(df)} rows")
                time.sleep(0.5)  # avoid rate limiting
                break
            except Exception as e:
                logger.warning(f"  {ticker} attempt {attempt+1} failed: {e}")
                time.sleep(2)
    return frames


# ─── Step 2: Feature Engineering ────────────────────────────────────────────

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]
    v = df["volume"]
    n = len(df)

    # RSI-14
    delta  = c.diff()
    gain   = delta.clip(lower=0).rolling(14).mean()
    loss   = (-delta.clip(upper=0)).rolling(14).mean()
    rs     = gain / loss.replace(0, np.nan)
    df["RSI_14"] = 100 - (100 / (1 + rs))

    # MACD (12/26/9)
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    # Bollinger Bands
    sma20    = c.rolling(20).mean()
    std20    = c.rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    df["BB_pct"] = (c - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    # ATR-14
    hl   = df["high"] - df["low"]
    hc   = (df["high"] - c.shift()).abs()
    lc   = (df["low"]  - c.shift()).abs()
    df["ATR_14"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

    # Volatility (20-day annualised)
    df["Volatility_20"] = df["daily_return"].rolling(20).std() * np.sqrt(252)

    # Momentum
    df["Momentum_20"] = c.pct_change(20) * 100

    # Volume
    df["Volume_SMA_20"] = v.rolling(20).mean()
    df["Volume_ratio"]  = v / df["Volume_SMA_20"].replace(0, np.nan)

    # SMA / EMA
    df["SMA_20"] = sma20
    df["SMA_50"] = c.rolling(50).mean()
    df["EMA_12"] = ema12
    df["EMA_26"] = ema26

    return df


# ─── Step 3: AlphaScore ─────────────────────────────────────────────────────

def score_rsi(rsi):
    if   rsi < 30:  return 90
    elif rsi < 40:  return 75
    elif rsi < 50:  return 60
    elif rsi < 60:  return 50
    elif rsi < 70:  return 35
    else:           return 15

def score_macd(macd_hist):
    if   macd_hist >  2: return 90
    elif macd_hist >  0: return 65
    elif macd_hist > -2: return 35
    else:                return 10

def score_bb(bb_pct):
    if   bb_pct < 0.2:  return 85
    elif bb_pct < 0.4:  return 65
    elif bb_pct < 0.6:  return 50
    elif bb_pct < 0.8:  return 35
    else:               return 15

def score_momentum(mom):
    if   mom >  10: return 90
    elif mom >   5: return 75
    elif mom >   0: return 55
    elif mom >  -5: return 40
    elif mom > -10: return 25
    else:           return 10

def score_volatility(vol):
    if   vol < 0.20: return 80
    elif vol < 0.35: return 65
    elif vol < 0.50: return 50
    elif vol < 0.75: return 35
    else:            return 20

def score_volratio(vr):
    if   vr > 3.0: return 85
    elif vr > 2.0: return 75
    elif vr > 1.5: return 60
    elif vr > 1.0: return 45
    else:          return 30

def compute_alpha_score(row) -> tuple[float, dict]:
    weights = {"rsi": 0.30, "macd": 0.20, "bb": 0.20,
               "mom": 0.15, "vol":  0.10, "volrat": 0.05}
    components = {
        "rsi_score":    score_rsi(row.get("RSI_14",       50)),
        "macd_score":   score_macd(row.get("MACD_hist",    0)),
        "bb_score":     score_bb(row.get("BB_pct",       0.5)),
        "mom_score":    score_momentum(row.get("Momentum_20", 0)),
        "vol_score":    score_volatility(row.get("Volatility_20", 0.3)),
        "volrat_score": score_volratio(row.get("Volume_ratio",  1.0)),
    }
    score = (
        components["rsi_score"]    * weights["rsi"]    +
        components["macd_score"]   * weights["macd"]   +
        components["bb_score"]     * weights["bb"]      +
        components["mom_score"]    * weights["mom"]    +
        components["vol_score"]    * weights["vol"]    +
        components["volrat_score"] * weights["volrat"]
    )
    return round(score, 1), components


def rsi_signal(rsi: float) -> str:
    if rsi < 30:  return "Oversold"
    if rsi < 50:  return "Neutral-Low"
    if rsi < 70:  return "Neutral-High"
    return "Overbought"


# ─── Step 4: Keyword Sentiment → Social Score ────────────────────────────────

BULLISH_WORDS = ["beat", "surge", "rally", "upgrade", "buy", "strong",
                 "growth", "record", "outperform", "profit", "bull",
                 "positive", "exceed", "gain"]
BEARISH_WORDS = ["miss", "drop", "downgrade", "sell", "weak", "cut",
                 "decline", "loss", "bear", "negative", "lawsuit",
                 "layoff", "fail", "concern", "risk"]

def keyword_sentiment(articles: list[dict]) -> dict:
    if not articles:
        return {"social_score": 5.0, "bullish_pct": 0.0, "bearish_pct": 0.0,
                "article_count": 0, "news_velocity_flag": False}

    bull, bear = 0, 0
    for a in articles:
        text = (a.get("headline", "") + " " + a.get("summary", "")).lower()
        b = sum(1 for w in BULLISH_WORDS if w in text)
        n = sum(1 for w in BEARISH_WORDS if w in text)
        if b > n:   bull += 1
        elif n > b: bear += 1

    total  = len(articles)
    bull_p = bull / total
    bear_p = bear / total
    sent   = bull_p - bear_p           # -1 to +1
    score  = round((sent + 1) / 2 * 9 + 1, 2)

    prev_week_count = max(total - 3, 1)
    velocity_flag   = total > 1.5 * prev_week_count

    return {
        "social_score":       score,
        "bullish_pct":        round(bull_p, 3),
        "bearish_pct":        round(bear_p, 3),
        "article_count":      total,
        "news_velocity_flag": velocity_flag,
    }


def fetch_news(ticker: str) -> list[dict]:
    if not FINNHUB_KEY:
        return []
    try:
        import requests
        end_d   = date.today()
        start_d = end_d - timedelta(days=7)
        url = (f"https://finnhub.io/api/v1/company-news"
               f"?symbol={ticker}&from={start_d}&to={end_d}&token={FINNHUB_KEY}")
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json()[:20]
    except Exception as e:
        logger.warning(f"Finnhub fetch failed for {ticker}: {e}")
    return []


# ─── Step 5 & 6: Load ML models from S3 ─────────────────────────────────────

_model_cache: dict = {}

def load_model_from_s3(key: str):
    if key in _model_cache:
        return _model_cache[key]
    try:
        obj  = s3.get_object(Bucket=MODEL_BUCKET, Key=key)
        data = pickle.loads(obj["Body"].read())
        _model_cache[key] = data
        logger.info(f"Loaded model: {key}")
        return data
    except Exception as e:
        logger.warning(f"Could not load {key} from S3: {e}")
        return None


def run_anomaly_detection(df: pd.DataFrame, ticker: str) -> tuple[int, float]:
    """Returns (anomaly_flag, anomaly_score) for the latest row."""
    model_data = load_model_from_s3(f"models/iso_forest_{ticker}.pkl")
    if not model_data:
        return 0, 0.0

    feature_cols = ["daily_return", "Volume_ratio", "Volatility_20",
                    "ATR_14", "BB_pct"]
    latest = df.dropna(subset=feature_cols).iloc[-1]
    X = latest[feature_cols].values.reshape(1, -1)

    try:
        from sklearn.preprocessing import StandardScaler
        model  = model_data["model"]
        scaler = model_data["scaler"]
        X_scaled = scaler.transform(X)
        flag  = int(model.predict(X_scaled)[0] == -1)
        score = float(model.decision_function(X_scaled)[0])
        return flag, round(score, 4)
    except Exception as e:
        logger.warning(f"Anomaly detection failed for {ticker}: {e}")
        return 0, 0.0


FEATURE_COLS = ["RSI_14", "MACD", "MACD_signal", "MACD_hist",
                "BB_pct", "ATR_14", "Volatility_20", "Momentum_20",
                "Volume_ratio", "SMA_20", "SMA_50", "EMA_12", "EMA_26"]
LABEL_MAP = {0: "DOWN", 1: "NEUTRAL", 2: "UP"}

def run_xgboost(df: pd.DataFrame) -> dict:
    """Returns prediction dict for the latest row."""
    model = load_model_from_s3("models/xgb_classifier.pkl")
    if not model:
        return {"prediction": "NEUTRAL", "confidence": 0.34,
                "prob_up": 0.33, "prob_down": 0.33, "prob_neutral": 0.34}

    available = [c for c in FEATURE_COLS if c in df.columns]
    latest = df.dropna(subset=available).iloc[-1]
    X = latest[available].values.reshape(1, -1)

    try:
        label_code = int(model.predict(X)[0])
        proba      = model.predict_proba(X)[0]
        label      = LABEL_MAP.get(label_code, "NEUTRAL")
        confidence = float(max(proba))
        return {
            "prediction":   label,
            "confidence":   round(confidence, 4),
            "prob_down":    round(float(proba[0]), 4),
            "prob_neutral": round(float(proba[1]), 4),
            "prob_up":      round(float(proba[2]), 4),
            "horizon_days": 5,
        }
    except Exception as e:
        logger.warning(f"XGBoost prediction failed: {e}")
        return {"prediction": "NEUTRAL", "confidence": 0.34,
                "prob_up": 0.33, "prob_down": 0.33, "prob_neutral": 0.34}


# ─── Step 7: Write to DynamoDB ───────────────────────────────────────────────

def to_decimal(v) -> Decimal:
    return Decimal(str(round(float(v), 4)))


def write_score(table, ticker: str, row: pd.Series,
                alpha_score: float, components: dict,
                anomaly_flag: int, anomaly_score: float):
    rsi  = float(row.get("RSI_14", 50))
    meta = TICKER_META.get(ticker, {"name": ticker, "sector": "Unknown"})

    table.put_item(Item={
        "PK":             f"TICKER#{ticker}",
        "SK":             f"SCORE#{today}",
        "ticker":         ticker,
        "name":           meta["name"],
        "sector":         meta["sector"],
        "close":          to_decimal(row["close"]),
        "momentum_20":    to_decimal(row.get("Momentum_20", 0)),
        "rsi":            to_decimal(rsi),
        "rsi_signal":     rsi_signal(rsi),
        "macd_hist":      to_decimal(row.get("MACD_hist", 0)),
        "bb_pct":         to_decimal(row.get("BB_pct", 0.5)),
        "volatility_20":  to_decimal(row.get("Volatility_20", 0)),
        "vol_spikes":     int(row.get("Volume_ratio", 0) > 2.0),
        "alpha_score":    to_decimal(alpha_score),
        "anomaly_flag":   anomaly_flag,
        "anomaly_score":  to_decimal(anomaly_score),
        # component scores
        **{k: to_decimal(v) for k, v in components.items()},
        "updated_at":     today,
    })


def write_summary(table, ticker: str, sentiment: dict):
    table.put_item(Item={
        "PK":                f"TICKER#{ticker}",
        "SK":                f"SUMMARY#{today}",
        "ticker":            ticker,
        "social_score":      to_decimal(sentiment["social_score"]),
        "bullish_pct":       to_decimal(sentiment["bullish_pct"]),
        "bearish_pct":       to_decimal(sentiment["bearish_pct"]),
        "article_count":     int(sentiment["article_count"]),
        "news_velocity_flag":bool(sentiment["news_velocity_flag"]),
        "updated_at":        today,
    })


def write_prediction(table, ticker: str, pred: dict):
    table.put_item(Item={
        "PK":           f"TICKER#{ticker}",
        "SK":           f"PRED#{today}",
        "ticker":       ticker,
        "prediction":   pred["prediction"],
        "confidence":   to_decimal(pred["confidence"]),
        "prob_up":      to_decimal(pred["prob_up"]),
        "prob_down":    to_decimal(pred["prob_down"]),
        "prob_neutral": to_decimal(pred["prob_neutral"]),
        "horizon_days": int(pred.get("horizon_days", 5)),
        "updated_at":   today,
    })


# ─── Step 8: Archive history to S3 ──────────────────────────────────────────

def archive_history(ticker: str, df: pd.DataFrame):
    """Write the full 2yr OHLCV CSV to S3 for the /history API."""
    cols   = ["open", "high", "low", "close", "volume", "daily_return"]
    avail  = [c for c in cols if c in df.columns]
    csv    = df[avail].to_csv()
    key    = f"processed/{ticker}/history.csv"
    s3.put_object(Bucket=DATA_BUCKET, Key=key, Body=csv.encode("utf-8"))
    logger.info(f"  Archived history to s3://{DATA_BUCKET}/{key}")


# ─── Main handler ────────────────────────────────────────────────────────────

def handler(event, context):
    logger.info(f"=== AlphaLens Nightly Pipeline — {today} ===")

    scores_table      = dynamodb.Table(SCORES_TABLE)
    summaries_table   = dynamodb.Table(SUMMARIES_TABLE)
    predictions_table = dynamodb.Table(PREDICTIONS_TABLE)

    # 1. Fetch prices
    frames = fetch_prices()
    if not frames:
        return {"statusCode": 500, "body": "Failed to fetch price data"}

    results = []
    for ticker in TICKERS:
        df = frames.get(ticker)
        if df is None or len(df) < 30:
            logger.warning(f"{ticker}: insufficient data, skipping")
            continue

        logger.info(f"\n--- Processing {ticker} ---")

        # 2. Features
        df = compute_features(df)
        latest = df.iloc[-1]

        # 3. AlphaScore
        alpha_score, components = compute_alpha_score(latest.to_dict())
        logger.info(f"  AlphaScore: {alpha_score}")

        # 4. Sentiment
        articles  = fetch_news(ticker)
        sentiment = keyword_sentiment(articles)
        discovery = round(0.6 * alpha_score + 0.4 * (sentiment["social_score"] * 10), 1)
        logger.info(f"  Social: {sentiment['social_score']}  Discovery: {discovery}")

        # 5. Anomaly detection
        anomaly_flag, anomaly_score = run_anomaly_detection(df, ticker)
        logger.info(f"  Anomaly: {'🚨' if anomaly_flag else '✅'} ({anomaly_score:.4f})")

        # 6. XGBoost prediction
        pred = run_xgboost(df)
        logger.info(f"  Prediction: {pred['prediction']} ({pred['confidence']*100:.0f}%)")

        # 7. Write to DynamoDB
        write_score(scores_table, ticker, latest, alpha_score, components,
                    anomaly_flag, anomaly_score)
        write_summary(summaries_table, ticker, sentiment)
        write_prediction(predictions_table, ticker, pred)

        # 8. Archive history
        archive_history(ticker, df)

        results.append({
            "ticker":       ticker,
            "alpha_score":  alpha_score,
            "social_score": sentiment["social_score"],
            "discovery":    discovery,
            "prediction":   pred["prediction"],
            "anomaly":      bool(anomaly_flag),
        })

    logger.info(f"\n=== Pipeline complete — {len(results)}/{len(TICKERS)} tickers processed ===")
    for r in results:
        flag = "🚨" if r["anomaly"] else "✅"
        logger.info(f"  {r['ticker']:<6} α={r['alpha_score']} s={r['social_score']} "
                    f"d={r['discovery']} {r['prediction']} {flag}")

    return {"statusCode": 200, "body": json.dumps({"processed": len(results), "results": results})}
