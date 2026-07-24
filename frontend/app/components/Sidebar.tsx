"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/",          label: "Dashboard",  icon: "⊞" },
  { href: "/discover",  label: "Discover",   icon: "✦" },
  { href: "/watchlist", label: "Watchlist",  icon: "☆" },
];

export default function Sidebar() {
  const path = usePathname();
  const isActive = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  return (
    <aside className="w-56 shrink-0 flex flex-col border-r border-slate-800 bg-[#0d1120] min-h-screen">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-800">
        <span className="text-emerald-400 font-bold text-xl tracking-tight">
          Alpha<span className="text-white">Lens</span>
        </span>
        <p className="text-slate-500 text-xs mt-0.5">AI Stock Intelligence</p>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 p-3 flex-1">
        {NAV.map(({ href, label, icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive(href)
                ? "bg-emerald-500/10 text-emerald-400"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
          >
            <span className="text-base">{icon}</span>
            {label}
          </Link>
        ))}
      </nav>

      {/* Bottom badge */}
      <div className="p-4 border-t border-slate-800">
        <div className="rounded-lg bg-slate-800/60 px-3 py-2 text-xs text-slate-500">
          <p className="font-medium text-slate-400">Week 2 — In Progress</p>
          <p className="mt-0.5">ML models coming Week 3</p>
        </div>
      </div>
    </aside>
  );
}
