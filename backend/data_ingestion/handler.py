import os, json, boto3, requests
from datetime import date, timedelta

MASSIVE_API_KEY = os.environ['MASSIVE_API_KEY']
MASSIVE_BASE_URL = os.environ.get('MASSIVE_BASE_URL', 'https://api.massive.com')
S3_BUCKET = os.environ['S3_BUCKET_RAW']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE_SCORES']

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "GOOGL",
    "AMZN", "META", "NFLX", "AMD", "INTC"
]

def fetch_ticker(ticker: str, trade_date: str):
    url = f"{MASSIVE_BASE_URL}/v1/open-close/{ticker}/{trade_date}"
    r = requests.get(url, params={"apiKey": MASSIVE_API_KEY}, timeout=10)
    if r.status_code == 200:
        return r.json()
    print(f"[WARN] {ticker} returned {r.status_code}: {r.text[:100]}")
    return None

def save_to_s3(data: list, trade_date: str):
    key = f"raw/daily/{trade_date}/snapshot.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data),
        ContentType="application/json"
    )
    print(f"[S3] Saved {len(data)} records to s3://{S3_BUCKET}/{key}")

def save_to_dynamodb(record: dict, trade_date: str):
    table = dynamodb.Table(DYNAMODB_TABLE)
    ticker = record.get("symbol")
    table.put_item(Item={
        "PK": f"TICKER#{ticker}",
        "SK": f"SCORE#{trade_date}",
        "symbol": ticker,
        "date": trade_date,
        "open": str(record.get("open", 0)),
        "high": str(record.get("high", 0)),
        "low": str(record.get("low", 0)),
        "close": str(record.get("close", 0)),
        "volume": str(record.get("volume", 0)),
        "pre_market": str(record.get("preMarket", 0)),
        "after_hours": str(record.get("afterHours", 0)),
        "alpha_score": None,
        "anomaly_flag": False,
        "classification": None
    })

def handler(event, context):
    # Use yesterday by default (last completed trading day)
    trade_date = event.get("date", str(date.today() - timedelta(days=1)))
    tickers = event.get("tickers", TICKERS)

    print(f"[START] Fetching {len(tickers)} tickers for {trade_date}")

    results = []
    for ticker in tickers:
        data = fetch_ticker(ticker, trade_date)
        if data:
            results.append(data)
            save_to_dynamodb(data, trade_date)
            print(f"[OK] {ticker}: close={data.get('close')}, volume={data.get('volume')}")

    if results:
        save_to_s3(results, trade_date)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "date": trade_date,
            "fetched": len(results),
            "failed": len(tickers) - len(results)
        })
    }
