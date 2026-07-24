# Anomaly Badge — Code Change

## Summary

Two files need to change:

1. **`app/lib/mock-data.ts`** — add `anomaly_flag` to the `Stock` interface and seed values on each stock object.
2. **`app/page.tsx`** — render the anomaly badge in the Badges section of the stock card.

---

## File 1: `app/lib/mock-data.ts`

### BEFORE

```ts
export interface Stock {
  ticker: string;
  name: string;
  sector: string;
  close: number;
  changePercent: number;   // 20-day momentum (%)
  rsi: number;
  rsiSignal: RSISignal;
  macd: MACDSignal;
  bbPct: number;           // 0-1, Bollinger Band position
  volatility: number;      // annualised (%)
  volSpikes: number;       // count of volume spikes in 2yr window
  socialScore: number;     // 1–10
  alphaScore: number;      // 0–100  from alpha_score_engine.py (Week 3)
  discoveryScore: number;  // 0–100  = 60% alphaScore + 40% (socialScore×10)
  inWatchlist: boolean;
}
```

### AFTER

```ts
export interface Stock {
  ticker: string;
  name: string;
  sector: string;
  close: number;
  changePercent: number;   // 20-day momentum (%)
  rsi: number;
  rsiSignal: RSISignal;
  macd: MACDSignal;
  bbPct: number;           // 0-1, Bollinger Band position
  volatility: number;      // annualised (%)
  volSpikes: number;       // count of volume spikes in 2yr window
  socialScore: number;     // 1–10
  alphaScore: number;      // 0–100  from alpha_score_engine.py (Week 3)
  discoveryScore: number;  // 0–100  = 60% alphaScore + 40% (socialScore×10)
  inWatchlist: boolean;
  anomaly_flag: boolean;   // true = Isolation Forest flagged this ticker
}
```

Also add `anomaly_flag` to each stock object in the `STOCKS` array. Example (set whichever tickers the model flags to `true`):

```ts
{ ticker: "AAPL", ..., inWatchlist: true,  anomaly_flag: false },
{ ticker: "AMD",  ..., inWatchlist: true,  anomaly_flag: true  },
// etc.
```

---

## File 2: `app/page.tsx`

### BEFORE (lines 72–82)

```tsx
            {/* Badges */}
            <div className="flex flex-wrap gap-2 mb-3">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${rsiColor(s.rsiSignal)}`}>
                RSI {s.rsi} · {s.rsiSignal}
              </span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                s.macd === "Bullish" ? "text-emerald-400 bg-emerald-400/10" : "text-red-400 bg-red-400/10"
              }`}>
                MACD {s.macd === "Bullish" ? "▲" : "▼"}
              </span>
            </div>
```

### AFTER

```tsx
            {/* Badges */}
            <div className="flex flex-wrap gap-2 mb-3">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${rsiColor(s.rsiSignal)}`}>
                RSI {s.rsi} · {s.rsiSignal}
              </span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                s.macd === "Bullish" ? "text-emerald-400 bg-emerald-400/10" : "text-red-400 bg-red-400/10"
              }`}>
                MACD {s.macd === "Bullish" ? "▲" : "▼"}
              </span>
              {s.anomaly_flag && (
                <span className="text-xs font-medium px-2 py-0.5 rounded-full text-red-400 bg-red-400/10">
                  🚨 Anomaly
                </span>
              )}
            </div>
```

---

## Notes

- The badge uses the design token `red-400 / red-400/10` as specified in the skill for anomaly colours.
- The badge only renders when `anomaly_flag === true`, so cards with `false` are unaffected.
- When the API replaces `mock-data.ts` (Week 4), the `anomaly_flag` field should come from the Isolation Forest model output on the `/scores` endpoint — no frontend change needed beyond that substitution.
