"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  ArrowLeftRight, Send, UserPlus, Clock, Check, AlertTriangle,
  Search, Trash2
} from "lucide-react";
import { NotificationBell } from "@/components/NotificationBell";
import { getCollector } from "@/lib/behavioral-collector";
import { getCsrfToken } from "@/lib/auth-utils";

interface Beneficiary {
  id: string;
  name: string;
  account: string;
  bank: string;
  verified: boolean;
}

interface Transfer {
  id: string;
  to: string;
  amount: number;
  date: string;
  status: "completed" | "pending" | "failed";
}

const MOCK_BENEFICIARIES: Beneficiary[] = [
  { id: "b1", name: "Priya Sharma", account: "XXXX4829", bank: "HDFC Bank", verified: true },
  { id: "b2", name: "Cloud Services Inc.", account: "XXXX7156", bank: "ICICI Bank", verified: true },
  { id: "b3", name: "Rahul Patel", account: "XXXX3021", bank: "SBI", verified: false },
];

const MOCK_HISTORY: Transfer[] = [
  { id: "t1", to: "Priya Sharma", amount: 5000, date: "Today, 10:30 AM", status: "completed" },
  { id: "t2", to: "Cloud Services Inc.", amount: 12050, date: "Yesterday, 14:30 PM", status: "completed" },
  { id: "t3", to: "Rahul Patel", amount: 25000, date: "May 9, 09:15 AM", status: "pending" },
];

export default function TransfersPage() {
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([]);
  const [history, setHistory] = useState<Transfer[]>([]);
  const [selectedBeneficiary, setSelectedBeneficiary] = useState<string>("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [search, setSearch] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAccount, setNewAccount] = useState("");
  const [newBank, setNewBank] = useState("");

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("TRANSFERS_PAGE");

    const fetchData = async () => {
      try {
        const [benRes, histRes] = await Promise.all([
          fetch("/api/v1/beneficiaries"),
          fetch("/api/v1/transaction/history")
        ]);
        if (benRes.ok) {
          const bData = await benRes.json();
          setBeneficiaries(bData.beneficiaries || []);
        }
        if (histRes.ok) {
          const hData = await histRes.json();
          const mappedHistory = (hData.transactions || []).map((t: any) => ({
            id: t.id,
            to: t.merchant || "Unknown",
            amount: t.amount,
            date: t.date,
            status: t.decision === "allow" ? "completed" : "failed"
          }));
          setHistory(mappedHistory);
        }
      } catch (err) {
        console.error("Failed to load transfers data:", err);
      }
    };
    fetchData();
  }, []);

  const filteredBeneficiaries = beneficiaries.filter(b =>
    b.name.toLowerCase().includes(search.toLowerCase()) ||
    b.bank.toLowerCase().includes(search.toLowerCase())
  );

  const handleSend = async () => {
    if (!selectedBeneficiary || !amount || parseFloat(amount) <= 0) return;
    setSending(true);
    
    const collector = getCollector();
    const behavioralData = await collector.flush("transaction_assess");
    const ben = beneficiaries.find(b => b.id === selectedBeneficiary);
    const sessionId = document.cookie.match(/session_id=([^;]+)/)?.[1] || "";

    try {
      // Step 1: Acquire cryptographic nonce
      const nonceRes = await fetch("/api/v1/transaction/nonce", {
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
      if (!nonceRes.ok) throw new Error("Failed to acquire transaction nonce");
      const { nonce } = await nonceRes.json();

      // Step 2: Sign the intent payload server-side
      const intentPayload = {
        session_id: sessionId,
        amount: parseFloat(amount),
        operation: "transfer",
        nonce
      };
      const signRes = await fetch("/api/v1/transaction/sign-intent", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify(intentPayload)
      });
      if (!signRes.ok) throw new Error("Failed to sign transaction intent");
      const { signature } = await signRes.json();

      // Step 3: Submit the fully signed transaction for risk assessment
      const res = await fetch("/api/v1/transaction/assess", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify({
          ...intentPayload,
          signature,
          merchant_name: ben?.name || "Unknown",
          transaction_type: "transfer",
          beneficiary_id: ben?.id || "",
          behavioral_data: behavioralData,
          note
        })
      });
      
      const result = await res.json();
      
      if (!res.ok) {
        if (result.decision === "step_up_required") {
          toast.warning("Step-up authentication required for this transaction.");
        } else {
          throw new Error(result.error || "Transaction blocked");
        }
        return;
      }
      
      if (result.decision === "blocked") {
        toast.error(`Transaction blocked: ${(result.reasons || []).join(", ")}`);
        return;
      }
      
      if (result.decision === "step_up_required") {
        toast.warning("Additional verification required for this amount.");
        return;
      }

      setSent(true);
      toast.success(`₹${parseFloat(amount).toLocaleString()} sent to ${ben?.name || "beneficiary"}`);
      
      // Refresh history
      const histRes = await fetch("/api/v1/transaction/history", {
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
      if (histRes.ok) {
        const hData = await histRes.json();
        const mappedHistory = (hData.transactions || []).map((t: any) => ({
          id: t.id,
          to: t.merchant || "Unknown",
          amount: parseFloat(t.amount || "0"),
          date: t.date,
          status: t.decision === "allow" ? "completed" : "failed"
        }));
        setHistory(mappedHistory);
      }
      
      setTimeout(() => { setSent(false); setAmount(""); setNote(""); setSelectedBeneficiary(""); }, 3000);
    } catch (err: any) {
      console.error(err);
      toast.error(err.message || "Transaction failed");
    } finally {
      setSending(false);
    }
  };

  const handleAddBeneficiary = async () => {
    if (!newName || !newAccount) return;
    try {
      const res = await fetch("/api/v1/beneficiaries", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify({ name: newName, account: newAccount, bank: newBank || "Unknown Bank" })
      });
      if (res.ok) {
        const data = await res.json();
        setBeneficiaries(prev => [...prev, data.beneficiary]);
        setNewName(""); setNewAccount(""); setNewBank(""); setShowAddForm(false);
      }
    } catch (err) {
      console.error("Failed to add beneficiary:", err);
    }
  };

  const removeBeneficiary = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/beneficiaries/${id}`, {
        method: "DELETE",
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
      if (res.ok) {
        setBeneficiaries(prev => prev.filter(b => b.id !== id));
      }
    } catch (err) {
      console.error("Failed to delete beneficiary:", err);
    }
  };

  return (
    <>
      <header className="h-16 px-6 lg:px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
        <h1 className="text-xl font-medium text-fg">Transfers</h1>
        <NotificationBell />
      </header>

      <div className="flex-1 overflow-auto p-6 lg:p-8">
        <div className="max-w-5xl mx-auto space-y-8">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">

            {/* Transfer form — 3 cols */}
            <div className="lg:col-span-3 space-y-6">
              <div className="glass-panel rounded-2xl p-6 border border-border space-y-5">
                <div className="flex items-center gap-2 mb-2">
                  <Send className="w-5 h-5 text-accent-primary" />
                  <h2 className="text-sm font-semibold text-fg uppercase tracking-wider">Send Money</h2>
                </div>

                {sent ? (
                  <div className="flex flex-col items-center py-8 gap-3">
                    <div className="w-14 h-14 rounded-full bg-accent-success/10 flex items-center justify-center border border-accent-success/20">
                      <Check className="w-7 h-7 text-accent-success" />
                    </div>
                    <span className="text-lg font-medium text-accent-success">Transfer Initiated</span>
                    <span className="text-xs text-muted">Behavioral verification passed</span>
                  </div>
                ) : (
                  <>
                    {/* Beneficiary select */}
                    <div>
                      <label className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5 block">To</label>
                      <select
                        value={selectedBeneficiary}
                        onChange={e => setSelectedBeneficiary(e.target.value)}
                        className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                      >
                        <option value="">Select beneficiary</option>
                        {beneficiaries.map(b => (
                          <option key={b.id} value={b.id}>{b.name} — {b.account} ({b.bank})</option>
                        ))}
                      </select>
                    </div>

                    {/* Amount */}
                    <div>
                      <label className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5 block">Amount (₹)</label>
                      <input
                        type="number"
                        value={amount}
                        onChange={e => setAmount(e.target.value)}
                        placeholder="0.00"
                        min="1"
                        className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-fg font-mono focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                      />
                    </div>

                    {/* Note */}
                    <div>
                      <label className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5 block">Note (optional)</label>
                      <input
                        type="text"
                        value={note}
                        onChange={e => setNote(e.target.value)}
                        placeholder="Payment for..."
                        className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                      />
                    </div>

                    <button
                      onClick={handleSend}
                      disabled={sending || !selectedBeneficiary || !amount}
                      className="w-full bg-accent-primary text-white font-medium text-sm py-3 rounded-xl hover:bg-blue-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {sending ? (
                        <><Clock className="w-4 h-4 animate-spin" /> Verifying & Sending...</>
                      ) : (
                        <><Send className="w-4 h-4" /> Send Transfer</>
                      )}
                    </button>

                    <div className="flex items-center gap-2 text-[10px] text-muted font-mono">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
                      Behavioral telemetry active — typing rhythm monitored
                    </div>
                  </>
                )}
              </div>

              {/* Transfer history */}
              <div className="glass-panel rounded-2xl p-6 border border-border">
                <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-4">Recent Transfers</h3>
                <div className="space-y-0">
                  {history.map(tx => (
                    <div key={tx.id} className="flex items-center justify-between py-3 border-b border-border last:border-0">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-black/20 flex items-center justify-center border border-border text-xs font-bold text-muted">
                          {tx.to.charAt(0)}
                        </div>
                        <div>
                          <div className="text-sm text-fg font-medium">{tx.to}</div>
                          <div className="text-xs text-muted">{tx.date}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-mono text-fg">-₹{tx.amount.toLocaleString()}</span>
                        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full border ${
                          tx.status === "completed" ? "text-accent-success bg-accent-success/10 border-accent-success/20" :
                          tx.status === "pending" ? "text-amber-400 bg-amber-500/10 border-amber-500/20" :
                          "text-red-400 bg-red-500/10 border-red-500/20"
                        }`}>{tx.status.toUpperCase()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Beneficiary management — 2 cols */}
            <div className="lg:col-span-2 space-y-6">
              <div className="glass-panel rounded-2xl p-6 border border-border">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">Beneficiaries</h3>
                  <button
                    onClick={() => setShowAddForm(!showAddForm)}
                    className="text-xs text-accent-primary hover:text-blue-400 transition-colors flex items-center gap-1"
                  >
                    <UserPlus className="w-3.5 h-3.5" />
                    {showAddForm ? "Cancel" : "Add New"}
                  </button>
                </div>

                {showAddForm && (
                  <div className="space-y-3 mb-4 p-4 bg-black/20 rounded-xl border border-border">
                    <input
                      value={newName}
                      onChange={e => setNewName(e.target.value)}
                      placeholder="Full name"
                      className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                    />
                    <input
                      value={newAccount}
                      onChange={e => setNewAccount(e.target.value)}
                      placeholder="Account number"
                      className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-fg font-mono focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                    />
                    <input
                      value={newBank}
                      onChange={e => setNewBank(e.target.value)}
                      placeholder="Bank name"
                      className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                    />
                    <button
                      onClick={handleAddBeneficiary}
                      disabled={!newName || !newAccount}
                      className="w-full bg-accent-primary text-white text-xs font-medium py-2.5 rounded-lg disabled:opacity-40"
                    >
                      Add Beneficiary
                    </button>
                  </div>
                )}

                {/* Search */}
                <div className="relative mb-3">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
                  <input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search beneficiaries..."
                    className="w-full bg-surface border border-border rounded-lg pl-9 pr-3 py-2 text-xs text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                  />
                </div>

                <div className="space-y-2">
                  {filteredBeneficiaries.map(b => (
                    <div key={b.id} className="flex items-center justify-between p-3 bg-black/20 rounded-xl border border-border hover:border-accent-primary/20 transition-colors group">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-surface-2 flex items-center justify-center text-xs font-bold text-muted border border-border shrink-0">
                          {b.name.charAt(0)}
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm text-fg font-medium truncate flex items-center gap-1.5">
                            {b.name}
                            {b.verified && <Check className="w-3 h-3 text-accent-success" />}
                          </div>
                          <div className="text-[10px] text-muted font-mono">{b.account} · {b.bank}</div>
                        </div>
                      </div>
                      <button
                        onClick={() => removeBeneficiary(b.id)}
                        className="opacity-0 group-hover:opacity-100 w-7 h-7 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-400 transition-all shrink-0"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                  {filteredBeneficiaries.length === 0 && (
                    <div className="text-center text-xs text-muted py-4">No beneficiaries found</div>
                  )}
                </div>
              </div>

              {/* Security notice */}
              <div className="flex items-start gap-3 bg-amber-500/5 border border-amber-500/20 rounded-xl p-4">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <div className="text-xs font-medium text-amber-400">Transfer Security</div>
                  <p className="text-[10px] text-muted mt-1 leading-relaxed">
                    All transfers are protected by behavioral verification. High-value or unusual transactions may require step-up authentication.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}