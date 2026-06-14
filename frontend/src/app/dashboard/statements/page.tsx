"use client";

import { useState, useEffect } from "react";
import {
  FileText, Download, Calendar, Filter, Search,
  ArrowDownLeft, ArrowUpRight, ChevronLeft, ChevronRight
} from "lucide-react";
import { NotificationBell } from "@/components/NotificationBell";
import { getCollector } from "@/lib/behavioral-collector";

interface Statement {
  id: string;
  date: string;
  description: string;
  type: "credit" | "debit";
  amount: number;
  balance: number;
  category: string;
  reference: string;
}

// MOCK_STATEMENTS used as fallback if API fails
const MOCK_STATEMENTS: Statement[] = [
  { id: "s1", date: "2026-05-11", description: "Salary Credit — TechCorp", type: "credit", amount: 85000, balance: 142350, category: "Income", reference: "NEFT/2026/05/8829" },
];

const CATEGORIES = ["All", "Income", "Shopping", "Transfer", "Utilities", "Cash", "Insurance", "Investment", "Food", "Subscription"];

export default function StatementsPage() {
  const [statements, setStatements] = useState<Statement[]>([]);
  const [search, setSearch] = useState("");
  const [merchantFilter, setMerchantFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "credit" | "debit">("all");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const perPage = 5;

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("STATEMENTS_PAGE");
    
    const fetchHistory = async () => {
      try {
        const res = await fetch("/api/v1/transaction/history");
        if (res.ok) {
          const data = await res.json();
          let currentBalance = 50000; // start balance
          const mapped = (data.transactions || []).map((t: any) => {
            const isDebit = t.type === "transfer" || t.type === "debit";
            if (isDebit) currentBalance -= t.amount;
            else currentBalance += t.amount;
            return {
              id: t.id,
              date: t.date.split("T")[0] || t.date,
              description: t.merchant || "Transaction",
              type: isDebit ? "debit" : "credit",
              amount: t.amount,
              balance: currentBalance,
              category: "Transfer",
              reference: `TXN/${t.id.slice(0,6).toUpperCase()}`
            };
          });
          setStatements(mapped.length ? mapped : MOCK_STATEMENTS);
        } else {
          setStatements(MOCK_STATEMENTS);
        }
      } catch {
        setStatements(MOCK_STATEMENTS);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, []);

  // Apply filters
  const filtered = statements.filter(s => {
    if (typeFilter !== "all" && s.type !== typeFilter) return false;
    if (categoryFilter !== "All" && s.category !== categoryFilter) return false;
    if (search && !s.description.toLowerCase().includes(search.toLowerCase()) && !s.reference.toLowerCase().includes(search.toLowerCase())) return false;
    if (merchantFilter && !s.description.toLowerCase().includes(merchantFilter.toLowerCase())) return false;
    return true;
  });

  const totalPages = Math.ceil(filtered.length / perPage);
  const paginated = filtered.slice((page - 1) * perPage, page * perPage);

  const totalCredits = filtered.filter(s => s.type === "credit").reduce((s, t) => s + t.amount, 0);
  const totalDebits = filtered.filter(s => s.type === "debit").reduce((s, t) => s + t.amount, 0);

  const handleDownload = () => {
    const csv = [
      "Date,Description,Type,Amount,Balance,Category,Reference",
      ...filtered.map(s =>
        `${s.date},"${s.description}",${s.type},${s.amount},${s.balance},${s.category},${s.reference}`
      )
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `statement_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <header className="h-16 px-6 lg:px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-medium text-fg">Statements</h1>
          <span className="px-2.5 py-1 rounded-md bg-accent-primary/10 border border-accent-primary/20 text-[10px] font-mono font-bold text-accent-primary tracking-wider">
            {filtered.length} ENTRIES
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent-primary/10 border border-accent-primary/20 text-accent-primary rounded-lg hover:bg-accent-primary/20 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>
          <NotificationBell />
        </div>
      </header>

      <div className="flex-1 overflow-auto p-6 lg:p-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted">
            <div className="w-8 h-8 rounded-full border-2 border-accent-primary border-t-transparent animate-spin mb-4"></div>
            Loading statements...
          </div>
        ) : (
        <div className="max-w-5xl mx-auto space-y-6">

          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="glass-panel rounded-xl p-5 border border-border">
              <div className="text-xs text-muted uppercase tracking-wider font-bold mb-2">Total Credits</div>
              <div className="text-xl font-mono font-semibold text-accent-success tabular-nums">+₹{totalCredits.toLocaleString()}</div>
            </div>
            <div className="glass-panel rounded-xl p-5 border border-border">
              <div className="text-xs text-muted uppercase tracking-wider font-bold mb-2">Total Debits</div>
              <div className="text-xl font-mono font-semibold text-red-400 tabular-nums">-₹{totalDebits.toLocaleString()}</div>
            </div>
            <div className="glass-panel rounded-xl p-5 border border-border">
              <div className="text-xs text-muted uppercase tracking-wider font-bold mb-2">Net Flow</div>
              <div className={`text-xl font-mono font-semibold tabular-nums ${totalCredits - totalDebits >= 0 ? 'text-accent-success' : 'text-red-400'}`}>
                {totalCredits - totalDebits >= 0 ? "+" : ""}₹{(totalCredits - totalDebits).toLocaleString()}
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-3 items-center">
            <div className="relative flex-1 min-w-[200px] max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
              <input
                value={search}
                onChange={e => { setSearch(e.target.value); setPage(1); }}
                placeholder="Search transactions..."
                className="w-full bg-surface border border-border rounded-lg pl-9 pr-3 py-2 text-xs text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
              />
            </div>

            <input
              type="text"
              placeholder="Filter by merchant..."
              value={merchantFilter}
              onChange={e => { setMerchantFilter(e.target.value); setPage(1); }}
              className="bg-surface border border-border rounded-lg px-3 py-2 text-xs text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50 min-w-[160px]"
            />

            <div className="flex gap-1.5">
              {(["all", "credit", "debit"] as const).map(t => (
                <button
                  key={t}
                  onClick={() => { setTypeFilter(t); setPage(1); }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    typeFilter === t
                      ? 'bg-accent-primary/10 border-accent-primary/30 text-accent-primary'
                      : 'bg-surface border-border text-muted hover:text-fg'
                  }`}
                >
                  {t === "all" ? "All" : t === "credit" ? "Credits" : "Debits"}
                </button>
              ))}
            </div>

            <select
              value={categoryFilter}
              onChange={e => { setCategoryFilter(e.target.value); setPage(1); }}
              className="bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-fg focus:outline-none"
            >
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Statement table */}
          <div className="glass-panel rounded-2xl border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-black/20">
                    <th className="text-left text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Date</th>
                    <th className="text-left text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Description</th>
                    <th className="text-left text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Category</th>
                    <th className="text-right text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Amount</th>
                    <th className="text-right text-[10px] text-muted uppercase tracking-wider font-bold px-6 py-3">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {paginated.map(s => (
                    <tr key={s.id} className="border-b border-border last:border-0 hover:bg-surface-2/30 transition-colors">
                      <td className="px-6 py-3">
                        <div className="text-xs font-mono text-fg">{s.date}</div>
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-2">
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center border border-border shrink-0 ${
                            s.type === "credit" ? "bg-accent-success/10" : "bg-surface-2"
                          }`}>
                            {s.type === "credit"
                              ? <ArrowDownLeft className="w-3.5 h-3.5 text-accent-success" />
                              : <ArrowUpRight className="w-3.5 h-3.5 text-muted" />
                            }
                          </div>
                          <div>
                            <div className="text-sm text-fg">{s.description}</div>
                            <div className="text-[9px] text-muted font-mono">{s.reference}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-3">
                        <span className="text-[10px] font-medium text-muted bg-surface-2 px-2 py-0.5 rounded-full border border-border">{s.category}</span>
                      </td>
                      <td className={`px-6 py-3 text-right font-mono font-medium ${s.type === "credit" ? "text-accent-success" : "text-fg"}`}>
                        {s.type === "credit" ? "+" : "-"}₹{s.amount.toLocaleString()}
                      </td>
                      <td className="px-6 py-3 text-right font-mono text-muted">
                        ₹{s.balance.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                  {paginated.length === 0 && (
                    <tr><td colSpan={5} className="px-6 py-8 text-center text-xs text-muted">No matching transactions</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-3 border-t border-border bg-black/10">
                <span className="text-xs text-muted">
                  Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, filtered.length)} of {filtered.length}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="w-8 h-8 flex items-center justify-center rounded-md hover:bg-surface-2 text-muted disabled:opacity-30 transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  {Array.from({length: totalPages}, (_, i) => (
                    <button
                      key={i}
                      onClick={() => setPage(i + 1)}
                      className={`w-8 h-8 flex items-center justify-center rounded-md text-xs font-medium transition-colors ${
                        page === i + 1 ? 'bg-accent-primary/20 text-accent-primary' : 'text-muted hover:bg-surface-2'
                      }`}
                    >
                      {i + 1}
                    </button>
                  ))}
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="w-8 h-8 flex items-center justify-center rounded-md hover:bg-surface-2 text-muted disabled:opacity-30 transition-colors"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 text-[10px] text-muted font-mono bg-black/20 border border-border/50 rounded-lg p-3">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
            Statement browsing pattern captured — scroll and search telemetry active
          </div>
        </div>
        )}
      </div>
    </>
  );
}