"use client";

import { useState, useEffect } from "react";
import {
  PieChart, TrendingUp, TrendingDown, BarChart3, ArrowUpRight, ArrowDownRight, Search
} from "lucide-react";
import { NotificationBell } from "@/components/NotificationBell";
import { getCollector } from "@/lib/behavioral-collector";

interface Holding {
  id: string;
  name: string;
  symbol: string;
  type: "equity" | "mf" | "bond" | "fd";
  value: number;
  change: number;        // percent change
  units: number;
  avgCost: number;
}

// Fallback demo holdings
const MOCK_HOLDINGS: Holding[] = [
  { id: "h1", name: "Reliance Industries", symbol: "RELIANCE", type: "equity", value: 145200, change: 2.4, units: 50, avgCost: 2650 },
];

const TYPE_LABELS: Record<string, string> = { equity: "Equity", mf: "Mutual Fund", bond: "Bond", fd: "Fixed Deposit" };
const TYPE_COLORS: Record<string, string> = { equity: "text-blue-400", mf: "text-purple-400", bond: "text-amber-400", fd: "text-emerald-400" };

export default function InvestmentsPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [holdingSearch, setHoldingSearch] = useState("");
  const [expandedHolding, setExpandedHolding] = useState<string | null>(null);
  const [holdingNotes, setHoldingNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("INVESTMENTS_PAGE");

    const fetchPortfolio = async () => {
      try {
        const res = await fetch("/api/v1/investments/portfolio");
        if (res.ok) {
          const data = await res.json();
          setHoldings(data.holdings || []);
        } else {
          setHoldings(MOCK_HOLDINGS);
        }
      } catch {
        setHoldings(MOCK_HOLDINGS);
      } finally {
        setLoading(false);
      }
    };
    fetchPortfolio();
  }, []);

  const totalValue = holdings.reduce((s, h) => s + h.value, 0);
  const totalCost = holdings.reduce((s, h) => s + h.avgCost * h.units, 0);
  const totalGain = totalValue - totalCost;
  const totalGainPct = totalCost > 0 ? ((totalGain / totalCost) * 100) : 0;

  const filtered = holdings.filter(h => 
    (filter === "all" || h.type === filter) &&
    (h.name.toLowerCase().includes(holdingSearch.toLowerCase()) || h.symbol.toLowerCase().includes(holdingSearch.toLowerCase()))
  );

  // Allocation breakdown
  const allocation = ["equity", "mf", "bond", "fd"].map(type => {
    const val = holdings.filter(h => h.type === type).reduce((s, h) => s + h.value, 0);
    return { type, value: val, pct: totalValue > 0 ? Math.round((val / totalValue) * 100) : 0 };
  }).filter(a => a.value > 0);

  return (
    <>
      <header className="h-16 px-6 lg:px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-medium text-fg">Investments</h1>
          <span className="px-2.5 py-1 rounded-md bg-accent-primary/10 border border-accent-primary/20 text-[10px] font-mono font-bold text-accent-primary tracking-wider">
            {holdings.length} HOLDINGS
          </span>
        </div>
        <NotificationBell />
      </header>

      <div className="flex-1 overflow-auto p-6 lg:p-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted">
            <div className="w-8 h-8 rounded-full border-2 border-accent-primary border-t-transparent animate-spin mb-4"></div>
            Loading portfolio...
          </div>
        ) : (
        <div className="max-w-5xl mx-auto space-y-8">

          {/* Portfolio summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="glass-panel rounded-2xl p-6 border border-border">
              <div className="text-xs text-muted uppercase tracking-wider font-bold mb-2">Portfolio Value</div>
              <div className="text-2xl font-mono font-semibold text-fg tabular-nums">₹{totalValue.toLocaleString()}</div>
            </div>
            <div className="glass-panel rounded-2xl p-6 border border-border">
              <div className="text-xs text-muted uppercase tracking-wider font-bold mb-2">Total Gain / Loss</div>
              <div className={`text-2xl font-mono font-semibold tabular-nums flex items-center gap-2 ${totalGain >= 0 ? 'text-accent-success' : 'text-red-400'}`}>
                {totalGain >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                {totalGain >= 0 ? "+" : ""}₹{Math.abs(totalGain).toLocaleString()}
              </div>
              <div className={`text-xs font-mono mt-1 ${totalGain >= 0 ? 'text-accent-success' : 'text-red-400'}`}>
                {totalGainPct >= 0 ? "+" : ""}{totalGainPct.toFixed(2)}%
              </div>
            </div>
            <div className="glass-panel rounded-2xl p-6 border border-border">
              <div className="text-xs text-muted uppercase tracking-wider font-bold mb-2">Asset Allocation</div>
              <div className="space-y-1.5">
                {allocation.map(a => (
                  <div key={a.type} className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${TYPE_COLORS[a.type].replace('text-', 'bg-')}`} />
                    <span className="text-xs text-muted flex-1">{TYPE_LABELS[a.type]}</span>
                    <span className="text-xs font-mono text-fg">{a.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Filter tabs */}
          <div className="flex gap-2 flex-wrap">
            {[{key: "all", label: "All"}, {key: "equity", label: "Equity"}, {key: "mf", label: "Mutual Funds"}, {key: "bond", label: "Bonds"}, {key: "fd", label: "Fixed Deposits"}].map(f => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors border ${
                  filter === f.key
                    ? 'bg-accent-primary/10 border-accent-primary/30 text-accent-primary'
                    : 'bg-surface border-border text-muted hover:text-fg'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Search Bar */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
            <input
              type="text"
              value={holdingSearch}
              onChange={e => setHoldingSearch(e.target.value)}
              placeholder="Search holdings, symbols, or fund names..."
              className="w-full bg-surface border border-border rounded-xl pl-9 pr-4 py-2.5 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
            />
          </div>

          {/* Holdings table */}
          <div className="glass-panel rounded-2xl border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-black/20">
                    <th className="text-left text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Instrument</th>
                    <th className="text-right text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Units</th>
                    <th className="text-right text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Avg Cost</th>
                    <th className="text-right text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Current Value</th>
                    <th className="text-right text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(h => {
                    const gain = h.value - (h.avgCost * h.units);
                    return (
                      <tr key={h.id} className="border-b border-border last:border-0 hover:bg-surface-2/30 transition-colors cursor-pointer" onClick={() => setExpandedHolding(expandedHolding === h.id ? null : h.id)}>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold border border-border ${TYPE_COLORS[h.type]} bg-black/20`}>
                              {h.symbol.charAt(0)}
                            </div>
                            <div className="flex-1">
                              <div className="font-medium text-fg">{h.name}</div>
                              <div className="text-[10px] text-muted font-mono">{h.symbol} · {TYPE_LABELS[h.type]}</div>
                              {expandedHolding === h.id && (
                                <div className="mt-3 pt-3 border-t border-border" onClick={e => e.stopPropagation()}>
                                  <input
                                    type="text"
                                    placeholder="Add a note about this holding..."
                                    value={holdingNotes[h.id] || ""}
                                    onChange={e => setHoldingNotes(prev => ({ ...prev, [h.id]: e.target.value }))}
                                    className="w-full bg-black/20 border border-border rounded-lg px-3 py-2 text-xs text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right font-mono text-fg align-top">{h.units.toLocaleString()}</td>
                        <td className="px-6 py-4 text-right font-mono text-muted align-top">₹{h.avgCost.toLocaleString()}</td>
                        <td className="px-6 py-4 text-right font-mono font-medium text-fg align-top">₹{h.value.toLocaleString()}</td>
                        <td className="px-6 py-4 text-right align-top">
                          <div className={`flex items-center justify-end gap-1 font-mono ${h.change > 0 ? 'text-accent-success' : h.change < 0 ? 'text-red-400' : 'text-muted'}`}>
                            {h.change > 0 ? <ArrowUpRight className="w-3 h-3" /> : h.change < 0 ? <ArrowDownRight className="w-3 h-3" /> : null}
                            {h.change > 0 ? "+" : ""}{h.change.toFixed(1)}%
                          </div>
                          <div className={`text-[10px] font-mono ${gain >= 0 ? 'text-accent-success' : 'text-red-400'}`}>
                            {gain >= 0 ? "+" : ""}₹{gain.toLocaleString()}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Behavioral notice */}
          <div className="flex items-center gap-2 text-[10px] text-muted font-mono bg-black/20 border border-border/50 rounded-lg p-3">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
            Investment page browsing patterns captured — portfolio interaction telemetry active
          </div>
        </div>
        )}
      </div>
    </>
  );
}