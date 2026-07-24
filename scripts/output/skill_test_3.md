# skill_test_3 — PredictionBadge Component

## What was built

A reusable React component `PredictionBadge` saved to:

```
alphalens/frontend/app/components/PredictionBadge.tsx
```

## Purpose

Displays the XGBoost classifier output for a stock ticker — one of **UP**, **DOWN**, or **NEUTRAL** — alongside the model's confidence score as a percentage.

## Props

| Prop | Type | Description |
|------|------|-------------|
| `prediction` | `"UP" \| "DOWN" \| "NEUTRAL"` | XGBoost classifier signal |
| `confidence` | `number` (0–1) | Model confidence score |

## Design decisions

- Follows the AlphaLens dark-theme token system from the frontend skill:
  - **UP** → `text-emerald-400 bg-emerald-400/10 border-emerald-400/20` (green)
  - **DOWN** → `text-red-400 bg-red-400/10 border-red-400/20` (red)
  - **NEUTRAL** → `text-slate-400 bg-slate-700/50 border-slate-600/30` (grey)
- Badge shape matches the existing RSI and MACD badge patterns: `rounded-full`, `text-xs font-semibold`, `px-2.5 py-1`.
- Confidence is clamped to [0, 1] before rounding to a percentage, so bad input can't break the UI.
- A directional icon (▲ / ▼ / —) is prepended for quick at-a-glance scanning.
- No external dependencies — pure Tailwind CSS, no shadcn/ui needed.

## Usage example

```tsx
import PredictionBadge from "@/app/components/PredictionBadge";

// In a stock card or detail page:
<PredictionBadge prediction="UP" confidence={0.83} />
// → ▲ UP 83%

<PredictionBadge prediction="DOWN" confidence={0.61} />
// → ▼ DOWN 61%

<PredictionBadge prediction="NEUTRAL" confidence={0.49} />
// → — NEUTRAL 49%
```

## API integration note

The badge is ready to wire up to the `/predictions/{ticker}` endpoint (Week 4):

```typescript
const res = await fetch(`${API_BASE}/predictions/${ticker}`);
const { prediction, confidence } = await res.json();
// prediction: "UP" | "DOWN" | "NEUTRAL"
// confidence: 0.0 – 1.0
```
