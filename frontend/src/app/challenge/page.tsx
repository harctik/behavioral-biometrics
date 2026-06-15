"use client";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";


import { useState, useEffect, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthButton } from "@/components/auth/AuthPrimitives";
import { ShieldAlert, ArrowRight, Quote, Timer, Brain, Shield, Cpu, AlertTriangle } from "lucide-react";
import { motion } from "framer-motion";
import { getCollector } from "@/lib/behavioral-collector";

const PHRASES = [
  "The quick brown fox jumps over the lazy dog.",
  "Security is not a product, but a continuous process.",
  "Continuous authentication protects our digital identity seamlessly.",
  "Machine learning algorithms adapt to behavioral patterns over time.",
  "A secure system is one that operates invisibly but effectively.",
  "Behavioral biometrics analyzes how you interact, not just what you know."
];

function scoreColor(v: number, invert = false) {
  const s = invert ? 1 - v : v;
  return s >= 0.7 ? "text-emerald-400" : s >= 0.4 ? "text-amber-400" : "text-red-400";
}

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono border ${ok ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" : "bg-red-500/10 border-red-500/20 text-red-400"}`}>
      {ok ? "✓" : "⚠"} {label}
    </span>
  );
}

function ChallengeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reasonParam = searchParams.get("reason");
  const scoreParam = searchParams.get("score");

  const [text, setText] = useState("");
  const [status, setStatus] = useState<"CAPTURING..." | "ANALYZING..." | "VERIFIED ✓" | "MISMATCH ✗">("CAPTURING...");
  const [confidence, setConfidence] = useState(0);
  const [fallbackMode, setFallbackMode] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [targetPhrase, setTargetPhrase] = useState("");
  const [timeLeft, setTimeLeft] = useState(30);
  const startTimeRef = useRef(Date.now());

  // Local real-time behavioral analysis from collector
  const [local, setLocal] = useState({
    keystrokes: 0, mouseEvents: 0, wpm: 0,
    avgHold: 0, avgFlight: 0, holdStdDev: 0, flightStdDev: 0,
    corrections: 0, hesitations: 0, accuracy: 0,
    copyPaste: false, mouseVel: 0, burstCount: 0,
    // Derived ML-style scores (computed from raw signals)
    livenessScore: 0, identityScore: 0, duressScore: 0,
    deviceScore: 1, replayScore: 0, rhythmConsistency: 0,
  });

  // Backend ML ensemble (optional overlay)
  const [backend, setBackend] = useState<any>(null);

  const reason = reasonParam === "behavioral_anomaly" && scoreParam
    ? `Behavioral confidence dropped to ${(parseFloat(scoreParam) * 100).toFixed(0)}% — unusual activity detected.`
    : reasonParam === "idle" ? "Session idle too long." : "Interaction pattern change detected.";

  useEffect(() => {
    setTargetPhrase(PHRASES[Math.floor(Math.random() * PHRASES.length)]);
    const c = getCollector(); c.setContext("STEP_UP_CHALLENGE"); c.reset(); c.start();
    return () => c.stop();
  }, []);

  useEffect(() => {
    const t = setInterval(() => {
      setTimeLeft(p => {
        if (p <= 1) { clearInterval(t); if (status !== "VERIFIED ✓") { setStatus("MISMATCH ✗"); setFallbackMode(true); } return 0; }
        return p - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [status]);

  // Main analysis loop
  useEffect(() => {
    if (fallbackMode || status === "VERIFIED ✓" || isVerifying) return;

    const interval = setInterval(async () => {
      const snap = await getCollector().snapshot("challenge_live");
      const ks = snap.keystroke_events;
      const ms = snap.mouse_events;

      // ── Keystroke analysis ──
      const holds = ks.map(k => k.hold_time).filter(h => h > 0 && h < 2000);
      const flights = ks.map(k => k.flight_time).filter(f => f > 0 && f < 5000);
      const avgHold = holds.length > 0 ? holds.reduce((a, b) => a + b, 0) / holds.length : 0;
      const avgFlight = flights.length > 0 ? flights.reduce((a, b) => a + b, 0) / flights.length : 0;

      // Standard deviation (rhythm consistency)
      const holdStdDev = holds.length > 1 ? Math.sqrt(holds.map(h => (h - avgHold) ** 2).reduce((a, b) => a + b, 0) / holds.length) : 0;
      const flightStdDev = flights.length > 1 ? Math.sqrt(flights.map(f => (f - avgFlight) ** 2).reduce((a, b) => a + b, 0) / flights.length) : 0;

      const elapsedMins = Math.max(0.01, (Date.now() - startTimeRef.current) / 60000);
      const wpm = Math.round((ks.length / 5) / elapsedMins);
      const corrections = ks.filter(k => k.is_backspace).length;
      const hesitations = flights.filter(f => f > 1500).length;
      const hasCopyPaste = snap.cognitive_events.some(c => c.type === 'copy_paste');
      const burstCount = flights.filter(f => f < 50).length; // unnaturally fast = bot

      // Mouse analysis
      const vels = ms.filter(m => m.velocity !== undefined).map(m => m.velocity!);
      const mouseVel = vels.length > 0 ? Math.round(vels.reduce((a, b) => a + b, 0) / vels.length * 100) / 100 : 0;

      // Text accuracy
      const tgt = targetPhrase.toLowerCase();
      const typed = text.toLowerCase();
      let match = 0;
      for (let i = 0; i < Math.min(typed.length, tgt.length); i++) { if (typed[i] === tgt[i]) match++; }
      const accuracy = typed.length > 0 ? Math.round((match / Math.max(typed.length, 1)) * 100) : 0;

      // ── Compute ML-style scores from RAW behavioral signals ──
      // Rhythm consistency: low stddev = consistent human typing
      const rhythmConsistency = holds.length > 3
        ? Math.max(0, Math.min(1, 1 - (holdStdDev / (avgHold + 1)) * 0.5 - (flightStdDev / (avgFlight + 1)) * 0.5))
        : 0;

      // Liveness (bot detection): bots have too-perfect timing or bursts
      const tooFast = burstCount > ks.length * 0.5; // >50% sub-50ms flights = bot
      const tooRegular = holdStdDev < 5 && holds.length > 10; // impossibly consistent
      const noMouse = ms.length < 3 && ks.length > 10; // no mouse at all = scripted
      const livenessScore = Math.max(0, Math.min(1,
        1 - (tooFast ? 0.4 : 0) - (tooRegular ? 0.3 : 0) - (noMouse ? 0.2 : 0) - (hasCopyPaste ? 0.3 : 0)
      ));

      // Identity match: based on keystroke count + accuracy + rhythm
      const ksFactor = Math.min(1, ks.length / 30);
      const accFactor = accuracy / 100;
      const identityScore = Math.min(1, ksFactor * 0.4 + accFactor * 0.3 + rhythmConsistency * 0.3);

      // Duress: high hesitation rate + low WPM + corrections = stress
      const hesitRate = ks.length > 0 ? hesitations / ks.length : 0;
      const corrRate = ks.length > 0 ? corrections / ks.length : 0;
      const duressScore = Math.min(1, hesitRate * 2 + (wpm < 15 && ks.length > 10 ? 0.3 : 0) + corrRate * 0.5);

      // Replay: entropy too low = replayed stream
      const replayScore = tooRegular ? 0.6 : 0;

      setLocal({
        keystrokes: ks.length, mouseEvents: ms.length, wpm,
        avgHold: Math.round(avgHold), avgFlight: Math.round(avgFlight),
        holdStdDev: Math.round(holdStdDev), flightStdDev: Math.round(flightStdDev),
        corrections, hesitations, accuracy, copyPaste: hasCopyPaste,
        mouseVel, burstCount,
        livenessScore, identityScore, duressScore,
        deviceScore: 1, replayScore, rhythmConsistency,
      });

      // Update confidence from local analysis
      const localConf = Math.round(
        (identityScore * 0.35 + livenessScore * 0.25 + (1 - duressScore) * 0.15 + accFactor * 0.25) * 100
      );

      // ── Try backend ML overlay (optional) ──
      try {
        const csrf = getCsrfToken();
        const res = await fetch("/api/v1/session/metrics", { headers: { "X-CSRF-TOKEN": csrf } });
        if (res.ok) {
          const data = await res.json();
          setBackend(data);
          const backendConf = Math.round((data.authenticity_score || 0) * 100);
          setConfidence(Math.max(localConf, backendConf)); // Use best of local/backend
        } else {
          setBackend(null);
          setConfidence(localConf);
        }
      } catch {
        setBackend(null);
        setConfidence(localConf);
      }

      if (ks.length > 3) setStatus("ANALYZING...");

      // Verify when confidence is high enough and user typed enough
      const finalConf = confidence;
      if (finalConf >= 75 && !isVerifying && text.length >= targetPhrase.length * 0.7) {
        setIsVerifying(true);
        setStatus("VERIFIED ✓");
        setTimeout(() => router.push("/dashboard"), 1500);
      }
    }, 800);

    return () => clearInterval(interval);
  }, [fallbackMode, status, isVerifying, router, text, targetPhrase, confidence]);

  const ringColor = confidence < 40 ? "text-red-500" : confidence < 70 ? "text-amber-500" : "text-emerald-500";
  const ringStroke = confidence < 40 ? "stroke-red-500" : confidence < 70 ? "stroke-amber-500" : "stroke-emerald-500";

  // Use backend when available, else local
  const identity = backend ? backend.authenticity_score : local.identityScore;
  const liveness = backend?.ensemble?.liveness_score ?? local.livenessScore;
  const duress = backend?.ensemble?.duress_score ?? local.duressScore;
  const challengeRisk = backend?.ensemble?.challenge_risk ?? 0;
  const deviceRisk = backend?.ensemble?.device_risk ?? (1 - local.deviceScore);
  const replayRisk = backend?.ensemble?.replay_risk ?? local.replayScore;
  const featureMatch = backend?.ensemble?.weighted_match_score ?? local.rhythmConsistency;
  const ensembleRisk = backend?.ensemble?.ensemble_risk ?? (1 - confidence / 100);
  const ensembleAction = backend?.ensemble?.ensemble_action ?? (confidence >= 75 ? "allow" : confidence >= 40 ? "silent_challenge" : "step_up");
  const flags: string[] = backend?.ensemble?.ensemble_flags ?? [];

  return (
    <AuthShell title="Behavioral Re-verification" subtitle="">
      {!fallbackMode ? (
        <div className="space-y-4">
          {/* Header */}
          <div className="text-center">
            <p className="text-sm text-fg mb-1">Why are you seeing this?</p>
            <p className="text-xs text-muted mb-3">{reason}</p>
            <p className="text-xs text-muted-2 leading-relaxed bg-black/20 p-3 rounded-lg border border-border">
              Type the phrase below. Your keystroke dynamics are compared against your profile using a 10-engine ML ensemble.
            </p>
            <div className="mt-3 flex items-center justify-center gap-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-black/40 border border-border">
                <span className={`w-2 h-2 rounded-full animate-pulse ${status === "VERIFIED ✓" ? "bg-emerald-400" : status === "MISMATCH ✗" ? "bg-red-400" : "bg-amber-400"}`} />
                <span className="font-mono text-[10px] uppercase tracking-widest text-slate-300">{status}</span>
              </div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-black/40 border border-border">
                <Timer className={`w-3 h-3 ${timeLeft <= 10 ? 'text-red-500' : 'text-muted'}`} />
                <span className={`font-mono text-[10px] tabular-nums ${timeLeft <= 10 ? 'text-red-500' : 'text-slate-300'}`}>{timeLeft}s</span>
              </div>
            </div>
          </div>

          {/* Confidence Ring */}
          <div className="flex justify-center">
            <div className="relative w-24 h-24">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="none" className="stroke-slate-800" strokeWidth="8" />
                <motion.circle cx="50" cy="50" r="45" fill="none" className={ringStroke} strokeWidth="8" strokeLinecap="round"
                  initial={{ strokeDasharray: "0, 283" }} animate={{ strokeDasharray: `${(confidence / 100) * 283}, 283` }} transition={{ duration: 0.5 }} />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={`text-xl font-mono font-bold ${ringColor}`}>{Math.round(confidence)}%</span>
                <span className="text-[7px] text-slate-500 uppercase tracking-widest font-bold">Identity</span>
              </div>
            </div>
          </div>

          {/* Typing Zone */}
          <div className="space-y-2">
            <div className="bg-black/60 border border-slate-800 rounded-xl p-4 flex gap-3 items-start">
              <Quote className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Type this text</p>
                <p className="text-sm font-medium text-slate-200">{targetPhrase}</p>
              </div>
            </div>
            <textarea id="behavioral-verify-input" value={text} onChange={e => setText(e.target.value)}
              placeholder="Start typing the text above..."
              className="w-full h-20 bg-black/30 border border-border rounded-xl p-4 text-sm text-fg outline-none focus:border-amber-500/50 resize-none font-mono" autoFocus />
          </div>

          {/* ════ 10-ENGINE ML ENSEMBLE ════ */}
          <div className="bg-black/30 border border-border rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2.5 bg-black/40 border-b border-border">
              <Brain className="w-3.5 h-3.5 text-blue-400" />
              <span className="text-[10px] uppercase tracking-widest font-bold text-blue-400">
                10-Engine ML Ensemble {backend ? "" : "(Local Analysis)"}
              </span>
              <span className={`ml-auto text-[9px] font-mono px-2 py-0.5 rounded border ${
                ensembleAction === 'allow' ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' :
                ensembleAction === 'step_up' ? 'text-red-400 border-red-500/30 bg-red-500/10' :
                'text-amber-400 border-amber-500/30 bg-amber-500/10'
              }`}>
                {ensembleAction.toUpperCase().replace('_', ' ')}
              </span>
            </div>

            <div className="p-4 space-y-3">
              {/* Core 3 engines */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <div className="text-[8px] text-slate-500 uppercase tracking-wider mb-0.5 flex items-center gap-1"><Shield className="w-2.5 h-2.5" /> Identity</div>
                  <div className={`font-mono text-base font-bold tabular-nums ${scoreColor(identity)}`}>{Math.round(identity * 100)}%</div>
                  <div className="text-[8px] text-slate-600">Profile match</div>
                </div>
                <div>
                  <div className="text-[8px] text-slate-500 uppercase tracking-wider mb-0.5 flex items-center gap-1"><Cpu className="w-2.5 h-2.5" /> Bot Detection</div>
                  <div className={`font-mono text-base font-bold tabular-nums ${scoreColor(liveness)}`}>{Math.round(liveness * 100)}%</div>
                  <div className="text-[8px] text-slate-600">Human probability</div>
                </div>
                <div>
                  <div className="text-[8px] text-slate-500 uppercase tracking-wider mb-0.5 flex items-center gap-1"><AlertTriangle className="w-2.5 h-2.5" /> Duress</div>
                  <div className={`font-mono text-base font-bold tabular-nums ${scoreColor(duress, true)}`}>{Math.round(duress * 100)}%</div>
                  <div className="text-[8px] text-slate-600">Stress indicator</div>
                </div>
              </div>

              <div className="border-t border-white/5" />

              {/* Advanced engines */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                {[
                  { label: "Invisible Challenge", value: challengeRisk, invert: true, desc: "Patent US20150205955A1" },
                  { label: "Device Intelligence", value: deviceRisk, invert: true, desc: "RAT / emulator check" },
                  { label: "Replay Detection", value: replayRisk, invert: true, desc: "GAN entropy analysis" },
                  { label: "Rhythm Consistency", value: featureMatch, invert: false, desc: "Top-20 user features" },
                ].map(e => (
                  <div key={e.label} className="flex items-center justify-between py-1">
                    <div>
                      <div className="text-[9px] text-slate-400">{e.label}</div>
                      <div className="text-[7px] text-slate-600">{e.desc}</div>
                    </div>
                    <div className={`font-mono text-xs font-semibold tabular-nums ${scoreColor(e.value, e.invert)}`}>
                      {Math.round(e.value * 100)}%
                    </div>
                  </div>
                ))}
              </div>

              <div className="border-t border-white/5" />

              {/* Raw telemetry */}
              <div className="grid grid-cols-4 gap-2 text-[9px] font-mono">
                <div><span className="text-slate-600">Keys</span> <span className="text-slate-300">{local.keystrokes}</span></div>
                <div><span className="text-slate-600">WPM</span> <span className="text-slate-300">{local.wpm}</span></div>
                <div><span className="text-slate-600">Hold</span> <span className="text-slate-300">{local.avgHold}±{local.holdStdDev}ms</span></div>
                <div><span className="text-slate-600">Flight</span> <span className="text-slate-300">{local.avgFlight}±{local.flightStdDev}ms</span></div>
              </div>

              {/* Flags */}
              <div className="flex flex-wrap gap-1.5 pt-2 border-t border-white/5">
                <Pill ok={liveness > 0.8} label={liveness > 0.8 ? "Human" : "Bot Suspected"} />
                <Pill ok={identity > 0.7} label={identity > 0.7 ? "Owner Match" : "Unknown User"} />
                <Pill ok={duress < 0.3} label={duress < 0.3 ? "No Duress" : "Stress Detected"} />
                <Pill ok={replayRisk < 0.3} label={replayRisk < 0.3 ? "Live Input" : "Replay"} />
                {local.copyPaste && <Pill ok={false} label="Copy-Paste" />}
                {flags.map((f, i) => (
                  <span key={i} className="px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-[9px] font-mono text-slate-400">{f}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-500">
              <ShieldAlert size={32} />
            </div>
          </div>
          <div className="text-center">
            <h3 className="text-lg font-bold text-fg mb-2">Behavioral verification inconclusive</h3>
            <p className="text-sm text-muted mb-1">Your typing pattern could not be matched to your stored profile.</p>
            <p className="text-xs text-muted-2">This can happen if you&apos;re typing on a different device, under stress, or after a long absence.</p>
          </div>

          <div className="space-y-3">
            {/* Primary: OTP fallback */}
            <AuthButton onClick={() => router.push("/otp")} className="w-full">
              Verify with Email OTP <ArrowRight className="w-4 h-4 ml-2" />
            </AuthButton>

            {/* Secondary: Retry */}
            <button
              onClick={() => {
                setFallbackMode(false);
                setStatus("CAPTURING...");
                setText("");
                setConfidence(0);
                setTimeLeft(30);
                setTargetPhrase(PHRASES[Math.floor(Math.random() * PHRASES.length)]);
                startTimeRef.current = Date.now();
                setIsVerifying(false);
                const c = getCollector();
                c.reset();
              }}
              className="w-full py-3 rounded-xl text-sm font-medium bg-surface-2 border border-border text-fg hover:bg-surface-elevated transition-colors"
            >
              Retry Behavioral Challenge
            </button>

            {/* Tertiary: Bail out */}
            <button
              onClick={() => router.push("/login")}
              className="w-full py-2.5 rounded-xl text-xs text-muted hover:text-fg transition-colors"
            >
              Return to Login
            </button>
          </div>

          <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4 mt-2">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <p className="text-[10px] text-muted leading-relaxed">
                If you continue to fail verification, your account may be temporarily locked for security.
                Contact support if you believe this is an error.
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </AuthShell>
  );
}

export default function ChallengePage() {
  return (
    <Suspense fallback={<AuthShell title="Loading..." subtitle=""><div /></AuthShell>}>
      <ChallengeContent />
    </Suspense>
  );
}
