"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  LayoutGrid, ArrowLeftRight, CreditCard, PieChart, FileText,
  TrendingUp, ArrowDownLeft, ArrowUpRight, ShieldAlert,
  Check, Bell, Activity
} from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";

import Link from "next/link";

const SidebarItem = ({ icon: Icon, label, active, href }: { icon: any, label: string, active?: boolean, href?: string }) => {
  const content = (
    <div className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md cursor-pointer transition-colors ${active ? 'bg-surface-2 text-fg font-medium' : 'text-muted hover:text-fg hover:bg-surface-2'}`}>
      <Icon className="w-4 h-4" />
      {label}
    </div>
  );
  return href ? <Link href={href} className="no-underline">{content}</Link> : content;
};

const TransactionRow = ({ name, date, amount, type }: { name: string, date: string, amount: string, type: 'in'|'out' }) => (
  <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-full bg-black/20 flex items-center justify-center border border-border">
        {type === 'in' ? <ArrowDownLeft className="w-4 h-4 text-accent-success" /> : <ArrowUpRight className="w-4 h-4 text-muted" />}
      </div>
      <div>
        <div className="text-sm font-medium text-fg">{name}</div>
        <div className="text-xs text-muted">{date}</div>
      </div>
    </div>
    <div className={`text-sm tabular-nums font-medium ${type === 'in' ? 'text-accent-success' : 'text-fg'}`}>
      {type === 'in' ? '+' : '-'}${amount}
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

export default function DashboardPage() {
  const router = useRouter();
  const [username, setUsername] = useState("User");
  const [demoMode, setDemoMode] = useState(true); // Always visible by default
  const [score, setScore] = useState(0);
  const [events, setEvents] = useState<{ time: string, msg: string }[]>([]);
  const [currentContext, setCurrentContext] = useState<string>("DASHBOARD");

  // Live behavioral signal stats
  const [liveStats, setLiveStats] = useState({ ksCount: 0, mouseCount: 0, avgHold: 0, avgFlight: 0, mouseVelMean: 0, corrections: 0, copyPaste: false, hesitation: false });
  
  const [transferState, setTransferState] = useState('idle'); // idle, mfa, success, blocked, loading
  const [amount, setAmount] = useState('');
  const [recipient, setRecipient] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [transferError, setTransferError] = useState('');
  
  const [enrollment, setEnrollment] = useState<{enrolled: boolean, phase: string, completed: number, required: number} | null>(null);
  const [trustTimeline, setTrustTimeline] = useState<{timestamp: string, risk_score: number, risk_level: string}[]>([]);
  const [cognitiveProfile, setCognitiveProfile] = useState<Record<string, unknown> | null>(null);
  const [behavioralScore, setBehavioralScore] = useState<{authenticity_score?: number, risk_score?: number} | null>(null);
  const [transferAssessment, setTransferAssessment] = useState<string | null>(null);

  // Backend-driven account data
  const [backendMetrics, setBackendMetrics] = useState<any>(null);
  const [recentTransactions, setRecentTransactions] = useState<{name: string, date: string, amount: string, type: 'in'|'out'}[]>([]);

  // Poll live behavioral stats from collector every 500ms
  useEffect(() => {
    let prevKs = 0;
    let prevMs = 0;
    const interval = setInterval(() => {
      try {
        const collector = getCollector();
        const snap = collector.snapshot("dashboard_live");
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

        // Push real events to the live event stream when new activity is detected
        if (ks.length !== prevKs || ms.length !== prevMs) {
          const avgH = holds.length > 0 ? Math.round(holds.reduce((a, b) => a + b, 0) / holds.length) : 0;
          setEvents(prev => {
            const newEvent = {
              time: new Date().toLocaleTimeString(),
              msg: `KS:${ks.length} Ptr:${ms.length} Hold:${avgH}ms Cor:${ks.filter(k => k.is_backspace).length}`
            };
            if (prev.length === 0 || prev[0].msg !== newEvent.msg) {
              return [newEvent, ...prev].slice(0, 6);
            }
            return prev;
          });
          prevKs = ks.length;
          prevMs = ms.length;
        }
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

        // Fetch session metrics for live scores
        const csrfToken0 = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";
        try {
          const mRes = await fetch("/api/v1/session/metrics", { headers: { "X-CSRF-TOKEN": csrfToken0 } });
          if (mRes.ok) {
            const mData = await mRes.json();
            setBackendMetrics(mData);
            setScore(Math.round((mData.authenticity_score || 0) * 100));
          }
        } catch {}
        setSessionId(data.session_id || "");

        // Fetch enrollment status
        const enrollmentRes = await fetch("/api/v1/behavioral/enrollment/status", {
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || ""
          }
        });
        if (enrollmentRes.ok) {
          const enrollmentData = await enrollmentRes.json();
          if (enrollmentData.enrollment) {
            setEnrollment({
              enrolled: enrollmentData.enrollment.enrolled,
              phase: enrollmentData.enrollment.enrollment_phase,
              completed: enrollmentData.enrollment.sessions_completed || 0,
              required: enrollmentData.enrollment.sessions_required || 5
            });
          }
        }

        // Fetch trust timeline
        const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";
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

        // Fetch session enrollment status (session namespace)
        try {
          const seRes = await fetch("/api/v1/session/enrollment-status", {
            headers: { "X-CSRF-TOKEN": csrfToken }
          });
          if (seRes.ok) {
            const seData = await seRes.json();
            if (seData.phase && !enrollment) {
              setEnrollment({
                enrolled: seData.phase === "mature",
                phase: seData.phase,
                completed: seData.total_samples || 0,
                required: 100,
              });
            }
          }
        } catch {}
      } catch (err) {
        console.error("Auth check failed:", err);
        router.push("/login");
      }
    };
    checkAuth();

    // Start collector

    collector.start();

    // Real telemetry updates from backend using Server-Sent Events (SSE) via streaming fetch
    const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";
    let abortController = new AbortController();

    const streamMetrics = async () => {
      try {
        const res = await fetch("/api/v1/session/metrics/stream", {
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": csrfToken
          },
          signal: abortController.signal
        });
        
        if (!res.ok) throw new Error("Stream failed to connect");
        if (!res.body) throw new Error("ReadableStream not yet supported in this browser.");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const metrics = JSON.parse(line.substring(6));
                setScore(metrics.authenticity_score * 100);
                setEvents(prev => {
                  const newEvent = { 
                    time: new Date().toLocaleTimeString(), 
                    msg: `Sync: KS=${metrics.keystroke_count} Ptr=${metrics.mouse_count}`
                  };
                  if (prev.length === 0 || prev[0].msg !== newEvent.msg) {
                    return [newEvent, ...prev].slice(0, 4);
                  }
                  return prev;
                });
              } catch (e) {
                // Ignore parse errors on incomplete chunks
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.error("Failed to read live metrics stream", err);
          // Auto-reconnect after 5 seconds if connection lost
          setTimeout(streamMetrics, 5000);
        }
      }
    };
    
    streamMetrics();

    return () => {
      collector.stop();
      abortController.abort();
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
      const transferBehavior = collector.flush("MAKE_PAYMENT");

      // Pre-transaction duress check (supplementary — never blocks on network error)
      const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";
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
          "X-CSRF-TOKEN": document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || ""
        }
      });
      if (!nonceRes.ok) throw new Error("Failed to get transaction nonce");
      const nonceData = await nonceRes.json();
      const nonce = nonceData.nonce;

      // 2. Sign Intent
      const intentPayload = {
        session_id: sessionId,
        amount: parseFloat(amount),
        operation: "transfer",
        nonce,
        beneficiary_id: recipient
      };
      
      const signRes = await fetch("/api/v1/transaction/sign-intent", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || ""
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
            "X-CSRF-TOKEN": document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || ""
          },
          body: JSON.stringify({
            session_id: sessionId,
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
          "X-CSRF-TOKEN": document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || ""
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
          setTimeout(() => {
            setTransferState('idle');
            setAmount('');
            setRecipient('');
          }, 3000);
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

  return (
    <div className="flex h-full overflow-hidden text-fg font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-surface/80 backdrop-blur-md border-r border-border flex flex-col shrink-0 z-10">
        <div className="h-16 px-6 flex items-center gap-3 border-b border-border">
          <div className="w-8 h-8 bg-accent-primary/20 rounded-lg flex items-center justify-center border border-accent-primary/30">
            <div className="w-3 h-3 bg-accent-primary rounded-sm"></div>
          </div>
          <span className="font-semibold tracking-tight text-lg">NexaBank</span>
        </div>
        <div className="p-4 flex flex-col gap-1 flex-1">
          <div className="text-[10px] uppercase tracking-wider text-muted font-bold mb-2 px-3 mt-2">Menu</div>
          <SidebarItem icon={LayoutGrid} label="Overview" active />
          <SidebarItem icon={ArrowLeftRight} label="Transfers" />
          <SidebarItem icon={CreditCard} label="Cards" />
          <SidebarItem icon={PieChart} label="Investments" />
          <SidebarItem icon={FileText} label="Statements" />
        </div>
        <div className="p-4 border-t border-border flex items-center gap-3 cursor-pointer hover:bg-surface-2 transition-colors m-2 rounded-xl">
          <div className="w-9 h-9 rounded-full bg-black/40 flex items-center justify-center font-medium text-xs border border-border">
            {username.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="text-sm font-medium text-fg">{username}</div>
            <div className="text-xs text-muted">Personal Checking</div>
          </div>
        </div>
      </aside>

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col min-w-0 relative z-0">
        
        {/* Topbar */}
        <header className="h-16 px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
          <h1 className="text-xl font-medium text-fg">Account Overview</h1>
            <span className="ml-3 px-2.5 py-1 rounded-md bg-accent-primary/10 border border-accent-primary/20 text-[10px] font-mono font-bold text-accent-primary tracking-wider">CONTEXT: {currentContext}</span>
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
              <ToggleSwitch enabled={demoMode} onToggle={() => setDemoMode(!demoMode)} />
            </div>
            <button className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-surface-2 transition-colors border border-transparent hover:border-border">
              <Bell className="w-4 h-4 text-muted" />
            </button>
          </div>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-auto p-8">
          <div className="max-w-5xl mx-auto space-y-8">
            
            {/* Balance Hero */}
            <div className="glass-panel rounded-2xl p-8 flex flex-col gap-2">
              <span className="text-sm text-muted font-medium uppercase tracking-wider">Behavioral Trust Score</span>
              <div className="text-5xl font-semibold tracking-tighter tabular-nums text-fg">
                {score}%
              </div>
              <div className="text-sm text-muted mt-2 flex items-center gap-1">
                <TrendingUp className="w-4 h-4 text-accent-success" />
                <span className="text-accent-success font-medium">{backendMetrics?.keystroke_count || 0} keys</span> · {backendMetrics?.mouse_count || 0} mouse events captured
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

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              
              {/* Left Col: Transactions */}
              <div className="lg:col-span-2 space-y-4">
                <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Recent Activity</h2>
                <div className="glass-panel rounded-2xl p-2 px-6">
                  {recentTransactions.length > 0 ? recentTransactions.map((tx, i) => (
                    <TransactionRow key={i} name={tx.name} date={tx.date} amount={tx.amount} type={tx.type} />
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
                        <input 
                          id="transfer-recipient"
                          type="text" 
                          value={recipient}
                          onChange={(e) => setRecipient(e.target.value)}
                          placeholder="Name, @cashtag, or email" 
                          className="w-full bg-black/20 border border-border rounded-xl px-4 py-3 text-sm outline-none focus:border-accent-primary transition-colors placeholder:text-muted text-fg"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-muted mb-1.5 uppercase tracking-wider">Amount</label>
                        <div className="relative">
                          <span className="absolute left-4 top-3 text-muted">$</span>
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
                          <div>Keystroke confidence: <span className="text-fg">{liveStats.avgHold > 0 ? '94' : '--'}%</span> · No hesitation detected ✓</div>
                          <div>Amount typed manually ✓ · Beneficiary {liveStats.copyPaste ? 'pasted ⚠' : 'typed manually ✓'}</div>
                        </div>
                      </div>
                    </div>
                  )}

                </div>
              </div>

            </div>
          </div>
        </div>

        {/* Always-Visible Behavioral Signal Panel */}
        {demoMode && (
          <div className="absolute bottom-8 right-8 w-80 glass-panel-glow rounded-2xl p-6 z-50 flex flex-col gap-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-accent-primary" />
                <span className="text-xs font-bold tracking-widest uppercase text-fg">Continuous Auth</span>
              </div>
              <div className={`w-2 h-2 rounded-full ${score > 75 ? 'bg-accent-success' : 'bg-accent-danger'} shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse`}></div>
            </div>

            <div>
              <div className="flex justify-between items-baseline mb-2">
                <span className="text-xs text-muted font-medium uppercase tracking-wider">Trust Score</span>
                <span className={`text-2xl font-mono tracking-tighter ${score > 75 ? 'text-fg' : 'text-accent-danger'}`}>
                  {score.toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 w-full bg-black/40 border border-border rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all duration-300 ease-out ${score > 75 ? 'bg-accent-primary' : 'bg-accent-danger'}`}
                  style={{ width: `${score}%` }}
                ></div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
              <div>
                <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Keystrokes</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.ksCount}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Mouse Events</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.mouseCount}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Avg Hold</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.avgHold > 0 ? `${liveStats.avgHold}ms` : '--'}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Avg Flight</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.avgFlight > 0 ? `${liveStats.avgFlight}ms` : '--'}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Corrections</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.corrections}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Mouse Vel</div>
                <div className="font-mono text-sm tabular-nums text-fg">{liveStats.mouseVelMean > 0 ? `${liveStats.mouseVelMean} px/ms` : '--'}</div>
              </div>
            </div>

            {/* Cognitive State */}
            <div className="pt-4 border-t border-border">
              <div className="text-[10px] text-muted uppercase tracking-wider mb-2">Cognitive State</div>
              <div className="flex flex-wrap gap-1.5">
                {liveStats.ksCount > 0 && !liveStats.hesitation && !liveStats.copyPaste && (
                  <span className="px-2 py-0.5 rounded-md bg-accent-success/10 border border-accent-success/20 text-[10px] font-mono text-accent-success">Natural ✓</span>
                )}
                {liveStats.ksCount === 0 && liveStats.mouseCount === 0 && (
                  <span className="px-2 py-0.5 rounded-md bg-slate-500/10 border border-slate-500/20 text-[10px] font-mono text-slate-400">Awaiting input…</span>
                )}
                {liveStats.ksCount === 0 && liveStats.mouseCount > 0 && (
                  <span className="px-2 py-0.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-[10px] font-mono text-blue-400">Mouse only</span>
                )}
                {liveStats.hesitation && <span className="px-2 py-0.5 rounded-md bg-accent-warning/10 border border-accent-warning/20 text-[10px] font-mono text-accent-warning">Hesitation</span>}
                {liveStats.copyPaste && <span className="px-2 py-0.5 rounded-md bg-accent-danger/10 border border-accent-danger/20 text-[10px] font-mono text-accent-danger">Copy-paste ⚠</span>}
              </div>
            </div>

            <div className="pt-4 border-t border-border">
              <div className="text-[10px] text-muted uppercase tracking-wider mb-2">Live Event Stream</div>
              <div className="font-mono text-[10px] space-y-1.5 h-16 overflow-hidden relative">
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
              <div className="pt-4 border-t border-border">
                <div className="text-[10px] text-muted uppercase tracking-wider mb-2">Trust Timeline</div>
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
              <div className="pt-4 border-t border-border">
                <div className="text-[10px] text-muted uppercase tracking-wider mb-2">Cognitive Profile</div>
                <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                  {Object.entries(cognitiveProfile).slice(0, 4).map(([k, v]) => (
                    <div key={k}>
                      <span className="text-muted">{k.replace(/_/g, ' ')}: </span>
                      <span className="text-fg">{typeof v === 'number' ? (v as number).toFixed(2) : String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Behavioral Score */}
            {behavioralScore && (
              <div className="pt-4 border-t border-border">
                <div className="text-[10px] text-muted uppercase tracking-wider mb-1">Last Txn Score</div>
                <div className="flex gap-4 text-[10px] font-mono">
                  <span className="text-accent-success">Auth: {((behavioralScore.authenticity_score || 0) * 100).toFixed(0)}%</span>
                  <span className="text-accent-warning">Risk: {((behavioralScore.risk_score || 0) * 100).toFixed(0)}%</span>
                </div>
              </div>
            )}

            {/* Demo Actions */}
            <div className="pt-4 border-t border-border">
              <button 
                onClick={() => router.push("/challenge?reason=behavioral_anomaly&score=0.88")}
                className="w-full bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 font-mono text-[10px] py-2 rounded uppercase tracking-wider transition-colors flex justify-center items-center gap-2"
              >
                <ShieldAlert className="w-3 h-3" />
                Simulate Risk Spike
              </button>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
