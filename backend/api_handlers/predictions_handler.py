"""
Predictions API Handler — Week 4
==================================
Handles:
  GET /predictions/{ticker}  → XGBoost UP/DOWN/NEUTRAL signal + probabilities

Data source: DynamoDB table AlphaLens-Predictions
  PK: TICKER#<symbol>
  SK: PRED#<date>

The nightly pipeline writes here after running xgboost_classifier.py.
We return the latest prediction plus probability breakdown.

Also returns the Isolation Forest anomaly flag so the frontend can show
the 🚨 badge without a separate request.

Environment variables:
  PREDICTIONS_TABLE — DynamoDB table name (set by CDK)
  SCORES_TABLE      — also reads anomaly flag from here
"""

import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
PREDICTIONS_TABLE = os.environ.get("PREDICTIONS_TABLE", "StockPredictions")
SCORES_TABLE      = os.environ.get("SCORES_TABLE", "StockScores")

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
           "AMZN", "META", "NFLX", "AMD",  "INTC"]

SIGNAL_LABELS = {
    "UP":      {"icon": "▲", "color": "emerald"},
    "DOWN":    {"icon": "▼", "color": "red"},
    "NEUTRAL": {"icon": "—", "color": "slate"},
}


def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


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


def get_latest_prediction(ticker: str) -> dict | None:
    table = dynamodb.Table(PREDICTIONS_TABLE)
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"TICKER#{ticker}") & Key("SK").begins_with("PRED#"),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def get_anomaly_flag(ticker: str) -> tuple[bool, float]:
    """Pull anomaly_flag + anomaly_score from the scores table."""
    table = dynamodb.Table(SCORES_TABLE)
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"TICKER#{ticker}") & Key("SK").begins_with("SCORE#"),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return False, 0.0
    item = items[0]
    return bool(item.get("anomaly_flag", False)), float(item.get("anomaly_score", 0))


# ─────────────────────────────────────────────────────────────
# Lambda handler
# ─────────────────────────────────────────────────────────────

def handler(event: dict, context) -> dict:
    """
    Route: GET /predictions/{ticker}

    Returns:
      prediction   : "UP" | "DOWN" | "NEUTRAL"
      confidence   : 0.0–1.0 (max class probability)
      prob_up      : 0.0–1.0
      prob_down    : 0.0–1.0
      prob_neutral : 0.0–1.0
      horizon_days : 5  (5-day forward prediction)
      anomaly_flag : bool  (from Isolation Forest)
      anomaly_score: float (more negative = more anomalous)
      date         : date the model ran
    """
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    if http_method == "OPTIONS":
        return response(200, {})

    path_params = event.get("pathParameters") or {}
    ticker = path_params.get("ticker", "").upper()

    if not ticker or ticker not in TICKERS:
        return response(400, {"error": f"Invalid or missing ticker: '{ticker}'"})

    try:
        pred = get_latest_prediction(ticker)

        if not pred:
            return response(404, {
                "error": f"No prediction found for {ticker}",
                "hint": "Run xgboost_classifier.py via the nightly Lambda to populate.",
            })

        anomaly_flag, anomaly_score = get_anomaly_flag(ticker)

        prediction  = str(pred.get("prediction", "NEUTRAL"))
        confidence  = float(pred.get("confidence", 0.34))
        prob_up     = float(pred.get("prob_up",     0.33))
        prob_down   = float(pred.get("prob_down",   0.33))
        prob_neutral= float(pred.get("prob_neutral",0.34))

        meta = SIGNAL_LABELS.get(prediction, SIGNAL_LABELS["NEUTRAL"])

        return response(200, {
            "ticker":       ticker,
            "prediction":   prediction,
            "confidence":   round(confidence, 4),
            "prob_up":      round(prob_up, 4),
            "prob_down":    round(prob_down, 4),
            "prob_neutral": round(prob_neutral, 4),
            "horizon_days": int(pred.get("horizon_days", 5)),
            "date":         str(pred.get("SK", "")).replace("PRED#", ""),
            "anomaly_flag": anomaly_flag,
            "anomaly_score":round(anomaly_score, 4),
            "display": {
                "icon":    meta["icon"],
                "color":   meta["color"],
                "label":   f"{prediction} ({confidence*100:.0f}% confidence)",
            },
        })

    except Exception as e:
        print(f"Error fetching prediction for {ticker}: {e}")
        return response(500, {"error": "Internal server error", "detail": str(e)})
