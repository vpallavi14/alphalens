/**
 * Data seeded from real computed values — Week 3 updated:
 *   - OHLCV:        yfinance backfill (backfill_historical.py)
 *   - RSI/MACD/BB%: feature_engineering.py
 *   - AlphaScore:   alpha_score_engine.py  (RSI 30% + MACD 20% + BB% 20% + Mom 15% + Vol 10% + VolRat 5%)
 *   - Social Score: finbert_social_score.py  (ProsusAI/finbert on Finnhub headlines)
 *   - Discovery:    60% AlphaScore + 40% (SocialScore × 10)
 */

export type RSISignal = "Oversold" | "Neutral-Low" | "Neutral-High" | "Overbought";
export type MACDSignal = "Bullish" | "Bearish";

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

export const STOCKS: Stock[] = [
  {
    ticker: "AAPL", name: "Apple Inc.", sector: "Technology",
    close: 298.01, changePercent: -1.4,
    rsi: 51.0, rsiSignal: "Neutral-High", macd: "Bearish",
    bbPct: 0.33, volatility: 24.8, volSpikes: 11,
    socialScore: 5.7, alphaScore: 46.6, discoveryScore: 51,
    inWatchlist: true,
  },
  {
    ticker: "AMD", name: "Advanced Micro Devices", sector: "Semiconductors",
    close: 537.37, changePercent: 20.1,
    rsi: 61.2, rsiSignal: "Neutral-High", macd: "Bearish",
    bbPct: 0.81, volatility: 81.7, volSpikes: 15,
    socialScore: 5.3, alphaScore: 42.5, discoveryScore: 47,
    inWatchlist: true,
  },
  {
    ticker: "AMZN", name: "Amazon.com Inc.", sector: "Consumer Cyclical",
    close: 244.39, changePercent: -7.8,
    rsi: 44.0, rsiSignal: "Neutral-Low", macd: "Bearish",
    bbPct: 0.32, volatility: 32.9, volSpikes: 18,
    socialScore: 6.2, alphaScore: 44.3, discoveryScore: 51,
    inWatchlist: false,
  },
  {
    ticker: "GOOGL", name: "Alphabet Inc.", sector: "Technology",
    close: 368.03, changePercent: -5.3,
    rsi: 49.2, rsiSignal: "Neutral-Low", macd: "Bearish",
    bbPct: 0.42, volatility: 29.0, volSpikes: 12,
    socialScore: 6.0, alphaScore: 43.9, discoveryScore: 50,
    inWatchlist: false,
  },
  {
    ticker: "INTC", name: "Intel Corporation", sector: "Semiconductors",
    close: 133.99, changePercent: 12.6,
    rsi: 64.2, rsiSignal: "Neutral-High", macd: "Bullish",
    bbPct: 1.03, volatility: 93.7, volSpikes: 29,
    socialScore: 5.3, alphaScore: 57.3, discoveryScore: 56,
    inWatchlist: true,
  },
  {
    ticker: "META", name: "Meta Platforms Inc.", sector: "Technology",
    close: 577.22, changePercent: -4.5,
    rsi: 43.0, rsiSignal: "Neutral-Low", macd: "Bearish",
    bbPct: 0.26, volatility: 45.0, volSpikes: 17,
    socialScore: 5.6, alphaScore: 46.5, discoveryScore: 50,
    inWatchlist: false,
  },
  {
    ticker: "MSFT", name: "Microsoft Corporation", sector: "Technology",
    close: 379.40, changePercent: -9.7,
    rsi: 35.0, rsiSignal: "Neutral-Low", macd: "Bearish",
    bbPct: 0.12, volatility: 38.3, volSpikes: 16,
    socialScore: 7.0, alphaScore: 54.7, discoveryScore: 61,
    inWatchlist: true,
  },
  {
    ticker: "NFLX", name: "Netflix Inc.", sector: "Entertainment",
    close: 77.38, changePercent: -12.2,
    rsi: 28.0, rsiSignal: "Oversold", macd: "Bearish",
    bbPct: 0.10, volatility: 22.2, volSpikes: 18,
    socialScore: 4.6, alphaScore: 58.8, discoveryScore: 54,
    inWatchlist: false,
  },
  {
    ticker: "NVDA", name: "NVIDIA Corporation", sector: "Semiconductors",
    close: 210.69, changePercent: -5.6,
    rsi: 50.5, rsiSignal: "Neutral-High", macd: "Bearish",
    bbPct: 0.46, volatility: 45.3, volSpikes: 3,
    socialScore: 6.2, alphaScore: 42.9, discoveryScore: 51,
    inWatchlist: true,
  },
  {
    ticker: "TSLA", name: "Tesla Inc.", sector: "Automotive",
    close: 400.49, changePercent: -4.0,
    rsi: 47.0, rsiSignal: "Neutral-Low", macd: "Bearish",
    bbPct: 0.31, volatility: 45.8, volSpikes: 5,
    socialScore: 5.9, alphaScore: 42.9, discoveryScore: 49,
    inWatchlist: false,
  },
];

export const getStock = (ticker: string) =>
  STOCKS.find((s) => s.ticker === ticker.toUpperCase());

export const watchlist = () => STOCKS.filter((s) => s.inWatchlist);

export const byDiscovery = () =>
  [...STOCKS].sort((a, b) => b.discoveryScore - a.discoveryScore);
