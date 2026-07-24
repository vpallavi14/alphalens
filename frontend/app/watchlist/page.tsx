import Link from "next/link";
import { fetchAllScores } from "../lib/api";

export default async function Watchlist() {
  const all = await fetchAllScores();
  const stocks = all.filter((s) => s.inWatchlist);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Watchlist</h1>
          <p className="text-slate-500 text-sm mt-1">{stocks.length} stocks saved</p>
        </div>
        <Link
          href="/discover"
          className="text-sm text-emerald-400 border border-emerald-500/30 px-3 py-1.5 rounded-lg hover:bg-emerald-500/10 transition-colors"
        >
          + Add from Discover
        </Link>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-800 bg-[#131929] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 bg-[#0d1120]">
                {["Ticker", "Price", "20d Change", "RSI", "MACD", "Alpha", "Social", "Discovery", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stocks.map((s, i) => (
                <tr
                  key={s.ticker}
                  className={`border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors ${
                    i % 2 === 0 ? "" : "bg-slate-900/20"
                  }`}
                >
                  {/* Ticker */}
                  <td className="px-4 py-3">
                    <Link href={`/stock/${s.ticker}`} className="hover:text-emerald-400 transition-colors">
                      <span className="font-bold text-white">{s.ticker}</span>
                      <p className="text-slate-500 text-xs">{s.sector}</p>
                    </Link>
                  </td>

                  {/* Price */}
                  <td className="px-4 py-3 text-white font-medium">
                    ${s.close.toFixed(2)}
                  </td>

                  {/* 20d Change */}
                  <td className={`px-4 py-3 font-medium ${s.changePercent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {s.changePercent >= 0 ? "▲" : "▼"} {Math.abs(s.changePercent)}%
                  </td>

                  {/* RSI */}
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      s.rsi < 30 ? "text-blue-400 bg-blue-400/10" :
                      s.rsi > 70 ? "text-red-400 bg-red-400/10" :
                      "text-slate-400 bg-slate-700/50"
                    }`}>
                      {s.rsi.toFixed(0)}
                    </span>
                  </td>

                  {/* MACD */}
                  <td className={`px-4 py-3 font-medium text-xs ${
                    s.macd === "Bullish" ? "text-emerald-400" : "text-red-400"
                  }`}>
                    {s.macd === "Bullish" ? "▲ Bull" : "▼ Bear"}
                  </td>

                  {/* Alpha Score */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className={`font-semibold ${
                        s.alphaScore >= 65 ? "text-emerald-400" :
                        s.alphaScore >= 50 ? "text-yellow-400" : "text-slate-400"
                      }`}>
                        {s.alphaScore}
                      </span>
                      <div className="w-16 h-1.5 rounded-full bg-slate-800">
                        <div className="h-1.5 rounded-full bg-emerald-500" style={{ width: `${s.alphaScore}%` }} />
                      </div>
                    </div>
                  </td>

                  {/* Social Score */}
                  <td className="px-4 py-3">
                    <span className="text-blue-400 font-semibold">{s.socialScore}</span>
                    <span className="text-slate-600 text-xs">/10</span>
                  </td>

                  {/* Discovery */}
                  <td className="px-4 py-3">
                    <span className="text-purple-400 font-semibold">{s.discoveryScore}</span>
                  </td>

                  {/* Action */}
                  <td className="px-4 py-3">
                    <Link
                      href={`/stock/${s.ticker}`}
                      className="text-xs text-slate-500 hover:text-emerald-400 transition-colors"
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Summary */}
      <div className="mt-4 grid grid-cols-3 gap-4">
        {[
          {
            label: "Avg Alpha Score",
            value: Math.round(stocks.reduce((s, x) => s + x.alphaScore, 0) / stocks.length),
            suffix: "/100",
            color: "text-emerald-400",
          },
          {
            label: "Avg Social Score",
            value: (stocks.reduce((s, x) => s + x.socialScore, 0) / stocks.length).toFixed(1),
            suffix: "/10",
            color: "text-blue-400",
          },
          {
            label: "Avg Discovery",
            value: Math.round(stocks.reduce((s, x) => s + x.discoveryScore, 0) / stocks.length),
            suffix: "/100",
            color: "text-purple-400",
          },
        ].map(({ label, value, suffix, color }) => (
          <div key={label} className="rounded-xl border border-slate-800 bg-[#131929] p-4 text-center">
            <p className="text-slate-500 text-xs">{label}</p>
            <p className={`text-xl font-bold mt-1 ${color}`}>{value}<span className="text-slate-600 text-sm">{suffix}</span></p>
          </div>
        ))}
      </div>
    </div>
  );
}
