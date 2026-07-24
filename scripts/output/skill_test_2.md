# Skill Test 2 — Recharts AreaChart on Stock Detail Page

## Task
Replace the chart placeholder div on `/stock/[ticker]/page.tsx` with a real Recharts AreaChart plotting 10-day mock price history.

## Files Changed

### 1. New file: `frontend/app/components/PriceChart.tsx`

Created a dedicated `"use client"` component for the chart. This is required because Recharts uses browser APIs and cannot render in a Next.js server component. Keeping it isolated means the stock detail page itself stays a server component.

```tsx
"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const MOCK_PRICE_DATA = [
  { date: "Jun 13", close: 212.45 },
  { date: "Jun 14", close: 215.30 },
  { date: "Jun 15", close: 213.80 },
  { date: "Jun 16", close: 218.60 },
  { date: "Jun 17", close: 221.15 },
  { date: "Jun 18", close: 219.40 },
  { date: "Jun 19", close: 224.75 },
  { date: "Jun 20", close: 222.90 },
  { date: "Jun 21", close: 226.50 },
  { date: "Jun 22", close: 229.00 },
];

export default function PriceChart() {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={MOCK_PRICE_DATA}>
        <defs>
          <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tick={{ fill: "#64748b", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#64748b", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v}`}
          domain={["auto", "auto"]}
          width={55}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#131929",
            border: "1px solid #1e293b",
            borderRadius: 8,
          }}
          labelStyle={{ color: "#94a3b8" }}
          formatter={(value: number) => [`$${value.toFixed(2)}`, "Close"]}
        />
        <Area
          type="monotone"
          dataKey="close"
          stroke="#10b981"
          fill="url(#colorClose)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#10b981" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

### 2. Modified: `frontend/app/stock/[ticker]/page.tsx`

**Added import at top:**
```tsx
import PriceChart from "../../components/PriceChart";
```

**Replaced placeholder section (was lines 102–116):**

Before:
```tsx
{/* Chart Placeholder */}
<div className="rounded-xl border border-slate-800 bg-[#131929] p-6 mb-6">
  <div className="flex items-center justify-between mb-4">
    <h2 className="text-sm font-semibold text-slate-300">Price Chart</h2>
    <span className="text-xs text-slate-600 bg-slate-800 px-2 py-1 rounded">
      Live chart coming Week 4
    </span>
  </div>
  <div className="h-48 flex items-center justify-center rounded-lg border border-dashed border-slate-700">
    <div className="text-center">
      <p className="text-slate-500 text-sm">📈 Recharts area chart</p>
      <p className="text-slate-700 text-xs mt-1">2-year OHLCV from all_tickers.csv</p>
    </div>
  </div>
</div>
```

After:
```tsx
{/* Price Chart */}
<div className="rounded-xl border border-slate-800 bg-[#131929] p-6 mb-6">
  <div className="flex items-center justify-between mb-4">
    <h2 className="text-sm font-semibold text-slate-300">Price Chart</h2>
    <span className="text-xs text-slate-500">10-day price history (mock)</span>
  </div>
  <PriceChart />
</div>
```

## Design decisions

- **Client component isolation:** Recharts requires browser APIs. Rather than adding `"use client"` to the entire server page, the chart is extracted into `PriceChart.tsx` which is a standalone client component. The server page imports it normally — Next.js handles the boundary automatically.
- **Design tokens:** Follows the AlphaLens skill spec exactly — emerald-500 (`#10b981`) stroke, gradient fill fading to transparent, tooltip on `#131929` with `slate-800` border, axis ticks in `#64748b` (slate-500).
- **YAxis formatting:** Adds `$` prefix to close price ticks and uses `domain={["auto","auto"]}` so the chart auto-scales to the data range rather than starting from 0.
- **No dots on line:** `dot={false}` keeps the chart clean; `activeDot` still shows on hover.
- **Prerequisite:** `recharts` must be installed — `npm install recharts` in the `frontend/` directory if not already present.

## Week 4 migration path

Replace `MOCK_PRICE_DATA` with a fetch to `GET /history/{ticker}` from the AWS API Gateway endpoint. The `PriceChart` component can accept a `data` prop once the API is wired up:

```tsx
// Future signature
export default function PriceChart({ data }: { data: { date: string; close: number }[] }) {
```
