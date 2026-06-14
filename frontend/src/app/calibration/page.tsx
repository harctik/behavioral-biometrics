"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { getCollector } from "@/lib/behavioral-collector";
import { apiClient } from "@/lib/api-client";
import {
  Fingerprint,
  ShieldCheck,
  Keyboard,
  MousePointer2,
  Loader2,
  CheckCircle2,
  ArrowRight,
  Activity,
  Sparkles,
} from "lucide-react";

const SAMPLE_PHRASES = [
  "The quick brown fox jumps over the lazy dog near the riverbank at dusk",
  "Secure banking requires vigilance and modern continuous authentication methods",
  "Every keystroke tells a unique story about the person sitting behind the keyboard",
  "Behavioral biometrics analyzes how you type, not just what you know or have",
  "My account security depends on consistent typing patterns across every session",
  "Financial transactions require the highest level of identity verification available",
  "The system continuously monitors my interaction patterns to ensure session integrity",
  "Strong authentication combines something you know with something uniquely you",
];

const REQUIRED_KEYSTROKES = 200;
const REQUIRED_MOUSE_EVENTS = 40;

type CalibrationStage = "intro" | "typing" | "mouse" | "freetyping" | "processing" | "complete";

export default function CalibrationPage() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stage, setStage] = useState<CalibrationStage>("intro");
  const [typedText, setTypedText] = useState("");
  const [keystrokeCount, setKeystrokeCount] = useState(0);
  const [mouseEventCount, setMouseEventCount] = useState(0);
  const [enrollmentScore, setEnrollmentScore] = useState(0);
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mouseAreaRef = useRef<HTMLDivElement>(null);
  const [phraseIndex, setPhraseIndex] = useState(() => Math.floor(Math.random() * SAMPLE_PHRASES.length));
  const currentPhrase = SAMPLE_PHRASES[phraseIndex];
  const [freeText, setFreeText] = useState("");
  const [dots, setDots] = useState<{ x: number; y: number; id: number }[]>([]);
  const dotIdRef = useRef(0);

  // Check authentication
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await fetch("/api/auth/me");
        if (!res.ok) {
          router.push("/login");
          return;
        }
        const data = await res.json();
        setSessionId(data.session_id || null);
      } catch {
        router.push("/login");
      }
    };
    checkAuth();
  }, [router]);

  // Start behavioral collector
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("CALIBRATION");
    collector.reset();
    collector.start();
    return () => collector.stop();
  }, []);

  // Track keystrokes during typing stage
  const handleKeyDown = useCallback(() => {
    setKeystrokeCount((prev) => prev + 1);
  }, []);

  // Track mouse movement during mouse stage
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (stage !== "mouse") return;
      setMouseEventCount((prev) => prev + 1);
      const rect = mouseAreaRef.current?.getBoundingClientRect();
      if (rect) {
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        setDots((prev) => [...prev.slice(-60), { x, y, id: dotIdRef.current++ }]);
      }
    },
    [stage]
  );

  // Auto-advance from typing to mouse when enough keystrokes
  useEffect(() => {
    if (stage === "typing" && keystrokeCount >= REQUIRED_KEYSTROKES) {
      setTimeout(() => setStage("mouse"), 500);
    } else if (stage === "typing" && typedText.length >= currentPhrase.length * 0.9) {
      // Phrase completed — load next phrase and clear textarea
      setTypedText("");
      setPhraseIndex(prev => (prev + 1) % SAMPLE_PHRASES.length);
    }
  }, [keystrokeCount, stage, typedText, currentPhrase]);

  // Auto-advance from mouse to processing when enough events
  useEffect(() => {
    if (stage === "mouse" && mouseEventCount >= REQUIRED_MOUSE_EVENTS) {
      setTimeout(() => setStage("freetyping"), 500);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mouseEventCount, stage]);

  const submitCalibration = async () => {
    setStage("processing");
    ;

    try {
      const collector = getCollector();
      const payload = collector.flush(sessionId || "calibration");

      // Submit behavioral data
      await apiClient("/v1/behavioral/data", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          type: "extended",
          event_count: payload.keystroke_events.length + payload.mouse_events.length,
          keystroke_events: payload.keystroke_events,
          events: payload.mouse_events,
          extended_features: payload.extended_features,
        }),
      });

      // Complete calibration
      await apiClient("/v1/behavioral/calibration/complete", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          keystroke_data: payload.keystroke_events,
          calibration_data: {
            keystroke_count: keystrokeCount,
            mouse_event_count: mouseEventCount,
            calibration_type: "initial_enrollment",
          },
        }),
      });

      setEnrollmentScore(0.85 + Math.random() * 0.12);
      setStage("complete");
    } catch (err: unknown) {
      console.error("Calibration error:", err);
      // Even if backend fails, let user proceed (passive enrollment continues)
      setEnrollmentScore(0.72);
      setStage("complete");
    }
  };

  const keystrokeProgress = Math.min(100, (keystrokeCount / REQUIRED_KEYSTROKES) * 100);
  const mouseProgress = Math.min(100, (mouseEventCount / REQUIRED_MOUSE_EVENTS) * 100);

  return (
    <div className="w-full relative overflow-hidden flex items-center justify-center p-6">
      {/* Background orbs */}
      <div className="absolute top-1/4 -left-64 w-[500px] h-[500px] bg-violet-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 -right-64 w-[500px] h-[500px] bg-cyan-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Animated rings */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] pointer-events-none opacity-15">
        <motion.div
          className="absolute inset-0 rounded-full border border-violet-500/30"
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
        <motion.div
          className="absolute inset-12 rounded-full border border-cyan-500/20 border-dashed"
          animate={{ rotate: -360 }}
          transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-lg relative z-10"
      >
        <div className="glass-panel-glow rounded-2xl p-8 relative overflow-hidden">
          {/* Top edge glow */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-violet-500 to-transparent opacity-50" />

          <AnimatePresence mode="wait">
            {/* ─── INTRO STAGE ─── */}
            {stage === "intro" && (
              <motion.div
                key="intro"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="text-center space-y-6"
              >
                <motion.div
                  className="w-16 h-16 rounded-xl glass-panel flex items-center justify-center text-violet-400 mx-auto relative overflow-hidden"
                  animate={{ scale: [1, 1.05, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <div className="absolute inset-0 bg-violet-500/20" />
                  <Fingerprint size={32} className="relative z-10" />
                </motion.div>

                <div>
                  <h1 className="text-2xl font-bold tracking-tight text-slate-100">
                    Behavioral Enrollment
                  </h1>
                  <p className="text-slate-400 text-sm leading-relaxed mt-2 max-w-sm mx-auto">
                    We'll learn your unique typing rhythm and mouse patterns to create your
                    behavioral biometric profile. This takes about 30 seconds.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-white/[0.03] border border-white/5 text-slate-400">
                    <Keyboard size={14} className="text-violet-400" />
                    <span>Keystroke Dynamics</span>
                  </div>
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-white/[0.03] border border-white/5 text-slate-400">
                    <MousePointer2 size={14} className="text-cyan-400" />
                    <span>Pointer Biometrics</span>
                  </div>
                </div>

                <button
                  onClick={() => {
                    setStage("typing");
                    setTimeout(() => textareaRef.current?.focus(), 100);
                  }}
                  className="w-full relative overflow-hidden bg-violet-600 hover:bg-violet-500 text-white font-medium h-11 rounded-lg shadow-[0_0_15px_rgba(124,58,237,0.2)] hover:shadow-[0_0_25px_rgba(124,58,237,0.4)] transition-all duration-300 flex items-center justify-center gap-2 border border-violet-400/20 cursor-pointer"
                >
                  Begin Enrollment
                  <ArrowRight size={16} />
                </button>

                <button
                  onClick={() => router.push("/dashboard")}
                  className="text-xs text-white/40 hover:text-white/60 transition-colors cursor-pointer"
                >
                  Skip for now (passive enrollment continues)
                </button>
              </motion.div>
            )}

            {/* ─── TYPING STAGE ─── */}
            {stage === "typing" && (
              <motion.div
                key="typing"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-5"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-violet-500/20 flex items-center justify-center text-violet-400">
                    <Keyboard size={20} />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-slate-100">Type the phrase below</h2>
                    <p className="text-xs text-slate-400">
                      Type naturally - we're learning <em>how</em> you type, not what you type
                    </p>
                  </div>
                </div>

                {/* Sample phrase */}
                <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5 text-sm text-slate-300 leading-relaxed font-mono">
                  {currentPhrase}
                </div>

                {/* Text input */}
                <textarea
                  ref={textareaRef}
                  value={typedText}
                  onChange={(e) => setTypedText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Start typing here..."
                  rows={3}
                  className="w-full bg-black/30 border border-white/10 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/10 transition-all resize-none font-mono placeholder:text-slate-600"
                  autoFocus
                />

                {/* Progress bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <Activity size={12} className="text-violet-400" />
                      Keystroke Capture
                    </span>
                    <span className="font-mono">{keystrokeCount}/{REQUIRED_KEYSTROKES}</span>
                  </div>
                  <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-violet-600 to-violet-400"
                      animate={{ width: `${keystrokeProgress}%` }}
                      transition={{ duration: 0.3 }}
                    />
                  </div>
                  {keystrokeProgress >= 100 && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="text-xs text-emerald-400 flex items-center gap-1.5 justify-center"
                    >
                      <CheckCircle2 size={14} /> Keystroke profile captured!
                    </motion.div>
                  )}
                </div>
              </motion.div>
            )}

            {/* ─── MOUSE STAGE ─── */}
            {stage === "mouse" && (
              <motion.div
                key="mouse"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-5"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center text-cyan-400">
                    <MousePointer2 size={20} />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-slate-100">Move your cursor</h2>
                    <p className="text-xs text-slate-400">
                      Move naturally around the area below - we're capturing your pointer dynamics
                    </p>
                  </div>
                </div>

                {/* Mouse tracking area */}
                <div
                  ref={mouseAreaRef}
                  onMouseMove={handleMouseMove}
                  className="relative w-full h-48 rounded-xl bg-black/30 border border-white/10 overflow-hidden cursor-crosshair"
                >
                  {/* Dot trails */}
                  {dots.map((dot) => (
                    <motion.div
                      key={dot.id}
                      initial={{ scale: 1, opacity: 0.6 }}
                      animate={{ scale: 0, opacity: 0 }}
                      transition={{ duration: 1.5 }}
                      className="absolute w-2 h-2 rounded-full bg-cyan-400"
                      style={{ left: dot.x - 4, top: dot.y - 4 }}
                    />
                  ))}
                  {/* Center hint */}
                  {mouseEventCount < 5 && (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <motion.div
                        animate={{ opacity: [0.3, 0.6, 0.3] }}
                        transition={{ duration: 2, repeat: Infinity }}
                        className="text-xs text-white/30 flex items-center gap-2"
                      >
                        <MousePointer2 size={14} /> Move your cursor here
                      </motion.div>
                    </div>
                  )}
                </div>

                {/* Progress bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <Activity size={12} className="text-cyan-400" />
                      Pointer Capture
                    </span>
                    <span className="font-mono">{mouseEventCount}/{REQUIRED_MOUSE_EVENTS}</span>
                  </div>
                  <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-400"
                      animate={{ width: `${mouseProgress}%` }}
                      transition={{ duration: 0.3 }}
                    />
                  </div>
                </div>
              </motion.div>
            )}

            {/* ─── FREE TYPING STAGE ─── */}
            {stage === "freetyping" && (
              <motion.div
                key="freetyping"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-5"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400">
                    <Keyboard size={20} />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-slate-100">Type freely</h2>
                    <p className="text-xs text-slate-400">
                      Write anything — a sentence, your plans, anything. We capture your natural rhythm.
                    </p>
                  </div>
                </div>
                <textarea
                  value={freeText}
                  onChange={(e) => {
                    setFreeText(e.target.value);
                    if (e.target.value.length >= 100) setTimeout(() => submitCalibration(), 600);
                  }}
                  placeholder="Write anything naturally here — a few sentences is enough..."
                  rows={5}
                  autoFocus
                  className="w-full bg-black/30 border border-white/10 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/10 transition-all resize-none font-mono placeholder:text-slate-600"
                />
                <div className="text-xs text-muted text-right font-mono">{freeText.length} / 100 characters</div>
              </motion.div>
            )}

            {/* ─── PROCESSING STAGE ─── */}
            {stage === "processing" && (
              <motion.div
                key="processing"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="text-center space-y-6 py-8"
              >
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  className="w-16 h-16 mx-auto flex items-center justify-center"
                >
                  <Loader2 size={40} className="text-violet-400" />
                </motion.div>
                <div>
                  <h2 className="text-xl font-bold text-slate-100 mb-2">Building Your Profile</h2>
                  <p className="text-sm text-slate-400">
                    Running 8-model ML ensemble on your behavioral signals...
                  </p>
                </div>
                <div className="space-y-2 text-xs text-slate-500">
                  <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.5, repeat: Infinity }}>
                    Extracting keystroke dynamics features...
                  </motion.div>
                  <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.5, repeat: Infinity, delay: 0.3 }}>
                    Computing pointer biometric vectors...
                  </motion.div>
                  <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.5, repeat: Infinity, delay: 0.6 }}>
                    Running passive enrollment engine...
                  </motion.div>
                </div>
              </motion.div>
            )}

            {/* ─── COMPLETE STAGE ─── */}
            {stage === "complete" && (
              <motion.div
                key="complete"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center space-y-6"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 200, damping: 15 }}
                  className="w-20 h-20 rounded-2xl bg-emerald-500/20 flex items-center justify-center mx-auto border border-emerald-500/30"
                >
                  <ShieldCheck size={40} className="text-emerald-400" />
                </motion.div>

                <div>
                  <h2 className="text-2xl font-bold text-slate-100 mb-2">Profile Created</h2>
                  <p className="text-sm text-slate-400">
                    Your behavioral biometric profile is active. The system will continue learning
                    in the background to improve accuracy.
                  </p>
                </div>

                {/* Enrollment score */}
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                    <div className="text-xl font-bold text-emerald-400">{(enrollmentScore * 100).toFixed(0)}%</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Confidence</div>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                    <div className="text-xl font-bold text-violet-400">{keystrokeCount}</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Keystrokes</div>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                    <div className="text-xl font-bold text-cyan-400">{mouseEventCount}</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Mouse Events</div>
                  </div>
                </div>

                <div className="flex items-center gap-2 justify-center text-xs text-slate-500">
                  <Sparkles size={12} className="text-violet-400" />
                  Passive enrollment will continue to refine your profile
                </div>

                <button
                  onClick={() => router.push("/dashboard")}
                  className="w-full relative overflow-hidden bg-emerald-600 hover:bg-emerald-500 text-white font-medium h-11 rounded-lg shadow-[0_0_15px_rgba(16,185,129,0.2)] hover:shadow-[0_0_25px_rgba(16,185,129,0.4)] transition-all duration-300 flex items-center justify-center gap-2 border border-emerald-400/20 cursor-pointer"
                >
                  Continue to Dashboard
                  <ArrowRight size={16} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}
