"""
Scores API Handler — Week 4
============================
Handles:
  GET /scores          → latest AlphaScore, SocialScore, DiscoveryScore for all 10 tickers
  GET /scores/{ticker} → same but single ticker, plus full component breakdown

DynamoDB schema:
  Table: AlphaLens-StockScores
  PK: TICKER#<symbol>   e.g. TICKER#AAPL
  SK: SCORE#<date>      e.g. SCORE#2024-01-15

The nightly Lambda pipeline writes here after running AlphaScore + Isolation Forest.
We always query the latest item per ticker (SK descending, Limit=1).

Environment variables:
  SCORES_TABLE  — DynamoDB table name (set by CDK)
  SUMMARIES_TABLE — DynamoDB table name for social/sentiment data
"""

import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
SCORES_TABLE     = os.environ.get("SCORES_TABLE", "StockScores")
SUMMARIES_TABLE  = os.environ.get("SUMMARIES_TABLE", "StockSummaries")

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
           "AMZN", "META", "NFLX", "AMD",  "INTC"]

# RSI signal classifier — mirrors alpha_score_engine.py logic
def rsi_signal(rsi: float) -> str:
    if rsi < 30:   return "Oversold"
    if rsi < 50:   return "Neutral-Low"
    if rsi < 70:   return "Neutral-High"
    return "Overbought"


def decimal_to_float(obj):
    """DynamoDB returns Decimal; JSON can't serialize it."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def get_latest_score(table, ticker: str) -> dict | None:
    """Fetch the most recent score record for a ticker."""
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"TICKER#{ticker}") & Key("SK").begins_with("SCORE#"),
        ScanIndexForward=False,   # descending — newest first
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def get_latest_summary(table, ticker: str) -> dict | None:
    """Fetch the most recent social/sentiment summary for a ticker."""
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"TICKER#{ticker}") & Key("SK").begins_with("SUMMARY#"),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def build_stock_item(score_item: dict, summary_item: dict | None) -> dict:
    """Merge score + summary into the shape the frontend expects."""
    rsi = float(score_item.get("rsi", 50))
    close = float(score_item.get("close", 0))
    social_score = float((summary_item or {}).get("social_score", 5.0))
    alpha_score  = float(score_item.get("alpha_score", 50.0))
    discovery    = round(0.6 * alpha_score + 0.4 * (social_score * 10), 1)

    return {
        "ticker":         score_item.get("ticker"),
        "name":           score_item.get("name", ""),
        "sector":         score_item.get("sector", ""),
        "close":          close,
        "changePercent":  float(score_item.get("momentum_20", 0)),
        "rsi":            rsi,
        "rsiSignal":      rsi_signal(rsi),
        "macd":           "Bullish" if float(score_item.get("macd_hist", 0)) > 0 else "Bearish",
        "bbPct":          float(score_item.get("bb_pct", 0.5)),
        "volatility":     float(score_item.get("volatility_20", 0)),
        "volSpikes":      int(score_item.get("vol_spikes", 0)),
        "socialScore":    round(social_score, 1),
        "alphaScore":     round(alpha_score, 1),
        "discoveryScore": round(discovery, 1),
        "anomalyFlag":    bool(score_item.get("anomaly_flag", False)),
        "anomalyScore":   float(score_item.get("anomaly_score", 0)),
        "date":           score_item.get("SK", "").replace("SCORE#", ""),
    }


def cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Content-Type": "application/json",
    }


def response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": cors_headers(),
        "body": json.dumps(body, default=decimal_to_float),
    }


# ─────────────────────────────────────────────────────────────
# Lambda handler
# ─────────────────────────────────────────────────────────────

def handler(event: dict, context) -> dict:
    """
    Routes:
      GET /scores           → all tickers
      GET /scores/{ticker}  → single ticker
    """
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    # CORS preflight
    if http_method == "OPTIONS":
        return response(200, {})

    scores_table    = dynamodb.Table(SCORES_TABLE)
    summaries_table = dynamodb.Table(SUMMARIES_TABLE)

    path_params = event.get("pathParameters") or {}
    ticker = path_params.get("ticker", "").upper()

    try:
        if ticker:
            # ── Single ticker ──────────────────────────────────
            if ticker not in TICKERS:
                return response(404, {"error": f"Unknown ticker: {ticker}"})

            score_item   = get_latest_score(scores_table, ticker)
            summary_item = get_latest_summary(summaries_table, ticker)

            if not score_item:
                return response(404, {"error": f"No data found for {ticker}"})

            stock = build_stock_item(score_item, summary_item)

            # Extra detail fields for the stock deep-dive page
            stock["components"] = {
                "rsi_score":    float(score_item.get("rsi_score", 0)),
                "macd_score":   float(score_item.get("macd_score", 0)),
                "bb_score":     float(score_item.get("bb_score", 0)),
                "mom_score":    float(score_item.get("mom_score", 0)),
                "vol_score":    float(score_item.get("vol_score", 0)),
                "volrat_score": float(score_item.get("volrat_score", 0)),
            }
            if summary_item:
                stock["sentiment"] = {
                    "bullish_pct":    float(summary_item.get("bullish_pct", 0)),
                    "bearish_pct":    float(summary_item.get("bearish_pct", 0)),
                    "article_count":  int(summary_item.get("article_count", 0)),
                    "news_velocity":  bool(summary_item.get("news_velocity_flag", False)),
                }

            return response(200, {"stock": stock})

        else:
            # ── All tickers ────────────────────────────────────
            stocks = []
            for t in TICKERS:
                score_item   = get_latest_score(scores_table, t)
                summary_item = get_latest_summary(summaries_table, t)
                if score_item:
                    stocks.append(build_stock_item(score_item, summary_item))

            # Sort by discoveryScore descending
            stocks.sort(key=lambda s: s["discoveryScore"], reverse=True)

            return response(200, {
                "stocks": stocks,
                "count":  len(stocks),
            })

    except Exception as e:
        print(f"Error: {e}")
        return response(500, {"error": "Internal server error", "detail": str(e)})
