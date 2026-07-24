"""
Local test runner for social_score_handler.py
=============================================
Simulates a Lambda invocation locally — prints results to terminal
instead of writing to DynamoDB.

Run:
  python scripts/test_social_score.py

Requires FINNHUB_API_KEY in your .env file.
"""

import os, sys, time, requests
from datetime import date, timedelta
from dotenv import load_dotenv

# ── Load env ──────────────────────────────────────────────────
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

FINNHUB_KEY  = os.environ.get("FINNHUB_API_KEY", "")
FINNHUB_BASE = "https://finnhub.io/api/v1"
NEWS_DAYS    = 7

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
           "AMZN", "META", "NFLX", "AMD",  "INTC"]

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

def fetch_news(ticker):
    end   = date.today()
    start = end - timedelta(days=NEWS_DAYS)
    r = requests.get(f"{FINNHUB_BASE}/company-news", params={
        "symbol": ticker, "from": str(start), "to": str(end), "token": FINNHUB_KEY
    }, timeout=15)
    return r.json() if r.status_code == 200 else []

def score_articles(articles):
    if not articles:
        return {"score": 0.0, "bullish_pct": 0.0, "bearish_pct": 0.0, "article_count": 0}
    pos = neg = 0
    for a in articles:
        words   = set(a.get("headline", "").lower().split())
        has_pos = bool(words & POSITIVE_WORDS)
        has_neg = bool(words & NEGATIVE_WORDS)
        if has_pos and not has_neg:   pos += 1
        elif has_neg and not has_pos: neg += 1
    total = len(articles)
    return {
        "score":        round((pos - neg) / total, 4),
        "bullish_pct":  round(pos / total, 4),
        "bearish_pct":  round(neg / total, 4),
        "article_count": total,
    }

def to_social_score(raw):
    return round((raw + 1) / 2 * 9 + 1, 1)

def score_label(s):
    if s >= 7.5: return "Very Positive 🟢"
    if s >= 6.0: return "Positive 🟡"
    if s >= 4.5: return "Neutral ⚪"
    if s >= 3.0: return "Negative 🟠"
    return "Very Negative 🔴"

def main():
    if not FINNHUB_KEY:
        print("❌ FINNHUB_API_KEY not set in .env")
        return

    print(f"Social Score Test Runner — {date.today()}")
    print(f"Fetching {NEWS_DAYS} days of news for {len(TICKERS)} tickers...\n")

    rows = []
    for ticker in TICKERS:
        print(f"  {ticker}...", end=" ", flush=True)
        articles  = fetch_news(ticker)
        sentiment = score_articles(articles)
        score     = to_social_score(sentiment["score"])
        label     = score_label(score)
        rows.append({**sentiment, "ticker": ticker, "social_score": score, "label": label})
        print(f"{sentiment['article_count']} articles | score={sentiment['score']:+.3f} | Social={score}/10 {label}")
        time.sleep(0.5)

    # ── Summary table ────────────────────────────────────────
    print(f"\n{'='*85}")
    print(f"  SOCIAL SCORE SUMMARY  (1=Very Negative → 10=Very Positive)")
    print(f"{'='*85}")
    print(f"\n{'Ticker':<8} {'Social':>7} {'Sentiment':>10} {'Bullish%':>9} {'Bearish%':>9} {'Articles':>9}  Label")
    print("-"*85)
    for r in sorted(rows, key=lambda x: -x["social_score"]):
        print(f"{r['ticker']:<8} {r['social_score']:>7.1f} {r['score']:>+10.4f} "
              f"{r['bullish_pct']*100:>8.1f}% {r['bearish_pct']*100:>8.1f}% "
              f"{r['article_count']:>9}  {r['label']}")

    # ── Sample headlines for top + bottom ticker ─────────────
    top    = sorted(rows, key=lambda x: -x["social_score"])[0]["ticker"]
    bottom = sorted(rows, key=lambda x:  x["social_score"])[0]["ticker"]

    for ticker in [top, bottom]:
        articles = fetch_news(ticker)
        label_tag = "📈 TOP" if ticker == top else "📉 BOTTOM"
        print(f"\n{label_tag}: {ticker} — Recent Headlines")
        print("-"*70)
        for a in articles[:5]:
            headline = a.get("headline", "")[:75]
            source   = a.get("source", "?")
            words    = set(headline.lower().split())
            tag      = "🟢" if words & POSITIVE_WORDS and not words & NEGATIVE_WORDS \
                      else "🔴" if words & NEGATIVE_WORDS and not words & POSITIVE_WORDS \
                      else "⚪"
            print(f"  {tag} [{source}] {headline}")

    print(f"\n✅ Done. In production, these scores write to DynamoDB StockSummaries.")
    print(f"   Lambda: backend/data_ingestion/social_score_handler.py")

if __name__ == "__main__":
    main()
