"""
Explore Polygon.io data with timestamps.
Massive API key works directly on api.polygon.io (same infrastructure).
Endpoints explored:
  1. Aggregates (OHLCV bars with Unix timestamps) — great for trend analysis
  2. Daily open/close (single day with timestamp)
  3. Previous close (most recent trading day)
"""

import os, json, requests
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("MASSIVE_API_KEY", "0pWckqzeoG1dxGtfu_pZrpPL_JKoQbvk")
BASE = "https://api.polygon.io"

TICKER = "AAPL"

def ts_to_human(ms: int) -> str:
    """Convert Unix milliseconds timestamp to readable date string."""
    return datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S UTC")

def divider(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ─────────────────────────────────────────────────────────────
# 1. AGGREGATE BARS — daily candles with timestamps
#    /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
#    Perfect for: trend analysis, RSI/MACD computation, charting
# ─────────────────────────────────────────────────────────────
divider("1. AGGREGATE BARS (daily) — Last 10 trading days")

end_date   = date.today() - timedelta(days=1)
start_date = end_date - timedelta(days=14)   # 14 calendar days ≈ 10 trading days

url = f"{BASE}/v2/aggs/ticker/{TICKER}/range/1/day/{start_date}/{end_date}"
r = requests.get(url, params={"apiKey": API_KEY, "adjusted": "true", "sort": "asc", "limit": 50})
data = r.json()

print(f"\nStatus : {data.get('status')}")
print(f"Ticker : {data.get('ticker')}")
print(f"Count  : {data.get('resultsCount')} bars returned")
print(f"\nRaw fields in each bar: {list(data['results'][0].keys()) if data.get('results') else 'none'}")

print("\n{'t'=timestamp_ms, 'o'=open, 'h'=high, 'l'=low, 'c'=close, 'v'=volume, 'vw'=vwap, 'n'=trades}")
print(f"\n{'Date (UTC)':<25} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Volume':>12} {'VWAP':>10}")
print("-"*85)

if data.get("results"):
    for bar in data["results"]:
        date_str = ts_to_human(bar["t"])
        print(f"{date_str:<25} {bar['o']:>8.2f} {bar['h']:>8.2f} {bar['l']:>8.2f} {bar['c']:>8.2f} {bar['v']:>12,.0f} {bar.get('vw', 0):>10.2f}")

print(f"\n✅ Key insight: 't' field = Unix milliseconds timestamp")
print(f"   Example: {data['results'][0]['t']} → {ts_to_human(data['results'][0]['t'])}")

# ─────────────────────────────────────────────────────────────
# 2. INTRADAY BARS — 1-hour candles (today's session)
#    Perfect for: intraday trend, hourly momentum
# ─────────────────────────────────────────────────────────────
divider("2. INTRADAY BARS — 1-hour candles (last 2 days)")

url2 = f"{BASE}/v2/aggs/ticker/{TICKER}/range/1/hour/{end_date - timedelta(days=1)}/{end_date}"
r2 = requests.get(url2, params={"apiKey": API_KEY, "adjusted": "true", "sort": "asc", "limit": 20})
data2 = r2.json()

print(f"\nStatus : {data2.get('status')}")
print(f"Count  : {data2.get('resultsCount')} hourly bars")
print(f"\n{'DateTime (UTC)':<25} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Volume':>12}")
print("-"*75)

if data2.get("results"):
    for bar in data2["results"][:10]:  # show first 10
        print(f"{ts_to_human(bar['t']):<25} {bar['o']:>8.2f} {bar['h']:>8.2f} {bar['l']:>8.2f} {bar['c']:>8.2f} {bar['v']:>12,.0f}")
    if len(data2["results"]) > 10:
        print(f"  ... {len(data2['results']) - 10} more bars")

# ─────────────────────────────────────────────────────────────
# 3. PREVIOUS CLOSE — quick last trading day snapshot
# ─────────────────────────────────────────────────────────────
divider("3. PREVIOUS CLOSE — last trading day")

url3 = f"{BASE}/v2/aggs/ticker/{TICKER}/prev"
r3 = requests.get(url3, params={"apiKey": API_KEY})
data3 = r3.json()

if data3.get("results"):
    bar = data3["results"][0]
    print(f"\nTicker    : {bar.get('T')}")
    print(f"Timestamp : {bar.get('t')} → {ts_to_human(bar['t'])}")
    print(f"Open      : ${bar.get('o'):.2f}")
    print(f"High      : ${bar.get('h'):.2f}")
    print(f"Low       : ${bar.get('l'):.2f}")
    print(f"Close     : ${bar.get('c'):.2f}")
    print(f"Volume    : {bar.get('v'):,.0f}")
    print(f"VWAP      : ${bar.get('vw', 0):.2f}")

# ─────────────────────────────────────────────────────────────
# 4. MULTIPLE TICKERS — show timestamps across tickers
# ─────────────────────────────────────────────────────────────
divider("4. MULTI-TICKER daily bars (AAPL, MSFT, NVDA) — last 3 days")

for ticker in ["AAPL", "MSFT", "NVDA"]:
    url4 = f"{BASE}/v2/aggs/ticker/{ticker}/range/1/day/{end_date - timedelta(days=3)}/{end_date}"
    r4 = requests.get(url4, params={"apiKey": API_KEY, "adjusted": "true", "sort": "asc", "limit": 5})
    d4 = r4.json()
    print(f"\n{ticker}:")
    if d4.get("results"):
        for bar in d4["results"]:
            print(f"  {ts_to_human(bar['t'])}  close=${bar['c']:.2f}  vol={bar['v']:,.0f}")
    else:
        print(f"  No data: {d4.get('status')} — {d4.get('error','')}")

# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
divider("SUMMARY — What Polygon gives us")
print("""
Polygon Aggregate endpoint gives us:
  ✅ Unix millisecond timestamps ('t') — convert to any timezone
  ✅ OHLCV per bar (daily, hourly, 1-min)
  ✅ VWAP (volume-weighted average price)
  ✅ Trade count per bar ('n')
  ✅ Adjusted prices (splits/dividends corrected)
  ✅ Up to years of historical data

Perfect for:
  → RSI, MACD, Bollinger Bands computation
  → Trend detection (50/200 day MA crossovers)
  → Anomaly detection on volume spikes
  → Feeding into ML feature pipeline

Missing (need Finnhub or similar):
  ❌ No news articles
  ❌ No sentiment score
  ❌ No social/Reddit data
""")
