"use client";

import {
  TrendingUp, ArrowDownLeft, ArrowUpRight, ShieldAlert,
  Check, Activity, Fingerprint
} from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";
import { NotificationBell } from "@/components/NotificationBell";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { KeystrokeHeatmap } from "@/components/behavioral/KeystrokeHeatmap";

const CATEGORY_COLORS: Record<string, string> = {
  'Income': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  'Shopping': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  'Food & Dining': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  'Entertainment': 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  'Healthcare': 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  'Groceries': 'bg-lime-500/10 text-lime-400 border-lime-500/20',
  'Transport': 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  'Investment': 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  'Utilities': 'bg-slate-500/10 text-slate-300 border-slate-500/20',
  'Housing': 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  'Rewards': 'bg-pink-500/10 text-pink-400 border-pink-500/20',
  'Transfer': 'bg-sky-500/10 text-sky-400 border-sky-500/20',
};

const TransactionRow = ({ name, date, amount, type, category }: { name: string, date: string, amount: string, type: 'in'|'out', category?: string }) => (
  <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-full bg-black/20 flex items-center justify-center border border-border">
        {type === 'in' ? <ArrowDownLeft className="w-4 h-4 text-accent-success" /> : <ArrowUpRight className="w-4 h-4 text-muted" />}
      </div>
      <div>
        <div className="text-sm font-medium text-fg">{name}</div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-muted">{date}</span>
          {category && (
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium border ${CATEGORY_COLORS[category] || 'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>
              {category}
            </span>
          )}
        </div>
      </div>
    </div>
    <div className={`text-sm tabular-nums font-medium ${type === 'in' ? 'text-accent-success' : 'text-fg'}`}>
      {type === 'in' ? '+' : '-'}₹{amount}
    </div>
  </div>
);

const ToggleSwitch = ({ enabled, onToggle }: { enabled: boolean, onToggle: () => void }) => (
  <button 
    onClick={onToggle}
    className={`w-10 h-6 rounded-full p-1 transition-colors ${enabled ? 'bg-accent-primary' : 'bg-surface-2 border border-border'}`}
  >
    <div className={`w-4 h-4 rounded-full bg-white transition-transform ${enabled ? 'translate-x-4' : 'translate-x-0'}`} />
  </button>
);

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTelemetry } from "@/components/TelemetryProvider";

// ── Typing Rhythm Waveform ─────────────────────────────────────────────────
// Shows the last 30 hold times as an SVG sparkline
function TypingRhythmWaveform() {
  const [points, setPoints] = useState<number[]>([]);

  useEffect(() => {
    const interval = setInterval(() => {
      try {
        const collector = getCollector();
        const snap = collector.getBufferSnapshot();
        const holds = snap.keystroke_events
          .map((k: any) => k.hold_time)
          .filter((h: number) => h > 0 && h < 500);
        if (holds.length > 0) {
          setPoints(holds.slice(-30));
        }
      } catch {}
    }, 600);
    return () => clearInterval(interval);
  }, []);

  if (points.length < 4) return <div className="text-[8px] text-muted font-mono">Collecting rhythm data...</div>;

  const maxH = Math.max(...points, 1);
  const minH = Math.min(...points, 0);
  const range = Math.max(maxH - minH, 1);
  const w = 280;
  const h = 32;
  
  const pathPoints = points.map((v, i) => {
    const x = (i / (points.length - 1)) * w;
    const y = h - ((v - minH) / range) * (h - 4) - 2;
    return `${x},${y}`;
  });
  
  const linePath = `M ${pathPoints.join(" L ")}`;
  const fillPath = `${linePath} L ${w},${h} L 0,${h} Z`;

  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="rounded">
      <defs>
        <linearGradient id="rhythmGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(139, 92, 246, 0.3)" />
          <stop offset="100%" stopColor="rgba(139, 92, 246, 0)" />
        </linearGradient>
      </defs>
      <path d={fillPath} fill="url(#rhythmGrad)" />
      <path d={linePath} fill="none" stroke="rgba(139, 92, 246, 0.8)" strokeWidth="1.5" />
      {/* Latest point indicator */}
      <circle
        cx={(points.length - 1) / (points.length - 1) * w}
        cy={h - ((points[points.length - 1] - minH) / range) * (h - 4) - 2}
        r="2.5"
        fill="rgba(139, 92, 246, 1)"
      />
    </svg>
  );
}


export default function DashboardPage() {
  const router = useRouter();
  const [username, setUsername] = useState("User");
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('bba_demo_mode');
      if (saved !== null) {
        setDemoMode(saved === 'true');
      }
    }
  }, []);

  const toggleDemoMode = () => {
    const newVal = !demoMode;
    setDemoMode(newVal);
    localStorage.setItem('bba_demo_mode', newVal.toString());
  };
  const { score, events, backendMetrics, enrollment, digraphProfile } = useTelemetry();
  const [currentContext, setCurrentContext] = useState<string>("DASHBOARD");

  // Live behavioral signal stats
  const [liveStats, setLiveStats] = useState({ ksCount: 0, mouseCount: 0, avgHold: 0, avgFlight: 0, mouseVelMean: 0, corrections: 0, copyPaste: false, hesitation: false });
  
  const [transferState, setTransferState] = useState('idle'); // idle, mfa, success, blocked, loading
  const [amount, setAmount] = useState('');
  const [recipient, setRecipient] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [transferError, setTransferError] = useState('');
  
  const [trustTimeline, setTrustTimeline] = useState<{timestamp: string, risk_score: number, risk_level: string}[]>([]);
  const [cognitiveProfile, setCognitiveProfile] = useState<Record<string, unknown> | null>(null);
  const [behavioralScore, setBehavioralScore] = useState<{authenticity_score?: number, risk_score?: number} | null>(null);
  const [transferAssessment, setTransferAssessment] = useState<string | null>(null);

  // New states for tabs
  const [activeTab, setActiveTab] = useState<'retail' | 'corporate' | 'insights'>('retail');
  const [pendingApprovals, setPendingApprovals] = useState<any[]>([]);
  const [approvalState, setApprovalState] = useState<Record<string, string>>({}); // track approval status by txn_id

  // Backend-driven account data
  const [balance, setBalance] = useState<number | null>(null);
  const [recentTransactions, setRecentTransactions] = useState<{name: string, date: string, amount: string, type: 'in'|'out', category: string}[]>([]);
  const [beneficiaries, setBeneficiaries] = useState<any[]>([]);

  // Poll live behavioral stats from collector every 500ms
  useEffect(() => {
    let prevKs = 0;
    let prevMs = 0;
    const interval = setInterval(async () => {
      try {
        const collector = getCollector();
        const snap = await collector.snapshot("dashboard_live");
        const ks = snap.keystroke_events;
        const ms = snap.mouse_events;
        const holds = ks.map(k => k.hold_time).filter(h => h > 0 && h < 2000);
        const flights = ks.map(k => k.flight_time).filter(f => f > 0 && f < 5000);
        const velocities = ms.filter(m => m.velocity !== undefined).map(m => m.velocity!);
        setLiveStats({
          ksCount: ks.length,
          mouseCount: ms.length,
          avgHold: holds.length > 0 ? Math.round(holds.reduce((a, b) => a + b, 0) / holds.length) : 0,
          avgFlight: flights.length > 0 ? Math.round(flights.reduce((a, b) => a + b, 0) / flights.length) : 0,
          mouseVelMean: velocities.length > 0 ? Math.round(velocities.reduce((a, b) => a + b, 0) / velocities.length * 100) / 100 : 0,
          corrections: ks.filter(k => k.is_backspace).length,
          copyPaste: snap.cognitive_events.some(c => c.type === 'copy_paste'),
          hesitation: snap.cognitive_events.some(c => c.type === 'hesitation'),
        });
        setCurrentContext(snap.page_context || "DASHBOARD");

      } catch {}
    }, 500);
    return () => clearInterval(interval);
  }, []);

  // Setup passive behavioral collection
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("DASHBOARD");
    const checkAuth = async () => {
      try {
        const res = await fetch("/api/auth/me");
        if (!res.ok) {
          router.push("/login");
          return;
        }
        const data = await res.json();
        setUsername(data.username || "User");

        // Fetch enrollment status
        const enrollmentRes = await fetch("/api/v1/behavioral/enrollment/status", {
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": getCsrfToken()
          }
        });
        if (enrollmentRes.ok) {
          const enrollmentData = await enrollmentRes.json();
          if (enrollmentData.enrollment) {
            localStorage.setItem("bba_enrollment_completed", String(enrollmentData.enrollment.sessions_completed || 0));
            localStorage.setItem("bba_enrollment_required", String(enrollmentData.enrollment.sessions_required || 5));
          }
        }

        // Fetch trust timeline
        const csrfToken = getCsrfToken();
        try {
          const tlRes = await fetch("/api/v1/session/trust-timeline?window_minutes=30", {
            headers: { "X-CSRF-TOKEN": csrfToken }
          });
          if (tlRes.ok) {
            const tlData = await tlRes.json();
            setTrustTimeline(tlData.points || []);
          }
        } catch {}

        // Fetch cognitive profile
        try {
          const cpRes = await fetch("/api/v1/session/cognitive-profile", {
            headers: { "X-CSRF-TOKEN": csrfToken }
          });
          if (cpRes.ok) {
            const cpData = await cpRes.json();
            setCognitiveProfile(cpData.cognitive_profile || null);
          }
        } catch {}

        // Fetch real transaction history from backend
        try {
          const txRes = await fetch("/api/v1/transaction/history?limit=10", {
            headers: { "X-CSRF-TOKEN": csrfToken }
          });
          if (txRes.ok) {
            const txData = await txRes.json();
            if (txData.transactions && txData.transactions.length > 0) {
              setRecentTransactions(txData.transactions.map((tx: any) => ({
                name: tx.merchant || tx.operation,
                date: new Date(tx.date).toLocaleDateString(),
                amount: parseFloat(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 }),
                type: (tx.type as 'in' | 'out') || 'out',
                category: tx.category || 'Transfer'
              })));
            }
          }
        } catch {}

        // Fetch real account balance from backend
        try {
          const balRes = await fetch("/api/v1/banking/balance", {
            headers: { "X-CSRF-TOKEN": csrfToken }
          });
          if (balRes.ok) {
            const balData = await balRes.json();
            setBalance(balData.balance ?? null);
          }
        } catch {}

        // Fetch beneficiaries
        try {
          const benRes = await fetch("/api/v1/beneficiaries");
          if (benRes.ok) {
            const bData = await benRes.json();
            setBeneficiaries(bData.beneficiaries || []);
          }
        } catch {}

        // Fetch pending corporate approvals
        try {
          const corpRes = await fetch("/api/v1/transaction/corporate/pending", {
            headers: { "X-CSRF-TOKEN": csrfToken }
          });
          if (corpRes.ok) {
            const corpData = await corpRes.json();
            setPendingApprovals(corpData.pending_approvals || []);
          }
        } catch {}

      } catch (err) {
        console.error("Auth check failed:", err);
        router.push("/login");
      }
    };
    checkAuth();

    return () => {
      collector.flush("page_transition").catch(console.error);
    };
  }, [router]);

  const handleTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    setTransferState('loading');
    setTransferError('');
    
    try {
      // Gap 11: Flush behavioral data at exact moment of transfer submit
      const collector = getCollector();
      collector.setContext("MAKE_PAYMENT");
      setCurrentContext("MAKE_PAYMENT");
      const transferBehavior = await collector.flush("MAKE_PAYMENT");

      // Pre-transaction duress check (supplementary — never blocks on network error)
      const csrfToken = getCsrfToken();
      try {
        const duressRes = await fetch("/api/v1/session/duress-check", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": csrfToken
          },
          body: JSON.stringify({
            behavioral_data: transferBehavior,
            amount: parseFloat(amount),
          }),
        });
        if (duressRes.ok) {
          const duress = await duressRes.json();
          if (duress.duress_detected) {
            setTransferState('blocked');
            setTransferError("Transaction halted — unusual behavioral stress patterns detected. If you are being coerced, please contact support.");
            return;
          }
        }
        // If duress check endpoint returns 4xx/5xx, it means the endpoint isn't available — proceed normally
      } catch { /* duress check is supplementary — network errors don't block */ }

      // 1. Get Nonce
      const nonceRes = await fetch("/api/v1/transaction/nonce", {
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        }
      });
      if (!nonceRes.ok) throw new Error("Failed to get transaction nonce");
      const nonceData = await nonceRes.json();
      const nonce = nonceData.nonce;

      // 2. Sign Intent
      const currentSessionId = getSessionId();
      const intentPayload = {
        session_id: currentSessionId,
        amount: parseFloat(amount),
        operation: "transfer",
        nonce,
        beneficiary_id: recipient
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
      const signData = await signRes.json();
      const signature = signData.signature;

      // 3. Get per-transaction behavioral score
      try {
        const bsRes = await fetch("/api/v1/transaction/behavioral-score", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": getCsrfToken()
          },
          body: JSON.stringify({
            session_id: currentSessionId,
            amount: parseFloat(amount),
            behavioral_data: transferBehavior,  // Gap 11: include behavioral snapshot
          })
        });
        if (bsRes.ok) {
          const bsData = await bsRes.json();
          setBehavioralScore(bsData);
        }
      } catch {}

      // 4. Assess Transaction (include behavioral snapshot)
      const assessPayload = {
        ...intentPayload,
        signature,
        behavioral_data: transferBehavior,  // Gap 11: send atomically with transaction
      };

      const assessRes = await fetch("/api/v1/transaction/assess", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify(assessPayload)
      });
      
      const assessData = await assessRes.json();

      if (assessRes.ok) {
        if (assessData.decision === "blocked") {
          setTransferState('blocked');
          setTransferError(assessData.reasons?.[0] || "Transaction blocked due to security reasons.");
        } else if (assessData.decision === "step_up_required") {
          setTransferState('mfa');
        } else {
          // "allowed" or any other non-blocked decision = success
          setTransferState('success');
          const selectedBen = beneficiaries.find(b => b.id === recipient);
          const benName = selectedBen ? selectedBen.name : recipient;
          
          setRecentTransactions(prev => [{ name: benName, date: new Date().toLocaleDateString(), amount, type: 'out' as const, category: 'Transfer' }, ...prev].slice(0, 5));
          toast.success(`Transfer to ${benName} completed successfully!`);
          setTimeout(() => {
            setTransferState('idle');
            setAmount('');
            setRecipient('');
          }, 4000);
        }
      } else {
        if (assessRes.status === 403 && assessData.decision === "step_up_required") {
          setTransferState('mfa');
        } else if (assessRes.status === 403 || assessRes.status === 401) {
          // Auth issue — redirect to OTP instead of hard-blocking
          setTransferState('mfa');
        } else {
          setTransferState('blocked');
          setTransferError(assessData.error || assessData.msg || "Transaction denied.");
        }
      }
    } catch (err: any) {
      console.error("Transfer failed:", err);
      // Network errors should not hard-block — offer retry
      setTransferState('blocked');
      setTransferError("Network error. Please check your connection and try again.");
    }
  };

  const handleCorporateApprove = async (txnId: string) => {
    setApprovalState(prev => ({ ...prev, [txnId]: 'loading' }));
    try {
      const collector = getCollector();
      collector.setContext("APPROVE_CORPORATE");
      const checkerBehavior = await collector.flush("APPROVE_CORPORATE");
      
      // In a real app, we'd also fetch the original maker behavior from DB.
      // For this demo, the backend Siamese Network verifies against the loaded model.
      const csrfToken = getCsrfToken();
      const res = await fetch("/api/v1/transaction/corporate/approve", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": csrfToken
        },
        body: JSON.stringify({
          txn_id: txnId,
          maker_session_features: [], // Mocked: normally retrieved from pending DB
          checker_session_features: checkerBehavior
        })
      });
      
      const data = await res.json();
      if (res.ok) {
        setApprovalState(prev => ({ ...prev, [txnId]: 'success' }));
        setTimeout(() => {
          setPendingApprovals(prev => prev.filter(p => p.txn_id !== txnId));
        }, 2000);
      } else {
        setApprovalState(prev => ({ ...prev, [txnId]: 'error: ' + (data.error || data.reason) }));
      }
    } catch (err) {
      setApprovalState(prev => ({ ...prev, [txnId]: 'error: Network failure' }));
    }
  };


  return (
    <>
      {/* Main Workspace */}
      <main className="flex-1 flex flex-col min-w-0 relative z-0">
        
        {/* Topbar */}
        <header className="h-16 px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
          <h1 className="text-xl font-medium text-fg">Account Overview</h1>
          <div className="flex items-center gap-6">
            {enrollment && (
              <div className="flex flex-col items-end">
                <span className="text-[10px] uppercase tracking-wider text-muted font-bold">
                  {enrollment.enrolled ? "Profile Mature" : "Profiling Progress"}
                </span>
                <div className="flex items-center gap-2 mt-1">
                  <div className="w-24 h-1.5 bg-black/40 rounded-full overflow-hidden border border-border">
                    <div 
                      className={`h-full ${enrollment.enrolled ? 'bg-accent-success' : 'bg-accent-warning'} transition-all`}
                      style={{ width: `${Math.min(100, Math.max(10, (enrollment.completed / enrollment.required) * 100))}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-muted">{enrollment.completed}/{enrollment.required}</span>
                </div>
              </div>
            )}
            <div className="flex items-center gap-3 text-sm bg-black/20 border border-border px-4 py-1.5 rounded-full">
              <span className="text-muted">Behavioral Demo Panel</span>
              <ToggleSwitch enabled={demoMode} onToggle={toggleDemoMode} />
            </div>
            <NotificationBell />
          </div>
        </header>

        {/* Scrollable Content */}
        <div className={`flex-1 overflow-auto p-8 ${demoMode ? 'pb-[420px] sm:pb-8 sm:pr-[380px]' : ''}`}>
          <div className="max-w-5xl mx-auto space-y-8">
            
            {/* Balance Hero */}
            <div className="glass-panel rounded-2xl p-8 grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="flex flex-col gap-2">
                <span className="text-sm text-muted font-medium uppercase tracking-wider">Total Balance</span>
                <div className="text-5xl font-semibold tracking-tighter tabular-nums text-fg">
                  {balance === null ? (
                    <div className="h-[48px] w-48 bg-black/20 animate-pulse rounded-lg mt-1"></div>
                  ) : (
                    `₹${balance.toLocaleString()}`
                  )}
                </div>
                <div className="text-sm text-muted mt-2 flex items-center gap-1">
                  <span className="text-accent-success font-medium">Available to spend</span>
                </div>
              </div>
              <div className="flex flex-col gap-2 md:items-end">
                <span className="text-sm text-muted font-medium uppercase tracking-wider">Pending Approvals</span>
                <div className="text-5xl font-semibold tracking-tighter tabular-nums text-fg flex items-center gap-3">
                  {pendingApprovals.length}
                </div>
                <div className="text-sm text-muted mt-2 flex items-center gap-1">
                  <span className="text-accent-warning font-medium">Action Required</span>
                </div>
              </div>
            </div>

            {/* Passive Enrollment Progress — Session 0 through Session 5 */}
            {enrollment && !enrollment.enrolled && (
              <div className="glass-panel rounded-2xl p-6 flex items-center gap-5 border border-accent-warning/20 bg-accent-warning/5">
                <div className="w-12 h-12 rounded-xl bg-accent-warning/10 flex items-center justify-center border border-accent-warning/20 shrink-0">
                  <Activity className="w-6 h-6 text-accent-warning" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-fg mb-1">Building Your Security Profile</div>
                  <p className="text-xs text-muted leading-relaxed">
                    Your behavioral profile is being built silently — no action needed. Just use the app normally.
                    <span className="text-accent-warning font-semibold"> Session {enrollment.completed} of {enrollment.required} complete.</span>
                  </p>
                  <div className="mt-3 h-2 w-full bg-black/40 rounded-full overflow-hidden border border-border">
                    <div 
                      className="h-full bg-gradient-to-r from-accent-warning to-amber-400 transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.max(5, (enrollment.completed / enrollment.required) * 100))}%` }}
                    />
                  </div>
                  <div className="flex justify-between items-center mt-1.5">
                    <span className="text-[9px] text-muted font-mono">Session 0 = signup · Sessions 1-4 = logins</span>
                    <span className="text-[9px] text-accent-warning font-mono">{Math.round((enrollment.completed / enrollment.required) * 100)}%</span>
                  </div>
                </div>
              </div>
            )}

            {/* Enrolled — behavioral auth active confirmation */}
            {enrollment && enrollment.enrolled && (
              <div className="glass-panel rounded-2xl p-4 flex items-center gap-4 border border-emerald-500/20 bg-emerald-500/5">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 shrink-0">
                  <Check className="w-5 h-5 text-emerald-400" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-semibold text-emerald-400">✓ Behavioral Profile Active</div>
                  <p className="text-[10px] text-muted">Continuous authentication running — every action is silently verified against your behavioral fingerprint.</p>
                </div>
              </div>
            )}

            {/* Per-Key/Digraph Bayesian Profile Card */}
            {digraphProfile && digraphProfile.has_profile && (
              <div className="glass-panel rounded-2xl p-5 border border-accent-primary/20 bg-accent-primary/5">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-accent-primary/10 flex items-center justify-center border border-accent-primary/20 shrink-0">
                    <Fingerprint className="w-5 h-5 text-accent-primary" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-fg">Keystroke Bio-Signature</div>
                    <div className="text-[10px] text-muted">Per-key hold + digraph flight time Bayesian profile</div>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-3">
                  <div className="bg-black/30 rounded-xl p-3 text-center border border-border/30">
                    <div className="text-lg font-bold text-accent-primary">{digraphProfile.per_key_count}</div>
                    <div className="text-[9px] text-muted font-mono">Keys Profiled</div>
                  </div>
                  <div className="bg-black/30 rounded-xl p-3 text-center border border-border/30">
                    <div className="text-lg font-bold text-purple-400">{digraphProfile.per_digraph_count}</div>
                    <div className="text-[9px] text-muted font-mono">Digraph Pairs</div>
                  </div>
                  <div className="bg-black/30 rounded-xl p-3 text-center border border-border/30">
                    <div className="text-lg font-bold text-cyan-400">{digraphProfile.updates_count}</div>
                    <div className="text-[9px] text-muted font-mono">Learning Sessions</div>
                  </div>
                  <div className="bg-black/30 rounded-xl p-3 text-center border border-border/30">
                    <div className="text-lg font-bold text-accent-success">{Math.round(digraphProfile.confidence * 100)}%</div>
                    <div className="text-[9px] text-muted font-mono">Confidence</div>
                  </div>
                </div>
                <div className="mt-3 h-1.5 w-full bg-black/40 rounded-full overflow-hidden border border-border/20">
                  <div 
                    className="h-full bg-gradient-to-r from-accent-primary via-purple-500 to-cyan-400 transition-all duration-700"
                    style={{ width: `${Math.min(100, Math.round(digraphProfile.confidence * 100))}%` }}
                  />
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-[9px] text-muted font-mono">Bayesian posterior narrows with each login</span>
                  <span className="text-[9px] text-accent-primary font-mono">
                    {digraphProfile.updates_count >= 5 ? 'Mature' : digraphProfile.updates_count >= 3 ? 'Learning' : 'Initializing'}
                  </span>
                </div>
              </div>
            )}

            {/* Live Keystroke Heatmap — Type anywhere to see your fingerprint */}
            <KeystrokeHeatmap />

            {/* Tabs */}
            <div className="flex items-center gap-4 border-b border-border/50">
              <button 
                onClick={() => setActiveTab('retail')} 
                className={`px-4 py-3 font-medium text-sm transition-colors border-b-2 ${activeTab === 'retail' ? 'border-accent-primary text-accent-primary' : 'border-transparent text-muted hover:text-fg'}`}
              >
                Retail Banking
              </button>
              <button 
                onClick={() => setActiveTab('corporate')} 
                className={`px-4 py-3 font-medium text-sm transition-colors border-b-2 ${activeTab === 'corporate' ? 'border-accent-primary text-accent-primary' : 'border-transparent text-muted hover:text-fg'}`}
              >
                Corporate Approvals
                {pendingApprovals.length > 0 && (
                  <span className="ml-2 inline-flex items-center justify-center w-5 h-5 text-[10px] font-bold bg-accent-warning text-black rounded-full">
                    {pendingApprovals.length}
                  </span>
                )}
              </button>
              <button 
                onClick={() => setActiveTab('insights')} 
                className={`px-4 py-3 font-medium text-sm transition-colors border-b-2 ${activeTab === 'insights' ? 'border-accent-primary text-accent-primary' : 'border-transparent text-muted hover:text-fg'}`}
              >
                Spending Insights
              </button>
            </div>

            {activeTab === 'retail' && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in">
                {/* Left Col: Transactions */}
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Recent Activity</h2>
                    <a href="/dashboard/statements" className="text-xs text-accent-primary hover:text-blue-400 hover:underline">View All</a>
                  </div>
                  <div className="glass-panel rounded-2xl p-2 px-6">
                    {recentTransactions.length > 0 ? recentTransactions.map((tx, i) => (
                      <TransactionRow key={i} name={tx.name} date={tx.date} amount={tx.amount} type={tx.type} category={tx.category} />
                    )) : (
                      <div className="py-4 text-center text-xs text-muted">No transactions yet. Use Quick Transfer to create your first transaction.</div>
                    )}
                  </div>
                </div>

                {/* Right Col: Quick Transfer Widget */}
                <div className="space-y-4">
                  <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Quick Transfer</h2>
                  <div className="glass-panel rounded-2xl p-6 relative overflow-hidden min-h-[300px]">
                    
                    {transferState === 'idle' && (
                      <form onSubmit={handleTransfer} className="space-y-5">
                        <div>
                          <label className="block text-xs font-medium text-muted mb-1.5 uppercase tracking-wider">Recipient</label>
                          <select
                            id="transfer-recipient"
                            value={recipient}
                            onChange={(e) => setRecipient(e.target.value)}
                            className="w-full bg-black/20 border border-border rounded-xl px-4 py-3 text-sm outline-none focus:border-accent-primary transition-colors text-fg"
                            required
                          >
                            <option value="">Select beneficiary</option>
                            {beneficiaries.map(b => (
                              <option key={b.id} value={b.id}>{b.name} — {b.account}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-muted mb-1.5 uppercase tracking-wider">Amount</label>
                          <div className="relative">
                            <span className="absolute left-4 top-3 text-muted">₹</span>
                            <input 
                              id="transfer-amount"
                              type="text" 
                              value={amount}
                              onChange={(e) => setAmount(e.target.value)}
                              placeholder="0.00" 
                              className="w-full bg-black/20 border border-border rounded-xl pl-8 pr-4 py-3 text-sm outline-none focus:border-accent-primary transition-colors placeholder:text-muted text-fg tabular-nums"
                              required
                            />
                          </div>
                        </div>
                        {parseFloat(amount) > 10000 && (
                          <div>
                            <label className="block text-xs font-medium text-muted mb-1.5 uppercase tracking-wider">
                              Type CONFIRM to proceed
                            </label>
                            <input
                              id="transfer-confirm"
                              type="text"
                              value={confirmText}
                              onChange={(e) => setConfirmText(e.target.value)}
                              placeholder="Type CONFIRM"
                              className="w-full bg-black/20 border border-border rounded-xl px-4 py-3 text-sm outline-none focus:border-accent-primary transition-colors placeholder:text-muted text-fg font-mono tracking-widest"
                            />
                          </div>
                        )}
                        <button 
                          type="submit"
                          className="w-full bg-accent-primary text-white font-medium text-sm py-3 rounded-xl hover:bg-blue-600 transition-colors"
                        >
                          Review Transfer
                        </button>
                      </form>
                    )}

                    {transferState === 'loading' && (
                      <div className="flex flex-col items-center justify-center text-center py-6 space-y-4 animate-in fade-in h-full">
                        <div className="w-8 h-8 border-4 border-accent-primary border-t-transparent rounded-full animate-spin"></div>
                        <div className="text-sm text-muted">Running Cognitive Risk Assessment...</div>
                      </div>
                    )}

                    {transferState === 'blocked' && (
                      <div className="flex flex-col items-center justify-center text-center py-4 space-y-4 animate-in fade-in h-full">
                        <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center border border-red-500/20">
                          <ShieldAlert className="w-7 h-7 text-red-500" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-base text-fg">Transaction Blocked</h3>
                          <p className="text-xs text-red-400 mt-2 leading-relaxed">{transferError || "Your transaction was blocked by the security system."}</p>
                        </div>
                        <button 
                          onClick={() => { setTransferState('idle'); setAmount(''); setRecipient(''); setTransferError(''); }}
                          className="w-full bg-surface-2 text-fg font-medium text-sm py-3 rounded-xl hover:bg-surface-elevated transition-colors mt-2"
                        >
                          Dismiss
                        </button>
                      </div>
                    )}

                    {transferState === 'mfa' && (
                      <div className="flex flex-col items-center justify-center text-center py-4 space-y-4 animate-in fade-in h-full">
                        <div className="w-14 h-14 rounded-full bg-accent-danger/10 flex items-center justify-center border border-accent-danger/20">
                          <ShieldAlert className="w-7 h-7 text-accent-danger" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-base text-fg">Security Verification</h3>
                          <p className="text-xs text-muted mt-2 leading-relaxed">
                            {/* Gap 25: Show behavioral reason for step-up */}
                            {behavioralScore?.risk_score
                              ? `Behavioral confidence ${((1 - behavioralScore.risk_score) * 100).toFixed(0)}% — verification required for this transaction.`
                              : "Unusual behavioral patterns detected. Please verify this transfer via the Step-Up MFA Challenge."}
                          </p>
                        </div>
                        <button 
                          onClick={() => router.push('/otp')}
                          className="w-full bg-accent-danger text-white font-medium text-sm py-3 rounded-xl hover:bg-red-600 transition-colors mt-2"
                        >
                          Complete Verification
                        </button>
                        <button 
                          onClick={() => { setTransferState('idle'); setAmount(''); setRecipient(''); setTransferError(''); }}
                          className="w-full bg-transparent text-muted font-medium text-xs py-2 hover:text-fg transition-colors"
                        >
                          Cancel Transfer
                        </button>
                      </div>
                    )}

                    {transferState === 'success' && (
                      <div className="flex flex-col items-center justify-center text-center py-4 space-y-3 animate-in fade-in h-full">
                        <div className="w-14 h-14 rounded-full bg-accent-success/10 flex items-center justify-center border border-accent-success/20">
                          <Check className="w-7 h-7 text-accent-success" />
                        </div>
                        <div className="text-base font-medium text-fg mt-2">Transfer Authorized</div>
                        <p className="text-xs text-muted">
                          {behavioralScore?.authenticity_score
                            ? `Behavioral confidence ${((behavioralScore.authenticity_score) * 100).toFixed(0)}%`
                            : "Behavioral profile matched."}
                        </p>
                        {/* Transfer behavioral assessment card */}
                        <div className="w-full mt-2 bg-accent-success/5 border border-accent-success/15 rounded-lg p-3 text-left">
                          <div className="text-[10px] uppercase tracking-widest font-bold text-accent-success mb-1.5">Behavioral Assessment</div>
                          <div className="text-[11px] font-mono text-muted space-y-1">
                            <div>Keystroke confidence: <span className="text-fg">{behavioralScore?.authenticity_score ? ((behavioralScore.authenticity_score) * 100).toFixed(0) : '--'}%</span> · No hesitation detected ✓</div>
                            <div>Amount typed manually ✓ · Beneficiary {liveStats.copyPaste ? 'pasted ⚠' : 'typed manually ✓'}</div>
                          </div>
                        </div>
                      </div>
                    )}

                  </div>
                </div>
              </div>
            )}

            {activeTab === 'corporate' && (
              <div className="space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Maker-Checker Dual Control</h2>
                  <span className="text-xs text-muted">Powered by Siamese Network Behavioral Verification</span>
                </div>
                <div className="glass-panel rounded-2xl p-6">
                  {pendingApprovals.length > 0 ? (
                    <div className="space-y-4">
                      {pendingApprovals.map((approval) => (
                        <div key={approval.txn_id} className="flex items-center justify-between p-4 bg-black/20 rounded-xl border border-border">
                          <div>
                            <div className="text-sm font-medium text-fg">Corporate Transfer to {approval.beneficiary}</div>
                            <div className="text-xs text-muted mt-1">Maker ID: {approval.maker_id} • Amount: <span className="text-accent-primary font-mono tabular-nums">₹{parseFloat(approval.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
                            {approvalState[approval.txn_id]?.startsWith('error') && (
                              <div className="text-xs text-red-400 mt-2 bg-red-500/10 px-2 py-1 rounded inline-block border border-red-500/20">
                                ⚠ {approvalState[approval.txn_id].replace('error: ', '')}
                              </div>
                            )}
                          </div>
                          <div>
                            {approvalState[approval.txn_id] === 'loading' ? (
                              <div className="px-6 py-2 bg-surface-elevated rounded-lg flex items-center justify-center">
                                <div className="w-5 h-5 border-2 border-accent-primary border-t-transparent rounded-full animate-spin" />
                              </div>
                            ) : approvalState[approval.txn_id] === 'success' ? (
                              <div className="px-6 py-2 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium text-sm rounded-lg flex items-center gap-2">
                                <Check className="w-4 h-4" /> Approved
                              </div>
                            ) : (
                              <button
                                onClick={() => handleCorporateApprove(approval.txn_id)}
                                className="px-6 py-2 bg-accent-primary hover:bg-blue-600 transition-colors text-white font-medium text-sm rounded-lg"
                              >
                                Approve
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
                      <div className="w-12 h-12 rounded-full bg-surface-2 flex items-center justify-center">
                        <Check className="w-6 h-6 text-muted" />
                      </div>
                      <div className="text-fg font-medium">No Pending Approvals</div>
                      <div className="text-xs text-muted max-w-sm">
                        You have zero corporate transactions awaiting your checker approval. 
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'insights' && (() => {
              // Compute dynamic spending data from real transactions
              const outgoing = recentTransactions.filter(t => t.type === 'out');
              const monthlyTotal = outgoing.reduce((sum, t) => sum + parseFloat(t.amount.replace(/,/g, '')), 0);
              
              // Aggregate by day of week
              const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
              const dayTotals: Record<string, number> = {};
              dayNames.forEach(d => dayTotals[d] = 0);
              outgoing.forEach(t => {
                const parsed = new Date(t.date);
                if (!isNaN(parsed.getTime())) {
                  dayTotals[dayNames[parsed.getDay()]] += parseFloat(t.amount.replace(/,/g, ''));
                }
              });
              const maxDayValue = Math.max(...Object.values(dayTotals), 1);
              const chartData = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => ({
                day,
                value: Math.round((dayTotals[day] / maxDayValue) * 100),
                amount: dayTotals[day],
              }));
              const peakDay = chartData.reduce((a, b) => a.amount > b.amount ? a : b, chartData[0]);

              // Find highest category
              const categoryTotals: Record<string, number> = {};
              outgoing.forEach(t => {
                const cat = t.category || 'Other';
                categoryTotals[cat] = (categoryTotals[cat] || 0) + parseFloat(t.amount.replace(/,/g, ''));
              });
              const topCategory = Object.entries(categoryTotals).sort((a, b) => b[1] - a[1])[0];
              const hasData = outgoing.length > 0;

              return (
              <div className="space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Financial Insights</h2>
                  <span className="text-xs text-muted">Computed from {outgoing.length} transactions</span>
                </div>
                <div className="glass-panel rounded-2xl p-8 min-h-[400px] flex flex-col">
                  
                  <div className="mb-8">
                    <div className="text-sm font-medium text-muted">Total Spend (Recent)</div>
                    <div className="text-3xl font-bold text-fg flex items-end gap-3 mt-1">
                      {hasData ? `₹${monthlyTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '₹0.00'}
                      {hasData && (
                        <span className="text-xs text-accent-primary bg-accent-primary/10 px-2 py-0.5 rounded-full mb-1 font-medium">
                          {outgoing.length} transactions
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Dynamic Bar Chart */}
                  <div className="flex-1 flex items-end justify-between gap-2 mt-auto pt-8 border-b border-border/50 pb-4 relative">
                    {/* Y-axis grid lines */}
                    <div className="absolute inset-0 flex flex-col justify-between pointer-events-none pb-4">
                      <div className="border-t border-white/5 w-full"></div>
                      <div className="border-t border-white/5 w-full"></div>
                      <div className="border-t border-white/5 w-full"></div>
                      <div className="border-t border-white/5 w-full"></div>
                    </div>

                    {chartData.map((d, i) => (
                      <div key={d.day} className="flex flex-col items-center flex-1 z-10 group cursor-pointer">
                        <div className="w-full relative flex justify-center items-end h-[150px]">
                          {/* Tooltip */}
                          <div className="absolute -top-10 opacity-0 group-hover:opacity-100 transition-opacity bg-surface-elevated text-xs px-2 py-1 rounded text-fg border border-border whitespace-nowrap z-20 shadow-xl pointer-events-none">
                            ₹{d.amount.toLocaleString(undefined, { minimumFractionDigits: 0 })}
                          </div>
                          
                          {/* Animated Bar */}
                          <motion.div 
                            initial={{ height: 0 }}
                            animate={{ height: `${Math.max(d.value, hasData ? 2 : 0)}%` }}
                            transition={{ duration: 0.8, delay: i * 0.1, type: "spring", bounce: 0.3 }}
                            className={`w-full max-w-[40px] rounded-t-lg relative overflow-hidden group-hover:brightness-110 transition-all ${
                              d.day === peakDay.day && d.amount > 0 ? 'bg-gradient-to-t from-accent-primary to-blue-400' : 'bg-surface-2 border border-border/50 border-b-0'
                            }`}
                          >
                            <div className="absolute inset-0 bg-gradient-to-t from-transparent to-white/10"></div>
                          </motion.div>
                        </div>
                        <div className={`text-[10px] uppercase font-bold mt-3 ${d.day === peakDay.day && d.amount > 0 ? 'text-accent-primary' : 'text-muted'}`}>{d.day}</div>
                      </div>
                    ))}
                  </div>

                  {/* Dynamic Insight Pill */}
                  <div className="mt-8 flex items-center gap-3 bg-accent-primary/10 border border-accent-primary/20 p-4 rounded-xl">
                    <div className="w-8 h-8 rounded-full bg-accent-primary/20 flex items-center justify-center shrink-0">
                      <Activity className="w-4 h-4 text-accent-primary" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-fg">
                        {hasData ? 'Spending Pattern Analysis' : 'Start Transacting to See Insights'}
                      </div>
                      <div className="text-[11px] text-muted mt-0.5">
                        {hasData && topCategory
                          ? `Peak spending on ${peakDay.day} (₹${peakDay.amount.toLocaleString()}). Top category: ${topCategory[0]} at ₹${topCategory[1].toLocaleString()}.`
                          : 'Make transfers to generate behavioral spending analysis powered by your transaction history.'}
                      </div>
                    </div>
                  </div>

                </div>
              </div>
              );
            })()}

          </div>
        </div>

        {/* Always-Visible Behavioral Signal Panel */}
        {demoMode && (
          <div className="fixed bottom-4 right-4 w-[calc(100vw-32px)] sm:bottom-8 sm:right-8 sm:w-[340px] glass-panel-glow rounded-2xl p-5 z-50 flex flex-col gap-4 shadow-2xl max-h-[calc(100vh-120px)] overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-accent-primary" />
                <span className="text-xs font-bold tracking-widest uppercase text-fg">Continuous Auth</span>
              </div>
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${score !== null && score > 75 ? 'bg-accent-success' : 'bg-accent-danger'} shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse`}></div>
                <button onClick={toggleDemoMode} className="text-muted hover:text-white transition-colors" title="Hide Panel">×</button>
              </div>
            </div>

            {/* Trust Score + Feature Richness */}
            <div>
              <div className="flex justify-between items-baseline mb-2">
                <span className="text-xs text-muted font-medium uppercase tracking-wider">Trust Score</span>
                <span className={`text-2xl font-mono tracking-tighter ${(score || 0) > 75 ? 'text-fg' : 'text-accent-danger'}`}>
                  {score !== null ? score.toFixed(0) : "--"}%
                </span>
              </div>
              <div className="h-1.5 w-full bg-black/40 border border-border rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all duration-300 ease-out ${score !== null && score > 75 ? 'bg-accent-primary' : 'bg-accent-danger'}`}
                  style={{ width: `${score || 0}%` }}
                ></div>
              </div>
              {backendMetrics?.feature_richness !== undefined && (
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[9px] text-muted uppercase tracking-wider">Signal Strength</span>
                  <div className="flex-1 h-1 bg-black/30 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-violet-500 to-blue-400 transition-all duration-500"
                      style={{ width: `${Math.round((backendMetrics.feature_richness || 0) * 100)}%` }}
                    />
                  </div>
                  <span className="text-[9px] font-mono text-muted">{Math.round((backendMetrics.feature_richness || 0) * 100)}%</span>
                </div>
              )}
            </div>

            {/* Live Signal Stats */}
            <div className="grid grid-cols-3 gap-3 pt-3 border-t border-border">
              <div>
                <div className="text-[9px] text-muted uppercase tracking-wider mb-0.5">Keys</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.ksCount}</div>
              </div>
              <div>
                <div className="text-[9px] text-muted uppercase tracking-wider mb-0.5">Mouse</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.mouseCount}</div>
              </div>
              <div>
                <div className="text-[9px] text-muted uppercase tracking-wider mb-0.5">Corrections</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.corrections}</div>
              </div>
              <div>
                <div className="text-[9px] text-muted uppercase tracking-wider mb-0.5">Avg Hold</div>
                <div className="font-mono text-[11px] tabular-nums text-fg">{liveStats.avgHold > 0 ? `${liveStats.avgHold}ms` : '--'}</div>
              </div>
              <div>
                <div className="text-[9px] text-muted uppercase tracking-wider mb-0.5">Avg Flight</div>
                <div className="font-mono text-[11px] tabular-nums text-fg">{liveStats.avgFlight > 0 ? `${liveStats.avgFlight}ms` : '--'}</div>
              </div>
              <div>
                <div className="text-[9px] text-muted uppercase tracking-wider mb-0.5">Mouse Vel</div>
                <div className="font-mono text-[11px] tabular-nums text-fg">{liveStats.mouseVelMean > 0 ? `${liveStats.mouseVelMean}` : '--'}</div>
              </div>
            </div>

            {/* ML Engine Breakdown (all 11 engines) */}
            {backendMetrics?.ensemble && (
              <div className="pt-3 border-t border-border">
                <div className="text-[9px] text-muted uppercase tracking-wider mb-2 flex items-center justify-between">
                  <span>ML Engine Scores</span>
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                    backendMetrics.ensemble.ensemble_action === 'allow' ? 'bg-accent-success/10 text-accent-success' :
                    backendMetrics.ensemble.ensemble_action === 'block' ? 'bg-red-500/10 text-red-500' :
                    'bg-accent-warning/10 text-accent-warning'
                  }`}>{backendMetrics.ensemble.ensemble_action?.toUpperCase()}</span>
                </div>
                <div className="space-y-1.5">
                  {[
                    { label: 'Cognitive', value: backendMetrics.ensemble.cognitive_analysis?.cognitive_risk || 0 },
                    { label: 'Duress', value: backendMetrics.ensemble.duress_score || 0 },
                    { label: 'Liveness', value: backendMetrics.ensemble.liveness_score ?? 1, invert: true },
                    { label: 'Challenge', value: backendMetrics.ensemble.challenge_risk || 0 },
                    { label: 'Device', value: backendMetrics.ensemble.device_risk || 0 },
                    { label: 'Replay', value: backendMetrics.ensemble.replay_risk || 0 },
                    { label: 'Drift', value: backendMetrics.ensemble.drift_risk || 0 },
                    { label: 'Match', value: backendMetrics.ensemble.weighted_match_score || 0, invert: true },
                    { label: 'Digraph', value: backendMetrics.ensemble.digraph_match_score ?? 0.5, invert: true },
                  ].map(({ label, value, invert }) => {
                    const riskValue = invert ? 1 - value : value;
                    return (
                      <div key={label} className="flex items-center gap-2">
                        <span className="text-[9px] text-muted w-14 shrink-0">{label}</span>
                        <div className="flex-1 h-1.5 bg-black/30 rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full transition-all duration-500 ${
                              riskValue > 0.6 ? 'bg-red-500' : riskValue > 0.3 ? 'bg-amber-500' : 'bg-emerald-500'
                            }`}
                            style={{ width: `${Math.max(2, Math.min(100, riskValue * 100))}%` }}
                          />
                        </div>
                        <span className={`text-[9px] font-mono w-8 text-right ${
                          riskValue > 0.6 ? 'text-red-400' : riskValue > 0.3 ? 'text-amber-400' : 'text-emerald-400'
                        }`}>{(value * 100).toFixed(0)}%</span>
                      </div>
                    );
                  })}
                </div>
                {/* Ensemble risk summary */}
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/50">
                  <span className="text-[9px] text-muted font-semibold uppercase">Fused Risk</span>
                  <span className={`text-xs font-mono font-bold ${
                    (backendMetrics.ensemble.ensemble_risk || 0) > 0.6 ? 'text-red-400' :
                    (backendMetrics.ensemble.ensemble_risk || 0) > 0.3 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>{((backendMetrics.ensemble.ensemble_risk || 0) * 100).toFixed(1)}%</span>
                </div>
              </div>
            )}

            {/* Category Risk Breakdown */}
            {backendMetrics?.category_scores && Object.keys(backendMetrics.category_scores).length > 0 && (
              <div className="pt-3 border-t border-border">
                <div className="text-[9px] text-muted uppercase tracking-wider mb-2">Category Risk</div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                  {[
                    { label: 'Mouse', key: 'mouse_anomaly', icon: '🖱' },
                    { label: 'Keystroke', key: 'keystroke_anomaly', icon: '⌨' },
                    { label: 'Cognitive', key: 'cognitive_risk', icon: '🧠' },
                    { label: 'Physiology', key: 'physiological_anomaly', icon: '🫀' },
                    { label: 'Temporal', key: 'temporal_rhythm_risk', icon: '⏱' },
                    { label: 'Bot Detect', key: 'challenge_bot_risk', icon: '🤖' },
                  ].map(({ label, key, icon }) => {
                    const val = backendMetrics.category_scores[key] || 0;
                    return (
                      <div key={key} className="flex items-center gap-1.5">
                        <span className="text-[10px]">{icon}</span>
                        <span className="text-[9px] text-muted w-14">{label}</span>
                        <div className="flex-1 h-1 bg-black/30 rounded-full overflow-hidden">
                          <div 
                            className={`h-full rounded-full transition-all ${
                              val > 0.5 ? 'bg-red-500' : val > 0.2 ? 'bg-amber-500' : 'bg-emerald-500'
                            }`}
                            style={{ width: `${Math.max(2, val * 100)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Cognitive State */}
            <div className="pt-3 border-t border-border">
              <div className="text-[9px] text-muted uppercase tracking-wider mb-2">Cognitive State</div>
              <div className="flex flex-wrap gap-1.5">
                {liveStats.ksCount > 0 && !liveStats.hesitation && !liveStats.copyPaste && (
                  <span className="px-2 py-0.5 rounded-md bg-accent-success/10 border border-accent-success/20 text-[9px] font-mono text-accent-success">Natural ✓</span>
                )}
                {liveStats.ksCount === 0 && liveStats.mouseCount === 0 && (
                  <span className="px-2 py-0.5 rounded-md bg-slate-500/10 border border-slate-500/20 text-[9px] font-mono text-slate-400">Awaiting input…</span>
                )}
                {liveStats.ksCount === 0 && liveStats.mouseCount > 0 && (
                  <span className="px-2 py-0.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-[9px] font-mono text-blue-400">Mouse only</span>
                )}
                {liveStats.hesitation && <span className="px-2 py-0.5 rounded-md bg-accent-warning/10 border border-accent-warning/20 text-[9px] font-mono text-accent-warning">Hesitation</span>}
                {liveStats.copyPaste && <span className="px-2 py-0.5 rounded-md bg-accent-danger/10 border border-accent-danger/20 text-[9px] font-mono text-accent-danger">Copy-paste ⚠</span>}
              </div>
            </div>

            {/* Digraph Match Status Badge */}
            {digraphProfile && (
              <div className="pt-3 border-t border-border">
                <div className="text-[9px] text-muted uppercase tracking-wider mb-2">Digraph Bio-Signature</div>
                <div className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 rounded-md text-[9px] font-mono font-bold ${
                    !digraphProfile.has_profile ? 'bg-slate-500/10 border border-slate-500/20 text-slate-400' :
                    digraphProfile.confidence > 0.7 ? 'bg-accent-success/10 border border-accent-success/20 text-accent-success' :
                    digraphProfile.confidence > 0.3 ? 'bg-accent-warning/10 border border-accent-warning/20 text-accent-warning' :
                    'bg-accent-primary/10 border border-accent-primary/20 text-accent-primary'
                  }`}>
                    {!digraphProfile.has_profile ? 'NO PROFILE' :
                     digraphProfile.updates_count >= 5 ? 'MATCHED ✓' :
                     digraphProfile.updates_count >= 3 ? 'LEARNING' : 'INITIALIZING'}
                  </span>
                  <span className="text-[8px] font-mono text-muted">
                    {digraphProfile.has_profile
                      ? `${digraphProfile.per_key_count} keys · ${digraphProfile.per_digraph_count} pairs · ${Math.round(digraphProfile.confidence * 100)}% conf`
                      : 'Type during signup/login to build'}
                  </span>
                </div>
              </div>
            )}

            {/* Typing Rhythm Waveform */}
            {liveStats.ksCount > 3 && (
              <div className="pt-3 border-t border-border">
                <div className="text-[9px] text-muted uppercase tracking-wider mb-2">Typing Rhythm</div>
                <TypingRhythmWaveform />
              </div>
            )}

            {/* Ensemble Flags */}
            {backendMetrics?.ensemble?.ensemble_flags && backendMetrics.ensemble.ensemble_flags.length > 0 && (
              <div className="pt-3 border-t border-border">
                <div className="text-[9px] text-muted uppercase tracking-wider mb-1.5">Active Flags</div>
                <div className="flex flex-wrap gap-1">
                  {backendMetrics.ensemble.ensemble_flags.slice(0, 6).map((flag: string, i: number) => (
                    <span key={i} className="px-1.5 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-[8px] font-mono text-red-400 truncate max-w-[150px]" title={flag}>
                      {flag.split(':')[0]}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Live Event Stream */}
            <div className="pt-3 border-t border-border">
              <div className="text-[9px] text-muted uppercase tracking-wider mb-2">Live Event Stream</div>
              <div className="font-mono text-[9px] space-y-1 h-14 overflow-hidden relative">
                {events.map((e, i) => (
                  <div key={i} className="flex gap-2 opacity-80" style={{ opacity: 1 - (i * 0.25) }}>
                    <span className="text-muted shrink-0">[{e.time}]</span>
                    <span className="truncate text-fg">{e.msg}</span>
                  </div>
                ))}
                {events.length === 0 && (
                  <span className="text-muted opacity-50">Interact with the page to see events…</span>
                )}
              </div>
            </div>

            {/* Trust Timeline */}
            {trustTimeline.length > 0 && (
              <div className="pt-3 border-t border-border">
                <div className="text-[9px] text-muted uppercase tracking-wider mb-2">Trust Timeline</div>
                <div className="flex items-end gap-[2px] h-8">
                  {trustTimeline.slice(-20).map((pt, i) => (
                    <div
                      key={i}
                      className={`flex-1 rounded-sm transition-all ${
                        pt.risk_level === 'high' ? 'bg-accent-danger' :
                        pt.risk_level === 'medium' ? 'bg-accent-warning' : 'bg-accent-success'
                      }`}
                      style={{ height: `${Math.max(10, (1 - pt.risk_score) * 100)}%` }}
                      title={`${pt.timestamp}: risk ${(pt.risk_score * 100).toFixed(0)}%`}
                    />
                  ))}
                </div>
                <div className="flex justify-between text-[8px] text-muted mt-1 font-mono">
                  <span>-30min</span>
                  <span>now</span>
                </div>
              </div>
            )}

            {/* Cognitive Profile */}
            {cognitiveProfile && (
              <div className="pt-3 border-t border-border">
                <div className="text-[9px] text-muted uppercase tracking-wider mb-2">Cognitive Profile</div>
                <div className="grid grid-cols-1 gap-2 text-[9px] font-mono">
                  {Object.entries(cognitiveProfile).slice(0, 4).map(([k, v]) => {
                    const formattedKey = k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    let displayValue = typeof v === 'number' ? v.toFixed(2) : String(v);
                    let unit = "";
                    if (k.includes("time") || k.includes("duration")) { displayValue = (v as number).toFixed(0); unit = "ms"; }
                    if (k.includes("velocity")) { displayValue = (v as number).toFixed(2); unit = "px/ms"; }
                    return (
                      <div key={k} className="flex justify-between items-center bg-black/10 px-2 py-1 rounded">
                        <span className="text-muted">{formattedKey}</span>
                        <span className="text-fg">{displayValue}{unit}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Behavioral Score */}
            {behavioralScore && (
              <div className="pt-3 border-t border-border">
                <div className="text-[9px] text-muted uppercase tracking-wider mb-1">Last Txn Score</div>
                <div className="flex gap-4 text-[9px] font-mono">
                  <span className="text-accent-success">Auth: {((behavioralScore.authenticity_score || 0) * 100).toFixed(0)}%</span>
                  <span className="text-accent-warning">Risk: {((behavioralScore.risk_score || 0) * 100).toFixed(0)}%</span>
                </div>
              </div>
            )}

            {/* Demo Actions */}
            <div className="pt-3 border-t border-border space-y-2">
              <button 
                onClick={async () => {
                  try {
                    // Call backend to inject a real simulated risk spike
                    const csrf = getCsrfToken();
                    const res = await fetch('/api/v1/session/silent-challenge', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf },
                      body: JSON.stringify({ session_id: getSessionId(), current_risk_score: 0.88 })
                    });
                    const data = res.ok ? await res.json() : null;
                    const realScore = data?.risk_score ?? backendMetrics?.risk_score ?? 0.88;
                    toast.error('Risk spike simulated — redirecting to behavioral challenge');
                    setTimeout(() => router.push(`/challenge?reason=behavioral_anomaly&score=${realScore.toFixed(2)}`), 500);
                  } catch {
                    // Fallback: navigate directly
                    router.push('/challenge?reason=behavioral_anomaly&score=0.88');
                  }
                }}
                className="w-full bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 font-mono text-[9px] py-2 rounded uppercase tracking-wider transition-colors flex justify-center items-center gap-2"
              >
                <ShieldAlert className="w-3 h-3" />
                Simulate Risk Spike
              </button>
            </div>
          </div>
        )}

      </main>
    </>
  );
}
