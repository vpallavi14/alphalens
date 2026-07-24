import Link from "next/link";
import { STOCKS } from "../../lib/mock-data";
import { fetchScore, fetchPrediction } from "../../lib/api";
import { notFound } from "next/navigation";
import PriceChart from "../../components/PriceChart";

// Pre-generate routes for all 10 tickers
export function generateStaticParams() {
  return STOCKS.map((s) => ({ ticker: s.ticker }));
}

const MOCK_NEWS: Record<string, { headline: string; source: string; sentiment: "positive" | "neutral" | "negative" }[]> = {
  AAPL: [
    { headline: "Apple (AAPL) BofA Stays Bullish as Price Increases Could Offset Higher Memo", source: "Yahoo Finance", sentiment: "positive" },
    { headline: "Apple Watch Series 11 Rumors: Blood Pressure Monitor Gets Regulatory Boost", source: "Bloomberg", sentiment: "positive" },
    { headline: "Apple Supply Chain Faces Tariff Headwinds in Q3", source: "Reuters", sentiment: "negative" },
    { headline: "AAPL Options Activity Suggests Institutional Accumulation", source: "Barron's", sentiment: "positive" },
    { headline: "Apple Services Revenue Expected to Hit Record in Q2", source: "CNBC", sentiment: "positive" },
  ],
  MSFT: [
    { headline: "Microsoft Azure Growth Decelerates but Cloud Dominance Intact", source: "WSJ", sentiment: "neutral" },
    { headline: "How Does Microsoft Turn Cloud Dominance Into $223B For Shareholders?", source: "Yahoo Finance", sentiment: "positive" },
    { headline: "Microsoft Copilot Adoption Slower Than Expected in Enterprise", source: "Bloomberg", sentiment: "negative" },
  ],
};

const DEFAULT_NEWS = [
  { headline: "Stock in focus as earnings season approaches", source: "Yahoo Finance", sentiment: "neutral" as const },
  { headline: "Technical indicators suggest consolidation phase", source: "Reuters", sentiment: "neutral" as const },
  { headline: "Institutional investors adjust positions ahead of Fed meeting", source: "Bloomberg", sentiment: "neutral" as const },
];

function MetricCard({ label, value, sub, accent }: {
  label: string; value: string; sub?: string; accent?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-[#131929] p-4">
      <p className="text-slate-500 text-xs font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 ${accent ?? "text-white"}`}>{value}</p>
      {sub && <p className="text-slate-600 text-xs mt-0.5">{sub}</p>}
    </div>
  );
}

export default async function StockPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const [stock, prediction] = await Promise.all([
    fetchScore(ticker),
    fetchPrediction(ticker),
  ]);
  if (!stock) notFound();

  const news = MOCK_NEWS[stock.ticker] ?? DEFAULT_NEWS;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Back */}
      <Link href="/" className="text-slate-500 text-sm hover:text-slate-300 transition-colors mb-4 inline-block">
        ← Dashboard
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-white">{stock.ticker}</h1>
            <span className={`text-xs font-medium px-2 py-1 rounded-full ${
              stock.macd === "Bullish"
                ? "bg-emerald-500/10 text-emerald-400"
                : "bg-red-500/10 text-red-400"
            }`}>
              MACD {stock.macd === "Bullish" ? "▲ Bullish" : "▼ Bearish"}
            </span>
            {stock.rsiSignal === "Oversold" && (
              <span className="text-xs font-medium px-2 py-1 rounded-full bg-blue-500/10 text-blue-400">
                Oversold — Watch
              </span>
            )}
            {prediction && (
              <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                prediction.prediction === "UP"
                  ? "bg-emerald-500/10 text-emerald-400"
                  : prediction.prediction === "DOWN"
                  ? "bg-red-500/10 text-red-400"
                  : "bg-slate-700/50 text-slate-400"
              }`}>
                {prediction.display.icon} {prediction.prediction} · {(prediction.confidence * 100).toFixed(0)}% conf
              </span>
            )}
          </div>
          <p className="text-slate-400 mt-1">{stock.name} · {stock.sector}</p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-white">${stock.close.toFixed(2)}</p>
          <p className={`text-sm font-medium mt-0.5 ${stock.changePercent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {stock.changePercent >= 0 ? "▲" : "▼"} {Math.abs(stock.changePercent)}% over 20 days
          </p>
        </div>
      </div>

      {/* Score Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        <MetricCard label="Alpha Score"      value={`${stock.alphaScore}/100`}
          sub="Technical composite" accent="text-emerald-400" />
        <MetricCard label="Social Score"     value={`${stock.socialScore}/10`}
          sub="Sentiment composite" accent="text-blue-400" />
        <MetricCard label="Discovery Score"  value={`${stock.discoveryScore}/100`}
          sub="60% Alpha + 40% Social" accent="text-purple-400" />
        <MetricCard label="RSI (14)"         value={stock.rsi.toFixed(1)}
          sub={stock.rsiSignal}
          accent={stock.rsi < 30 ? "text-blue-400" : stock.rsi > 70 ? "text-red-400" : "text-yellow-400"} />
        <MetricCard label="Bollinger Band %"  value={`${(stock.bbPct * 100).toFixed(0)}%`}
          sub={stock.bbPct < 0.2 ? "Near lower band" : stock.bbPct > 0.8 ? "Near upper band" : "Mid-range"} />
        <MetricCard label="Volatility (20d)"  value={`${stock.volatility}%`}
          sub="Annualised" accent={stock.volatility > 60 ? "text-red-400" : "text-slate-300"} />
      </div>

      {/* Price Chart */}
      <div className="rounded-xl border border-slate-800 bg-[#131929] p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-300">Price Chart</h2>
          <span className="text-xs text-slate-500">10-day price history (mock)</span>
        </div>
        <PriceChart />
      </div>

      {/* Technical Indicators */}
      <div className="rounded-xl border border-slate-800 bg-[#131929] p-5 mb-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Technical Indicators</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          {[
            { label: "Momentum (20d)", value: `${stock.changePercent}%`,
              color: stock.changePercent >= 0 ? "text-emerald-400" : "text-red-400" },
            { label: "Volume Spikes (2yr)", value: `${stock.volSpikes}×`, color: "text-yellow-400" },
            { label: "BB Position",   value: `${(stock.bbPct * 100).toFixed(0)}%`,  color: "text-slate-300" },
            { label: "MACD Signal",   value: stock.macd,
              color: stock.macd === "Bullish" ? "text-emerald-400" : "text-red-400" },
          ].map(({ label, value, color }) => (
            <div key={label} className="border border-slate-800 rounded-lg p-3">
              <p className="text-slate-500 text-xs">{label}</p>
              <p className={`font-semibold mt-1 ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent News */}
      <div className="rounded-xl border border-slate-800 bg-[#131929] p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-300">Recent News</h2>
          <span className="text-xs text-slate-600">Social Score: <span className="text-blue-400 font-semibold">{stock.socialScore}/10</span></span>
        </div>
        <div className="space-y-3">
          {news.map((article, i) => (
            <div key={i} className="flex items-start gap-3 py-2 border-b border-slate-800 last:border-0">
              <span className="mt-0.5 text-sm">
                {article.sentiment === "positive" ? "🟢" : article.sentiment === "negative" ? "🔴" : "⚪"}
              </span>
              <div>
                <p className="text-slate-200 text-sm leading-snug">{article.headline}</p>
                <p className="text-slate-600 text-xs mt-0.5">{article.source}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
