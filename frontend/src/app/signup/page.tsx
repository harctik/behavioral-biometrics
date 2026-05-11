"use client";

import { FormEvent, useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { getCollector } from "@/lib/behavioral-collector";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthButton, AuthInlineMessage, AuthInput } from "@/components/auth/AuthPrimitives";
import { Eye, EyeClosed, Mail, Lock, User, Activity, Fingerprint, ShieldCheck, Type, AlertTriangle } from "lucide-react";

// ── Verification Prompts ───────────────────────────────────────────────────
// Pangrams and sentences designed for maximum digraph coverage
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

function getRandomPrompt() {
  return TYPING_PROMPTS[Math.floor(Math.random() * TYPING_PROMPTS.length)];
}

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
  const [mfaSecret, setMfaSecret] = useState("");

  // ── Behavioral Typing Prompt ──────────────────────────────────────────
  const [typingPrompt] = useState(() => getRandomPrompt());
  const [typedText, setTypedText] = useState("");
  const [pasteDetected, setPasteDetected] = useState(false);
  const typingRef = useRef<HTMLTextAreaElement>(null);

  // ── Live Analysis State ───────────────────────────────────────────────
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
    const interval = setInterval(() => {
      const snap = collector.snapshot("signup_live");
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

      // Unique digraph counting (consecutive character pairs)
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

  // ── Submit ────────────────────────────────────────────────────────────
  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMsg("");

    // Client-side validation
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

    // ── Behavioral data quality check ──
    const collector = getCollector();
    const preCheck = collector.snapshot("signup_quality_check");
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

    // ── Flush enrollment seed with full behavioral context ──
    const enrollmentSeed = collector.flush("NEW_ACCOUNT_ENROLLMENT");

    console.log("🧬 [BBA] Enrollment Seed Captured:", {
      keystroke_events: enrollmentSeed.keystroke_events.length,
      mouse_events: enrollmentSeed.mouse_events.length,
      cognitive_events: enrollmentSeed.cognitive_events.length,
      context: enrollmentSeed.page_context,
    });

    try {
      const result = await apiClient<{
        data?: { user_id: number; mfa_secret: string; mfa_provisioning_uri: string };
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
          },
        }),
      });

      if (!result.data?.user_id) {
        setError(result.error ?? "Registration failed");
        setIsLoading(false);
        return;
      }

      setMfaSecret(result.data.mfa_secret);
      setIsEnrolled(true);
      setIsLoading(false);
      
      // Store initial enrollment progress in localStorage for the login page banner
      localStorage.setItem("bba_enrollment_completed", "1");
      localStorage.setItem("bba_enrollment_required", "5");
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : "Registration failed";
      if (raw.includes("Password must contain")) {
        const match = raw.match(/Password must contain a? ?(.+)/i);
        setError(match ? `Password must contain ${match[1]}` : raw);
      } else if (raw.includes("VALIDATION_ERROR")) {
        setError("Please check your inputs and try again.");
      } else {
        setError(raw);
      }
      setIsLoading(false);
    }
  };

  if (isEnrolled) {
    return (
      <AuthShell title="Welcome to Secure Banking" subtitle="Your account has been created.">
        <div className="space-y-6 text-center">
          <div className="mx-auto w-16 h-16 bg-emerald-500/10 flex items-center justify-center rounded-full border border-emerald-500/20">
            <ShieldCheck className="w-8 h-8 text-emerald-400" />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-medium text-fg">Verify your email to continue</h3>
            <p className="text-sm text-muted">
              We've sent a verification link to <strong>{email}</strong>. Please check your inbox.
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
              <div className="h-full bg-cyan-400 rounded-full w-1/5" />
            </div>
          </div>
          {mfaSecret && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-left">
              <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2">Save MFA Secret</h4>
              <p className="text-xs text-amber-400/80 font-mono select-all bg-black/40 p-2 rounded">{mfaSecret}</p>
            </div>
          )}
          <Link href="/login" className="block w-full">
            <AuthButton className="w-full">Continue to Login</AuthButton>
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Create your account" subtitle="Sign up for secure banking. We protect your account using behavioral patterns.">
      <form onSubmit={handleSubmit} className="space-y-5">
        {error ? <AuthInlineMessage tone="error">{error}</AuthInlineMessage> : null}
        {successMsg ? <AuthInlineMessage tone="success">{successMsg}</AuthInlineMessage> : null}

        <div className="space-y-4">
          {/* ── Username ── */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider ml-1">Username</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-2" />
              <AuthInput
                id="signup-username"
                type="text"
                name="username"
                autoComplete="username"
                placeholder="Enter username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="pl-10"
              />
            </div>
          </div>

          {/* ── Email ── */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider ml-1">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-2" />
              <AuthInput
                id="signup-email"
                type="email"
                name="email"
                autoComplete="email"
                placeholder="Enter email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="pl-10"
              />
            </div>
          </div>

          {/* ── Password ── */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider ml-1">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-2" />
              <AuthInput
                id="signup-password"
                type={showPassword ? "text" : "password"}
                name="password"
                autoComplete="new-password"
                placeholder="Secure password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="pl-10 pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-2 hover:text-fg transition-colors"
              >
                {showPassword ? <Eye className="w-4 h-4" /> : <EyeClosed className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* ── Password Strength Meter ── */}
          {password.length > 0 && (
            <div className="space-y-1.5 mt-3">
              <div className="flex justify-between items-center text-[10px] uppercase tracking-wider">
                <span className="text-muted">Password Strength</span>
                <span className={strengthColors[Math.max(0, strength)].replace("bg-", "text-")}>
                  {strengthLabels[Math.max(0, strength)]}
                </span>
              </div>
              <div className="flex gap-1 h-1.5">
                {[1, 2, 3, 4, 5].map((level) => (
                  <div
                    key={level}
                    className={`h-full flex-1 rounded-full transition-colors duration-300 ${
                      level <= strength ? strengthColors[strength] : "bg-white/10"
                    }`}
                  />
                ))}
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 mt-2">
                {[
                  { label: "8+ characters", ok: passwordChecks.length },
                  { label: "Lowercase", ok: passwordChecks.lowercase },
                  { label: "Uppercase", ok: passwordChecks.uppercase },
                  { label: "Digit", ok: passwordChecks.digit },
                  { label: "Special @$!%*?&", ok: passwordChecks.special },
                ].map((c) => (
                  <span key={c.label} className={`text-[10px] ${c.ok ? "text-emerald-400" : "text-white/30"}`}>
                    {c.ok ? "✓" : "○"} {c.label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ── Behavioral Typing Verification ── */}
          <div className="mt-4 space-y-2">
            <div className="flex items-center gap-2">
              <Fingerprint className="w-4 h-4 text-cyan-400" />
              <label className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                Create Your Typing Profile
              </label>
            </div>
            <div className="bg-cyan-500/10 border border-cyan-500/20 rounded-lg p-3">
              <p className="text-xs text-cyan-300">
                Type this naturally — we're capturing your rhythm, not your speed. Pasting won't work here.
              </p>
            </div>

            {/* Prompt display */}
            <div className="bg-slate-900/60 border border-cyan-500/20 rounded-lg px-4 py-3 font-mono text-sm text-cyan-300 tracking-wide select-none">
              {typingPrompt}
            </div>

            {/* Typing textarea */}
            <div className="relative">
              <Type className="absolute left-3 top-3 w-4 h-4 text-muted-2" />
              <textarea
                ref={typingRef}
                id="behavioral-verify-text"
                value={typedText}
                onChange={(e) => setTypedText(e.target.value)}
                onPaste={handleVerifyPaste}
                placeholder="Type the text above here..."
                rows={2}
                className="w-full bg-surface border border-border rounded-lg pl-10 pr-4 py-3 text-sm text-fg placeholder:text-muted-2 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/40 font-mono resize-none transition-all"
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            {/* Paste detection warning */}
            {pasteDetected && (
              <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 animate-pulse">
                <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                <span className="text-[10px] text-red-400 font-medium">
                  Paste detected — please type the text manually. This is a behavioral verification.
                </span>
              </div>
            )}

            {/* Live accuracy meter */}
            {typedText.length > 0 && (
              <div className="flex items-center gap-3">
                <div className="flex-1 h-1 bg-black/40 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 rounded-full ${
                      liveStats.typingAccuracy >= 90 ? "bg-emerald-400" :
                      liveStats.typingAccuracy >= 70 ? "bg-yellow-400" : "bg-red-400"
                    }`}
                    style={{ width: `${liveStats.typingAccuracy}%` }}
                  />
                </div>
                <span className={`text-[10px] tabular-nums font-mono ${
                  liveStats.typingAccuracy >= 90 ? "text-emerald-400" :
                  liveStats.typingAccuracy >= 70 ? "text-yellow-400" : "text-red-400"
                }`}>
                  {liveStats.typingAccuracy}% match
                </span>
              </div>
            )}
          </div>
        </div>

        <AuthButton type="submit" disabled={isLoading || !allPasswordValid} className="mt-6 w-full">
          {isLoading ? "Provisioning..." : "Enroll Device"}
        </AuthButton>

        <p className="text-center text-xs text-muted mt-4">
          Already have an account?{" "}
          <Link href="/login" className="text-accent-primary hover:text-blue-400 transition-colors">
            Sign in
          </Link>
        </p>
      </form>

      {/* ── Enrollment Seed Analysis Panel ── */}
      <div className="mt-6 bg-slate-900/40 border border-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-accent-primary" />
          <span className="text-[10px] uppercase tracking-widest font-bold text-accent-primary">Your Behavioral Profile Baseline</span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {/* Keystroke Collection */}
          <div className="bg-black/20 rounded-lg p-3 border border-slate-700/50">
            <div className="text-[9px] uppercase tracking-wider text-muted mb-2">Keystroke Data</div>
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-muted">Total Keys</span>
                <span className={liveStats.keystrokes > 20 ? "text-emerald-400" : "text-amber-400"}>{liveStats.keystrokes}</span>
              </div>
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-muted">Hold Time</span>
                <span className="text-slate-300">{liveStats.holdMean}ms</span>
              </div>
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-muted">Flight Time</span>
                <span className="text-slate-300">{liveStats.flightMean}ms</span>
              </div>
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-muted">Unique Digraphs</span>
                <span className={liveStats.digraphCount > 15 ? "text-emerald-400" : "text-slate-300"}>{liveStats.digraphCount}</span>
              </div>
            </div>
          </div>

          {/* Behavioral Signals */}
          <div className="bg-black/20 rounded-lg p-3 border border-slate-700/50">
            <div className="text-[9px] uppercase tracking-wider text-muted mb-2">Behavioral Signals</div>
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-muted">WPM</span>
                <span className={liveStats.wpm > 80 ? "text-amber-400" : "text-emerald-400"}>{liveStats.wpm}</span>
              </div>
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-muted">Corrections</span>
                <span className="text-slate-300">{liveStats.correctionRate}%</span>
              </div>
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-muted">Mouse Events</span>
                <span className="text-slate-300">{liveStats.mouseEvents}</span>
              </div>
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-muted">Paste Attempts</span>
                <span className={liveStats.pasteCount > 0 ? "text-red-400" : "text-emerald-400"}>
                  {liveStats.pasteCount > 0 ? `⚠ ${liveStats.pasteCount}` : "0 ✓"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Data Quality Indicator */}
        <div className="mt-3 pt-3 border-t border-slate-700/50">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[9px] uppercase tracking-wider text-muted">Enrollment Seed Quality</span>
            <span className={`text-[10px] font-mono ${
              liveStats.keystrokes >= 40 && liveStats.digraphCount >= 15 ? "text-emerald-400" :
              liveStats.keystrokes >= 20 ? "text-yellow-400" : "text-red-400"
            }`}>
              {liveStats.keystrokes >= 40 && liveStats.digraphCount >= 15 ? "✓ Excellent" :
               liveStats.keystrokes >= 20 ? "◐ Sufficient" : "○ Need more typing"}
            </span>
          </div>
          <div className="h-1.5 w-full bg-black/40 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                liveStats.keystrokes >= 40 ? "bg-emerald-400" :
                liveStats.keystrokes >= 20 ? "bg-yellow-400" : "bg-red-400"
              }`}
              style={{ width: `${Math.min(100, (liveStats.keystrokes / 50) * 100)}%` }}
            />
          </div>
        </div>

        {/* Field Sequence */}
        <div className="mt-3">
          <div className="text-[9px] uppercase tracking-wider text-muted mb-1.5">Field Navigation Sequence</div>
          <div className="flex flex-wrap gap-1.5">
            {liveStats.sequence.length === 0 ? (
              <span className="text-[10px] text-slate-500 italic">Waiting for interaction...</span>
            ) : (
              liveStats.sequence.map((id, idx) => (
                <span key={idx} className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-[9px] font-mono text-slate-300">
                  {idx + 1}. {id.replace('signup-', '').replace('behavioral-', '')}
                </span>
              ))
            )}
          </div>
        </div>

        {/* Passive enrollment explanation */}
        <div className="mt-3 flex items-start gap-2 bg-cyan-500/5 border border-cyan-500/15 rounded-lg px-3 py-2">
          <ShieldCheck className="w-3.5 h-3.5 text-cyan-400 mt-0.5 flex-shrink-0" />
          <p className="text-[9px] text-cyan-400/80 leading-relaxed">
            This data creates the foundation of your secure profile. Your next 4 logins will help us complete your behavioral fingerprint to ensure you are fully protected. No extra steps required!
          </p>
        </div>
      </div>
    </AuthShell>
  );
}
