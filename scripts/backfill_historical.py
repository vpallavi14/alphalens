"""
Historical Data Backfill — Week 2, Step 1
==========================================
Pulls 2 years of daily OHLCV data for all 10 tickers using yfinance (free, no API key).
Saves to:
  - scripts/output/historical/  (CSV per ticker, for local use + Excel inspection)
  - S3: s3://alphalens-raw-data/historical/{ticker}.csv  (for Lambda + ML pipeline)

Run:
  pip install yfinance pandas boto3 python-dotenv
  python scripts/backfill_historical.py
"""

import os, boto3
from datetime import date, timedelta
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd

load_dotenv()

TICKERS    = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META", "NFLX", "AMD", "INTC"]
END_DATE   = date.today()
START_DATE = END_DATE - timedelta(days=730)   # 2 years

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "historical")
S3_BUCKET  = os.environ.get("S3_BUCKET_RAW", "alphalens-raw-data")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── S3 client (optional — skips upload if no AWS creds) ──────
try:
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.head_bucket(Bucket=S3_BUCKET)
    USE_S3 = True
    print(f"✅ S3 connected → will upload to s3://{S3_BUCKET}/historical/\n")
except Exception as e:
    USE_S3 = False
    print(f"⚠️  S3 not available ({e.__class__.__name__}) — saving locally only\n")

# ── Pull and save ─────────────────────────────────────────────
all_frames = []
summary_rows = []

for ticker in TICKERS:
    print(f"  Pulling {ticker}...", end=" ")

    df = yf.download(ticker, start=str(START_DATE), end=str(END_DATE),
                     auto_adjust=True, progress=False)

    if df.empty:
        print("no data")
        continue

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Clean up
    df = df.reset_index()
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    df["ticker"]      = ticker
    df["date"]        = df["date"].astype(str)
    df["daily_return"] = df["close"].pct_change().round(6)

    # Reorder columns
    df = df[["ticker", "date", "open", "high", "low", "close", "volume", "daily_return"]]

    print(f"{len(df)} days  |  {df['date'].min()} → {df['date'].max()}")

    # Save CSV locally
    csv_path = os.path.join(OUTPUT_DIR, f"{ticker}.csv")
    df.to_csv(csv_path, index=False)

    # Upload to S3
    if USE_S3:
        s3_key = f"historical/{ticker}.csv"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=df.to_csv(index=False).encode(),
            ContentType="text/csv"
        )

    # For combined file
    all_frames.append(df)

    summary_rows.append({
        "ticker":    ticker,
        "days":      len(df),
        "start":     df["date"].min(),
        "end":       df["date"].max(),
        "avg_close": round(df["close"].mean(), 2),
        "avg_volume": int(df["volume"].mean()),
        "total_return": f"{((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.1f}%"
    })

# ── Combined CSV (all tickers in one file) ────────────────────
if all_frames:
    combined = pd.concat(all_frames, ignore_index=True)
    combined_path = os.path.join(OUTPUT_DIR, "all_tickers.csv")
    combined.to_csv(combined_path, index=False)

    if USE_S3:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key="historical/all_tickers.csv",
            Body=combined.to_csv(index=False).encode(),
            ContentType="text/csv"
        )

# ── Summary ───────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  BACKFILL SUMMARY")
print(f"{'='*60}")
print(f"\n{'Ticker':<8} {'Days':>5} {'Start':<12} {'End':<12} {'Avg Close':>10} {'2yr Return':>10}")
print("-"*60)
for r in summary_rows:
    print(f"{r['ticker']:<8} {r['days']:>5} {r['start']:<12} {r['end']:<12} ${r['avg_close']:>9} {r['total_return']:>10}")

print(f"\n✅ Saved {len(summary_rows)} tickers to {OUTPUT_DIR}/")
print(f"   Combined file: all_tickers.csv ({sum(r['days'] for r in summary_rows):,} total rows)")
if USE_S3:
    print(f"   S3: s3://{S3_BUCKET}/historical/")
