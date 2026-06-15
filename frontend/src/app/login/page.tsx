"use client";

import { FormEvent, useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Lock, User, ShieldCheck, ArrowRight, Keyboard, Fingerprint, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { getCollector } from "@/lib/behavioral-collector";
import { TypingDNA } from "@/components/behavioral/TypingDNA";
import { BiometricScanner } from "@/components/behavioral/BiometricScanner";

type LoginPhase = "credentials" | "typing" | "blocked";

interface ChallengeData {
  challenge_token: string;
  typing_prompt: string;
  enrollment_phase: string;
  sessions_completed: number;
  sessions_required: number;
  username: string;
}

export default function LoginPage() {
  const router = useRouter();

  // ── Phase state machine ──────────────────────────────────────────────
  const [phase, setPhase] = useState<LoginPhase>("credentials");
  const [challengeData, setChallengeData] = useState<ChallengeData | null>(null);

  // ── Phase 1: Credentials ─────────────────────────────────────────────
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [remainingAttempts, setRemainingAttempts] = useState<number | null>(null);
  const [lockoutUntil, setLockoutUntil] = useState<number | null>(null);
  const [lockoutCountdown, setLockoutCountdown] = useState<string>("");

  // ── Phase 2: Typing Challenge ────────────────────────────────────────
  const [typedText, setTypedText] = useState("");
  const [isVerifying, setIsVerifying] = useState(false);
  const typingAreaRef = useRef<HTMLTextAreaElement>(null);

  // ── Live keystroke telemetry ──────────────────────────────────────────
  const [keystrokeCount, setKeystrokeCount] = useState(0);
  const [avgHoldTime, setAvgHoldTime] = useState(0);
  const [avgFlightTime, setAvgFlightTime] = useState(0);
  const [holdTimeSeries, setHoldTimeSeries] = useState<number[]>([]);
  const [flightTimeSeries, setFlightTimeSeries] = useState<number[]>([]);

  // ── Collector setup ──────────────────────────────────────────────────
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("LOGIN");
    collector.reset();
    collector.start();
    return () => collector.stop();
  }, []);

  // ── Poll collector for live stats ────────────────────────────────────
  useEffect(() => {
    if (phase !== "typing") return;
    const interval = setInterval(async () => {
      const collector = getCollector();
      const snap = await collector.snapshot("login_typing_live");
      const ks = snap.keystroke_events;
      setKeystrokeCount(ks.length);
      if (ks.length > 0) {
        const holds = ks.map((k: { hold_time: number }) => k.hold_time).filter((h: number) => h > 0 && h < 2000);
        const flights = ks.map((k: { flight_time: number }) => k.flight_time).filter((f: number) => f > 0 && f < 5000);
        setAvgHoldTime(holds.length > 0 ? Math.round(holds.reduce((a: number, b: number) => a + b, 0) / holds.length) : 0);
        setAvgFlightTime(flights.length > 0 ? Math.round(flights.reduce((a: number, b: number) => a + b, 0) / flights.length) : 0);
        setHoldTimeSeries(holds);
        setFlightTimeSeries(flights);
      }
    }, 300);
    return () => clearInterval(interval);
  }, [phase]);

  // Focus typing area when entering Phase 2
  useEffect(() => {
    if (phase === "typing" && typingAreaRef.current) {
      setTimeout(() => typingAreaRef.current?.focus(), 300);
    }
  }, [phase]);

  // ── Lockout countdown timer ──────────────────────────────────────────
  useEffect(() => {
    if (!lockoutUntil) { setLockoutCountdown(""); return; }
    const tick = () => {
      const remaining = lockoutUntil - Date.now();
      if (remaining <= 0) {
        setLockoutUntil(null);
        setLockoutCountdown("");
        setError("");
        return;
      }
      const mins = Math.floor(remaining / 60000);
      const secs = Math.floor((remaining % 60000) / 1000);
      setLockoutCountdown(`${mins}:${secs.toString().padStart(2, "0")}`);
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [lockoutUntil]);

  // ── Compute typing accuracy ──────────────────────────────────────────
  const typingAccuracy = challengeData?.typing_prompt
    ? Math.round(
        (typedText.split("").filter((c, i) => c === challengeData.typing_prompt[i]).length /
          Math.max(challengeData.typing_prompt.length, 1)) * 100
      )
    : 0;


  // ══════════════════════════════════════════════════════════════════════
  // Phase 1: Submit credentials
  // ══════════════════════════════════════════════════════════════════════
  const handleCredentialSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (lockoutUntil && lockoutUntil > Date.now()) {
      setError("Account is temporarily locked. Please wait.");
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        const details = data.error?.details || data.details || data;
        if (details.remaining_attempts !== undefined) {
          setRemainingAttempts(details.remaining_attempts);
        }
        if (details.lockout_until) {
          const isNum = typeof details.lockout_until === "number";
          setLockoutUntil(isNum ? details.lockout_until * 1000 : new Date(details.lockout_until).getTime());
        } else if (res.status === 429 || res.status === 423) {
          setLockoutUntil(Date.now() + 5 * 60 * 1000);
        }

        // Check if behaviorally blocked
        if (data.code === "BEHAVIORAL_BLOCKED" || res.status === 403) {
          setPhase("blocked");
          return;
        }

        throw new Error(data.error?.message || data.error || data.message || "Invalid credentials.");
      }

      // Success — transition to Phase 2
      setRemainingAttempts(null);
      setLockoutUntil(null);

      setChallengeData({
        challenge_token: data.challenge_token,
        typing_prompt: data.typing_prompt,
        enrollment_phase: data.enrollment_phase,
        sessions_completed: data.sessions_completed,
        sessions_required: data.sessions_required,
        username: data.username,
      });

      // Reset collector for Phase 2 typing
      const collector = getCollector();
      collector.reset();
      collector.start();

      setPhase("typing");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Login failed.";
      if (msg.toLowerCase().includes("fetch")) {
        setError("Network error: Could not connect to the server.");
      } else {
        setError(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ══════════════════════════════════════════════════════════════════════
  // Phase 2: Submit typing challenge
  // ══════════════════════════════════════════════════════════════════════
  const handleTypingSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!challengeData) return;

    setError("");
    setIsVerifying(true);

    const collector = getCollector();
    const behavioralData = await collector.flush("login_typing_verify");
    const keystrokeProfile = collector.getKeystrokeProfile();

    try {
      const res = await fetch("/api/auth/login-verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          challenge_token: challengeData.challenge_token,
          typed_text: typedText,
          behavioral_data: behavioralData,
          keystroke_profile: keystrokeProfile,
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        if (data.code === "BEHAVIORAL_BLOCKED" || res.status === 403) {
          setPhase("blocked");
          return;
        }
        if (data.code === "CHALLENGE_EXPIRED" || res.status === 401) {
          setError("Challenge expired. Please start again.");
          setPhase("credentials");
          return;
        }
        throw new Error(data.error || "Verification failed.");
      }

      // Store enrollment info
      if (data.enrollment) {
        const e = data.enrollment;
        if (e.sessions_completed !== undefined) localStorage.setItem("bba_enrollment_completed", String(e.sessions_completed));
        if (e.sessions_required !== undefined) localStorage.setItem("bba_enrollment_required", String(e.sessions_required));
      }

      if (data.session_id) {
        document.cookie = `session_id=${data.session_id}; path=/; SameSite=Lax; max-age=86400`;
      }

      if (data.mfa_required) {
        router.push("/otp");
      } else {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Verification failed.";
      setError(msg);
    } finally {
      setIsVerifying(false);
    }
  };

  // ══════════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════════
  return (
    <div className="flex flex-1 min-h-screen items-center justify-center relative font-sans p-4">
      {/* Biometric scanner overlay */}
      <BiometricScanner isVisible={isLoading || isVerifying} />

      <AnimatePresence mode="wait">
        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* PHASE 1: CREDENTIALS                                         */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {phase === "credentials" && (
          <motion.div
            key="credentials"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="z-10 w-full max-w-md bg-surface/40 backdrop-blur-xl border border-white/10 rounded-3xl shadow-2xl overflow-hidden"
          >
            <div className="h-1 bg-gradient-to-r from-accent-primary to-accent-secondary" />
            <div className="p-8 lg:p-10 relative flex flex-col justify-center">
              <div className="w-full mx-auto">
                {/* Branding */}
                <div className="flex items-center gap-2.5 mb-6">
                  <div className="w-8 h-8 bg-accent-primary/10 border border-accent-primary/30 rounded-lg flex items-center justify-center text-accent-primary">
                    <ShieldCheck size={18} />
                  </div>
                  <span className="text-lg font-bold tracking-tight text-fg">AetherAuth</span>
                </div>

                <div className="mb-5">
                  <h2 className="text-2xl font-bold text-fg tracking-tight mb-1">Netbanking Login</h2>
                  <p className="text-sm text-muted">Enter your User ID and Password.</p>
                </div>

                {/* Phishing Banner */}
                <div className="mb-4 p-2.5 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-start gap-2.5">
                  <ShieldCheck className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                  <div className="text-xs text-blue-100/80 leading-relaxed">
                    <span className="font-semibold text-blue-300">Security Advisory:</span> AetherAuth Bank will never ask for your Password, PIN, or OTP over phone, email, or SMS.
                  </div>
                </div>

                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="bg-accent-danger/10 border border-accent-danger/20 text-accent-danger px-4 py-3 rounded-xl mb-6 text-xs flex items-center gap-2"
                  >
                    <div className="w-1.5 h-1.5 rounded-full bg-accent-danger"></div>
                    {error}
                  </motion.div>
                )}

                {lockoutCountdown && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-amber-500/10 border border-amber-500/20 text-amber-400 px-4 py-3 rounded-xl mb-6 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Lock className="w-3.5 h-3.5" />
                        Account locked — try again in <span className="font-mono font-bold text-amber-300">{lockoutCountdown}</span>
                      </span>
                    </div>
                    <p className="mt-2 text-[10px] text-amber-400/60">
                      Too many failed attempts.{" "}
                      <Link href="/forgot-password" className="underline hover:text-amber-300 transition-colors">
                        Reset password
                      </Link>{" "}
                      or contact support.
                    </p>
                  </motion.div>
                )}

                {remainingAttempts !== null && remainingAttempts <= 3 && !lockoutCountdown && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="bg-amber-500/5 border border-amber-500/15 text-amber-400/80 px-3 py-2 rounded-lg mb-4 text-[11px] flex items-center gap-2"
                  >
                    <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" />
                    {remainingAttempts === 0
                      ? "No attempts remaining. Account will be locked."
                      : `${remainingAttempts} attempt${remainingAttempts > 1 ? "s" : ""} remaining before lockout.`}
                  </motion.div>
                )}

                <form onSubmit={handleCredentialSubmit} className="space-y-4">
                  <div className="space-y-1.5">
                    <label htmlFor="login-username" className="text-xs font-semibold text-muted ml-1 uppercase tracking-wider">Username / Email</label>
                    <div className="relative group">
                      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-muted-2 group-focus-within:text-accent-primary transition-colors">
                        <User className="w-4 h-4" />
                      </div>
                      <input
                        id="login-username"
                        type="text"
                        name="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        onPaste={(e) => e.preventDefault()}
                        onCopy={(e) => e.preventDefault()}
                        required
                        placeholder="Username or email address"
                        className="w-full bg-black/20 border border-border text-fg rounded-xl py-3 pl-11 pr-4 text-sm outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/30 transition-all placeholder:text-muted-2 font-mono"
                        aria-label="Username or email address"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between ml-1">
                      <label htmlFor="login-password" className="text-xs font-semibold text-muted uppercase tracking-wider">Password</label>
                      <div className="flex items-center gap-2">
                        <Link href="/forgot-username" className="text-[10px] font-medium text-accent-primary hover:text-blue-400 transition-colors">
                          Forgot User ID?
                        </Link>
                        <span className="text-muted text-[10px]">|</span>
                        <Link href="/forgot-password" className="text-[10px] font-medium text-accent-primary hover:text-blue-400 transition-colors">
                          Forgot Password?
                        </Link>
                      </div>
                    </div>
                    <div className="relative group">
                      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-muted-2 group-focus-within:text-accent-primary transition-colors">
                        <Lock className="w-4 h-4" />
                      </div>
                      <input
                        id="login-password"
                        type={showPassword ? "text" : "password"}
                        name="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        onPaste={(e) => e.preventDefault()}
                        onCopy={(e) => e.preventDefault()}
                        required
                        placeholder="Enter your password"
                        className="w-full bg-black/20 border border-border text-fg rounded-xl py-3 pl-11 pr-12 text-sm outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/30 transition-all placeholder:text-muted-2 font-mono"
                        aria-label="Password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        aria-label={showPassword ? "Hide password" : "Show password"}
                        className="absolute inset-y-0 right-0 pr-4 flex items-center text-muted-2 hover:text-fg transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full bg-accent-primary hover:bg-blue-600 text-white font-medium rounded-xl mt-2 transition-colors relative overflow-hidden group disabled:opacity-90 disabled:cursor-not-allowed"
                  >
                    {isLoading ? (
                      <div className="w-full relative h-12 flex items-center justify-center gap-3">
                        <div className="absolute inset-0 bg-blue-600/50">
                          <motion.div
                            initial={{ width: "0%" }}
                            animate={{ width: "100%" }}
                            transition={{ duration: 1.5, ease: "easeInOut" }}
                            className="h-full bg-blue-500/50"
                          />
                        </div>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin relative z-10"></div>
                        <span className="text-sm relative z-10 font-medium">Verifying credentials...</span>
                      </div>
                    ) : (
                      <div className="w-full h-12 flex items-center justify-center gap-2">
                        Continue
                        <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                      </div>
                    )}
                  </button>
                </form>

                <div className="mt-5 pt-4 border-t border-border flex items-center justify-between text-xs">
                  <span className="text-muted">No account yet?</span>
                  <Link href="/signup" className="text-accent-primary font-medium hover:text-blue-400 transition-colors">
                    Create account
                  </Link>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* PHASE 2: TYPING CHALLENGE                                     */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {phase === "typing" && challengeData && (
          <motion.div
            key="typing"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="z-10 w-full max-w-lg bg-surface/40 backdrop-blur-xl border border-white/10 rounded-3xl shadow-2xl overflow-hidden"
          >
            <div className="h-1 bg-gradient-to-r from-cyan-500 to-blue-500" />
            <div className="p-8 lg:p-10">
              {/* Header */}
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-cyan-500/10 border border-cyan-500/30 rounded-xl flex items-center justify-center">
                  <Fingerprint className="w-5 h-5 text-cyan-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-fg tracking-tight">Verify Your Identity</h2>
                  <p className="text-xs text-muted">
                    Welcome back, <span className="text-cyan-400 font-medium">{challengeData.username}</span>
                  </p>
                </div>
              </div>

              {/* ── Dynamic Enrollment / Profile Status Badge ────────────── */}
              {challengeData && (() => {
                const completed = challengeData.sessions_completed;
                const required = challengeData.sessions_required;
                const current = completed + 1;
                const isCollecting = challengeData.enrollment_phase === "collecting";
                const isEnrolled = challengeData.enrollment_phase === "active" || challengeData.enrollment_phase === "ready";
                const progressPct = isEnrolled ? 100 : Math.min(100, (current / required) * 100);

                return (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className={`mb-5 rounded-xl px-4 py-3 flex items-center gap-3 ${
                      isEnrolled
                        ? "bg-emerald-500/10 border border-emerald-500/20"
                        : "bg-cyan-500/10 border border-cyan-500/20"
                    }`}
                  >
                    {/* Counter badge */}
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm ${
                      isEnrolled
                        ? "bg-emerald-500/20 text-emerald-400"
                        : "bg-cyan-500/20 text-cyan-400"
                    }`}>
                      {isEnrolled ? "✓" : `${current}/${required}`}
                    </div>

                    {/* Text */}
                    <div className="flex-1 min-w-0">
                      <div className={`text-xs font-semibold ${isEnrolled ? "text-emerald-300" : "text-cyan-300"}`}>
                        {isEnrolled ? "Typing Profile Active" : "Building Your Typing Profile"}
                      </div>
                      <div className={`text-[10px] ${isEnrolled ? "text-emerald-400/60" : "text-cyan-400/60"}`}>
                        {isEnrolled
                          ? `${completed} sessions enrolled — verifying your identity`
                          : `Session ${current} of ${required} — type naturally`}
                      </div>
                    </div>

                    {/* Session dot indicators + progress bar */}
                    <div className="flex flex-col items-end gap-1.5 ml-auto">
                      {/* Session dots */}
                      <div className="flex gap-1">
                        {Array.from({ length: required }, (_, i) => (
                          <div
                            key={i}
                            className={`w-2 h-2 rounded-full transition-all duration-500 ${
                              i < completed
                                ? isEnrolled ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" : "bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.5)]"
                                : i === completed && isCollecting
                                  ? "bg-cyan-400/60 animate-pulse"
                                  : "bg-white/10"
                            }`}
                          />
                        ))}
                      </div>
                      {/* Progress bar */}
                      <div className="h-1 w-20 bg-black/30 rounded-full overflow-hidden">
                        <motion.div
                          className={`h-full rounded-full ${isEnrolled ? "bg-emerald-400" : "bg-cyan-400"}`}
                          initial={{ width: 0 }}
                          animate={{ width: `${progressPct}%` }}
                          transition={{ duration: 0.8, ease: "easeOut" }}
                        />
                      </div>
                    </div>
                  </motion.div>
                );
              })()}

              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="bg-accent-danger/10 border border-accent-danger/20 text-accent-danger px-4 py-3 rounded-xl mb-5 text-xs flex items-center gap-2"
                >
                  <div className="w-1.5 h-1.5 rounded-full bg-accent-danger"></div>
                  {error}
                </motion.div>
              )}

              <form onSubmit={handleTypingSubmit} className="space-y-5">
                {/* Prompt display */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted ml-1 uppercase tracking-wider flex items-center gap-2">
                    <Keyboard className="w-3.5 h-3.5" />
                    Type the following text exactly
                  </label>
                  <div className="bg-black/30 border border-cyan-500/20 rounded-xl p-4 font-mono text-sm text-cyan-300 leading-relaxed select-none relative overflow-hidden">
                    <div className="absolute inset-0 opacity-5 pointer-events-none" style={{ backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 20px, rgba(6, 182, 212, 0.1) 20px, rgba(6, 182, 212, 0.1) 21px)" }} />
                    <span className="relative z-10">{challengeData.typing_prompt}</span>
                  </div>
                </div>

                {/* Typing area */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-muted ml-1 uppercase tracking-wider">Your Input</label>
                    <span className={`text-[10px] font-mono ${typingAccuracy >= 95 ? "text-emerald-400" : typingAccuracy >= 70 ? "text-amber-400" : "text-muted"}`}>
                      Accuracy: {typingAccuracy}%
                    </span>
                  </div>
                  <textarea
                    ref={typingAreaRef}
                    id="login-typing-challenge"
                    value={typedText}
                    onChange={(e) => setTypedText(e.target.value)}
                    onPaste={(e) => e.preventDefault()}
                    onCopy={(e) => e.preventDefault()}
                    rows={3}
                    placeholder="Start typing the text above..."
                    className="w-full bg-black/20 border border-border text-fg rounded-xl py-3 px-4 text-sm outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30 transition-all placeholder:text-muted-2 font-mono resize-none"
                  />
                </div>

                {/* ── Live Keystroke Telemetry ─────────────────────────────── */}
                <div className="bg-accent-primary/5 border border-accent-primary/15 rounded-xl px-4 py-3 min-h-[76px] flex flex-col justify-center">
                  <div className="flex items-center gap-2 mb-3">
                    <Keyboard className="w-3.5 h-3.5 text-accent-primary" />
                    <span className="text-[10px] uppercase tracking-widest font-bold text-accent-primary">Live Keystroke Capture</span>
                  </div>
                  {keystrokeCount === 0 ? (
                    <div className="text-xs text-muted font-mono italic">Waiting for keystrokes...</div>
                  ) : (
                    <div className="grid grid-cols-3 gap-4 text-[10px] font-mono text-muted">
                      <div>
                        <div className="mb-1">Keystrokes: <span className="text-fg font-semibold">{keystrokeCount}</span></div>
                        <div className="h-1 bg-black/40 rounded-full overflow-hidden"><div className="h-full bg-emerald-500 rounded-full transition-all duration-300" style={{ width: `${Math.min(100, keystrokeCount * 2)}%` }}></div></div>
                      </div>
                      <div>
                        <div className="mb-1">Hold: <span className="text-fg font-semibold">{avgHoldTime}ms</span></div>
                        <div className="h-1 bg-black/40 rounded-full overflow-hidden"><div className="h-full bg-cyan-500 rounded-full transition-all duration-300" style={{ width: `${Math.min(100, (avgHoldTime / 300) * 100)}%` }}></div></div>
                      </div>
                      <div>
                        <div className="mb-1">Flight: <span className="text-fg font-semibold">{avgFlightTime}ms</span></div>
                        <div className="h-1 bg-black/40 rounded-full overflow-hidden"><div className="h-full bg-blue-500 rounded-full transition-all duration-300" style={{ width: `${Math.min(100, (avgFlightTime / 600) * 100)}%` }}></div></div>
                      </div>
                    </div>
                  )}
                  {keystrokeCount > 0 && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[9px] uppercase tracking-widest text-muted font-mono">Bio-Signature</span>
                        <span className="text-[9px] text-accent-primary font-mono">{keystrokeCount} events</span>
                      </div>
                      <TypingDNA holdTimes={holdTimeSeries} flightTimes={flightTimeSeries} height={36} />
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={isVerifying || typedText.length < 10}
                  className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium rounded-xl transition-all relative overflow-hidden group disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isVerifying ? (
                    <div className="w-full relative h-12 flex items-center justify-center gap-3">
                      <div className="absolute inset-0 bg-cyan-600/50">
                        <motion.div
                          initial={{ width: "0%" }}
                          animate={{ width: "100%" }}
                          transition={{ duration: 2.5, ease: "easeInOut" }}
                          className="h-full bg-cyan-500/50"
                        />
                      </div>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin relative z-10"></div>
                      <span className="text-sm relative z-10 font-medium">Analyzing behavioral signature...</span>
                    </div>
                  ) : (
                    <div className="w-full h-12 flex items-center justify-center gap-2">
                      <Fingerprint className="w-4 h-4" />
                      Verify Identity
                    </div>
                  )}
                </button>
              </form>

              {/* Footer */}
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-2.5 text-[10px] text-muted font-mono">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(6,182,212,0.6)]"></span>
                  <span>Behavioral profiling active</span>
                </div>
                <button
                  onClick={() => { setPhase("credentials"); setError(""); setTypedText(""); }}
                  className="text-[10px] text-muted hover:text-fg transition-colors font-mono"
                >
                  ← Back to login
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* PHASE: BLOCKED                                                */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {phase === "blocked" && (
          <motion.div
            key="blocked"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="z-10 w-full max-w-md bg-surface/40 backdrop-blur-xl border border-red-500/20 rounded-3xl shadow-2xl overflow-hidden"
          >
            <div className="h-1 bg-gradient-to-r from-red-500 to-orange-500" />
            <div className="p-8 lg:p-10 text-center">
              <div className="w-16 h-16 mx-auto mb-6 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center justify-center">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>

              <h2 className="text-2xl font-bold text-fg mb-2">Access Denied</h2>
              <p className="text-sm text-muted mb-6 leading-relaxed">
                Unusual typing pattern detected. For your security, this account has been temporarily locked.
              </p>

              <div className="bg-red-500/5 border border-red-500/15 rounded-xl p-4 mb-6 text-left">
                <div className="text-xs text-red-300 font-semibold mb-1">What happened?</div>
                <div className="text-[11px] text-red-400/70 leading-relaxed">
                  Your typing rhythm did not match your established behavioral profile. This could mean someone else is trying to access your account.
                </div>
              </div>

              <div className="bg-blue-500/5 border border-blue-500/15 rounded-xl p-4 mb-6 text-left">
                <div className="text-xs text-blue-300 font-semibold mb-1">How to recover</div>
                <div className="text-[11px] text-blue-400/70 leading-relaxed">
                  We&apos;ve sent a recovery link to your registered email. Click the link to verify your identity and unlock your account.
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <button
                  onClick={() => { setPhase("credentials"); setError(""); }}
                  className="w-full h-11 bg-white/5 hover:bg-white/10 border border-white/10 text-fg font-medium rounded-xl text-sm transition-colors"
                >
                  ← Try again
                </button>
                <Link
                  href="/forgot-password"
                  className="text-xs text-accent-primary hover:text-blue-400 transition-colors"
                >
                  Reset password instead
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
