import Link from "next/link";
import { fetchAllScores } from "../lib/api";

function discoveryBadge(score: number) {
  if (score >= 65) return { label: "Strong Buy", bg: "bg-emerald-500/10", text: "text-emerald-400", dot: "bg-emerald-400" };
  if (score >= 55) return { label: "Moderate",   bg: "bg-yellow-500/10",  text: "text-yellow-400",  dot: "bg-yellow-400" };
  return            { label: "Neutral",    bg: "bg-slate-700/50",    text: "text-slate-400",  dot: "bg-slate-500" };
}

function rsiLabel(rsi: number, signal: string) {
  if (signal === "Oversold") return { text: "Oversold 🔵", color: "text-blue-400" };
  if (rsi >= 60)             return { text: `RSI ${rsi}`,  color: "text-yellow-400" };
  return                            { text: `RSI ${rsi}`,  color: "text-slate-400" };
}

export default async function Discover() {
  const all = await fetchAllScores();
  const stocks = [...all].sort((a, b) => b.discoveryScore - a.discoveryScore);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Discover</h1>
        <p className="text-slate-500 text-sm mt-1">
          Ranked by Discovery Score = 60% AlphaScore + 40% SocialRank
        </p>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mb-6 text-xs text-slate-500">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" /> Strong Buy (65+)</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" /> Moderate (55–64)</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-slate-500 inline-block" /> Neutral (&lt;55)</span>
        <span className="ml-auto text-slate-600">Week 3: ML classifier will predict UP/DOWN/NEUTRAL</span>
      </div>

      {/* Ranked List */}
      <div className="space-y-3">
        {stocks.map((s, rank) => {
          const badge = discoveryBadge(s.discoveryScore);
          const rsi   = rsiLabel(s.rsi, s.rsiSignal);

          return (
            <Link
              key={s.ticker}
              href={`/stock/${s.ticker}`}
              className="flex items-center gap-4 rounded-xl border border-slate-800 bg-[#131929] p-4 hover:border-emerald-500/30 hover:bg-[#151e30] transition-colors"
            >
              {/* Rank */}
              <div className="w-8 text-center">
                <span className={`text-lg font-bold ${rank < 3 ? "text-emerald-400" : "text-slate-600"}`}>
                  {rank + 1}
                </span>
              </div>

              {/* Ticker + Company */}
              <div className="w-32">
                <p className="font-bold text-white">{s.ticker}</p>
                <p className="text-slate-500 text-xs truncate">{s.name}</p>
              </div>

              {/* Price */}
              <div className="w-24 text-right">
                <p className="text-white font-medium">${s.close.toFixed(2)}</p>
                <p className={`text-xs ${s.changePercent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {s.changePercent >= 0 ? "▲" : "▼"}{Math.abs(s.changePercent)}%
                </p>
              </div>

              {/* Alpha + Social bars */}
              <div className="flex-1 hidden md:block">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-slate-500 text-xs w-14">Alpha</span>
                  <div className="flex-1 h-1.5 rounded-full bg-slate-800">
                    <div className="h-1.5 rounded-full bg-emerald-500" style={{ width: `${s.alphaScore}%` }} />
                  </div>
                  <span className="text-emerald-400 text-xs font-semibold w-8 text-right">{s.alphaScore}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500 text-xs w-14">Social</span>
                  <div className="flex-1 h-1.5 rounded-full bg-slate-800">
                    <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${s.socialScore * 10}%` }} />
                  </div>
                  <span className="text-blue-400 text-xs font-semibold w-8 text-right">{s.socialScore}</span>
                </div>
              </div>

              {/* RSI */}
              <div className="w-24 text-center hidden lg:block">
                <p className={`text-xs font-medium ${rsi.color}`}>{rsi.text}</p>
                <p className={`text-xs ${s.macd === "Bullish" ? "text-emerald-400" : "text-red-400"}`}>
                  MACD {s.macd === "Bullish" ? "▲" : "▼"}
                </p>
              </div>

              {/* Discovery Score + Badge */}
              <div className="text-right w-32">
                <p className="text-white font-bold text-lg">{s.discoveryScore}</p>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badge.bg} ${badge.text}`}>
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${badge.dot} mr-1`} />
                  {badge.label}
                </span>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Callout */}
      <div className="mt-6 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-4 text-center">
        <p className="text-slate-500 text-sm">
          🧠 <span className="text-slate-300 font-medium">Week 3 upgrade:</span> AlphaScore engine + FinBERT sentiment + XGBoost UP/DOWN/NEUTRAL classifier
        </p>
        <p className="text-slate-600 text-xs mt-1">Current scores are rule-based placeholders seeded from real feature data</p>
      </div>
    </div>
  );
}
