"use client";

import { FormEvent, useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { getCollector } from "@/lib/behavioral-collector";
import { AuthButton, AuthInlineMessage, AuthInput } from "@/components/auth/AuthPrimitives";
import { Eye, EyeClosed, Mail, Lock, User, Activity, Fingerprint, ShieldCheck, Type, AlertTriangle } from "lucide-react";
import { motion } from "framer-motion";
import { TypingDNA } from "@/components/behavioral/TypingDNA";
import { BiometricScanner } from "@/components/behavioral/BiometricScanner";
import { DataQualityRadar } from "@/components/behavioral/DataQualityRadar";

// ── Verification Prompts ───────────────────────────────────────────────────
const TYPING_PROMPTS = [
  "The quick brown fox jumps over the lazy dog",
  "Pack my box with five dozen liquor jugs",
  "A secure system operates invisibly but effectively",
  "I confirm this account belongs to me alone",
  "Banking security requires vigilant user behavior",
  "My password protects my financial identity today",
  "Every keystroke reveals the person behind the screen",
  "How vexingly quick daft zebras jump",
];

function computeMatchAccuracy(typed: string, target: string): number {
  if (!typed || !target) return 0;
  const t = typed.trim().toLowerCase();
  const p = target.trim().toLowerCase();
  let matches = 0;
  const maxLen = Math.max(t.length, p.length);
  for (let i = 0; i < Math.min(t.length, p.length); i++) {
    if (t[i] === p[i]) matches++;
  }
  return maxLen > 0 ? Math.round((matches / maxLen) * 100) : 0;
}

export default function SignUpPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [mfaSecret, setMfaSecret] = useState("");
  const [isEnrolled, setIsEnrolled] = useState(false);

  // ── OTP Verification State ─────────────────────────────────────────
  const [showOtp, setShowOtp] = useState(false);
  const [registeredUserId, setRegisteredUserId] = useState<number | null>(null);
  const [otpDigits, setOtpDigits] = useState(["" , "", "", "", "", ""]);
  const [otpError, setOtpError] = useState("");
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);
  const [devModeCode, setDevModeCode] = useState("");
  const [resendCooldown, setResendCooldown] = useState(0);
  const [errorType, setErrorType] = useState<"" | "user_exists" | "generic">("");

  // ── Behavioral Typing Prompt ──────────────────────────────────────────
  // Empty on server render to avoid hydration mismatch; randomized client-side.
  const [typingPrompt, setTypingPrompt] = useState("");
  useEffect(() => {
    setTypingPrompt(TYPING_PROMPTS[Math.floor(Math.random() * TYPING_PROMPTS.length)]);
  }, []);
  const [typedText, setTypedText] = useState("");
  const [pasteDetected, setPasteDetected] = useState(false);
  const typingRef = useRef<HTMLTextAreaElement>(null);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  // ── Live Analysis State ───────────────────────────────────────────────
  const [holdTimeSeries, setHoldTimeSeries] = useState<number[]>([]);
  const [flightTimeSeries, setFlightTimeSeries] = useState<number[]>([]);
  const [liveStats, setLiveStats] = useState<{
    wpm: number;
    correctionRate: number;
    sequence: string[];
    keystrokes: number;
    mouseEvents: number;
    holdMean: number;
    flightMean: number;
    typingAccuracy: number;
    digraphCount: number;
    pasteCount: number;
  }>({
    wpm: 0, correctionRate: 0, sequence: [],
    keystrokes: 0, mouseEvents: 0, holdMean: 0, flightMean: 0,
    typingAccuracy: 0, digraphCount: 0, pasteCount: 0,
  });

  // ── Start behavioral collection on page mount ─────────────────────────
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("SIGNUP");
    collector.reset();
    collector.start();

    // Poll for live stats
    const interval = setInterval(async () => {
      const snap = await collector.snapshot("signup_live");
      const ks = snap.keystroke_events;
      const ms = snap.mouse_events;
      const cog = snap.cognitive_events;
      const nav = snap.navigation_events;
      const backspaces = ks.filter(k => k.is_backspace).length;

      // Calculate WPM
      const elapsedMins = Math.max(0.01, (Date.now() - snap.window_start) / 60000);
      const wpm = Math.min(150, Math.round((ks.length / 5) / elapsedMins));

      // Correction rate
      const correctionRate = ks.length > 0 ? Math.round((backspaces / ks.length) * 100) : 0;

      // Hold/flight time analysis
      const holds = ks.map(k => k.hold_time).filter(h => h > 0 && h < 2000);
      const flights = ks.map(k => k.flight_time).filter(f => f > 0 && f < 5000);
      const holdMean = holds.length > 0 ? Math.round(holds.reduce((a, b) => a + b, 0) / holds.length) : 0;
      const flightMean = flights.length > 0 ? Math.round(flights.reduce((a, b) => a + b, 0) / flights.length) : 0;
      setHoldTimeSeries(holds);
      setFlightTimeSeries(flights);

      // Unique digraph counting
      const digraphs = new Set<string>();
      for (let i = 0; i < ks.length - 1; i++) {
        if (ks[i].key && ks[i+1].key && ks[i].key.length === 1 && ks[i+1].key.length === 1) {
          digraphs.add(ks[i].key + ks[i+1].key);
        }
      }

      // Paste detection count
      const pasteCount = cog.filter(c => c.type === "copy_paste").length;

      // Field sequence
      const seq = Array.from(new Set(nav.map(n => n.element_id).filter(Boolean)));

      setLiveStats({
        wpm, correctionRate,
        sequence: seq.slice(-5),
        keystrokes: ks.length,
        mouseEvents: ms.length,
        holdMean,
        flightMean,
        typingAccuracy: computeMatchAccuracy(typedText, typingPrompt),
        digraphCount: digraphs.size,
        pasteCount,
      });
    }, 500);

    return () => {
      clearInterval(interval);
      collector.stop();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update typing accuracy in real-time
  useEffect(() => {
    setLiveStats(prev => ({
      ...prev,
      typingAccuracy: computeMatchAccuracy(typedText, typingPrompt),
    }));
  }, [typedText, typingPrompt]);

  // ── Password Validation ───────────────────────────────────────────────
  const passwordChecks = {
    length: password.length >= 8,
    lowercase: /[a-z]/.test(password),
    uppercase: /[A-Z]/.test(password),
    digit: /\d/.test(password),
    special: /[@$!%*?&]/.test(password),
  };

  const calculatePasswordStrength = (pass: string) => {
    let score = 0;
    if (pass.length >= 8) score++;
    if (/[a-z]/.test(pass)) score++;
    if (/[A-Z]/.test(pass)) score++;
    if (/\d/.test(pass)) score++;
    if (/[@$!%*?&]/.test(pass)) score++;
    return score;
  };

  const strength = calculatePasswordStrength(password);
  const allPasswordValid = Object.values(passwordChecks).every(Boolean);
  const strengthLabels = ["", "Weak", "Fair", "Good", "Strong", "Excellent"];
  const strengthColors = ["bg-red-500", "bg-accent-danger", "bg-accent-warning", "bg-yellow-400", "bg-accent-success", "bg-emerald-400"];

  // ── Paste Prevention ──────────────────────────────────────────────────
  const handleVerifyPaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
    setPasteDetected(true);
    setTypedText("");
    setTimeout(() => setPasteDetected(false), 3000);
  }, []);

  // ── OTP Verification Handlers ─────────────────────────────────────────
  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    const newDigits = [...otpDigits];
    newDigits[index] = value.slice(-1);
    setOtpDigits(newDigits);
    setOtpError("");
    if (value && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otpDigits[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  const handleOtpPasteInput = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length > 0) {
      const newDigits = [...otpDigits];
      pasted.split("").forEach((d, i) => { newDigits[i] = d; });
      setOtpDigits(newDigits);
      otpRefs.current[Math.min(pasted.length, 5)]?.focus();
    }
  };

  const handleVerifyOtp = async () => {
    const code = otpDigits.join("");
    if (code.length !== 6) {
      setOtpError("Please enter the full 6-digit code.");
      return;
    }
    setIsVerifyingOtp(true);
    setOtpError("");
    try {
      const result = await apiClient<{
        success: boolean;
        data?: { mfa_secret?: string; mfa_provisioning_uri?: string };
        error?: string;
      }>("/v1/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ code, user_id: registeredUserId }),
      });
      if (result.success) {
        if (result.data?.mfa_secret) {
          setMfaSecret(result.data.mfa_secret);
        }
        setShowOtp(false);
        setIsEnrolled(true);
      } else {
        setOtpError(result.error || "Invalid code. Please try again.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Verification failed";
      setOtpError(msg.includes("INVALID_CODE") ? "Invalid or expired code. Please try again." : msg);
    } finally {
      setIsVerifyingOtp(false);
    }
  };

  const handleResendCode = async () => {
    if (resendCooldown > 0 || !registeredUserId) return;
    try {
      const result = await apiClient<{
        success: boolean;
        verification_code?: string;
        dev_mode?: boolean;
      }>("/v1/auth/resend-verification", {
        method: "POST",
        body: JSON.stringify({ user_id: registeredUserId }),
      });
      if (result.dev_mode && result.verification_code) {
        setDevModeCode(result.verification_code);
      }
      setResendCooldown(60);
      setOtpDigits(["", "", "", "", "", ""]);
      setOtpError("");
    } catch {
      setOtpError("Failed to resend code. Try again.");
    }
  };

  // Resend cooldown timer
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  // ── Submit ────────────────────────────────────────────────────────────
  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setErrorType("");

    if (username.length < 3) {
      setError("Username must be at least 3 characters.");
      return;
    }
    if (!allPasswordValid) {
      const missing: string[] = [];
      if (!passwordChecks.length) missing.push("at least 8 characters");
      if (!passwordChecks.lowercase) missing.push("a lowercase letter");
      if (!passwordChecks.uppercase) missing.push("an uppercase letter");
      if (!passwordChecks.digit) missing.push("a digit");
      if (!passwordChecks.special) missing.push("a special character (@$!%*?&)");
      setError(`Password must contain ${missing.join(", ")}.`);
      return;
    }

    const collector = getCollector();
    const preCheck = await collector.snapshot("signup_quality_check");
    if (preCheck.keystroke_events.length < 20) {
      setError("Please complete the typing verification below to proceed.");
      typingRef.current?.focus();
      return;
    }

    const typingAccuracy = computeMatchAccuracy(typedText, typingPrompt);
    if (typingAccuracy < 70) {
      setError("Please type the verification text more accurately.");
      typingRef.current?.focus();
      return;
    }

    setIsLoading(true);

    const enrollmentSeed = await collector.flush("NEW_ACCOUNT_ENROLLMENT");
    // Extract per-key/digraph profile for Bayesian enrollment (Session 0)
    const keystrokeProfile = collector.getKeystrokeProfile();

    try {
      const result = await apiClient<{
        data?: {
          user_id: number;
          requires_verification?: boolean;
          email?: string;
          verification_code?: string;
          dev_mode?: boolean;
          mfa_secret?: string;
          mfa_provisioning_uri?: string;
        };
        error?: string;
      }>("/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({
          username,
          email,
          password,
          behavioral_data: enrollmentSeed,
          enrollment_seed: {
            keystroke_events: enrollmentSeed.keystroke_events,
            mouse_events: enrollmentSeed.mouse_events,
            cognitive_events: enrollmentSeed.cognitive_events,
            typed_prompt: typingPrompt,
            typed_text: typedText,
            match_accuracy: typingAccuracy,
            context: "NEW_ACCOUNT_ENROLLMENT",
            total_keystrokes: enrollmentSeed.keystroke_events.length,
            total_mouse: enrollmentSeed.mouse_events.length,
            keystroke_profile: keystrokeProfile,
          },
        }),
      });

      if (!result.data?.user_id) {
        setError(result.error ?? "Registration failed");
        setIsLoading(false);
        return;
      }

      localStorage.setItem("bba_enrollment_completed", "1");
      localStorage.setItem("bba_enrollment_required", "5");

      if (result.data.requires_verification) {
        // Show OTP verification step
        setRegisteredUserId(result.data.user_id);
        setShowOtp(true);
        if (result.data.dev_mode && result.data.verification_code) {
          setDevModeCode(result.data.verification_code);
        }
      } else {
        // Auto-verified (no mail backend) — go straight to success
        if (result.data.mfa_secret) setMfaSecret(result.data.mfa_secret);
        setIsEnrolled(true);
      }
      setIsLoading(false);
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : "Registration failed";
      if (raw.includes("already taken") || raw.includes("USERNAME_TAKEN")) {
        setError("This username is already taken.");
        setErrorType("user_exists");
      } else if (raw.includes("already exists") || raw.includes("EMAIL_TAKEN")) {
        setError("An account with this email already exists.");
        setErrorType("user_exists");
      } else if (raw.includes("Password must contain")) {
        const match = raw.match(/Password must contain a? ?(.+)/i);
        setError(match ? `Password must contain ${match[1]}` : raw);
        setErrorType("generic");
      } else if (raw.includes("VALIDATION_ERROR")) {
        setError("Please check your inputs and try again.");
        setErrorType("generic");
      } else {
        setError(raw);
        setErrorType("generic");
      }
      setIsLoading(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen w-full relative overflow-hidden flex items-center justify-center p-4 lg:p-8 bg-bg bg-grid-pattern">
      {/* Background Orbs */}
      <div className="absolute top-1/4 -left-64 w-[500px] h-[500px] bg-accent-primary/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 -right-64 w-[500px] h-[500px] bg-accent-success/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Cyber-ring Scanner Animation */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] pointer-events-none opacity-20">
        <motion.div
          className="absolute inset-0 rounded-full border-[1px] border-accent-primary/20"
          animate={{ rotate: 360, scale: [1, 1.05, 1] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
        <motion.div
          className="absolute inset-8 rounded-full border-[1px] border-accent-success/20 border-dashed"
          animate={{ rotate: -360, scale: [1, 0.95, 1] }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
        />
      </div>

      <BiometricScanner isVisible={isLoading} status="Encrypting enrollment seed..." />

      {isEnrolled ? (
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md relative z-10 glass-panel-glow rounded-3xl p-8 overflow-hidden"
        >
          {/* Top Edge Glow line */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-accent-primary to-transparent opacity-50" />
          
          <div className="space-y-6 text-center">
            <div className="mx-auto w-16 h-16 bg-emerald-500/10 flex items-center justify-center rounded-full border border-emerald-500/20">
              <ShieldCheck className="w-8 h-8 text-emerald-400" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-bold tracking-tight text-fg">Account Created Successfully</h3>
              <p className="text-sm text-muted">
                Your email has been verified and your behavioral profile has been seeded.
              </p>
            </div>
            <div className="bg-slate-900/60 border border-border rounded-xl p-5 text-left space-y-4">
              <div className="flex items-start gap-3">
                <Activity className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-medium text-fg">Enrollment Phase: 1 of 5 Sessions</h4>
                  <p className="text-xs text-muted mt-1 leading-relaxed">
                    Your baseline profile has been seeded. The next 4 times you log in, we will continue building your behavioral profile silently.
                  </p>
                </div>
              </div>
              <div className="h-1.5 w-full bg-black/40 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-400 rounded-full" style={{ width: `${(1 / 5) * 100}%` }} />
              </div>
            </div>
            {mfaSecret && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-left">
                <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2">Save MFA Secret</h4>
                <div className="flex items-center gap-2">
                  <p className="flex-1 text-xs text-amber-400/80 font-mono bg-black/40 p-2 rounded">{mfaSecret}</p>
                  <button 
                    onClick={() => navigator.clipboard.writeText(mfaSecret)} 
                    className="bg-black/40 hover:bg-black/60 text-amber-400/80 p-2 rounded transition-colors text-xs font-medium"
                  >
                    Copy
                  </button>
                </div>
              </div>
            )}
            <Link href="/login" className="block w-full">
              <AuthButton className="w-full">Continue to Login</AuthButton>
            </Link>
          </div>
        </motion.div>
      ) : showOtp ? (
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md relative z-10 glass-panel-glow rounded-3xl p-8 overflow-hidden"
        >
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-50" />
          <div className="space-y-6 text-center">
            <div className="mx-auto w-16 h-16 bg-cyan-500/10 flex items-center justify-center rounded-full border border-cyan-500/20">
              <Mail className="w-8 h-8 text-cyan-400" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-bold tracking-tight text-fg">Verify your email</h3>
              <p className="text-sm text-muted">
                We sent a 6-digit code to <strong className="text-fg">{email}</strong>
              </p>
            </div>

            {devModeCode && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3">
                <p className="text-xs text-amber-400">Dev Mode — Your code: <strong className="font-mono text-lg tracking-widest">{devModeCode}</strong></p>
              </div>
            )}

            <div className="flex gap-2.5 justify-center">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <input
                  key={i}
                  ref={(el) => { otpRefs.current[i] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={otpDigits[i]}
                  onChange={(e) => handleOtpChange(i, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(i, e)}
                  onPaste={handleOtpPasteInput}
                  className="w-12 h-14 text-center text-2xl font-mono bg-black/40 border border-white/10 rounded-xl text-fg focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30 outline-none transition-all"
                />
              ))}
            </div>

            {otpError && (
              <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{otpError}</p>
            )}

            <AuthButton
              onClick={handleVerifyOtp}
              disabled={isVerifyingOtp || otpDigits.some((d) => !d)}
              className="w-full"
            >
              {isVerifyingOtp ? "Verifying..." : "Verify Email"}
            </AuthButton>

            <p className="text-xs text-muted">
              Didn&apos;t receive the code?{" "}
              <button
                onClick={handleResendCode}
                disabled={resendCooldown > 0}
                className="text-accent-primary hover:text-blue-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : "Resend Code"}
              </button>
            </p>
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-[1000px] h-[calc(100vh-2rem)] max-h-[760px] relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6 items-stretch"
        >
          {/* ── Left Column: Form ── */}
          <div className="lg:col-span-5 glass-panel-glow rounded-3xl p-5 lg:p-7 relative overflow-hidden flex flex-col h-full bg-slate-950/60 border border-white/5">
            <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-accent-primary to-transparent opacity-50" />
            
            <div className="flex items-center gap-3 mb-5 shrink-0">
              <motion.div 
                className="w-10 h-10 rounded-xl bg-black/40 border border-border flex items-center justify-center text-accent-primary relative overflow-hidden shrink-0"
                whileHover={{ scale: 1.05 }}
              >
                <div className="absolute inset-0 bg-accent-primary/10" />
                <ShieldCheck size={20} className="relative z-10" />
              </motion.div>
              <div>
                <h1 className="text-xl font-bold tracking-tight text-fg">Create account</h1>
                <p className="text-muted text-xs leading-relaxed">
                  Secured by invisible behavioral patterns.
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="flex-1 flex flex-col justify-between overflow-y-auto pr-1 custom-scrollbar">
              <div className="space-y-3.5">
                {error && errorType === "user_exists" ? (
                  <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                      <p className="text-sm text-amber-300">{error}</p>
                    </div>
                    <div className="flex gap-4 justify-center">
                      <Link href="/login" className="text-xs text-accent-primary hover:text-blue-400 transition-colors font-medium">
                        Log in instead →
                      </Link>
                      <Link href="/forgot-password" className="text-xs text-accent-primary hover:text-blue-400 transition-colors font-medium">
                        Forgot password?
                      </Link>
                    </div>
                  </div>
                ) : error ? <AuthInlineMessage tone="error">{error}</AuthInlineMessage> : null}

                {/* Username */}
                <div className="space-y-1">
                  <label htmlFor="signup-username" className="text-[10px] font-semibold text-muted uppercase tracking-wider ml-1">Username</label>
                  <div className="relative">
                    <User className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-2" />
                    <AuthInput
                      id="signup-username"
                      type="text"
                      name="username"
                      autoComplete="username"
                      placeholder="Enter username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      onPaste={(e) => e.preventDefault()}
                      onCopy={(e) => e.preventDefault()}
                      required
                      className="pl-8 py-2 text-sm"
                    />
                  </div>
                </div>

                {/* Email */}
                <div className="space-y-1">
                  <label htmlFor="signup-email" className="text-[10px] font-semibold text-muted uppercase tracking-wider ml-1">Email</label>
                  <div className="relative">
                    <Mail className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-2" />
                    <AuthInput
                      id="signup-email"
                      type="email"
                      name="email"
                      autoComplete="email"
                      placeholder="Enter email address"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      onPaste={(e) => e.preventDefault()}
                      onCopy={(e) => e.preventDefault()}
                      required
                      className="pl-8 py-2 text-sm"
                    />
                  </div>
                </div>

                {/* Password */}
                <div className="space-y-1">
                  <label htmlFor="signup-password" className="text-[10px] font-semibold text-muted uppercase tracking-wider ml-1">Password</label>
                  <div className="relative">
                    <Lock className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-2" />
                    <AuthInput
                      id="signup-password"
                      type={showPassword ? "text" : "password"}
                      name="password"
                      autoComplete="new-password"
                      placeholder="Secure password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      onPaste={(e) => e.preventDefault()}
                      onCopy={(e) => e.preventDefault()}
                      required
                      className="pl-8 pr-8 py-2 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-2 hover:text-fg transition-colors"
                    >
                      {showPassword ? <Eye className="w-3.5 h-3.5" /> : <EyeClosed className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                {/* Password Strength */}
                {password.length > 0 && (
                  <div className="space-y-1.5 mt-1">
                    <div className="flex justify-between items-center text-[9px] uppercase tracking-wider">
                      <span className="text-muted">Strength</span>
                      <span className={strengthColors[Math.max(0, strength)].replace("bg-", "text-")}>
                        {strengthLabels[Math.max(0, strength)]}
                      </span>
                    </div>
                    <div className="flex gap-1 h-1">
                      {[1, 2, 3, 4, 5].map((level) => (
                        <div
                          key={level}
                          className={`h-full flex-1 rounded-full transition-colors duration-300 ${
                            level <= strength ? strengthColors[strength] : "bg-white/10"
                          }`}
                        />
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-1">
                      {[
                        { label: "8+ chars", ok: passwordChecks.length },
                        { label: "Lowercase", ok: passwordChecks.lowercase },
                        { label: "Uppercase", ok: passwordChecks.uppercase },
                        { label: "Digit", ok: passwordChecks.digit },
                        { label: "Special", ok: passwordChecks.special },
                      ].map((c) => (
                        <span key={c.label} className={`text-[9px] ${c.ok ? "text-emerald-400" : "text-white/30"}`}>
                          {c.ok ? "✓" : "○"} {c.label}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* ── Typing Verification Widget ── */}
                <div className="pt-3 mt-2 border-t border-white/5 space-y-2.5">
                  <div className="flex items-center gap-1.5">
                    <Fingerprint className="w-3.5 h-3.5 text-cyan-400" />
                    <label htmlFor="behavioral-verify-text" className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider">
                      Seed Your Typing Profile
                    </label>
                  </div>
                  
                  <div className="bg-cyan-500/5 border border-cyan-500/10 rounded px-2.5 py-1.5">
                    <p className="text-[10px] text-cyan-400/80 leading-snug">
                      Type this naturally — we're capturing your rhythm. Pasting is disabled.
                    </p>
                  </div>

                  <div suppressHydrationWarning className="bg-slate-900/60 border border-cyan-500/20 rounded-md px-3 py-2 font-mono text-[11px] leading-tight text-cyan-300 tracking-wide select-none">
                    {typingPrompt || "\u00A0"}
                  </div>

                  <div className="relative">
                    <Type className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-2" />
                    <textarea
                      ref={typingRef}
                      id="behavioral-verify-text"
                      value={typedText}
                      onChange={(e) => setTypedText(e.target.value)}
                      onPaste={handleVerifyPaste}
                      placeholder="Type the text above here..."
                      className="w-full bg-black/40 border border-white/10 rounded-md pl-8 pr-3 py-2 text-xs text-fg placeholder:text-muted-2 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/40 font-mono resize-none transition-all h-[52px]"
                      autoComplete="off"
                      spellCheck={false}
                    />
                  </div>

                  {pasteDetected && (
                    <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded px-2 py-1.5 animate-pulse">
                      <AlertTriangle className="w-3 h-3 text-red-400" />
                      <span className="text-[9px] text-red-400 font-medium">
                        Paste detected — type manually.
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-5 pt-3 sticky bottom-0 bg-slate-950/60 backdrop-blur-md pb-1">
                <AuthButton type="submit" disabled={isLoading || !allPasswordValid} className="w-full py-2 text-sm">
                  {isLoading ? "Provisioning..." : "Create Account"}
                </AuthButton>
                <p className="text-center text-[10px] text-muted mt-3">
                  Already have an account?{" "}
                  <Link href="/login" className="text-accent-primary hover:text-blue-400 transition-colors">
                    Sign in
                  </Link>
                </p>
              </div>
            </form>
          </div>

          {/* ── Right Column: Behavioral Profile ── */}
          <div className="lg:col-span-7 glass-panel-glow rounded-3xl p-5 lg:p-7 relative overflow-hidden bg-slate-950/60 border border-white/5 flex flex-col h-full">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/10 shrink-0">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                <h2 className="text-[11px] uppercase tracking-widest font-bold text-cyan-400">Behavioral Profile Baseline</h2>
              </div>
              <div className="flex items-center gap-1.5 px-2.5 py-0.5 bg-black/40 rounded-full border border-white/5">
                <span className={`w-1.5 h-1.5 rounded-full ${liveStats.keystrokes >= 20 ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
                <span className="text-[9px] font-mono text-muted font-bold">{liveStats.keystrokes >= 20 ? 'READY' : 'RECORDING'}</span>
              </div>
            </div>

            {/* ── Live Stats Grid ── */}
            <div className="grid grid-cols-2 gap-3 mb-3 flex-1">
              {/* Left Data Column */}
              <div className="space-y-3 flex flex-col">
                <div className="bg-black/30 rounded-xl p-3 border border-white/5 flex-1 flex flex-col justify-center">
                  <div className="text-[9px] uppercase tracking-wider text-muted font-bold mb-2">Keystroke Data</div>
                  <div className="space-y-1.5">
                    <StatRow label="Total Keys" value={liveStats.keystrokes} color={liveStats.keystrokes > 20 ? "text-emerald-400" : "text-amber-400"} />
                    <StatRow label="Hold Time" value={`${liveStats.holdMean}ms`} color="text-blue-400" />
                    <StatRow label="Flight Time" value={`${liveStats.flightMean}ms`} color="text-purple-400" />
                    <StatRow label="Digraphs" value={liveStats.digraphCount} color={liveStats.digraphCount > 15 ? "text-emerald-400" : "text-slate-300"} />
                  </div>
                </div>

                <div className="bg-black/30 rounded-xl p-3 border border-white/5 flex-1 flex flex-col justify-center">
                  <div className="text-[9px] uppercase tracking-wider text-muted font-bold mb-2">Behavioral Signals</div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <StatBox label="WPM" value={liveStats.wpm} color={liveStats.wpm < 20 ? "text-amber-400" : "text-emerald-400"} />
                    <StatBox label="Corrections" value={`${liveStats.correctionRate}%`} color="text-slate-300" />
                    <StatBox label="Mouse Events" value={liveStats.mouseEvents} color="text-slate-300" />
                    <StatBox label="Paste" value={liveStats.pasteCount > 0 ? `⚠ ${liveStats.pasteCount}` : "0 ✓"} color={liveStats.pasteCount > 0 ? "text-red-400" : "text-emerald-400"} />
                  </div>
                </div>
              </div>

              {/* Right Data Column */}
              <div className="space-y-3 flex flex-col">
                <div className="flex flex-col items-center justify-center bg-black/30 rounded-xl p-3 border border-white/5 flex-[2]">
                  <DataQualityRadar
                    digraphs={liveStats.digraphCount}
                    consistency={Math.max(0, 100 - liveStats.correctionRate)}
                    rhythm={holdTimeSeries.length > 3 ? Math.min(100, Math.round(100 - (Math.abs(liveStats.holdMean - 120) / 120) * 50)) : 0}
                    volume={Math.min(100, Math.round((liveStats.keystrokes / 40) * 100))}
                    accuracy={liveStats.typingAccuracy}
                    size={140}
                  />
                  <span className="text-[9px] text-muted-2 font-mono mt-3 uppercase tracking-widest">Data Quality</span>
                </div>

                <div className="bg-black/30 rounded-xl p-3 border border-white/5 flex-1 flex flex-col justify-center">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[9px] uppercase tracking-wider text-muted font-bold">Enrollment Seed Quality</span>
                    <span className={`text-[9px] font-mono font-semibold ${
                      liveStats.keystrokes >= 40 && liveStats.digraphCount >= 15 ? "text-emerald-400" :
                      liveStats.keystrokes >= 20 ? "text-yellow-400" : "text-red-400"
                    }`}>
                      {liveStats.keystrokes >= 40 && liveStats.digraphCount >= 15 ? "✓ Excellent" :
                       liveStats.keystrokes >= 20 ? "◐ Sufficient" : "○ Need typing"}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-black/40 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${
                        liveStats.keystrokes >= 40 && liveStats.digraphCount >= 15 ? "bg-gradient-to-r from-emerald-500 to-emerald-400" :
                        liveStats.keystrokes >= 20 ? "bg-gradient-to-r from-yellow-500 to-yellow-400" : "bg-gradient-to-r from-red-500 to-red-400"
                      }`}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(100, ((liveStats.keystrokes / 40) * 50) + ((liveStats.digraphCount / 15) * 50))}%` }}
                      transition={{ duration: 0.5, ease: "easeOut" }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* ── Bio-Signature & Navigation Footer ── */}
            <div className="bg-black/30 rounded-xl p-3 border border-white/5 flex flex-col shrink-0">
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <div className="flex items-center gap-1.5">
                    <Fingerprint className="w-3.5 h-3.5 text-cyan-400" />
                    <span className="text-[9px] uppercase tracking-widest text-cyan-400 font-bold">Unique Bio-Signature</span>
                  </div>
                  <span className="text-[9px] text-muted font-mono">{holdTimeSeries.length} samples</span>
                </div>
                <div className="bg-black/20 rounded border border-white/5 p-1.5">
                  <TypingDNA holdTimes={holdTimeSeries} flightTimes={flightTimeSeries} height={32} />
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-white/5 space-y-2.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[9px] uppercase tracking-wider text-muted font-bold">Navigation:</span>
                  {liveStats.sequence.length === 0 ? (
                    <span className="text-[9px] text-slate-500 italic">Waiting...</span>
                  ) : (
                    liveStats.sequence.map((id, idx) => (
                      <span key={idx} className="px-1.5 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20 text-[8px] font-mono text-cyan-400">
                        {idx + 1}. {id.replace('signup-', '').replace('behavioral-verify-text', 'verify').replace('behavioral-', '')}
                      </span>
                    ))
                  )}
                </div>

                <div className="flex items-start gap-1.5">
                  <ShieldCheck className="w-3 h-3 text-cyan-400 mt-0.5 flex-shrink-0" />
                  <p className="text-[9px] text-cyan-400/80 leading-relaxed pr-1">
                    This data creates the foundation of your secure profile. Your next 4 logins will complete your behavioral fingerprint to ensure you are fully protected. No extra steps required!
                  </p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

function StatRow({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="flex items-center justify-between bg-black/40 rounded px-2.5 py-1 border border-white/5">
      <span className="text-[9px] text-muted">{label}</span>
      <span className={`text-[10px] font-mono font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="bg-black/40 rounded p-1.5 border border-white/5 flex flex-col items-center justify-center text-center">
      <span className={`text-[11px] font-mono font-bold ${color}`}>{value}</span>
      <span className="text-[7px] uppercase tracking-wider text-muted mt-0.5">{label}</span>
    </div>
  );
}
