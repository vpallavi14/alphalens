import requests
import pandas as pd
import json
from datetime import date, timedelta

API_KEY = "0pWckqzeoG1dxGtfu_pZrpPL_JKoQbvk"
BASE_URL = "https://api.massive.com"

tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"]
target_date = "2024-01-15"

print(f"Fetching data for {len(tickers)} tickers on {target_date}...\n")

rows = []
for ticker in tickers:
    url = f"{BASE_URL}/v1/open-close/{ticker}/{target_date}"
    r = requests.get(url, params={"apiKey": API_KEY})
    print(f"{ticker}: HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data, indent=2))
        rows.append(data)
    else:
        print(f"  Error: {r.text}")

if rows:
    df = pd.DataFrame(rows)
    output = f"scripts/massive_sample_{target_date}.csv"
    df.to_csv(output, index=False)
    print(f"\nSaved to {output} — open in Excel to explore!")
else:
    print("\nNo data returned. Check your API key or date.")
