"""
FinBERT Social Score — Week 3
==============================
Replaces keyword sentiment scoring with ProsusAI/finbert — a BERT model
fine-tuned specifically on financial text (10K filings, earnings calls, news).

What it does:
  1. Fetches last 7 days of news headlines per ticker from Finnhub
  2. Runs each headline through FinBERT → positive / negative / neutral
     confidence scores (0-1 each, sum to 1)
  3. Per-ticker aggregate: avg(positive) - avg(negative) → sentiment -1..+1
  4. Maps to Social Score 1-10
  5. Compares results vs keyword scoring (Week 2 baseline)
  6. Saves to scripts/output/finbert_scores.csv

Why FinBERT beats keywords:
  Keywords: "Apple disappoints but raises guidance" → negative (wrong — it's mixed/positive)
  FinBERT: understands context → correctly classifies as positive

Run:
  pip install transformers torch  (first time only — downloads ~440MB model)
  python scripts/finbert_social_score.py

Output:
  scripts/output/finbert_scores.csv   (per-ticker Social Scores)
  scripts/output/finbert_headlines.csv  (per-headline breakdown)
"""

import os, time, requests, json
from datetime import date, timedelta
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

FINNHUB_KEY  = os.environ.get("FINNHUB_API_KEY", "")
FINNHUB_BASE = "https://finnhub.io/api/v1"
NEWS_DAYS    = 7
MAX_HEADLINES_PER_TICKER = 30   # cap to keep inference fast

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
           "AMZN", "META", "NFLX", "AMD",  "INTC"]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
CACHE_FILE = os.path.join(OUTPUT_DIR, "news_cache.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Keyword baseline (Week 2) — for comparison
# ─────────────────────────────────────────────────────────────

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

def keyword_score(headlines: list[str]) -> float:
    if not headlines:
        return 0.0
    pos = neg = 0
    for h in headlines:
        words = set(h.lower().split())
        if words & POSITIVE_WORDS and not words & NEGATIVE_WORDS:
            pos += 1
        elif words & NEGATIVE_WORDS and not words & POSITIVE_WORDS:
            neg += 1
    return round((pos - neg) / len(headlines), 4)

# ─────────────────────────────────────────────────────────────
# Finnhub news fetching + caching
# ─────────────────────────────────────────────────────────────

def fetch_all_news(use_cache=True) -> dict:
    """Fetch news for all tickers. Caches to JSON so we don't hit API limits."""
    today = str(date.today())

    # Load cache if it's from today
    if use_cache and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        if cache.get("date") == today:
            print(f"  📦 Using cached news from {today}\n")
            return cache["data"]

    print(f"  📡 Fetching fresh news from Finnhub...\n")
    if not FINNHUB_KEY:
        print("❌ FINNHUB_API_KEY not set in .env")
        return {}

    end   = date.today()
    start = end - timedelta(days=NEWS_DAYS)
    data  = {}

    for ticker in TICKERS:
        print(f"    {ticker}...", end=" ", flush=True)
        r = requests.get(f"{FINNHUB_BASE}/company-news", params={
            "symbol": ticker, "from": str(start), "to": str(end), "token": FINNHUB_KEY
        }, timeout=15)
        articles = r.json() if r.status_code == 200 else []
        data[ticker] = [
            {"headline": a.get("headline", ""), "source": a.get("source", ""), "datetime": a.get("datetime", 0)}
            for a in articles if a.get("headline")
        ]
        print(f"{len(articles)} articles")
        time.sleep(0.5)

    # Save cache
    with open(CACHE_FILE, "w") as f:
        json.dump({"date": today, "data": data}, f)

    return data

# ─────────────────────────────────────────────────────────────
# FinBERT inference
# ─────────────────────────────────────────────────────────────

def load_finbert():
    """Load FinBERT pipeline. Downloads model on first run (~440MB)."""
    try:
        from transformers import pipeline
        print("\n🧠 Loading ProsusAI/finbert model...")
        print("   (First run downloads ~440MB — grab a coffee ☕)\n")
        pipe = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            top_k=None,          # return all 3 labels (positive/negative/neutral)
            device=-1,           # CPU — set to 0 for GPU
            truncation=True,
            max_length=512,
        )
        print("   ✅ FinBERT loaded\n")
        return pipe
    except ImportError:
        print("❌ transformers not installed. Run: pip install transformers torch")
        return None


def finbert_score_ticker(pipe, headlines: list[str]) -> dict:
    """
    Run FinBERT on a list of headlines.
    Returns:
      pos_avg   float  avg positive confidence
      neg_avg   float  avg negative confidence
      neu_avg   float  avg neutral confidence
      sentiment float  pos_avg - neg_avg  (-1 to +1)
      details   list   per-headline breakdown
    """
    if not headlines:
        return {"pos_avg": 0, "neg_avg": 0, "neu_avg": 0, "sentiment": 0, "details": []}

    capped = headlines[:MAX_HEADLINES_PER_TICKER]
    results = pipe(capped)   # list of lists: [[{label, score}, ...], ...]

    details = []
    pos_scores, neg_scores, neu_scores = [], [], []

    for headline, label_scores in zip(capped, results):
        scores = {item["label"]: item["score"] for item in label_scores}
        pos = scores.get("positive", 0)
        neg = scores.get("negative", 0)
        neu = scores.get("neutral",  0)
        top = max(scores, key=scores.get)

        pos_scores.append(pos)
        neg_scores.append(neg)
        neu_scores.append(neu)

        details.append({
            "headline": headline[:100],
            "label":    top,
            "positive": round(pos, 4),
            "negative": round(neg, 4),
            "neutral":  round(neu, 4),
        })

    pos_avg = sum(pos_scores) / len(pos_scores)
    neg_avg = sum(neg_scores) / len(neg_scores)
    neu_avg = sum(neu_scores) / len(neu_scores)

    return {
        "pos_avg":   round(pos_avg, 4),
        "neg_avg":   round(neg_avg, 4),
        "neu_avg":   round(neu_avg, 4),
        "sentiment": round(pos_avg - neg_avg, 4),
        "details":   details,
    }


def to_social_score(sentiment: float) -> float:
    """Map -1..+1 → 1-10 Social Score."""
    return round((sentiment + 1) / 2 * 9 + 1, 1)

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    print(f"\nFinBERT Social Score — {date.today()}")
    print("=" * 60)

    # 1. Fetch news
    news_data = fetch_all_news(use_cache=True)
    if not news_data:
        return

    # 2. Load FinBERT
    pipe = load_finbert()
    if pipe is None:
        return

    # 3. Score each ticker
    ticker_rows = []
    all_headlines = []

    print("Running FinBERT inference...\n")
    for ticker in TICKERS:
        articles  = news_data.get(ticker, [])
        headlines = [a["headline"] for a in articles if a["headline"]]

        print(f"  {ticker} ({len(headlines)} headlines)...", end=" ", flush=True)
        fb     = finbert_score_ticker(pipe, headlines)
        kw_raw = keyword_score(headlines)

        fb_score = to_social_score(fb["sentiment"])
        kw_score = to_social_score(kw_raw)
        delta    = round(fb_score - kw_score, 1)
        arrow    = f"↑{delta}" if delta > 0 else f"↓{abs(delta)}" if delta < 0 else "="

        print(f"FinBERT={fb_score}/10  Keyword={kw_score}/10  Δ={arrow}")

        ticker_rows.append({
            "ticker":          ticker,
            "articles":        len(headlines),
            "finbert_score":   fb_score,
            "keyword_score":   kw_score,
            "delta":           delta,
            "sentiment":       fb["sentiment"],
            "pos_avg":         fb["pos_avg"],
            "neg_avg":         fb["neg_avg"],
            "neu_avg":         fb["neu_avg"],
            "kw_raw":          kw_raw,
        })

        # Per-headline details
        for d in fb["details"]:
            all_headlines.append({"ticker": ticker, **d})

    # 4. Summary table
    print(f"\n{'='*75}")
    print(f"  FINBERT SOCIAL SCORE SUMMARY")
    print(f"{'='*75}")
    print(f"\n{'Ticker':<8} {'FinBERT':>9} {'Keyword':>9} {'Delta':>7} {'Pos%':>7} {'Neg%':>7} {'Neu%':>7}  {'Articles':>9}")
    print("-" * 75)

    for r in sorted(ticker_rows, key=lambda x: -x["finbert_score"]):
        delta_str = f"+{r['delta']}" if r["delta"] > 0 else str(r["delta"])
        print(f"{r['ticker']:<8} {r['finbert_score']:>9.1f} {r['keyword_score']:>9.1f} "
              f"{delta_str:>7} {r['pos_avg']*100:>6.1f}% {r['neg_avg']*100:>6.1f}% "
              f"{r['neu_avg']*100:>6.1f}% {r['articles']:>9}")

    # 5. Save CSVs
    scores_path    = os.path.join(OUTPUT_DIR, "finbert_scores.csv")
    headlines_path = os.path.join(OUTPUT_DIR, "finbert_headlines.csv")

    pd.DataFrame(ticker_rows).to_csv(scores_path, index=False)
    pd.DataFrame(all_headlines).to_csv(headlines_path, index=False)

    print(f"\n✅ Saved:")
    print(f"   {scores_path}")
    print(f"   {headlines_path}  ({len(all_headlines)} headlines scored)")
    print(f"\n🔄 Next: update social_score_handler.py to use FinBERT in Lambda")


if __name__ == "__main__":
    main()
