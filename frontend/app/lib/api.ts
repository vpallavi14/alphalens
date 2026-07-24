/**
 * AlphaLens API client — Week 4
 * Fetches from API Gateway. Falls back to mock data if the API is unavailable
 * (e.g. running locally without AWS credentials).
 *
 * API base URL is set in .env.local:
 *   NEXT_PUBLIC_API_URL=https://8ptxnd1uoi.execute-api.us-east-1.amazonaws.com
 */

import { Stock, STOCKS } from "./mock-data";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

// Revalidate cached API responses every hour
const FETCH_OPTS: RequestInit = { next: { revalidate: 3600 } };

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Prediction {
  ticker: string;
  prediction: "UP" | "DOWN" | "NEUTRAL";
  confidence: number;        // 0–1
  prob_up: number;
  prob_down: number;
  prob_neutral: number;
  horizon_days: number;
  date: string;
  anomaly_flag: boolean;
  anomaly_score: number;
  display: {
    icon: string;
    color: string;
    label: string;
  };
}

export interface HistoryPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  dailyReturn: number;
}

// ─── Fetch helpers ────────────────────────────────────────────────────────────

/**
 * GET /scores — all 10 tickers sorted by discoveryScore desc.
 * Falls back to mock data if API is unreachable.
 */
export async function fetchAllScores(): Promise<Stock[]> {
  if (!API_BASE) return STOCKS;

  try {
    const res = await fetch(`${API_BASE}/scores`, FETCH_OPTS);
    if (!res.ok) throw new Error(`/scores returned ${res.status}`);
    const data = await res.json();
    return mapApiStocks(data.stocks ?? []);
  } catch (err) {
    console.warn("fetchAllScores: falling back to mock data", err);
    return STOCKS;
  }
}

/**
 * GET /scores/{ticker} — single ticker with component breakdown.
 * Falls back to mock data if API is unreachable.
 */
export async function fetchScore(ticker: string): Promise<Stock | null> {
  if (!API_BASE) {
    return STOCKS.find((s) => s.ticker === ticker.toUpperCase()) ?? null;
  }

  try {
    const res = await fetch(`${API_BASE}/scores/${ticker}`, FETCH_OPTS);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`/scores/${ticker} returned ${res.status}`);
    const data = await res.json();
    return mapApiStock(data.stock);
  } catch (err) {
    console.warn(`fetchScore(${ticker}): falling back to mock data`, err);
    return STOCKS.find((s) => s.ticker === ticker.toUpperCase()) ?? null;
  }
}

/**
 * GET /predictions/{ticker} — XGBoost UP/DOWN/NEUTRAL + anomaly flag.
 * Returns null if no prediction available yet (table not populated).
 */
export async function fetchPrediction(ticker: string): Promise<Prediction | null> {
  if (!API_BASE) return null;

  try {
    const res = await fetch(`${API_BASE}/predictions/${ticker}`, FETCH_OPTS);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * GET /history/{ticker}?days=90 — OHLCV array for Recharts.
 * Returns empty array if not yet populated in S3.
 */
export async function fetchHistory(
  ticker: string,
  days = 90
): Promise<HistoryPoint[]> {
  if (!API_BASE) return [];

  try {
    const res = await fetch(`${API_BASE}/history/${ticker}?days=${days}`, FETCH_OPTS);
    if (!res.ok) return [];
    const data = await res.json();
    return data.history ?? [];
  } catch {
    return [];
  }
}

// ─── API → Stock shape mapper ─────────────────────────────────────────────────
// The API returns snake_case; the frontend uses camelCase from mock-data.ts.

function mapApiStock(s: Record<string, unknown>): Stock {
  return {
    ticker:         String(s.ticker ?? ""),
    name:           String(s.name ?? ""),
    sector:         String(s.sector ?? ""),
    close:          Number(s.close ?? 0),
    changePercent:  Number(s.changePercent ?? s.momentum_20 ?? 0),
    rsi:            Number(s.rsi ?? 50),
    rsiSignal:      (s.rsiSignal ?? s.rsi_signal ?? "Neutral-Low") as Stock["rsiSignal"],
    macd:           (s.macd ?? "Bearish") as Stock["macd"],
    bbPct:          Number(s.bbPct ?? s.bb_pct ?? 0.5),
    volatility:     Number(s.volatility ?? s.volatility_20 ?? 0),
    volSpikes:      Number(s.volSpikes ?? s.vol_spikes ?? 0),
    socialScore:    Number(s.socialScore ?? s.social_score ?? 5),
    alphaScore:     Number(s.alphaScore ?? s.alpha_score ?? 50),
    discoveryScore: Number(s.discoveryScore ?? s.discovery_score ?? 50),
    inWatchlist:    Boolean(s.inWatchlist ?? false),
  };
}

function mapApiStocks(arr: Record<string, unknown>[]): Stock[] {
  return arr.map(mapApiStock);
}
