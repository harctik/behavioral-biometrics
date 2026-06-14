"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  CreditCard, Eye, EyeOff, Lock, Unlock, Snowflake, Flame,
  Copy, Check, ShieldCheck, AlertTriangle, KeyRound
} from "lucide-react";
import { NotificationBell } from "@/components/NotificationBell";
import { getCollector } from "@/lib/behavioral-collector";
import { getCsrfToken } from "@/lib/auth-utils";

interface Card {
  id: string;
  type: "debit" | "credit";
  last4: string;
  network: "Visa" | "Mastercard";
  expiry: string;
  holder: string;
  frozen: boolean;
  limit: number;
  spent: number;
  fullNumber: string;
  cvv: string;
}

// Fallback demo cards
const MOCK_CARDS: Card[] = [
  {
    id: "card_1",
    type: "debit",
    last4: "4829",
    network: "Visa",
    expiry: "09/28",
    holder: "ALEX JOHNSON",
    frozen: false,
    limit: 50000,
    spent: 12450,
    fullNumber: "4532 •••• •••• 4829",
    cvv: "•••",
  }
];

function CardVisual({ card, revealed }: { card: Card; revealed: boolean }) {
  const gradients: Record<string, string> = {
    debit: "from-slate-800 via-slate-700 to-slate-900",
    credit: "from-indigo-900 via-purple-900 to-slate-900",
  };

  return (
    <div className={`relative w-full aspect-[1.586/1] max-w-sm bg-gradient-to-br ${gradients[card.type]} rounded-2xl p-6 flex flex-col justify-between border border-white/10 shadow-2xl overflow-hidden`}>
      {/* Decorative circles */}
      <div className="absolute -top-10 -right-10 w-40 h-40 bg-white/5 rounded-full" />
      <div className="absolute -bottom-8 -left-8 w-32 h-32 bg-white/5 rounded-full" />

      <div className="flex justify-between items-start relative z-10">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-white/50 font-bold">{card.type} card</div>
          <div className="text-white/80 text-xs mt-1">{card.network}</div>
        </div>
        {card.frozen && (
          <div className="flex items-center gap-1 bg-blue-500/20 border border-blue-500/30 rounded-full px-2 py-0.5 text-[9px] text-blue-300 font-bold">
            <Snowflake className="w-3 h-3" /> FROZEN
          </div>
        )}
      </div>

      <div className="relative z-10">
        <div className="font-mono text-lg tracking-[0.25em] text-white/90 mb-4">
          {revealed ? card.fullNumber.replace(/••••/g, Math.random().toString().slice(2, 6)) : card.fullNumber}
        </div>
        <div className="flex justify-between items-end">
          <div>
            <div className="text-[9px] text-white/40 uppercase tracking-wider">Card Holder</div>
            <div className="text-xs text-white/80 font-medium tracking-wider">{card.holder}</div>
          </div>
          <div>
            <div className="text-[9px] text-white/40 uppercase tracking-wider">Expires</div>
            <div className="text-xs text-white/80 font-mono">{card.expiry}</div>
          </div>
          <div>
            <div className="text-[9px] text-white/40 uppercase tracking-wider">CVV</div>
            <div className="text-xs text-white/80 font-mono">{revealed ? Math.floor(Math.random() * 900 + 100) : card.cvv}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CardsPage() {
  const [cards, setCards] = useState<Card[]>([]);
  const [selectedCard, setSelectedCard] = useState<string>("");
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [stepUpPassword, setStepUpPassword] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [freezeReason, setFreezeReason] = useState("");
  const [cardNickname, setCardNickname] = useState("");

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("CARDS_PAGE");
    
    const fetchCards = async () => {
      try {
        const res = await fetch("/api/v1/cards");
        if (res.ok) {
          const data = await res.json();
          if (data.cards && data.cards.length > 0) {
            setCards(data.cards);
            setSelectedCard(data.cards[0].id);
          } else {
            setCards(MOCK_CARDS);
            setSelectedCard(MOCK_CARDS[0].id);
          }
        } else {
          setCards(MOCK_CARDS);
          setSelectedCard(MOCK_CARDS[0].id);
        }
      } catch {
        setCards(MOCK_CARDS);
        setSelectedCard(MOCK_CARDS[0].id);
      } finally {
        setLoading(false);
      }
    };
    fetchCards();
  }, []);

  const activeCard = cards.find(c => c.id === selectedCard) || cards[0];
  const spentPct = activeCard ? Math.round((activeCard.spent / activeCard.limit) * 100) : 0;

  const toggleFreeze = async (cardId: string) => {
    const card = cards.find(c => c.id === cardId);
    if (!card) return;
    
    const newFrozenState = !card.frozen;
    setCards(prev => prev.map(c => c.id === cardId ? { ...c, frozen: newFrozenState } : c));
    
    try {
      await fetch(`/api/v1/cards/${cardId}/freeze`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": getCsrfToken() },
        body: JSON.stringify({ freeze: newFrozenState })
      });
    } catch {}
  };

  const handleReveal = () => {
    if (revealed) {
      setRevealed(false);
      return;
    }
    // Prompt for step-up authentication
    setShowPasswordModal(true);
    setStepUpPassword("");
  };

  const handleStepUpSubmit = async () => {
    if (!stepUpPassword) return;
    setVerifying(true);
    try {
      const res = await fetch(`/api/v1/cards/${activeCard?.id}/cvv`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify({ password: stepUpPassword })
      });
      
      if (!res.ok) {
        const data = await res.json();
        toast.error(data.error || "Authentication failed");
        return;
      }
      
      const data = await res.json();
      setCards(prev => prev.map(c =>
        c.id === activeCard?.id
          ? { ...c, fullNumber: data.full_number, cvv: data.cvv }
          : c
      ));
      setRevealed(true);
      setShowPasswordModal(false);
      toast.success("Card details revealed");
      
      // Auto-hide after 30 seconds for security
      setTimeout(() => setRevealed(false), 30000);
    } catch {
      toast.error("Failed to verify identity");
    } finally {
      setVerifying(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(activeCard.last4);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      {/* Topbar */}
      <header className="h-16 px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-medium text-fg">Cards</h1>
          <span className="px-2.5 py-1 rounded-md bg-accent-primary/10 border border-accent-primary/20 text-[10px] font-mono font-bold text-accent-primary tracking-wider">
            {cards.length} ACTIVE
          </span>
        </div>
        <NotificationBell />
      </header>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6 lg:p-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted">
            <div className="w-8 h-8 rounded-full border-2 border-accent-primary border-t-transparent animate-spin mb-4"></div>
            Loading cards...
          </div>
        ) : (
        <div className="max-w-5xl mx-auto space-y-8">

          {/* Card selector tabs */}
          <div className="flex gap-3">
            {cards.map(card => (
              <button
                key={card.id}
                onClick={() => { setSelectedCard(card.id); setRevealed(false); }}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm transition-all border ${
                  selectedCard === card.id
                    ? 'bg-accent-primary/10 border-accent-primary/30 text-accent-primary font-medium'
                    : 'bg-surface border-border text-muted hover:text-fg hover:border-border'
                }`}
              >
                <CreditCard className="w-4 h-4" />
                {card.network} ••{card.last4}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Card visual */}
            <div className="flex flex-col items-center gap-4">
              <CardVisual card={activeCard} revealed={revealed} />

              {/* Action buttons */}
              <div className="flex gap-3 w-full max-w-sm">
                <button
                  onClick={handleReveal}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-surface-2 border border-border text-sm text-fg hover:bg-surface-elevated transition-colors"
                >
                  {revealed ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  {revealed ? "Hide" : "Reveal"}
                </button>
                <button
                  onClick={handleCopy}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-surface-2 border border-border text-sm text-fg hover:bg-surface-elevated transition-colors"
                >
                  {copied ? <Check className="w-4 h-4 text-accent-success" /> : <Copy className="w-4 h-4" />}
                  {copied ? "Copied" : "Copy Last 4"}
                </button>
                <button
                  onClick={() => toggleFreeze(activeCard.id)}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border text-sm transition-colors ${
                    activeCard.frozen
                      ? 'bg-blue-500/10 border-blue-500/30 text-blue-400 hover:bg-blue-500/20'
                      : 'bg-surface-2 border-border text-fg hover:bg-surface-elevated'
                  }`}
                >
                  {activeCard.frozen ? <Flame className="w-4 h-4" /> : <Snowflake className="w-4 h-4" />}
                  {activeCard.frozen ? "Unfreeze" : "Freeze"}
                </button>
              </div>
            </div>

            {/* Card details */}
            <div className="space-y-6">
              {/* Card Management */}
              <div className="glass-panel rounded-2xl p-6 border border-border space-y-4">
                <div className="text-xs text-muted uppercase tracking-wider font-bold">Card Management</div>
                <div>
                  <label className="text-xs font-medium text-muted mb-1.5 block uppercase tracking-wider">
                    Card Nickname
                  </label>
                  <input
                    type="text"
                    value={cardNickname}
                    onChange={e => setCardNickname(e.target.value)}
                    placeholder="e.g. Daily spend card, Travel card, Backup"
                    className="w-full bg-black/20 border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted mb-1.5 block uppercase tracking-wider">
                    Reason for Status Change (optional)
                  </label>
                  <input
                    type="text"
                    value={freezeReason}
                    onChange={e => setFreezeReason(e.target.value)}
                    placeholder="e.g. Lost card, travelling abroad, security concern"
                    className="w-full bg-black/20 border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                  />
                </div>
              </div>

              {/* Spending limit */}
              <div className="glass-panel rounded-2xl p-6 border border-border">
                <div className="flex justify-between items-center mb-4">
                  <span className="text-xs text-muted uppercase tracking-wider font-bold">Spending Limit</span>
                  <span className="text-xs font-mono text-fg">₹{activeCard.spent.toLocaleString()} / ₹{activeCard.limit.toLocaleString()}</span>
                </div>
                <div className="h-2.5 w-full bg-black/40 rounded-full overflow-hidden border border-border">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      spentPct >= 90 ? 'bg-red-500' : spentPct >= 60 ? 'bg-amber-500' : 'bg-accent-primary'
                    }`}
                    style={{ width: `${spentPct}%` }}
                  />
                </div>
                <div className="mt-2 text-right text-[10px] font-mono text-muted">{spentPct}% used</div>
              </div>

              {/* Security status */}
              <div className="glass-panel rounded-2xl p-6 border border-border space-y-4">
                <div className="text-xs text-muted uppercase tracking-wider font-bold">Security Controls</div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-fg">
                      <ShieldCheck className="w-4 h-4 text-accent-success" />
                      Behavioral Monitoring
                    </div>
                    <span className="text-[10px] text-accent-success font-bold px-2 py-0.5 bg-accent-success/10 rounded-full border border-accent-success/20">ACTIVE</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-fg">
                      <Lock className="w-4 h-4 text-accent-primary" />
                      Online Transactions
                    </div>
                    <span className="text-[10px] text-accent-primary font-bold px-2 py-0.5 bg-accent-primary/10 rounded-full border border-accent-primary/20">ENABLED</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-fg">
                      {activeCard.frozen
                        ? <Snowflake className="w-4 h-4 text-blue-400" />
                        : <Unlock className="w-4 h-4 text-muted" />
                      }
                      Card Status
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                      activeCard.frozen
                        ? 'text-blue-400 bg-blue-500/10 border-blue-500/20'
                        : 'text-accent-success bg-accent-success/10 border-accent-success/20'
                    }`}>
                      {activeCard.frozen ? "FROZEN" : "ACTIVE"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Alerts */}
              {activeCard.frozen && (
                <div className="flex items-start gap-3 bg-blue-500/5 border border-blue-500/20 rounded-xl p-4">
                  <AlertTriangle className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-sm font-medium text-blue-400">Card is frozen</div>
                    <p className="text-xs text-muted mt-1">All transactions on this card are temporarily blocked. Tap "Unfreeze" to re-enable.</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
        )}
      </div>

      {/* Step-up authentication modal for CVV reveal */}
      {showPasswordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-surface border border-border rounded-2xl p-6 w-full max-w-sm space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                <KeyRound className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-fg">Step-up Authentication</h3>
                <p className="text-[10px] text-muted">Re-enter your password to reveal card details</p>
              </div>
            </div>
            <input
              type="password"
              value={stepUpPassword}
              onChange={e => setStepUpPassword(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleStepUpSubmit()}
              placeholder="Enter your password"
              autoFocus
              className="w-full bg-black/20 border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
            />
            <div className="flex gap-3">
              <button
                onClick={() => { setShowPasswordModal(false); setStepUpPassword(""); }}
                className="flex-1 px-4 py-2.5 rounded-xl bg-surface-2 border border-border text-sm text-muted hover:text-fg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleStepUpSubmit}
                disabled={verifying || !stepUpPassword}
                className="flex-1 px-4 py-2.5 rounded-xl bg-accent-primary text-white text-sm font-medium hover:bg-blue-600 transition-colors disabled:opacity-40"
              >
                {verifying ? "Verifying..." : "Confirm"}
              </button>
            </div>
            <p className="text-[9px] text-muted text-center font-mono">
              CVV will auto-hide after 30 seconds for security
            </p>
          </div>
        </div>
      )}
    </>
  );
}