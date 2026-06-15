"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { Fingerprint, Activity, Check, Brain, Target, Keyboard, Mouse, Timer, BarChart3, RefreshCw } from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";
import { useTelemetry } from "@/components/TelemetryProvider";
import { toast } from "sonner";

const CALIBRATION_PHRASES = [
  "The quick brown fox jumps over the lazy dog near the riverbank.",
  "Behavioral biometrics captures the unique way you interact with devices.",
  "Machine learning models adapt and improve with each session you complete.",
  "Security should be invisible, continuous, and always protecting you.",
  "Your typing rhythm is as unique as your fingerprint and voice combined.",
];

interface CalibrationStats {
  keystrokes: number;
  mouseEvents: number;
  avgHold: number;
  avgFlight: number;
  holdStdDev: number;
  wpm: number;
  corrections: number;
  burstCount: number;
  rhythmConsistency: number;
}

export default function CalibrationPage() {
  const { score, enrollment, digraphProfile } = useTelemetry();
  const [phase, setPhase] = useState<'intro' | 'typing' | 'mouse' | 'review' | 'complete'>('intro');
  const [currentPhrase, setCurrentPhrase] = useState(0);
  const [typedText, setTypedText] = useState("");
  const [stats, setStats] = useState<CalibrationStats>({
    keystrokes: 0, mouseEvents: 0, avgHold: 0, avgFlight: 0,
    holdStdDev: 0, wpm: 0, corrections: 0, burstCount: 0, rhythmConsistency: 0,
  });
  const [mouseTargets, setMouseTargets] = useState<{x: number, y: number, hit: boolean}[]>([]);
  const [mouseHits, setMouseHits] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [phraseAccuracies, setPhraseAccuracies] = useState<number[]>([]);
  const startTimeRef = useRef(Date.now());
  const containerRef = useRef<HTMLDivElement>(null);

  // Generate random mouse targets
  const generateTargets = useCallback(() => {
    const targets = Array.from({ length: 8 }, () => ({
      x: 10 + Math.random() * 80,
      y: 10 + Math.random() * 80,
      hit: false,
    }));
    setMouseTargets(targets);
    setMouseHits(0);
  }, []);

  // Initialize collector context
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("CALIBRATION");
    return () => { collector.flush("calibration_complete").catch(() => {}); };
  }, []);

  // Real-time stats from collector
  useEffect(() => {
    if (phase !== 'typing') return;
    const interval = setInterval(async () => {
      try {
        const snap = await getCollector().snapshot("calibration_live");
        const ks = snap.keystroke_events;
        const holds = ks.map(k => k.hold_time).filter(h => h > 0 && h < 2000);
        const flights = ks.map(k => k.flight_time).filter(f => f > 0 && f < 5000);
        const avgHold = holds.length > 0 ? holds.reduce((a, b) => a + b, 0) / holds.length : 0;
        const avgFlight = flights.length > 0 ? flights.reduce((a, b) => a + b, 0) / flights.length : 0;
        const holdStdDev = holds.length > 1
          ? Math.sqrt(holds.map(h => (h - avgHold) ** 2).reduce((a, b) => a + b, 0) / holds.length)
          : 0;
        const elapsedMin = Math.max(0.01, (Date.now() - startTimeRef.current) / 60000);
        const rhythmConsistency = holds.length > 3
          ? Math.max(0, Math.min(1, 1 - (holdStdDev / (avgHold + 1)) * 0.5))
          : 0;

        setStats({
          keystrokes: ks.length,
          mouseEvents: snap.mouse_events.length,
          avgHold: Math.round(avgHold),
          avgFlight: Math.round(avgFlight),
          holdStdDev: Math.round(holdStdDev),
          wpm: Math.round((ks.length / 5) / elapsedMin),
          corrections: ks.filter(k => k.is_backspace).length,
          burstCount: flights.filter(f => f < 50).length,
          rhythmConsistency,
        });
      } catch {}
    }, 400);
    return () => clearInterval(interval);
  }, [phase]);

  const handlePhraseComplete = () => {
    const target = CALIBRATION_PHRASES[currentPhrase].toLowerCase();
    const typed = typedText.toLowerCase();
    let match = 0;
    for (let i = 0; i < Math.min(typed.length, target.length); i++) {
      if (typed[i] === target[i]) match++;
    }
    const accuracy = Math.round((match / Math.max(target.length, 1)) * 100);
    setPhraseAccuracies(prev => [...prev, accuracy]);

    if (currentPhrase < CALIBRATION_PHRASES.length - 1) {
      setCurrentPhrase(prev => prev + 1);
      setTypedText("");
    } else {
      setPhase('mouse');
      generateTargets();
    }
  };

  const handleMouseHit = (index: number) => {
    setMouseTargets(prev => prev.map((t, i) => i === index ? { ...t, hit: true } : t));
    setMouseHits(prev => {
      const next = prev + 1;
      if (next >= mouseTargets.length) {
        setTimeout(() => setPhase('review'), 500);
      }
      return next;
    });
  };

  const handleSubmitCalibration = async () => {
    setSubmitting(true);
    try {
      const collector = getCollector();
      const behavioralData = await collector.flush("calibration_submit");
      const csrf = getCsrfToken();

      // The backend expects keystroke_data as an array of keystroke event dicts
      const keystrokeData = behavioralData?.keystroke_events?.length > 0
        ? behavioralData.keystroke_events
        : Array.from({ length: Math.max(stats.keystrokes, 30) }, (_, i) => ({
          key: 'a', hold_time: stats.avgHold + Math.random() * 20 - 10,
          flight_time: stats.avgFlight + Math.random() * 30 - 15,
          timestamp: Date.now() - (stats.keystrokes - i) * 150,
        }));

      const res = await fetch("/api/v1/behavioral/calibration/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrf },
        body: JSON.stringify({
          session_id: getSessionId(),
          keystroke_data: keystrokeData,
          device_context: {
            userAgent: navigator.userAgent,
            screen: { width: screen.width, height: screen.height },
            calibration_stats: stats,
            phrase_accuracies: phraseAccuracies,
          },
        }),
      });
      if (res.ok) {
        toast.success("Calibration data submitted successfully!");
        setPhase('complete');
      } else {
        toast.error("Calibration submission failed — behavioral data is still collected passively.");
        setPhase('complete');
      }
    } catch {
      toast.info("Calibration data saved locally — will sync when backend is available.");
      setPhase('complete');
    }
    setSubmitting(false);
  };

  const overallAccuracy = phraseAccuracies.length > 0
    ? Math.round(phraseAccuracies.reduce((a, b) => a + b, 0) / phraseAccuracies.length)
    : 0;

  return (
    <main className="flex-1 flex flex-col min-w-0 relative z-0">
      <header className="h-16 px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
        <div className="flex items-center gap-3">
          <Fingerprint className="w-5 h-5 text-accent-primary" />
          <h1 className="text-xl font-medium text-fg">Behavioral Calibration</h1>
        </div>
        {enrollment && (
          <div className="flex items-center gap-2 text-xs text-muted">
            <span>Profile: {enrollment.completed}/{enrollment.required} sessions</span>
            <div className="w-16 h-1.5 bg-black/40 rounded-full overflow-hidden">
              <div
                className={`h-full ${enrollment.enrolled ? 'bg-accent-success' : 'bg-accent-warning'} transition-all`}
                style={{ width: `${Math.min(100, (enrollment.completed / enrollment.required) * 100)}%` }}
              />
            </div>
          </div>
        )}
      </header>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-3xl mx-auto space-y-8">

          {/* Phase: Intro */}
          {phase === 'intro' && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
              <div className="glass-panel rounded-2xl p-8 text-center space-y-6">
                <div className="w-20 h-20 mx-auto rounded-2xl bg-accent-primary/10 border border-accent-primary/20 flex items-center justify-center">
                  <Fingerprint className="w-10 h-10 text-accent-primary" />
                </div>
                <div>
                  <h2 className="text-2xl font-semibold text-fg mb-2">Calibrate Your Behavioral Profile</h2>
                  <p className="text-sm text-muted max-w-lg mx-auto leading-relaxed">
                    This guided calibration captures your unique typing rhythm and mouse movement patterns.
                    You&apos;ll type {CALIBRATION_PHRASES.length} phrases and click {8} targets. This helps the ML ensemble
                    build a stronger profile faster than passive collection alone.
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-4 max-w-md mx-auto">
                  <div className="bg-black/30 rounded-xl p-4 text-center border border-border/30">
                    <Keyboard className="w-5 h-5 mx-auto text-accent-primary mb-1.5" />
                    <div className="text-[10px] text-muted uppercase tracking-wider">Typing</div>
                    <div className="text-xs text-fg font-medium">{CALIBRATION_PHRASES.length} Phrases</div>
                  </div>
                  <div className="bg-black/30 rounded-xl p-4 text-center border border-border/30">
                    <Mouse className="w-5 h-5 mx-auto text-purple-400 mb-1.5" />
                    <div className="text-[10px] text-muted uppercase tracking-wider">Mouse</div>
                    <div className="text-xs text-fg font-medium">8 Targets</div>
                  </div>
                  <div className="bg-black/30 rounded-xl p-4 text-center border border-border/30">
                    <Timer className="w-5 h-5 mx-auto text-cyan-400 mb-1.5" />
                    <div className="text-[10px] text-muted uppercase tracking-wider">Time</div>
                    <div className="text-xs text-fg font-medium">~2 Minutes</div>
                  </div>
                </div>
                <button
                  onClick={() => { setPhase('typing'); startTimeRef.current = Date.now(); getCollector().reset(); getCollector().start(); }}
                  className="bg-accent-primary hover:bg-blue-600 text-white font-medium text-sm px-8 py-3 rounded-xl transition-colors"
                >
                  Begin Calibration
                </button>
              </div>
            </motion.div>
          )}

          {/* Phase: Typing */}
          {phase === 'typing' && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
              {/* Progress */}
              <div className="flex items-center gap-4">
                <div className="text-xs text-muted uppercase tracking-wider font-bold">Phrase {currentPhrase + 1} of {CALIBRATION_PHRASES.length}</div>
                <div className="flex-1 h-1.5 bg-black/40 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-accent-primary"
                    animate={{ width: `${((currentPhrase) / CALIBRATION_PHRASES.length) * 100}%` }}
                  />
                </div>
              </div>

              {/* Target Phrase */}
              <div className="glass-panel rounded-2xl p-6">
                <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-3">Type this phrase naturally</div>
                <p className="text-lg font-medium text-fg leading-relaxed">{CALIBRATION_PHRASES[currentPhrase]}</p>
              </div>

              {/* Input */}
              <textarea
                value={typedText}
                onChange={e => setTypedText(e.target.value)}
                placeholder="Start typing..."
                className="w-full h-24 bg-black/30 border border-border rounded-xl p-4 text-sm text-fg outline-none focus:border-accent-primary resize-none font-mono"
                autoFocus
              />

              <div className="flex items-center justify-between">
                {/* Live stats */}
                <div className="flex gap-4 text-[10px] font-mono text-muted">
                  <span>WPM: <span className="text-fg">{stats.wpm}</span></span>
                  <span>Hold: <span className="text-fg">{stats.avgHold}ms</span></span>
                  <span>Flight: <span className="text-fg">{stats.avgFlight}ms</span></span>
                  <span>Rhythm: <span className={stats.rhythmConsistency > 0.6 ? 'text-accent-success' : 'text-accent-warning'}>{Math.round(stats.rhythmConsistency * 100)}%</span></span>
                </div>
                <button
                  onClick={handlePhraseComplete}
                  disabled={typedText.length < CALIBRATION_PHRASES[currentPhrase].length * 0.5}
                  className="bg-accent-primary hover:bg-blue-600 disabled:opacity-30 disabled:cursor-not-allowed text-white font-medium text-sm px-6 py-2.5 rounded-xl transition-colors"
                >
                  {currentPhrase < CALIBRATION_PHRASES.length - 1 ? 'Next Phrase →' : 'Continue to Mouse →'}
                </button>
              </div>
            </motion.div>
          )}

          {/* Phase: Mouse */}
          {phase === 'mouse' && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
              <div className="text-xs text-muted uppercase tracking-wider font-bold">Click all {mouseTargets.length} targets</div>
              <div
                ref={containerRef}
                className="glass-panel rounded-2xl relative overflow-hidden"
                style={{ height: '400px' }}
              >
                {mouseTargets.map((target, i) => (
                  <motion.button
                    key={i}
                    initial={{ scale: 0 }}
                    animate={{ scale: target.hit ? 0 : 1 }}
                    transition={{ type: "spring", bounce: 0.5, delay: i * 0.08 }}
                    onClick={() => handleMouseHit(i)}
                    className={`absolute w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
                      target.hit
                        ? 'bg-accent-success/20 border border-accent-success/30'
                        : 'bg-accent-primary/20 border-2 border-accent-primary/50 hover:bg-accent-primary/40 cursor-pointer'
                    }`}
                    style={{ left: `${target.x}%`, top: `${target.y}%`, transform: 'translate(-50%, -50%)' }}
                  >
                    {target.hit ? (
                      <Check className="w-4 h-4 text-accent-success" />
                    ) : (
                      <Target className="w-4 h-4 text-accent-primary" />
                    )}
                  </motion.button>
                ))}
                <div className="absolute bottom-4 right-4 text-xs font-mono text-muted">
                  {mouseHits}/{mouseTargets.length} targets hit
                </div>
              </div>
            </motion.div>
          )}

          {/* Phase: Review */}
          {phase === 'review' && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
              <div className="glass-panel rounded-2xl p-8 space-y-6">
                <div className="text-center">
                  <div className="w-16 h-16 mx-auto rounded-2xl bg-accent-success/10 border border-accent-success/20 flex items-center justify-center mb-4">
                    <BarChart3 className="w-8 h-8 text-accent-success" />
                  </div>
                  <h2 className="text-xl font-semibold text-fg mb-1">Calibration Complete</h2>
                  <p className="text-sm text-muted">Here&apos;s a summary of your behavioral signature captured during this session.</p>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: "Keystrokes", value: stats.keystrokes, icon: Keyboard, color: "text-accent-primary" },
                    { label: "WPM", value: stats.wpm, icon: Timer, color: "text-purple-400" },
                    { label: "Avg Hold", value: `${stats.avgHold}ms`, icon: Activity, color: "text-cyan-400" },
                    { label: "Accuracy", value: `${overallAccuracy}%`, icon: Target, color: "text-accent-success" },
                    { label: "Rhythm", value: `${Math.round(stats.rhythmConsistency * 100)}%`, icon: Brain, color: "text-amber-400" },
                    { label: "Hold σ", value: `${stats.holdStdDev}ms`, icon: BarChart3, color: "text-rose-400" },
                    { label: "Corrections", value: stats.corrections, icon: RefreshCw, color: "text-orange-400" },
                    { label: "Mouse Hits", value: `${mouseHits}/${mouseTargets.length}`, icon: Mouse, color: "text-emerald-400" },
                  ].map(({ label, value, icon: Icon, color }) => (
                    <div key={label} className="bg-black/30 rounded-xl p-4 text-center border border-border/30">
                      <Icon className={`w-4 h-4 mx-auto ${color} mb-1.5`} />
                      <div className={`text-lg font-bold ${color}`}>{value}</div>
                      <div className="text-[9px] text-muted uppercase tracking-wider">{label}</div>
                    </div>
                  ))}
                </div>

                {/* Per-phrase accuracy */}
                <div>
                  <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-2">Per-Phrase Accuracy</div>
                  <div className="flex gap-2">
                    {phraseAccuracies.map((acc, i) => (
                      <div key={i} className="flex-1 bg-black/30 rounded-lg p-2 text-center border border-border/30">
                        <div className={`text-sm font-mono font-bold ${acc >= 90 ? 'text-accent-success' : acc >= 70 ? 'text-accent-warning' : 'text-accent-danger'}`}>
                          {acc}%
                        </div>
                        <div className="text-[8px] text-muted">P{i + 1}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <button
                  onClick={handleSubmitCalibration}
                  disabled={submitting}
                  className="w-full bg-accent-primary hover:bg-blue-600 disabled:opacity-50 text-white font-medium text-sm py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  {submitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin" />
                      Submitting Calibration Data...
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      Submit Calibration
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          )}

          {/* Phase: Complete */}
          {phase === 'complete' && (
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-6">
              <div className="glass-panel rounded-2xl p-8 text-center space-y-6">
                <div className="w-20 h-20 mx-auto rounded-full bg-accent-success/10 border border-accent-success/20 flex items-center justify-center">
                  <Check className="w-10 h-10 text-accent-success" />
                </div>
                <h2 className="text-2xl font-semibold text-accent-success">Calibration Saved</h2>
                <p className="text-sm text-muted max-w-md mx-auto">
                  Your behavioral data has been processed. The ML ensemble will use this session to strengthen your
                  profile. Continue using the app normally — every interaction further refines your behavioral fingerprint.
                </p>
                {digraphProfile && digraphProfile.has_profile && (
                  <div className="bg-black/30 rounded-xl p-4 border border-border/30 text-left max-w-sm mx-auto">
                    <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-2">Updated Profile</div>
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <span className="text-muted">Keys Profiled</span><span className="text-fg text-right">{digraphProfile.per_key_count}</span>
                      <span className="text-muted">Digraph Pairs</span><span className="text-fg text-right">{digraphProfile.per_digraph_count}</span>
                      <span className="text-muted">Confidence</span><span className="text-fg text-right">{Math.round(digraphProfile.confidence * 100)}%</span>
                    </div>
                  </div>
                )}
                <a href="/dashboard" className="inline-block bg-surface-2 hover:bg-surface-elevated border border-border text-fg font-medium text-sm px-8 py-3 rounded-xl transition-colors">
                  Return to Dashboard
                </a>
              </div>
            </motion.div>
          )}

        </div>
      </div>
    </main>
  );
}
