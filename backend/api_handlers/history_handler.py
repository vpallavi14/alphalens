"""
History API Handler — Week 4
==============================
Handles:
  GET /history/{ticker}              → last 90 trading days of OHLCV
  GET /history/{ticker}?days=365     → up to 2 years

Data source: S3 bucket with per-ticker CSV files written by the nightly pipeline.
  s3://<BUCKET>/processed/<ticker>/history.csv

CSV columns (from backfill_historical.py):
  date, open, high, low, close, volume, daily_return

We read the CSV from S3 and return a JSON array of OHLCV points.
The frontend uses this to render the Recharts AreaChart on the stock detail page.

Environment variables:
  DATA_BUCKET — S3 bucket name (set by CDK)
"""

import json
import os
import io
import boto3
import csv
from decimal import Decimal

s3 = boto3.client("s3")
DATA_BUCKET = os.environ.get("DATA_BUCKET", "alphalens-data")

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
           "AMZN", "META", "NFLX", "AMD",  "INTC"]

DEFAULT_DAYS = 90
MAX_DAYS     = 504   # ~2 trading years


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
        "body": json.dumps(body),
    }


def load_history_from_s3(ticker: str) -> list[dict]:
    """
    Download the ticker's history CSV from S3 and parse it.
    Returns a list of OHLCV dicts, newest last.
    """
    key = f"processed/{ticker}/history.csv"
    try:
        obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
        content = obj["Body"].read().decode("utf-8")
    except s3.exceptions.NoSuchKey:
        return []
    except Exception as e:
        print(f"S3 error for {ticker}: {e}")
        return []

    rows = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        try:
            rows.append({
                "date":         row["date"],
                "open":         round(float(row["open"]), 2),
                "high":         round(float(row["high"]), 2),
                "low":          round(float(row["low"]), 2),
                "close":        round(float(row["close"]), 2),
                "volume":       int(float(row["volume"])),
                "dailyReturn":  round(float(row.get("daily_return", 0)) * 100, 3),
            })
        except (ValueError, KeyError):
            continue  # skip malformed rows

    # Sort oldest → newest (Recharts expects chronological order)
    rows.sort(key=lambda r: r["date"])
    return rows


# ─────────────────────────────────────────────────────────────
# Lambda handler
# ─────────────────────────────────────────────────────────────

def handler(event: dict, context) -> dict:
    """
    Route:  GET /history/{ticker}?days=90
    """
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    if http_method == "OPTIONS":
        return response(200, {})

    path_params = event.get("pathParameters") or {}
    ticker = path_params.get("ticker", "").upper()

    if not ticker or ticker not in TICKERS:
        return response(400, {"error": f"Invalid or missing ticker: '{ticker}'"})

    # Parse ?days= query param
    query = event.get("queryStringParameters") or {}
    try:
        days = min(int(query.get("days", DEFAULT_DAYS)), MAX_DAYS)
    except ValueError:
        days = DEFAULT_DAYS

    try:
        all_rows = load_history_from_s3(ticker)

        if not all_rows:
            return response(404, {
                "error": f"No history found for {ticker}",
                "hint": "Run the nightly pipeline to populate S3.",
            })

        # Slice to requested number of days (tail = most recent)
        rows = all_rows[-days:] if len(all_rows) > days else all_rows

        return response(200, {
            "ticker":     ticker,
            "days":       len(rows),
            "start_date": rows[0]["date"] if rows else None,
            "end_date":   rows[-1]["date"] if rows else None,
            "history":    rows,
        })

    except Exception as e:
        print(f"Error fetching history for {ticker}: {e}")
        return response(500, {"error": "Internal server error", "detail": str(e)})
