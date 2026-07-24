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
          formatter={(value) => [`$${Number(value).toFixed(2)}`, "Close"]}
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
