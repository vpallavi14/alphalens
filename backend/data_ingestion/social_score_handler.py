"""
Social Score Lambda — Week 3 (FinBERT upgrade)
===============================================
Runs nightly (EventBridge cron). For each ticker:
  1. Fetches last 7 days of news from Finnhub /company-news (free tier)
  2. Scores each headline with keyword sentiment → raw score (-1 to +1)
  3. Converts to Social Score (1-10)
  4. Reads previous week's article count from DynamoDB to compute news velocity
  5. Writes result to DynamoDB StockSummaries table

DynamoDB schema (StockSummaries):
  PK: TICKER#<symbol>       e.g.  TICKER#AAPL
  SK: SUMMARY#<YYYY-MM-DD>  e.g.  SUMMARY#2026-06-24
  Attributes:
    social_score       Decimal  1.0–10.0
    sentiment_score    Decimal  -1.0–1.0
    bullish_pct        Decimal  0.0–1.0
    bearish_pct        Decimal  0.0–1.0
    article_count      Number
    news_velocity_flag Boolean  True if articles > 1.5× previous week
    prev_article_count Number   (last known weekly count)
    updated_at         String   ISO-8601 UTC

Environment variables (set in Lambda console or CDK):
  FINNHUB_API_KEY        required
  DYNAMODB_TABLE_SUMMARIES  default: StockSummaries
  AWS_REGION             default: us-east-1
"""

import os
import json
import logging
import time
import requests
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

# ── FinBERT (loaded once at Lambda cold start) ────────────────
# Falls back to keyword scoring if transformers not installed.
FINBERT_PIPE = None

def _load_finbert():
    global FINBERT_PIPE
    if FINBERT_PIPE is not None:
        return FINBERT_PIPE
    try:
        from transformers import pipeline
        # Model stored in /tmp on Lambda (loaded from S3 layer or EFS)
        FINBERT_PIPE = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            top_k=None,
            device=-1,
            truncation=True,
            max_length=512,
        )
        logger.info("FinBERT loaded successfully")
    except Exception as e:
        logger.warning(f"FinBERT unavailable ({e}) — falling back to keyword scoring")
        FINBERT_PIPE = None
    return FINBERT_PIPE

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FINNHUB_KEY   = os.environ.get("FINNHUB_API_KEY", "")
FINNHUB_BASE  = "https://finnhub.io/api/v1"
TABLE_NAME    = os.environ.get("DYNAMODB_TABLE_SUMMARIES", "StockSummaries")
REGION        = os.environ.get("AWS_REGION", "us-east-1")
NEWS_DAYS     = 7          # days of news to fetch
VELOCITY_MULT = 1.5        # flag if articles > 1.5× previous week

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
           "AMZN", "META", "NFLX", "AMD",  "INTC"]

# ─────────────────────────────────────────────────────────────────────────────
# Sentiment keywords (same as pull_finnhub_to_excel.py)
# Week 3 will replace this with FinBERT
# ─────────────────────────────────────────────────────────────────────────────

POSITIVE_WORDS = {
    "beats", "record", "surge", "growth", "profit", "upgrade",
    "buy", "bullish", "rally", "rises", "gain", "strong", "outperform",
    "raises", "exceeds", "soars", "momentum", "breakthrough", "wins",
    "beat", "top", "positive", "higher", "up", "boost",
}
NEGATIVE_WORDS = {
    "miss", "drop", "fall", "loss", "downgrade", "sell", "bearish",
    "decline", "cut", "layoff", "warn", "recall", "investigation",
    "lawsuit", "fraud", "crash", "disappoints", "weak", "risk", "concern",
    "missed", "fell", "dropped", "lower", "down", "fear", "trouble",
}

# ─────────────────────────────────────────────────────────────────────────────
# Finnhub helpers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_news(ticker: str) -> list:
    """Fetch last NEWS_DAYS days of company news from Finnhub (free tier)."""
    end   = date.today()
    start = end - timedelta(days=NEWS_DAYS)
    try:
        r = requests.get(
            f"{FINNHUB_BASE}/company-news",
            params={"symbol": ticker, "from": str(start), "to": str(end), "token": FINNHUB_KEY},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        logger.warning(f"{ticker}: Finnhub returned {r.status_code}")
    except Exception as e:
        logger.error(f"{ticker}: fetch_news error — {e}")
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Sentiment scoring
# ─────────────────────────────────────────────────────────────────────────────

def finbert_sentiment(articles: list) -> dict | None:
    """
    Run ProsusAI/finbert on headlines. Returns same format as keyword_sentiment.
    Returns None if FinBERT is not available (caller falls back to keywords).
    """
    pipe = _load_finbert()
    if pipe is None or not articles:
        return None

    headlines = [a.get("headline", "") for a in articles if a.get("headline")][:30]
    if not headlines:
        return None

    try:
        results = pipe(headlines)
        pos_vals, neg_vals = [], []
        for label_scores in results:
            scores = {item["label"]: item["score"] for item in label_scores}
            pos_vals.append(scores.get("positive", 0))
            neg_vals.append(scores.get("negative", 0))

        pos_avg = sum(pos_vals) / len(pos_vals)
        neg_avg = sum(neg_vals) / len(neg_vals)
        total   = len(headlines)

        return {
            "sentiment": {
                "score":         round(pos_avg - neg_avg, 4),
                "bullishPercent": round(pos_avg, 4),
                "bearishPercent": round(neg_avg, 4),
            },
            "buzz": {
                "articlesInLastWeek": total,
                "buzz":               round(total / 10, 2),
                "weeklyAverage":      total,
            },
            "method": "finbert",
        }
    except Exception as e:
        logger.warning(f"FinBERT inference failed: {e} — falling back to keywords")
        return None


def keyword_sentiment(articles: list) -> dict:
    """
    Score headlines by counting positive vs negative keywords.
    Returns:
      score         float  -1 to +1  (positive = bullish)
      bullish_pct   float  0 to 1
      bearish_pct   float  0 to 1
      article_count int
    """
    if not articles:
        return {"score": 0.0, "bullish_pct": 0.0, "bearish_pct": 0.0, "article_count": 0}

    pos = neg = neutral = 0
    for article in articles:
        words   = set(article.get("headline", "").lower().split())
        has_pos = bool(words & POSITIVE_WORDS)
        has_neg = bool(words & NEGATIVE_WORDS)
        if has_pos and not has_neg:
            pos += 1
        elif has_neg and not has_pos:
            neg += 1
        else:
            neutral += 1

    total = len(articles)
    return {
        "score":        round((pos - neg) / total, 4),
        "bullish_pct":  round(pos / total, 4),
        "bearish_pct":  round(neg / total, 4),
        "article_count": total,
    }


def social_score(sentiment_score: float) -> float:
    """Map -1..+1 sentiment score → 1–10 Social Score."""
    return round((sentiment_score + 1) / 2 * 9 + 1, 1)


# ─────────────────────────────────────────────────────────────────────────────
# DynamoDB helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_dynamodb_table():
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return dynamodb.Table(TABLE_NAME)


def get_prev_article_count(table, ticker: str) -> int:
    """Read last week's article count from DynamoDB for velocity comparison."""
    prev_date = (date.today() - timedelta(days=7)).isoformat()
    try:
        resp = table.get_item(
            Key={"PK": f"TICKER#{ticker}", "SK": f"SUMMARY#{prev_date}"}
        )
        item = resp.get("Item", {})
        return int(item.get("article_count", 0))
    except Exception as e:
        logger.warning(f"{ticker}: could not read prev count — {e}")
        return 0


def write_summary(table, ticker: str, sentiment: dict, score: float,
                  velocity_flag: bool, prev_count: int) -> None:
    """Write Social Score record to DynamoDB StockSummaries."""
    today = date.today().isoformat()
    now   = datetime.now(timezone.utc).isoformat()

    item = {
        "PK":               f"TICKER#{ticker}",
        "SK":               f"SUMMARY#{today}",
        "ticker":           ticker,
        "date":             today,
        "social_score":     Decimal(str(score)),
        "sentiment_score":  Decimal(str(sentiment["score"])),
        "bullish_pct":      Decimal(str(sentiment["bullish_pct"])),
        "bearish_pct":      Decimal(str(sentiment["bearish_pct"])),
        "article_count":    sentiment["article_count"],
        "news_velocity_flag": velocity_flag,
        "prev_article_count": prev_count,
        "updated_at":       now,
    }
    table.put_item(Item=item)
    logger.info(f"{ticker}: wrote social_score={score} articles={sentiment['article_count']} velocity={velocity_flag}")


# ─────────────────────────────────────────────────────────────────────────────
# Lambda handler
# ─────────────────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Entry point for AWS Lambda.
    EventBridge trigger: runs nightly after price data ingestion.
    """
    if not FINNHUB_KEY:
        logger.error("FINNHUB_API_KEY not set — aborting")
        return {"statusCode": 500, "body": "Missing FINNHUB_API_KEY"}

    logger.info(f"Social Score Lambda started — processing {len(TICKERS)} tickers")

    table   = get_dynamodb_table()
    results = []

    for ticker in TICKERS:
        try:
            # 1. Fetch news
            articles  = fetch_news(ticker)

            # 2. Score sentiment — FinBERT first, keyword fallback
            sentiment = finbert_sentiment(articles) or keyword_sentiment(articles)
            score     = social_score(sentiment["sentiment"]["score"])

            # 3. News velocity: compare to previous week
            prev_count    = get_prev_article_count(table, ticker)
            velocity_flag = (
                sentiment["article_count"] > prev_count * VELOCITY_MULT
                and sentiment["article_count"] > 0
                and prev_count > 0
            )

            # 4. Write to DynamoDB
            write_summary(table, ticker, sentiment, score, velocity_flag, prev_count)

            results.append({
                "ticker":       ticker,
                "social_score": score,
                "articles":     sentiment["article_count"],
                "velocity":     velocity_flag,
            })

        except Exception as e:
            logger.error(f"{ticker}: unhandled error — {e}", exc_info=True)
            results.append({"ticker": ticker, "error": str(e)})

        time.sleep(0.5)   # Finnhub free tier = 60 calls/min

    logger.info(f"Social Score Lambda complete — {len(results)} tickers processed")
    return {
        "statusCode": 200,
        "body": json.dumps(results),
    }
