"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import { Keyboard, MousePointer2, Brain, ShieldAlert, ShieldCheck, Zap, Activity, AlertTriangle, Check, Copy, Timer } from "lucide-react";
import { getCollector, type ExtendedBehavioralPayload } from "@/lib/behavioral-collector";

// ── Risk Engine (client-side, mirrors CognitiveEngine logic) ──────────────
function computeRiskSignals(snap: ExtendedBehavioralPayload) {
  const ks = snap.keystroke_events;
  const ms = snap.mouse_events;
  const cog = snap.cognitive_events;

  // Keystroke rhythm risk — low variance = bot
  const holds = ks.map(k => k.hold_time).filter(h => h > 0 && h < 2000);
  const holdMean = holds.length > 0 ? holds.reduce((a, b) => a + b, 0) / holds.length : 0;
  const holdStd = holds.length > 1 ? Math.sqrt(holds.reduce((s, h) => s + (h - holdMean) ** 2, 0) / holds.length) : 0;
  const keystrokeRisk = holds.length < 3 ? 0 : Math.max(0, 1 - holdStd / 40); // Low variance = high risk

  // Mouse smoothness — jerky = bot or remote control
  const velocities = ms.filter(m => m.velocity !== undefined).map(m => m.velocity!);
  const velMean = velocities.length > 0 ? velocities.reduce((a, b) => a + b, 0) / velocities.length : 0;
  const velStd = velocities.length > 1 ? Math.sqrt(velocities.reduce((s, v) => s + (v - velMean) ** 2, 0) / velocities.length) : 0;
  const mouseRisk = velocities.length < 5 ? 0 : velStd > 3 ? 0.3 : velStd < 0.5 ? 0.9 : 0.1;

  // Correction rate risk
  const backspaces = ks.filter(k => k.is_backspace).length;
  const correctionRate = ks.length > 0 ? backspaces / ks.length : 0;
  const correctionRisk = correctionRate > 0.3 ? 0.7 : correctionRate > 0.15 ? 0.3 : 0.05;

  // Copy-paste risk
  const copyPasteCount = cog.filter(c => c.type === "copy_paste").length;
  const copyPasteRisk = copyPasteCount > 0 ? 0.6 + Math.min(0.35, copyPasteCount * 0.1) : 0;

  // Hesitation risk
  const hesitations = cog.filter(c => c.type === "hesitation");
  const hesitationRisk = hesitations.length > 0 ? 0.4 + Math.min(0.5, hesitations.length * 0.15) : 0;

  // Composite
  const composite = Math.min(1, (keystrokeRisk * 0.3 + mouseRisk * 0.2 + correctionRisk * 0.15 + copyPasteRisk * 0.2 + hesitationRisk * 0.15));

  return {
    keystrokeRisk: Math.round(keystrokeRisk * 100),
    mouseRisk: Math.round(mouseRisk * 100),
    correctionRisk: Math.round(correctionRisk * 100),
    copyPasteRisk: Math.round(copyPasteRisk * 100),
    hesitationRisk: Math.round(hesitationRisk * 100),
    composite: Math.round(composite * 100),
    holdMean: Math.round(holdMean),
    holdStd: Math.round(holdStd * 10) / 10,
    wpm: ks.length > 0 ? Math.round(ks.length / Math.max(1, (Date.now() - snap.window_start) / 60000)) : 0,
    correctionRate: Math.round(correctionRate * 100),
    copyPasteCount,
    totalKeystrokes: ks.length,
    totalMouse: ms.length,
  };
}

function RiskBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5 font-mono">
        <span className="text-slate-400">{label}</span>
        <span className={value > 50 ? "text-red-400 font-bold" : value > 25 ? "text-amber-400" : "text-emerald-400"}>{value}%</span>
      </div>
      <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${color}`}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>
    </div>
  );
}

export default function DemoPage() {
  const [text, setText] = useState("");
  const [risks, setRisks] = useState(computeRiskSignals({ customer_session_id: "", session_id: "", page_context: "", window_start: Date.now(), window_end: Date.now(), sdk_timing: { sdk_load_time: 0, first_interaction_time: -1, time_to_first_keystroke: -1 }, device_fingerprint: null, keystroke_events: [], mouse_events: [], touch_events: [], scroll_events: [], navigation_events: [], motion_events: [], cognitive_events: [], sequence_hash: "", clock_skew: 0, extended_features: {} as any }));
  const [decision, setDecision] = useState<"normal" | "elevated" | "critical" | null>(null);
  const [simLabel, setSimLabel] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("LANDING");
    collector.reset();
    collector.start();
    return () => collector.stop();
  }, []);

  // Poll live risks
  useEffect(() => {
    const interval = setInterval(() => {
      const collector = getCollector();
      const snap = collector.snapshot("demo_live");
      const r = computeRiskSignals(snap);
      setRisks(r);
      // Determine decision
      if (r.composite > 60) setDecision("critical");
      else if (r.composite > 30) setDecision("elevated");
      else if (r.totalKeystrokes > 3) setDecision("normal");
    }, 400);
    return () => clearInterval(interval);
  }, []);

  // ── Simulation handlers ────────────────────────────────────────────────
  const simulateBot = useCallback(() => {
    const collector = getCollector();
    collector.reset();
    setSimLabel("Bot Attack");
    setText("");
    // Inject perfectly uniform keystrokes (zero variance = bot signature)
    const phrase = "transfer $10000 to account 9876543210";
    let i = 0;
    const interval = setInterval(() => {
      if (i >= phrase.length) { clearInterval(interval); return; }
      setText(prev => prev + phrase[i]);
      // Simulate via direct keystroke injection won't work — instead we'll programmatically type
      const event = new KeyboardEvent("keydown", { key: phrase[i], bubbles: true });
      document.dispatchEvent(event);
      setTimeout(() => {
        const upEvent = new KeyboardEvent("keyup", { key: phrase[i], bubbles: true });
        document.dispatchEvent(upEvent);
        i++;
      }, 50); // Perfectly uniform 50ms hold time — bot signature
    }, 80); // Perfectly uniform 80ms flight time
  }, []);

  const simulateNormal = useCallback(() => {
    const collector = getCollector();
    collector.reset();
    setSimLabel("Normal User");
    setText("");
    setDecision(null);
  }, []);

  const simulateFraud = useCallback(() => {
    const collector = getCollector();
    collector.reset();
    setSimLabel("APP Fraud (Coerced)");
    setText("");
    // Simulate: long hesitation then paste
    setTimeout(() => {
      // Inject a hesitation cognitive event
      const snap = collector.snapshot("fraud_sim");
      // Simulate paste via clipboard event
      const pasteEvent = new Event("paste", { bubbles: true });
      document.dispatchEvent(pasteEvent);
      setText("Pasted: IBAN GB29 NWBK 6016 1331 9268 19");
    }, 3000); // 3 second hesitation before paste
  }, []);

  const compositeColor = risks.composite > 60 ? "from-red-600 to-red-400" : risks.composite > 30 ? "from-amber-600 to-amber-400" : "from-emerald-600 to-emerald-400";

  return (
    <div className="min-h-screen p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
            <Activity className="w-5 h-5 text-blue-400" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white">BBA Live Demo</h1>
        </div>
        <p className="text-slate-400 text-sm max-w-2xl">
          Interactive demonstration of Behavioral Biometric Authentication. Type in the text box to see live signal capture, 
          risk scoring, and decision engine output. Use the simulators to see how the system responds to different attack patterns.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* ── Section A: Signal Capture ──────────────────────────────── */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm">
            <div className="flex items-center gap-2 mb-4">
              <Keyboard className="w-5 h-5 text-blue-400" />
              <h2 className="text-lg font-bold text-white">Section A — Signal Capture</h2>
              <span className="ml-auto text-[10px] font-mono text-slate-500 bg-slate-800 px-2 py-0.5 rounded">CONTEXT: DEMO</span>
            </div>
            <p className="text-xs text-slate-500 mb-4">Type the phrase below (or anything you like) to see live behavioral signal capture, risk scoring, and decision output.</p>
            
            {/* Reference text for typing */}
            <div className="bg-black/40 border border-slate-700 rounded-xl p-4 mb-3 flex gap-3 items-start">
              <span className="text-amber-500 text-lg font-serif">&ldquo;</span>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Try typing this</p>
                <p className="text-sm text-slate-300 font-medium leading-relaxed">The quick brown fox jumps over the lazy dog. Security is not a product, but a continuous process.</p>
              </div>
            </div>
            
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Start typing the phrase above to see live behavioral analysis..."
              rows={4}
              className="w-full bg-black/40 border border-slate-700 rounded-xl p-4 text-sm text-white focus:outline-none focus:border-blue-500/50 focus:ring-2 focus:ring-blue-500/10 transition-all resize-none font-mono placeholder:text-slate-600"
            />

            {/* Live stats grid */}
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mt-4">
              {[
                { label: "Keystrokes", value: risks.totalKeystrokes, color: "text-blue-400" },
                { label: "Hold Mean", value: `${risks.holdMean}ms`, color: "text-violet-400" },
                { label: "Hold σ", value: `${risks.holdStd}ms`, color: "text-violet-400" },
                { label: "WPM", value: risks.wpm, color: "text-cyan-400" },
                { label: "Corrections", value: `${risks.correctionRate}%`, color: "text-amber-400" },
                { label: "Copy/Paste", value: risks.copyPasteCount, color: risks.copyPasteCount > 0 ? "text-red-400" : "text-emerald-400" },
              ].map((s, i) => (
                <div key={i} className="bg-black/30 rounded-lg p-3 border border-slate-800">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">{s.label}</div>
                  <div className={`text-lg font-mono font-bold tabular-nums ${s.color}`}>{s.value}</div>
                </div>
              ))}
            </div>

            {/* Status bar */}
            <div className="mt-4 flex items-center gap-2 text-[10px] text-slate-500 font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
              Behavioral profiling active — {risks.totalKeystrokes} keystrokes · {risks.totalMouse} pointer events captured
            </div>
          </div>

          {/* ── Section C: Decision Simulator ───────────────────────── */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-5 h-5 text-amber-400" />
              <h2 className="text-lg font-bold text-white">Section C — Decision Simulator</h2>
            </div>
            <p className="text-xs text-slate-500 mb-5">Click a simulation to inject synthetic behavioral patterns and watch the risk engine respond.</p>
            
            <div className="grid grid-cols-3 gap-3 mb-6">
              <button onClick={simulateNormal} className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors text-left">
                <ShieldCheck className="w-5 h-5 text-emerald-400 mb-2" />
                <div className="text-sm font-bold text-white">Normal Login</div>
                <div className="text-[10px] text-slate-500 mt-1">Reset & type naturally</div>
              </button>
              <button onClick={simulateBot} className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 transition-colors text-left">
                <ShieldAlert className="w-5 h-5 text-red-400 mb-2" />
                <div className="text-sm font-bold text-white">Bot Attack</div>
                <div className="text-[10px] text-slate-500 mt-1">Uniform hold time, zero variance</div>
              </button>
              <button onClick={simulateFraud} className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 hover:bg-amber-500/20 transition-colors text-left">
                <AlertTriangle className="w-5 h-5 text-amber-400 mb-2" />
                <div className="text-sm font-bold text-white">APP Fraud</div>
                <div className="text-[10px] text-slate-500 mt-1">Hesitation + paste on account</div>
              </button>
            </div>

            {/* Decision output */}
            {decision && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`p-4 rounded-xl border flex items-center gap-4 ${
                  decision === "critical" ? "bg-red-500/10 border-red-500/20" :
                  decision === "elevated" ? "bg-amber-500/10 border-amber-500/20" :
                  "bg-emerald-500/10 border-emerald-500/20"
                }`}
              >
                {decision === "critical" ? <ShieldAlert className="w-8 h-8 text-red-400" /> :
                 decision === "elevated" ? <AlertTriangle className="w-8 h-8 text-amber-400" /> :
                 <ShieldCheck className="w-8 h-8 text-emerald-400" />}
                <div>
                  <div className={`text-sm font-bold ${
                    decision === "critical" ? "text-red-400" : decision === "elevated" ? "text-amber-400" : "text-emerald-400"
                  }`}>
                    {decision === "critical" ? "BLOCKED — Step-Up MFA Required" :
                     decision === "elevated" ? "ELEVATED RISK — Monitoring" :
                     "APPROVED — Behavioral Profile Matched"}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5 font-mono">
                    Composite risk: {risks.composite}% · {simLabel || "Live analysis"}
                  </div>
                </div>
              </motion.div>
            )}
          </div>
        </div>

        {/* ── Section B: Risk Engine Output ──────────────────────────── */}
        <div className="space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm">
            <div className="flex items-center gap-2 mb-5">
              <Brain className="w-5 h-5 text-violet-400" />
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Risk Engine Output</h2>
            </div>

            <div className="space-y-4">
              <RiskBar label="Keystroke Rhythm" value={risks.keystrokeRisk} color="from-blue-600 to-blue-400 bg-gradient-to-r" />
              <RiskBar label="Mouse Smoothness" value={risks.mouseRisk} color="from-cyan-600 to-cyan-400 bg-gradient-to-r" />
              <RiskBar label="Correction Rate" value={risks.correctionRisk} color="from-amber-600 to-amber-400 bg-gradient-to-r" />
              <RiskBar label="Copy-Paste Risk" value={risks.copyPasteRisk} color="from-red-600 to-red-400 bg-gradient-to-r" />
              <RiskBar label="Hesitation Risk" value={risks.hesitationRisk} color="from-violet-600 to-violet-400 bg-gradient-to-r" />
            </div>

            {/* Composite Score */}
            <div className="mt-6 pt-5 border-t border-slate-800">
              <div className="flex justify-between items-baseline mb-2">
                <span className="text-xs text-slate-400 font-bold uppercase tracking-wider">Composite Risk</span>
                <span className={`text-3xl font-mono font-bold tabular-nums ${
                  risks.composite > 60 ? "text-red-400" : risks.composite > 30 ? "text-amber-400" : "text-emerald-400"
                }`}>{risks.composite}%</span>
              </div>
              <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden">
                <motion.div
                  className={`h-full rounded-full bg-gradient-to-r ${compositeColor}`}
                  animate={{ width: `${risks.composite}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            </div>
          </div>

          {/* Device Fingerprint Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Device Intelligence</h3>
            <div className="space-y-2 text-[11px] font-mono text-slate-500">
              <div className="flex justify-between"><span>Screen</span><span className="text-slate-300">{typeof screen !== 'undefined' ? `${screen.width}×${screen.height}` : '--'}</span></div>
              <div className="flex justify-between"><span>Color Depth</span><span className="text-slate-300">{typeof screen !== 'undefined' ? screen.colorDepth : '--'}-bit</span></div>
              <div className="flex justify-between"><span>CPU Cores</span><span className="text-slate-300">{typeof navigator !== 'undefined' ? navigator.hardwareConcurrency : '--'}</span></div>
              <div className="flex justify-between"><span>Touch Points</span><span className="text-slate-300">{typeof navigator !== 'undefined' ? navigator.maxTouchPoints : '--'}</span></div>
              <div className="flex justify-between"><span>Timezone</span><span className="text-slate-300">{typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : '--'}</span></div>
              <div className="flex justify-between"><span>Language</span><span className="text-slate-300">{typeof navigator !== 'undefined' ? navigator.language : '--'}</span></div>
              <div className="flex justify-between"><span>Platform</span><span className="text-slate-300">{typeof navigator !== 'undefined' ? (navigator as any).userAgentData?.platform || navigator.platform : '--'}</span></div>
              <div className="flex justify-between"><span>Pixel Ratio</span><span className="text-slate-300">{typeof window !== 'undefined' ? window.devicePixelRatio : '--'}x</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
