"use client";

import type { SessionMetrics } from "@/lib/api-types";
import { readStorage, useIsClient, useStoredString } from "@/hooks/useBrowser";
import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getCollector } from "@/lib/behavioral-collector";
import { getCsrfToken } from "@/lib/auth-utils";
import { useAutoPageContext } from "@/hooks/useAutoPageContext";
import {
  Activity, ShieldAlert, Fingerprint, Eye, EyeOff,
  ChevronDown, ChevronUp, Minimize2, Maximize2
} from "lucide-react";

// ── Types ───────────────────────────────────────────────────────────────────
interface LiveStats {
  ksCount: number;
  mouseCount: number;
  avgHold: number;
  avgFlight: number;
  mouseVelMean: number;
  corrections: number;
  copyPaste: boolean;
  hesitation: boolean;
  pasteCount: number;
  hesitationCount: number;
  tabSwitches: number;
  scrollReversals: number;
}

interface PageContextInfo {
  label: string;
  riskFocus: string;
  color: string;
}

const PAGE_CONTEXT_MAP: Record<string, PageContextInfo> = {
  "/login":           { label: "Login",          riskFocus: "Credential stuffing detection",   color: "text-blue-400" },
  "/signup":          { label: "Sign Up",        riskFocus: "Bot registration detection",     color: "text-cyan-400" },
  "/otp":             { label: "OTP Verify",     riskFocus: "Session hijack detection",       color: "text-amber-400" },
  "/forgot-password": { label: "Password Reset", riskFocus: "Account takeover detection",     color: "text-orange-400" },
  "/reset-password":  { label: "Reset Password", riskFocus: "Social engineering detection",   color: "text-red-400" },
  "/dashboard":       { label: "Dashboard",      riskFocus: "Session continuity verification",color: "text-emerald-400" },
  "/challenge":       { label: "Challenge",      riskFocus: "Step-up authentication",         color: "text-violet-400" },
  "/calibration":     { label: "Calibration",    riskFocus: "Baseline profile collection",    color: "text-sky-400" },
  "/compliance":      { label: "Compliance",     riskFocus: "Audit trail monitoring",         color: "text-slate-400" },
  "/explainability":  { label: "Explainability", riskFocus: "Model transparency",             color: "text-purple-400" },
};

function getPageContext(pathname: string): PageContextInfo {
  // Exact match
  if (PAGE_CONTEXT_MAP[pathname]) return PAGE_CONTEXT_MAP[pathname];
  // Prefix match (e.g. /dashboard/transfers)
  for (const [key, val] of Object.entries(PAGE_CONTEXT_MAP)) {
    if (pathname.startsWith(key)) return val;
  }
  return { label: "App", riskFocus: "Passive behavioral monitoring", color: "text-muted" };
}

// ── Hold time color ─────────────────────────────────────────────────────────
function holdColor(ms: number): string {
  if (ms < 80) return "text-cyan-400";
  if (ms < 120) return "text-emerald-400";
  if (ms < 180) return "text-amber-400";
  return "text-red-400";
}

// ── Mini keyboard for compact view ──────────────────────────────────────────
const MINI_ROWS = [
  ["q","w","e","r","t","y","u","i","o","p"],
  ["a","s","d","f","g","h","j","k","l"],
  ["z","x","c","v","b","n","m"],
];

function MiniKeyboard({ keyStats }: { keyStats: Record<string, { mean: number; count: number }> }) {
  const renderKey = (k: string) => {
    const cat = `alpha_${k}`;
    const stat = keyStats[cat];
    const hasData = !!stat;
    const t = hasData ? Math.min(1, Math.max(0, (stat.mean - 50) / 200)) : 0;
    
    let bg = "rgba(255,255,255,0.03)";
    if (hasData) {
      if (t < 0.3) bg = `hsla(210, 90%, 55%, ${0.3 + t})`;
      else if (t < 0.6) bg = `hsla(150, 80%, 45%, ${0.3 + t * 0.8})`;
      else bg = `hsla(0, 85%, 50%, ${0.3 + t * 0.7})`;
    }
    
    return (
      <div
        key={k}
        className="w-[14px] h-[14px] rounded-[2px] text-[6px] flex items-center justify-center font-mono uppercase transition-all"
        style={{
          background: bg,
          color: hasData ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.15)",
          border: `0.5px solid rgba(255,255,255,${hasData ? 0.15 : 0.05})`,
        }}
        title={hasData ? `${k}: ${Math.round(stat.mean)}ms (${stat.count}x)` : k}
      >
        {k}
      </div>
    );
  };

  return (
    <div className="space-y-[2px]">
      <div className="flex gap-[2px] justify-center">{MINI_ROWS[0].map(renderKey)}</div>
      <div className="flex gap-[2px] justify-center pl-1">{MINI_ROWS[1].map(renderKey)}</div>
      <div className="flex gap-[2px] justify-center pl-2">{MINI_ROWS[2].map(renderKey)}</div>
    </div>
  );
}

// ── Sparkline SVG ───────────────────────────────────────────────────────────
function Sparkline({ data, color = "rgba(189,189,184,0.8)" }: { data: number[]; color?: string }) {
  if (data.length < 3) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = Math.max(max - min, 1);
  const w = 120;
  const h = 20;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * (h - 2) - 1}`);
  const line = `M ${pts.join(" L ")}`;
  const fill = `${line} L ${w},${h} L 0,${h} Z`;
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fill} fill="url(#sparkGrad)" />
      <path d={line} fill="none" stroke={color} strokeWidth="1" />
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ██  GLOBAL BEHAVIORAL INTELLIGENCE OVERLAY  ██
// ═══════════════════════════════════════════════════════════════════════════

const VISIBLE_KEY = "bba_bio_overlay";
const POSITION_KEY = "bba_bio_overlay_pos";

function parsePosition(raw: string | null): { x: number; y: number } | null {
  try {
    const parsed = raw ? JSON.parse(raw) : null;
    return typeof parsed?.x === "number" && typeof parsed?.y === "number" ? parsed : null;
  } catch {
    return null;
  }
}

export function BehavioralIntelligenceOverlay() {
  const pathname = usePathname();
  const router = useRouter();
  const pageCtx = getPageContext(pathname);
  
  // Auto-set behavioral context on the collector for every page
  useAutoPageContext();
  
  // Panel state
  const mounted = useIsClient();
  const [storedVisible, setStoredVisible] = useStoredString(VISIBLE_KEY);
  const visible = storedVisible === "true";
  const setVisible = useCallback((next: boolean) => setStoredVisible(String(next)), [setStoredVisible]);
  const [expanded, setExpanded] = useState(false);
  const [minimized, setMinimized] = useState(false);

  // ── Drag-to-move state ──────────────────────────────────────────────
  const [storedPos, setStoredPos] = useStoredString(POSITION_KEY);
  const panelPos = useMemo(() => parsePosition(storedPos), [storedPos]);
  const setPanelPos = useCallback(
    (next: { x: number; y: number }) => setStoredPos(JSON.stringify(next)),
    [setStoredPos],
  );
  const isDraggingRef = useRef(false);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ px: number; py: number; ox: number; oy: number }>({ px: 0, py: 0, ox: 0, oy: 0 });
  const panelRef = useRef<HTMLDivElement>(null);

  // Clamp helper: ensures the panel stays within viewport bounds
  const clampPos = useCallback((x: number, y: number) => {
    const el = panelRef.current;
    const w = el?.offsetWidth || 320;
    const h = el?.offsetHeight || 200;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    return {
      x: Math.max(0, Math.min(x, vw - w)),
      y: Math.max(0, Math.min(y, vh - h)),
    };
  }, []);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    // Only drag on primary button (left-click)
    if (e.button !== 0) return;
    isDraggingRef.current = true;
    setIsDragging(true);
    const el = panelRef.current;
    const rect = el?.getBoundingClientRect();
    dragStartRef.current = {
      px: e.clientX,
      py: e.clientY,
      ox: rect?.left ?? 0,
      oy: rect?.top ?? 0,
    };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    e.preventDefault();
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - dragStartRef.current.px;
    const dy = e.clientY - dragStartRef.current.py;
    const newX = dragStartRef.current.ox + dx;
    const newY = dragStartRef.current.oy + dy;
    setPanelPos(clampPos(newX, newY));
  }, [clampPos, setPanelPos]);

  const onPointerUp = useCallback(() => {
    isDraggingRef.current = false;
    setIsDragging(false);
  }, []);

  // Re-clamp on window resize so the panel doesn't go off-screen
  useEffect(() => {
    const handleResize = () => {
      const prev = parsePosition(readStorage(POSITION_KEY));
      if (prev) setPanelPos(clampPos(prev.x, prev.y));
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [clampPos, setPanelPos]);

  // Live stats
  const [liveStats, setLiveStats] = useState<LiveStats>({
    ksCount: 0, mouseCount: 0, avgHold: 0, avgFlight: 0,
    mouseVelMean: 0, corrections: 0, copyPaste: false, hesitation: false,
    pasteCount: 0, hesitationCount: 0, tabSwitches: 0, scrollReversals: 0,
  });
  const [holdTimeline, setHoldTimeline] = useState<number[]>([]);
  const [keyStats, setKeyStats] = useState<Record<string, { mean: number; count: number }>>({});
  const [trustScore, setTrustScore] = useState<number | null>(null);
  const [riskLevel, setRiskLevel] = useState<string>("low");
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [sessionDuration, setSessionDuration] = useState(0);
  const [backendMetrics, setBackendMetrics] = useState<SessionMetrics | null>(null);
  const sessionStartRef = useRef(0);
  const [pasteWarning, setPasteWarning] = useState<{ show: boolean; count: number; charLen: number }>({ show: false, count: 0, charLen: 0 });
  const lastPasteCountRef = useRef(0);

  // Toggle keyboard shortcut (Ctrl+Shift+B)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "B") {
        e.preventDefault();
        setVisible(readStorage(VISIBLE_KEY) !== "true");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setVisible]);

  // Poll live stats from collector
  useEffect(() => {
    sessionStartRef.current = Date.now();
    const interval = setInterval(() => {
      try {
        const collector = getCollector();
        const snap = collector.getBufferSnapshot();
        const ks = snap.keystroke_events || [];
        const ms = snap.mouse_events || [];
        
        const holds = ks.map((k) => k.hold_time).filter((h: number) => h > 0 && h < 2000);
        const flights = ks.map((k) => k.flight_time).filter((f: number) => f > 0 && f < 5000);
        const velocities = ms.map((m) => m.velocity).filter((v): v is number => v !== undefined);

        // Read cognitive events for copy-paste and hesitation
        const cogEvents = snap.cognitive_events || [];
        const pasteEvents = cogEvents.filter((c) => c.type === "copy_paste" || c.type === "autofill");
        const hesitationEvents = cogEvents.filter((c) => c.type === "hesitation" || c.type === "pre_submit_pause");
        const tabSwitchEvents = cogEvents.filter((c) => c.type === "tab_switch");
        const scrollEvts = snap.scroll_events || [];
        let scrollReversals = 0;
        for (let i = 1; i < scrollEvts.length; i++) {
          if (scrollEvts[i].direction !== scrollEvts[i-1].direction) scrollReversals++;
        }

        const currentPasteCount = pasteEvents.length;
        // Trigger warning on NEW paste events
        if (currentPasteCount > lastPasteCountRef.current) {
          const latestPaste = pasteEvents[pasteEvents.length - 1];
          const charLen = parseInt(latestPaste?.context || "0") || 0;
          setPasteWarning({ show: true, count: currentPasteCount, charLen });
          // Auto-dismiss after 8 seconds
          setTimeout(() => setPasteWarning(prev => ({ ...prev, show: false })), 8000);
          lastPasteCountRef.current = currentPasteCount;
        }

        setLiveStats({
          ksCount: ks.length,
          mouseCount: ms.length,
          avgHold: holds.length > 0 ? Math.round(holds.reduce((a: number, b: number) => a + b, 0) / holds.length) : 0,
          avgFlight: flights.length > 0 ? Math.round(flights.reduce((a: number, b: number) => a + b, 0) / flights.length) : 0,
          mouseVelMean: velocities.length > 0 ? Math.round(velocities.reduce((a: number, b: number) => a + b, 0) / velocities.length * 100) / 100 : 0,
          corrections: ks.filter((k) => k.is_backspace).length,
          copyPaste: currentPasteCount > 0,
          hesitation: hesitationEvents.length > 0,
          pasteCount: currentPasteCount,
          hesitationCount: hesitationEvents.length,
          tabSwitches: tabSwitchEvents.length,
          scrollReversals,
        });

        // Hold timeline for sparkline
        if (holds.length > 0) {
          setHoldTimeline(holds.slice(-40));
        }

        // Build per-key stats
        const kMap: Record<string, { sum: number; count: number }> = {};
        for (const evt of ks) {
          const rawKey = (evt.key || "").toLowerCase();
          if (!rawKey || rawKey.length > 1) continue;
          const cat = `alpha_${rawKey}`;
          const hold = evt.hold_time || 0;
          if (hold <= 0 || hold > 2000) continue;
          if (!kMap[cat]) kMap[cat] = { sum: 0, count: 0 };
          kMap[cat].sum += hold;
          kMap[cat].count++;
        }
        const kStats: Record<string, { mean: number; count: number }> = {};
        for (const [k, v] of Object.entries(kMap)) {
          kStats[k] = { mean: v.sum / v.count, count: v.count };
        }
        setKeyStats(kStats);

        // Active key animation
        if (ks.length > 0) {
          const lastKey = (ks[ks.length - 1].key || "").toLowerCase();
          if (lastKey.length === 1) {
            setActiveKey(lastKey);
            setTimeout(() => setActiveKey(null), 400);
          }
        }

        setSessionDuration(Math.floor((Date.now() - sessionStartRef.current) / 1000));
      } catch {}
    }, 500);

    return () => clearInterval(interval);
  }, []);

  // Poll backend metrics
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const csrf = getCsrfToken();
        if (!csrf || !document.cookie.includes("csrf_access_token=")) return;
        
        const res = await fetch("/api/v1/session/metrics", {
          headers: { "X-CSRF-TOKEN": csrf },
        });
        if (res.ok) {
          const data = await res.json();
          setBackendMetrics(data);
          const auth = data.authenticity_score || 0;
          setTrustScore(auth <= 1 ? Math.round(auth * 100) : Math.round(auth));
          setRiskLevel(
            (data.risk_score || 0) > 0.6 ? "high" :
            (data.risk_score || 0) > 0.3 ? "medium" : "low"
          );
        }
      } catch {}
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Format session duration
  const formatDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const totalActivity = liveStats.ksCount + liveStats.mouseCount;

  // ── Minimized pill ────────────────────────────────────────────────────
  // Default position: bottom-right with 16px margin
  if (!mounted) return null;
  const resolvedPos = panelPos ?? { x: window.innerWidth - (visible ? 336 : 40), y: window.innerHeight - (visible && !minimized ? 420 : 48) };

  if (visible && minimized) {
    return (
      <button
        onClick={() => setMinimized(false)}
        className="fixed z-[9999] flex items-center gap-2 px-3 py-1.5 rounded-full
          bg-black/80 backdrop-blur-xl border border-border/50 shadow-2xl
          hover:border-accent-primary/30 transition-all group"
        style={{ left: resolvedPos.x, top: resolvedPos.y }}
      >
        <div className={`w-2 h-2 rounded-full ${
          riskLevel === "high" ? "bg-red-500" : riskLevel === "medium" ? "bg-amber-500" : "bg-emerald-500"
        } animate-pulse`} />
        <span className="text-[9px] font-mono text-muted group-hover:text-fg transition-colors">
          BIO {trustScore !== null ? `${trustScore}%` : "--"}
        </span>
        <Maximize2 className="w-2.5 h-2.5 text-muted" />
      </button>
    );
  }

  if (!visible) {
    // Invisible trigger — small floating dot
    return (
      <button
        onClick={() => setVisible(true)}
        className="fixed z-[9999] w-6 h-6 rounded-full
          bg-black/40 backdrop-blur border border-border/20 flex items-center justify-center
          hover:bg-accent-primary/20 hover:border-accent-primary/30 transition-all opacity-30 hover:opacity-100"
        style={{ left: resolvedPos.x, top: resolvedPos.y }}
        title="Show Behavioral Intelligence (Ctrl+Shift+B)"
      >
        <Activity className="w-3 h-3 text-muted" />
      </button>
    );
  }

  // ── Main overlay panel ────────────────────────────────────────────────
  return (
    <div
      ref={panelRef}
      className={`fixed z-[9999] 
      w-[calc(100vw-32px)] sm:w-[320px]
      rounded-2xl shadow-2xl overflow-hidden
      ${isDragging ? "" : "transition-all duration-300"}
      ${expanded ? "sm:w-[380px]" : ""}
    `}
      style={{
        left: resolvedPos.x,
        top: resolvedPos.y,
        background: "rgba(10,10,10,0.96)",
        backdropFilter: "blur(24px) saturate(1.5)",
        border: `1px solid ${riskLevel === "high" ? "rgba(239,68,68,0.3)" : riskLevel === "medium" ? "rgba(245,158,11,0.3)" : "rgba(16,185,129,0.15)"}`,
        boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
        maxHeight: "calc(100vh - 32px)",
      }}
    >
      {/* Header — draggable handle */}
      <div
        className="flex items-center justify-between px-4 py-2.5 border-b border-border/30 select-none"
        style={{ cursor: "grab", touchAction: "none" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            riskLevel === "high" ? "bg-red-500" : riskLevel === "medium" ? "bg-amber-500" : "bg-emerald-500"
          } animate-pulse`} />
          <span className="text-[10px] font-bold tracking-[0.15em] uppercase text-fg">Behavioral Intel</span>
          <span className={`text-[8px] px-1.5 py-0.5 rounded-full font-mono ${pageCtx.color} bg-white/5 border border-white/5`}>
            {pageCtx.label}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setExpanded(!expanded)} className="text-muted hover:text-fg p-0.5 transition-colors" title="Expand">
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
          </button>
          <button onClick={() => setMinimized(true)} className="text-muted hover:text-fg p-0.5 transition-colors" title="Minimize">
            <Minimize2 className="w-3 h-3" />
          </button>
          <button onClick={() => setVisible(false)} className="text-muted hover:text-fg p-0.5 transition-colors" title="Hide (Ctrl+Shift+B)">
            <EyeOff className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="overflow-y-auto" style={{ maxHeight: expanded ? "calc(100vh - 100px)" : "320px", scrollbarWidth: "thin" }}>
        <div className="px-4 py-3 space-y-3">

          {/* Trust Score + Session */}
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="flex justify-between items-baseline mb-1">
                <span className="text-[9px] text-muted uppercase tracking-wider">Trust</span>
                <span className={`text-lg font-mono font-bold ${
                  (trustScore || 0) > 75 ? "text-emerald-400" : (trustScore || 0) > 40 ? "text-amber-400" : "text-red-400"
                }`}>
                  {trustScore !== null ? `${trustScore}%` : "--"}
                </span>
              </div>
              <div className="h-1 w-full bg-black/40 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    (trustScore || 0) > 75 ? "bg-emerald-500" : (trustScore || 0) > 40 ? "bg-amber-500" : "bg-red-500"
                  }`}
                  style={{ width: `${trustScore || 0}%` }}
                />
              </div>
            </div>
            <div className="text-right">
              <div className="text-[8px] text-muted uppercase tracking-wider">Session</div>
              <div className="text-[10px] font-mono text-fg">{formatDuration(sessionDuration)}</div>
            </div>
          </div>

          {/* Live Signal Grid */}
          <div className="grid grid-cols-4 gap-2">
            {[
              { label: "Keys", value: liveStats.ksCount.toString(), sub: liveStats.avgHold > 0 ? `${liveStats.avgHold}ms` : "" },
              { label: "Mouse", value: liveStats.mouseCount.toString(), sub: liveStats.mouseVelMean > 0 ? `${liveStats.mouseVelMean}` : "" },
              { label: "Flight", value: liveStats.avgFlight > 0 ? `${liveStats.avgFlight}ms` : "--" },
              { label: "Corr", value: liveStats.corrections.toString() },
            ].map(({ label, value, sub }) => (
              <div key={label} className="text-center">
                <div className="text-[8px] text-muted uppercase tracking-wider">{label}</div>
                <div className="text-xs font-mono text-fg font-medium">{value}</div>
                {sub && <div className="text-[7px] font-mono text-muted">{sub}</div>}
              </div>
            ))}
          </div>

          {/* Copy-Paste Warning Banner */}
          {pasteWarning.show && (
            <div className="relative overflow-hidden rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2"
              style={{ animation: "pulse 2s ease-in-out infinite" }}
            >
              <div className="relative flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-400 shrink-0" style={{ animation: "pulse 1s ease-in-out infinite" }} />
                <div>
                  <div className="text-[10px] font-bold text-red-300 uppercase tracking-wider">Paste detected</div>
                  <div className="text-[8px] text-red-400/80 mt-0.5">
                    {pasteWarning.count}× clipboard paste{pasteWarning.charLen > 0 ? ` (${pasteWarning.charLen} chars)` : ""} — behavioral risk elevated
                  </div>
                </div>
                <button onClick={() => setPasteWarning(prev => ({ ...prev, show: false }))} 
                  className="ml-auto text-red-400/60 hover:text-red-300 text-xs">✕</button>
              </div>
            </div>
          )}

          {/* Cognitive State Badges */}
          <div className="flex flex-wrap gap-1">
            <span className={`px-1.5 py-0.5 rounded text-[8px] font-mono ${
              totalActivity === 0
                ? "bg-slate-500/10 border border-slate-500/20 text-slate-400"
                : "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
            }`}>
              {totalActivity === 0 ? "Awaiting input…" : "Active"}
            </span>
            <span className={`px-1.5 py-0.5 rounded text-[8px] font-mono ${pageCtx.color} bg-white/5 border border-white/5`}>
              {pageCtx.riskFocus}
            </span>
            {liveStats.hesitation && (
              <span className="px-1.5 py-0.5 rounded text-[8px] font-mono bg-amber-500/10 border border-amber-500/20 text-amber-400">
                Hesitation ×{liveStats.hesitationCount}
              </span>
            )}
            {liveStats.copyPaste && (
              <span className="px-1.5 py-0.5 rounded text-[8px] font-mono bg-red-500/10 border border-red-500/20 text-red-400"
                style={{ animation: "pulse 2s ease-in-out infinite" }}>
                Paste ×{liveStats.pasteCount}
              </span>
            )}
            {liveStats.tabSwitches > 0 && (
              <span className="px-1.5 py-0.5 rounded text-[8px] font-mono bg-violet-500/10 border border-violet-500/20 text-violet-400">
                Tab switch ×{liveStats.tabSwitches}
              </span>
            )}
            {liveStats.scrollReversals > 3 && (
              <span className="px-1.5 py-0.5 rounded text-[8px] font-mono bg-orange-500/10 border border-orange-500/20 text-orange-400">
                Scroll reversals ×{liveStats.scrollReversals}
              </span>
            )}
          </div>

          {/* Mini Keyboard + Rhythm Sparkline */}
          <div className="flex gap-3 items-start">
            <div className="flex-1">
              <div className="text-[8px] text-muted uppercase tracking-wider mb-1">Keystroke Heatmap</div>
              <MiniKeyboard keyStats={keyStats} />
            </div>
            <div className="flex-1">
              <div className="text-[8px] text-muted uppercase tracking-wider mb-1">Typing Rhythm</div>
              {holdTimeline.length >= 3 ? (
                <Sparkline data={holdTimeline} />
              ) : (
                <div className="text-[7px] font-mono text-muted h-5 flex items-center">Type to see rhythm…</div>
              )}
            </div>
          </div>

          {/* Expanded: ML Engine Breakdown */}
          {expanded && backendMetrics?.ensemble && (
            <div className="pt-2 border-t border-border/30">
              <div className="text-[8px] text-muted uppercase tracking-wider mb-1.5 flex items-center justify-between">
                <span>Engine scores</span>
                <span className={`text-[8px] font-mono px-1 py-0.5 rounded ${
                  backendMetrics.ensemble.ensemble_action === "allow" ? "bg-emerald-500/10 text-emerald-400" :
                  backendMetrics.ensemble.ensemble_action === "block" ? "bg-red-500/10 text-red-400" :
                  "bg-amber-500/10 text-amber-400"
                }`}>{(backendMetrics.ensemble.ensemble_action || "allow").toUpperCase()}</span>
              </div>
              <div className="space-y-1">
                {[
                  { label: "Cognitive",  value: backendMetrics.ensemble.cognitive_analysis?.cognitive_risk || 0 },
                  { label: "Duress",     value: backendMetrics.ensemble.duress_score || 0 },
                  { label: "Liveness",   value: backendMetrics.ensemble.liveness_score ?? 1, inv: true },
                  { label: "Challenge",  value: backendMetrics.ensemble.challenge_risk || 0 },
                  { label: "Device",     value: backendMetrics.ensemble.device_risk || 0 },
                  { label: "Replay",     value: backendMetrics.ensemble.replay_risk || 0 },
                  { label: "Drift",      value: backendMetrics.ensemble.drift_risk || 0 },
                  { label: "Match",      value: backendMetrics.ensemble.weighted_match_score || 0, inv: true },
                  { label: "Digraph",    value: backendMetrics.ensemble.digraph_match_score ?? 0.5, inv: true },
                ].map(({ label, value, inv }) => {
                  const risk = inv ? 1 - value : value;
                  return (
                    <div key={label} className="flex items-center gap-1.5">
                      <span className="text-[7px] text-muted w-12 shrink-0">{label}</span>
                      <div className="flex-1 h-1 bg-black/30 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            risk > 0.6 ? "bg-red-500" : risk > 0.3 ? "bg-amber-500" : "bg-emerald-500"
                          }`}
                          style={{ width: `${Math.max(2, risk * 100)}%` }}
                        />
                      </div>
                      <span className={`text-[7px] font-mono w-6 text-right ${
                        risk > 0.6 ? "text-red-400" : risk > 0.3 ? "text-amber-400" : "text-emerald-400"
                      }`}>{(value * 100).toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
              {/* Fused Risk */}
              <div className="flex items-center justify-between mt-1.5 pt-1.5 border-t border-border/20">
                <span className="text-[7px] text-muted font-semibold uppercase">Fused Risk</span>
                <span className={`text-[10px] font-mono font-bold ${
                  (backendMetrics.ensemble.ensemble_risk || 0) > 0.6 ? "text-red-400" :
                  (backendMetrics.ensemble.ensemble_risk || 0) > 0.3 ? "text-amber-400" : "text-emerald-400"
                }`}>{((backendMetrics.ensemble.ensemble_risk || 0) * 100).toFixed(1)}%</span>
              </div>
            </div>
          )}

          {/* Expanded: Ensemble Flags */}
          {expanded && (backendMetrics?.ensemble?.ensemble_flags?.length ?? 0) > 0 && (
            <div className="pt-2 border-t border-border/30">
              <div className="text-[8px] text-muted uppercase tracking-wider mb-1">Active Flags</div>
              <div className="flex flex-wrap gap-1">
                {backendMetrics?.ensemble?.ensemble_flags?.slice(0, 6).map((flag: string, i: number) => (
                  <span key={i} className="px-1 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-[7px] font-mono text-red-400 truncate max-w-[130px]" title={flag}>
                    {flag.split(":")[0]}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-1.5 border-t border-border/20 flex items-center justify-between">
        <span className="text-[7px] font-mono text-muted">
          {totalActivity} events · {Object.keys(keyStats).length}/26 keys
        </span>
        <button
          onClick={() => router.push("/challenge?reason=behavioral_anomaly&score=0.88")}
          className="text-[7px] font-mono text-red-500/60 hover:text-red-400 transition-colors"
        >
          Simulate risk
        </button>
      </div>
    </div>
  );
}
