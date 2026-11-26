"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ShieldAlert, Activity, Users, AlertTriangle, Keyboard, MousePointer2,
  ShieldBan, Terminal, Download,
  CheckCircle2, XCircle, FileCheck, UserCog, Wifi, HeartPulse
} from "lucide-react";
import { apiClient, getCsrfToken } from "@/lib/api-client";
import { getSessionId } from "@/lib/auth-utils";



const StatCard = ({ title, value, sub, icon: Icon }: { title: string, value: string | number, sub: string, icon: any }) => (
  <div className="glass-panel p-5 rounded-xl flex flex-col justify-between">
    <div className="flex justify-between items-start mb-4">
      <span className="text-muted text-xs uppercase tracking-wider font-semibold">{title}</span>
      <Icon className="w-4 h-4 text-muted" />
    </div>
    <div className="flex items-baseline gap-2">
      <span className="text-3xl font-mono tabular-nums tracking-tight text-fg">{value}</span>
      <span className="text-xs text-muted font-mono">{sub}</span>
    </div>
  </div>
);

const SidebarItem = ({ icon: Icon, label, active }: { icon: any, label: string, active?: boolean }) => (
  <div className={`flex items-center gap-3 px-4 py-2.5 text-sm rounded-lg cursor-pointer transition-all ${active ? 'bg-accent-primary/20 text-accent-primary font-medium border border-accent-primary/30' : 'text-muted hover:text-fg hover:bg-surface-2 border border-transparent'}`}>
    <Icon className="w-[18px] h-[18px]" />
    {label}
  </div>
);

export default function AdminPage() {
  const router = useRouter();
  // Gap 17: No more hardcoded mock data — sessions come from backend only
  const [liveSessions, setLiveSessions] = useState<any[]>([]);
  const [stats, setStats] = useState<{
    active_protected_sessions: number;
    anomalies_prevented_24h: number;
    duress_alerts: number;
    system_trust_score: number;
  } | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [auditEvidence, setAuditEvidence] = useState<any[]>([]);
  const [auditChainValid, setAuditChainValid] = useState<boolean | null>(null);
  const [auditVerifiedCount, setAuditVerifiedCount] = useState(0);
  const [duressResult, setDuressResult] = useState<{duress_score: number, alert_level: string} | null>(null);
  const [cbsHealth, setCbsHealth] = useState<Record<string, any> | null>(null);
  const [roleTarget, setRoleTarget] = useState("");
  const [roleValue, setRoleValue] = useState("user");
  const [activeTab, setActiveTab] = useState("telemetry");

  // Live Alert Feed & Device Intel
  const [liveAlerts, setLiveAlerts] = useState<{time: string, id: string, context: string, risk: number, status: string}[]>([]);
  const [deviceIntel, setDeviceIntel] = useState<any>(null);

  const [roleStatus, setRoleStatus] = useState<"" | "updating" | "success" | "failed">("");

  const fetchAuditEvidence = useCallback(async () => {
    try {
      const sid = getSessionId();
      if (!sid) return;
      const res = await fetch(`/api/v1/admin/audit-evidence?session_id=${sid}`, {
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
      if (res.ok) { const d = await res.json(); setAuditEvidence(d.evidence || []); }
    } catch {}
  }, []);

  const verifyAuditChain = async () => {
    try {
      const sid = getSessionId();
      if (!sid) return;
      const res = await fetch(`/api/v1/admin/audit-evidence/verify?session_id=${sid}`, {
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
      if (res.ok) {
        const d = await res.json();
        setAuditChainValid(d.is_valid);
        setAuditVerifiedCount(d.verified_count || 0);
      }
    } catch {}
  };

  const runDuressCheck = async (targetSessionId: string) => {
    try {
      const res = await fetch(`/api/v1/admin/duress-check?session_id=${targetSessionId}`, {
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
      if (res.ok) { setDuressResult(await res.json()); }
    } catch {}
  };

  const setUserRole = async () => {
    if (!roleTarget) return;
    setRoleStatus("updating");
    try {
      const res = await fetch("/api/v1/admin/users/role", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": getCsrfToken() },
        body: JSON.stringify({ user_id: parseInt(roleTarget), role: roleValue })
      });
      if (res.ok) {
        setRoleStatus("success");
        setRoleTarget("");
      } else {
        setRoleStatus("failed");
      }
    } catch {
      setRoleStatus("failed");
    }
    setTimeout(() => setRoleStatus(""), 3000);
  };

  const fetchCBSHealth = async () => {
    try {
      const res = await fetch("/api/v1/banking/cbs-health", {
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
      if (res.ok) { const d = await res.json(); setCbsHealth(d.cbs_status || null); }
    } catch {}
  };

  const exportTrustTimelineCsv = async () => {
    try {
      const res = await fetch("/api/v1/session/trust-timeline.csv", {
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
      if (res.ok) {
        const text = await res.text();
        const blob = new Blob([text], { type: "text/csv" });
        const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
        a.download = `trust_timeline_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
      }
    } catch {}
  };

  const runMakerChecker = async (makerSid: string, checkerSid: string) => {
    try {
      const res = await fetch("/api/v1/banking/maker-checker", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": getCsrfToken() },
        body: JSON.stringify({ maker_session_id: makerSid, checker_session_id: checkerSid })
      });
      if (res.ok) return await res.json();
    } catch {}
    return null;
  };

  const runAppFraudCheck = async (targetSessionId: string) => {
    try {
      const res = await fetch("/api/v1/banking/app-fraud-check", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": getCsrfToken() },
        body: JSON.stringify({ session_id: targetSessionId })
      });
      if (res.ok) return await res.json();
    } catch {}
    return null;
  };

  useEffect(() => {
    // Fetch real stats from backend
    const fetchStats = async () => {
      try {
        const res = await fetch("/api/v1/admin/dashboard-stats", {
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": getCsrfToken()
          }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.metrics) {
            setStats(data.metrics);
          }
        }
      } catch (err) {
        console.error("Failed to fetch dashboard stats", err);
      }
    };
    
    const fetchLiveSessions = async () => {
      try {
        const csrf = getCsrfToken();
        let res = await fetch("/api/v1/admin/live-sessions", { headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrf } });
        const data = res.ok ? await res.json() : null;
        
        if (!data?.sessions || data.sessions.length === 0) {
          // Fallback to trust timeline
          res = await fetch("/api/v1/session/trust-timeline", { headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrf } });
          if (res.ok) {
            const tl = await res.json();
            if (tl.timeline) {
              setLiveSessions(tl.timeline.map((t: any) => ({
                id: "current_user",
                risk: t.risk_score,
                keystroke: null, pointer: null,
                status: t.risk_level,
                time: new Date(t.timestamp).toLocaleTimeString(),
                ip: "127.0.0.1"
              })));
            } else {
              setLiveSessions([]);
            }
          } else {
            setLiveSessions([]);
          }
        } else {
          setLiveSessions(data.sessions);
        }
      } catch (err) {}
    };

    const fetchLiveMetrics = async () => {
      try {
        const csrf = getCsrfToken();
        const res = await fetch("/api/v1/session/metrics", { headers: { "X-CSRF-TOKEN": csrf } });
        if (res.ok) {
          const data = await res.json();
          const risk = data.risk_score ?? 0;
          let status = "Normal";
          if (risk > 0.6) status = "Critical";
          else if (risk > 0.3) status = "Elevated";
          
          if (data.cognitive_anomaly) status += " — cognitive anomaly";

          setLiveAlerts(prev => {
            const newAlerts = [{
              time: new Date().toLocaleTimeString('en-US', { hour12: false }),
              id: "usr_current",
              context: data.context || "DASHBOARD",
              risk,
              status
            }, ...prev];
            return newAlerts.slice(0, 50); // Keep last 50
          });
        }
      } catch {}
    };

    fetchStats();
    fetchLiveSessions();
    fetchLiveMetrics();

    // Get device intel
    if (typeof window !== "undefined") {
      import("@/lib/behavioral-collector").then(async ({ getCollector }) => {
        const collector = getCollector();
        collector.setContext("ADMIN");
        setDeviceIntel(collector.deviceFingerprint);
      });
    }

    const statsInterval = setInterval(fetchStats, 30000); // refresh every 30s
    const sessionsInterval = setInterval(fetchLiveSessions, 10000);
    const metricsInterval = setInterval(fetchLiveMetrics, 5000); // poll every 5s

    return () => {
      clearInterval(statsInterval);
      clearInterval(sessionsInterval);
      clearInterval(metricsInterval);
    };
  }, []);

  const handleComplianceExport = async () => {
    setIsExporting(true);
    try {
      const res = await fetch("/api/v1/compliance/report?type=rbi", {
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        }
      });
      
      if (!res.ok) throw new Error("Export failed");
      const data = await res.json();
      
      // Create a downloadable blob
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `compliance_report_rbi_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert("Failed to export compliance report");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="flex flex-col md:flex-row h-full overflow-hidden bg-bg text-fg font-sans">
      {/* Sidebar */}
      <aside className="w-full md:w-64 bg-surface/80 backdrop-blur-xl border-b md:border-b-0 md:border-r border-border flex flex-col shrink-0 z-10">
        <div className="h-16 border-b border-border flex items-center px-6 gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent-primary/20 flex items-center justify-center border border-accent-primary/30">
            <ShieldAlert className="w-4 h-4 text-accent-primary" />
          </div>
          <span className="font-bold tracking-tight text-lg">SOC Console</span>
        </div>
        <div className="flex-1 py-2 md:py-6 px-3 flex flex-row md:flex-col gap-1 overflow-x-auto md:overflow-y-auto whitespace-nowrap">
          <div className="hidden md:block px-3 text-[10px] uppercase tracking-wider text-muted font-bold mb-2">Operations</div>
          <div onClick={() => setActiveTab('telemetry')}><SidebarItem icon={Activity} label="Live Telemetry" active={activeTab==='telemetry'} /></div>
          <div onClick={() => { setActiveTab('audit'); fetchAuditEvidence(); }}><SidebarItem icon={FileCheck} label="Audit Evidence" active={activeTab==='audit'} /></div>
          <div onClick={() => setActiveTab('roles')}><SidebarItem icon={UserCog} label="User Roles" active={activeTab==='roles'} /></div>
          
          <div className="hidden md:block px-3 text-[10px] uppercase tracking-wider text-muted font-bold mb-2 mt-6">Banking</div>
          <div onClick={() => { setActiveTab('cbs'); fetchCBSHealth(); }}><SidebarItem icon={HeartPulse} label="CBS Health" active={activeTab==='cbs'} /></div>
          <div onClick={() => setActiveTab('banking')}><SidebarItem icon={ShieldAlert} label="Fraud & Duress" active={activeTab==='banking'} /></div>
          
        </div>
        <div className="hidden md:block p-4 border-t border-border">
          <div className="flex items-center gap-3 bg-surface-2 p-3 rounded-xl border border-border">
            <div className="w-10 h-10 rounded-lg bg-black/40 flex items-center justify-center font-mono text-xs border border-border">OP</div>
            <div className="flex flex-col">
              <span className="text-sm font-medium">Administrator</span>
              <span className="text-xs text-muted">Admin role</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 min-h-0 relative z-0">
        {/* Topbar */}
        <header className="h-16 border-b border-border flex items-center justify-between px-4 md:px-8 bg-surface/50 backdrop-blur-md shrink-0 z-10">
          <span className="text-sm font-medium text-muted">Security operations</span>
        </header>

        {/* Content Scrollable */}
        <div className="flex-1 overflow-auto p-4 md:p-8 flex flex-col gap-8">
          
          {/* Header Title */}
          <div className="flex flex-wrap justify-between items-end gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-fg">Live Telemetry</h1>
              <p className="text-sm text-muted mt-1">Continuous behavioral authentication metrics across all active channels.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button 
                onClick={handleComplianceExport}
                disabled={isExporting}
                className="px-4 py-2 text-sm font-medium bg-surface-2 border border-border hover:bg-surface-elevated transition-colors rounded-lg flex items-center gap-2 disabled:opacity-50"
              >
                <Download className="w-4 h-4" />
                {isExporting ? "Exporting..." : "Export Compliance Report"}
              </button>
              <button 
                onClick={exportTrustTimelineCsv}
                className="px-4 py-2 text-sm font-medium bg-surface-2 border border-border hover:bg-surface-elevated transition-colors rounded-lg flex items-center gap-2"
              >
                <Download className="w-4 h-4" /> Trust CSV
              </button>
            </div>
          </div>

          {activeTab === 'telemetry' && (<>
          {/* KPIs Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <StatCard title="Active Sessions" value={stats?.active_protected_sessions ?? "--"} sub="Last 15 min" icon={Users} />
            <StatCard title="System Trust" value={stats ? `${stats.system_trust_score.toFixed(1)}%` : "--"} sub="Overall" icon={Keyboard} />
            <StatCard title="High Risk Anomalies" value={stats?.anomalies_prevented_24h ?? "--"} sub="Last 24h" icon={AlertTriangle} />
            <StatCard title="Duress Alerts" value={stats?.duress_alerts ?? "--"} sub="Requires action" icon={ShieldBan} />
          </div>

          {/* Charts & Tables Area */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Live Alert Feed */}
            <div className="lg:col-span-2 space-y-6">
              <div className="glass-panel rounded-2xl flex flex-col overflow-hidden max-h-[400px]">
                <div className="p-4 border-b border-border flex justify-between items-center bg-surface-2/50 shrink-0">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-accent-primary animate-pulse" />
                    <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Live Alert Feed</h2>
                  </div>
                </div>
                <div className="overflow-y-auto p-4 space-y-1 font-mono text-xs text-muted font-medium bg-black/40">
                  {liveAlerts.length === 0 ? (
                    <div className="text-center py-4 text-slate-500 italic">Waiting for telemetry...</div>
                  ) : (
                    liveAlerts.map((alert, i) => (
                      <div key={i} className={`flex items-center gap-4 py-1.5 px-3 rounded hover:bg-white/5 transition-colors ${
                        alert.risk > 0.6 ? 'text-red-400' : alert.risk > 0.3 ? 'text-amber-400' : 'text-slate-300'
                      }`}>
                        <span className="text-slate-500 w-16 shrink-0">{alert.time}</span>
                        <span className="w-24 shrink-0 truncate">{alert.id}</span>
                        <span className="w-32 shrink-0 truncate">{alert.context}</span>
                        <span className="w-24 shrink-0">risk: {alert.risk.toFixed(2)}</span>
                        <span className="flex-1 truncate">{alert.status}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Legacy Live Stream Table (Sessions) */}
              <div className="glass-panel rounded-2xl flex flex-col overflow-hidden">
                <div className="p-4 border-b border-border flex justify-between items-center bg-surface-2/50">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Session Evaluation Stream</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm whitespace-nowrap">
                    <thead className="text-xs text-muted uppercase tracking-wider font-mono border-b border-border bg-black/20">
                      <tr>
                        <th className="px-6 py-4 font-medium">User ID</th>
                        <th className="px-6 py-4 font-medium">Risk</th>
                        <th className="px-6 py-4 font-medium">Key. Conf</th>
                        <th className="px-6 py-4 font-medium">Ptr. Conf</th>
                        <th className="px-6 py-4 font-medium">Enforcement</th>
                        <th className="px-6 py-4 font-medium text-right">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border font-mono text-xs">
                      {liveSessions.map((s, i) => (
                        <tr key={i} className="hover:bg-white/5 transition-colors">
                          <td className="px-6 py-4 flex flex-col gap-1">
                            <span className="text-fg font-medium">{s.id}</span>
                            <span className="text-[10px] text-muted">{s.ip}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className={s.risk > 0.8 ? 'text-accent-danger font-bold' : s.risk > 0.1 ? 'text-accent-warning font-bold' : 'text-accent-success font-bold'}>
                              {(s.risk * 100).toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-6 py-4 tabular-nums">{s.keystroke == null ? "--" : `${(s.keystroke * 100).toFixed(1)}%`}</td>
                          <td className="px-6 py-4 tabular-nums">{s.pointer == null ? "--" : `${(s.pointer * 100).toFixed(1)}%`}</td>
                          <td className="px-6 py-4">
                            <div className={`inline-flex items-center px-3 py-1 rounded-md border ${
                              s.status === 'Verified' ? 'bg-accent-success/10 border-accent-success/30 text-accent-success' :
                              s.status === 'Blocked' ? 'bg-accent-danger/10 border-accent-danger/30 text-accent-danger' :
                              'bg-accent-warning/10 border-accent-warning/30 text-accent-warning'
                            }`}>
                              {s.status}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right text-muted">{s.time}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Right Column Metrics */}
            <div className="flex flex-col gap-6">
              {/* Model Performance */}
              <div className="glass-panel rounded-2xl p-6">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-1">Ensemble Confidence</h2>
                <p className="text-xs text-muted mb-5">Sample values, not measured from this deployment.</p>
                <div className="space-y-5">
                  <div>
                    <div className="flex justify-between text-xs mb-2 font-mono">
                      <span className="text-muted">Siamese Network (Keystroke)</span>
                      <span className="text-fg">98.2%</span>
                    </div>
                    <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden border border-border">
                      <div className="h-full bg-accent-primary w-[98.2%]"></div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs mb-2 font-mono">
                      <span className="text-muted">SimCLR (Mouse Dynamics)</span>
                      <span className="text-fg">95.5%</span>
                    </div>
                    <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden border border-border">
                      <div className="h-full bg-accent-primary w-[95.5%]"></div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs mb-2 font-mono">
                      <span className="text-muted">Transformer (Sequence)</span>
                      <span className="text-accent-warning">82.1%</span>
                    </div>
                    <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden border border-border">
                      <div className="h-full bg-accent-warning w-[82.1%]"></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Device Intelligence Card */}
              <div className="glass-panel rounded-2xl p-6">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-4">Device Intelligence</h2>
                {deviceIntel ? (
                  <div className="space-y-2 text-[11px] font-mono text-muted">
                    <div className="flex justify-between"><span>Screen</span><span className="text-fg">{deviceIntel.screen_width}×{deviceIntel.screen_height}</span></div>
                    <div className="flex justify-between"><span>Color Depth</span><span className="text-fg">{deviceIntel.color_depth}-bit</span></div>
                    <div className="flex justify-between"><span>CPU Cores</span><span className="text-fg">{deviceIntel.hardware_concurrency}</span></div>
                    <div className="flex justify-between"><span>Touch Points</span><span className="text-fg">{deviceIntel.touch_points}</span></div>
                    <div className="flex justify-between"><span>Timezone</span><span className="text-fg">{deviceIntel.timezone}</span></div>
                    <div className="flex justify-between"><span>Language</span><span className="text-fg">{deviceIntel.language}</span></div>
                    <div className="flex justify-between"><span>Platform</span><span className="text-fg">{deviceIntel.platform}</span></div>
                  </div>
                ) : (
                  <div className="text-xs text-muted italic">Waiting for fingerprint...</div>
                )}
              </div>
            </div>

          </div>
        </>)}

        {/* ─── Audit Evidence Tab ─── */}
        {activeTab === 'audit' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-fg">Audit Evidence Chain</h2>
              <button onClick={verifyAuditChain} className="px-4 py-2 text-sm bg-accent-primary text-black rounded-lg hover:opacity-90 flex items-center gap-2">
                <FileCheck className="w-4 h-4" /> Verify Chain Integrity
              </button>
            </div>
            {auditChainValid !== null && (
              <div className={`flex items-center gap-3 p-4 rounded-xl border ${auditChainValid ? 'bg-accent-success/10 border-accent-success/30' : 'bg-accent-danger/10 border-accent-danger/30'}`}>
                {auditChainValid ? <CheckCircle2 className="w-5 h-5 text-accent-success" /> : <XCircle className="w-5 h-5 text-accent-danger" />}
                <div>
                  <div className="text-sm font-medium text-fg">{auditChainValid ? 'Chain Valid' : 'Chain Compromised'}</div>
                  <div className="text-xs text-muted">{auditVerifiedCount} records verified</div>
                </div>
              </div>
            )}
            <div className="glass-panel rounded-2xl overflow-hidden">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-black/20 border-b border-border text-muted uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">User</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {auditEvidence.slice(0, 20).map((ev: any, i: number) => (
                    <tr key={i} className="hover:bg-white/5">
                      <td className="px-4 py-3 text-fg">{ev.action}</td>
                      <td className="px-4 py-3"><span className={ev.status === 'ok' ? 'text-accent-success' : 'text-accent-warning'}>{ev.status}</span></td>
                      <td className="px-4 py-3 text-muted">{ev.user_id}</td>
                      <td className="px-4 py-3 text-muted truncate max-w-[200px]">{ev.resource}</td>
                      <td className="px-4 py-3 text-muted">{ev.timestamp}</td>
                    </tr>
                  ))}
                  {auditEvidence.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted">No audit evidence loaded</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ─── User Roles Tab ─── */}
        {activeTab === 'roles' && (
          <div className="space-y-6">
            <h2 className="text-lg font-bold text-fg">User Role Management</h2>
            <div className="glass-panel rounded-2xl p-6 max-w-md space-y-4">
              <div>
                <label className="text-xs text-muted uppercase tracking-wider font-bold mb-1 block">User ID</label>
                <input type="text" value={roleTarget} onChange={e => setRoleTarget(e.target.value)} placeholder="e.g. 1" className="w-full bg-black/20 border border-border rounded-lg px-4 py-2 text-sm text-fg outline-none focus:border-accent-primary" />
              </div>
              <div>
                <label className="text-xs text-muted uppercase tracking-wider font-bold mb-1 block">Role</label>
                <select value={roleValue} onChange={e => setRoleValue(e.target.value)} className="w-full bg-black/20 border border-border rounded-lg px-4 py-2 text-sm text-fg outline-none">
                  <option value="user">User</option>
                  <option value="analyst">Analyst</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <button id="role-btn" onClick={setUserRole} className="px-6 py-2 bg-accent-primary text-black rounded-lg text-sm hover:opacity-90">
                {roleStatus === "updating" ? "Updating..." : roleStatus === "success" ? "Updated ✓" : roleStatus === "failed" ? "Failed" : "Update Role"}
              </button>
            </div>
          </div>
        )}

        {/* ─── CBS Health Tab ─── */}
        {activeTab === 'cbs' && (
          <div className="space-y-6">
            <h2 className="text-lg font-bold text-fg">Core Banking System Health</h2>
            <div className="grid grid-cols-2 gap-4">
              {cbsHealth ? Object.entries(cbsHealth).map(([provider, status]: [string, any]) => (
                <div key={provider} className="glass-panel rounded-xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-bold text-fg uppercase">{provider}</span>
                    <Wifi className={`w-4 h-4 ${status?.healthy ? 'text-accent-success' : 'text-accent-danger'}`} />
                  </div>
                  <div className="text-xs text-muted font-mono">
                    {status?.healthy !== undefined ? (status.healthy ? '● Connected' : '● Unreachable') : JSON.stringify(status).slice(0, 60)}
                  </div>
                  {status?.latency_ms && <div className="text-xs text-muted mt-1">Latency: {status.latency_ms}ms</div>}
                </div>
              )) : <div className="text-sm text-muted col-span-2">Loading CBS health data...</div>}
            </div>
          </div>
        )}

        {/* ─── Banking Fraud & Duress Tab ─── */}
        {activeTab === 'banking' && (
          <div className="space-y-6">
            <h2 className="text-lg font-bold text-fg">Fraud Detection & Duress Monitoring</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Duress Check */}
              <div className="glass-panel rounded-2xl p-6 space-y-4">
                <h3 className="text-sm font-bold text-muted uppercase tracking-wider">Duress Detection</h3>
                <p className="text-xs text-muted">Check if a session shows signs of coerced usage.</p>
                <div className="flex gap-2">
                  <input id="duress-sid" placeholder="Session ID" className="flex-1 bg-black/20 border border-border rounded-lg px-3 py-2 text-sm text-fg outline-none" />
                  <button onClick={() => { const el = document.getElementById('duress-sid') as HTMLInputElement; if (el?.value) runDuressCheck(el.value); }} className="px-4 py-2 bg-accent-warning/20 border border-accent-warning/30 text-accent-warning rounded-lg text-sm">Check</button>
                </div>
                {duressResult && (
                  <div className={`p-3 rounded-lg border text-xs font-mono ${duressResult.alert_level === 'high' ? 'bg-accent-danger/10 border-accent-danger/30 text-accent-danger' : 'bg-accent-success/10 border-accent-success/30 text-accent-success'}`}>
                    Score: {(duressResult.duress_score * 100).toFixed(1)}% · Level: {duressResult.alert_level}
                  </div>
                )}
              </div>
              {/* APP Fraud Check */}
              <div className="glass-panel rounded-2xl p-6 space-y-4">
                <h3 className="text-sm font-bold text-muted uppercase tracking-wider">APP Fraud Check</h3>
                <p className="text-xs text-muted">Run authorized push payment fraud analysis on a session.</p>
                <div className="flex gap-2">
                  <input id="fraud-sid" placeholder="Session ID" className="flex-1 bg-black/20 border border-border rounded-lg px-3 py-2 text-sm text-fg outline-none" />
                  <button onClick={async () => { const el = document.getElementById('fraud-sid') as HTMLInputElement; if (el?.value) { const r = await runAppFraudCheck(el.value); if (r) alert(`APP Fraud Score: ${(r.app_fraud_score*100).toFixed(1)}%, Alert: ${r.alert_level}`); } }} className="px-4 py-2 bg-accent-danger/20 border border-accent-danger/30 text-accent-danger rounded-lg text-sm">Analyze</button>
                </div>
              </div>
              {/* Maker-Checker */}
              <div className="glass-panel rounded-2xl p-6 space-y-4 lg:col-span-2">
                <h3 className="text-sm font-bold text-muted uppercase tracking-wider">Maker-Checker Verification</h3>
                <p className="text-xs text-muted">Verify that maker and checker are distinct individuals via behavioral biometrics (Siamese Network).</p>
                <div className="flex gap-2">
                  <input id="maker-sid" placeholder="Maker Session ID" className="flex-1 bg-black/20 border border-border rounded-lg px-3 py-2 text-sm text-fg outline-none" />
                  <input id="checker-sid" placeholder="Checker Session ID" className="flex-1 bg-black/20 border border-border rounded-lg px-3 py-2 text-sm text-fg outline-none" />
                  <button onClick={async () => { const m = (document.getElementById('maker-sid') as HTMLInputElement)?.value; const c = (document.getElementById('checker-sid') as HTMLInputElement)?.value; if (m && c) { const r = await runMakerChecker(m, c); if (r) alert(`Verified: ${r.maker_checker_verified}, Similarity: ${(r.behavioral_similarity*100).toFixed(1)}%, Violation: ${r.compliance_violation}`); } }} className="px-4 py-2 bg-accent-primary/20 border border-accent-primary/30 text-accent-primary rounded-lg text-sm whitespace-nowrap">Verify</button>
                </div>
              </div>
            </div>
          </div>
        )}

        </div>
      </main>
    </div>
  );
}
