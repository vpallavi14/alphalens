import Link from "next/link";
import { fetchAllScores } from "./lib/api";

function rsiColor(signal: string) {
  if (signal === "Oversold")     return "text-blue-400 bg-blue-400/10";
  if (signal === "Neutral-Low")  return "text-slate-400 bg-slate-700/50";
  if (signal === "Neutral-High") return "text-yellow-400 bg-yellow-400/10";
  return "text-red-400 bg-red-400/10";
}

function alphaColor(score: number) {
  if (score >= 65) return "text-emerald-400";
  if (score >= 50) return "text-yellow-400";
  return "text-slate-400";
}

export default async function Dashboard() {
  const STOCKS = await fetchAllScores();
  const avgAlpha  = Math.round(STOCKS.reduce((s, x) => s + x.alphaScore, 0) / STOCKS.length);
  const avgSocial = (STOCKS.reduce((s, x) => s + x.socialScore, 0) / STOCKS.length).toFixed(1);
  const bullish   = STOCKS.filter((s) => s.macd === "Bullish").length;
  const oversold  = STOCKS.filter((s) => s.rsiSignal === "Oversold").length;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">10 tickers tracked · Updated June 24, 2026</p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Avg Alpha Score",   value: `${avgAlpha}/100`,  sub: "Technical composite",  color: "text-emerald-400" },
          { label: "Avg Social Score",  value: `${avgSocial}/10`,  sub: "Sentiment composite",  color: "text-blue-400"    },
          { label: "Bullish MACD",      value: `${bullish}/10`,    sub: "Tickers in uptrend",   color: "text-yellow-400"  },
          { label: "Oversold Signals",  value: `${oversold}`,      sub: "Potential bounce plays", color: "text-purple-400" },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="rounded-xl border border-slate-800 bg-[#131929] p-4">
            <p className="text-slate-500 text-xs font-medium uppercase tracking-wide">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
            <p className="text-slate-600 text-xs mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {/* Stock Grid */}
      <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-widest mb-3">
        All Tickers
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {STOCKS.map((s) => (
          <Link
            key={s.ticker}
            href={`/stock/${s.ticker}`}
            className="block rounded-xl border border-slate-800 bg-[#131929] p-4 hover:border-emerald-500/40 hover:bg-[#151e30] transition-colors"
          >
            {/* Top row */}
            <div className="flex items-start justify-between mb-3">
              <div>
                <span className="text-white font-bold text-lg">{s.ticker}</span>
                <p className="text-slate-500 text-xs">{s.name}</p>
              </div>
              <div className="text-right">
                <p className="text-white font-semibold">${s.close.toFixed(2)}</p>
                <p className={`text-xs font-medium ${s.changePercent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {s.changePercent >= 0 ? "▲" : "▼"} {Math.abs(s.changePercent)}% <span className="text-slate-600">(20d)</span>
                </p>
              </div>
            </div>

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

            {/* Score bars */}
            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500">Alpha Score</span>
                  <span className={`font-semibold ${alphaColor(s.alphaScore)}`}>{s.alphaScore}</span>
                </div>
                <div className="h-1 rounded-full bg-slate-800">
                  <div className="h-1 rounded-full bg-emerald-500" style={{ width: `${s.alphaScore}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500">Social Score</span>
                  <span className="font-semibold text-blue-400">{s.socialScore}/10</span>
                </div>
                <div className="h-1 rounded-full bg-slate-800">
                  <div className="h-1 rounded-full bg-blue-500" style={{ width: `${s.socialScore * 10}%` }} />
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
