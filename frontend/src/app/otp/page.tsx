"use client";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";


import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthButton, AuthInlineMessage, AuthInput } from "@/components/auth/AuthPrimitives";
import { KeyRound, Timer, ArrowRight, Mail, Brain, RefreshCw, AlertTriangle, Copy, Check } from "lucide-react";
import { normalizeOtp, isValidOtp } from "@/lib/otp";
import { getCollector } from "@/lib/behavioral-collector";

const DEFAULT_TTL = 120; // seconds — synced with backend OTP_TTL_SECONDS

export default function OtpPage() {
  const router = useRouter();
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  const [info, setInfo] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(DEFAULT_TTL);
  const [timerActive, setTimerActive] = useState(false);
  const [expired, setExpired] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);
  const [copied, setCopied] = useState(false);
  const [mlMetrics, setMlMetrics] = useState<{authenticityScore: number, riskLevel: string, manual: boolean, avgInterDigit: number} | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Start behavioral collection on OTP page
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("OTP_VERIFY");
    collector.reset();
    collector.start();
    return () => collector.stop();
  }, []);

  // Start or restart the countdown timer
  const startTimer = useCallback((ttl: number = DEFAULT_TTL) => {
    // Clear any existing timer
    if (timerRef.current) clearInterval(timerRef.current);
    setCountdown(ttl);
    setExpired(false);
    setTimerActive(true);

    timerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          // Timer hit zero — stop it
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;
          setTimerActive(false);
          setExpired(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Send OTP to user's email
  const sendOtpEmail = useCallback(async (sid: string) => {
    try {
      const res = await fetch("/api/auth/send-otp-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid }),
      });
      const data = await res.json();
      if (res.ok) {
        setEmailSent(true);

        // Check if backend returned OTP in dev mode
        if (data.dev_mode && data.otp_code) {
          setDevMode(true);
          setDevOtp(data.otp_code);
          setInfo("Development mode — OTP code displayed below (no email service configured).");
        } else {
          setDevMode(false);
          setDevOtp(null);
          setInfo("OTP code sent to your registered email address.");
        }

        const ttl = data.ttl_seconds || DEFAULT_TTL;
        startTimer(ttl);
      } else {
        toast.error(data.error || "Failed to send OTP. Please try again.");
      }
    } catch {
      toast.error("Network error. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, [startTimer]);

  // On mount: check auth + auto-send OTP
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const data = await res.json();
          const sid = data.session_id || null;
          setSessionId(sid);
          if (sid) {
            sendOtpEmail(sid);
          }
        }
      } catch {}
    };
    checkAuth();
  }, [sendOtpEmail]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    ;

    const normalizedOtp = normalizeOtp(otp);
    if (!isValidOtp(normalizedOtp)) {
      toast.error("Enter a valid 6-digit OTP code.");
      return;
    }

    if (!sessionId) {
      toast.error("No active session found. Please sign in again.");
      return;
    }

    if (expired) {
      toast.error("This OTP has expired. Please request a new one.");
      return;
    }

    setIsLoading(true);
    try {
      const collector = getCollector();
      const behavioralData = await collector.flush("otp_verify");

      const res = await fetch("/api/auth/mfa-verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, otp: normalizedOtp, behavioral_data: behavioralData }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        // Stop timer on successful verify
        if (timerRef.current) clearInterval(timerRef.current);
        router.push("/dashboard");
        return;
      }

      toast.error(data.error ?? "OTP verification failed.");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "OTP verification failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    setOtp("");
    ;
    setInfo("");
    setMlMetrics(null);
    setDevOtp(null);
    setCopied(false);
    if (sessionId) {
      setInfo("Sending new OTP...");
      setIsLoading(true);
      await sendOtpEmail(sessionId);
    }
  };

  const handleCopyOtp = () => {
    if (devOtp) {
      navigator.clipboard.writeText(devOtp).then(() => {
        setCopied(true);
        setOtp(devOtp);
        toast.success("OTP copied and auto-filled!");
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  const countdownLow = countdown <= 15 && countdown > 0;
  const minutes = String(Math.floor(countdown / 60)).padStart(2, '0');
  const seconds = String(countdown % 60).padStart(2, '0');

  return (
    <AuthShell title="Verify OTP" subtitle="Enter the 6-digit code to continue. Your typing behavior is being analyzed.">
      <form onSubmit={handleSubmit} className="space-y-5">
        
        {info ? (
          <div className={`${devMode ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-accent-primary/10 border-accent-primary/20 text-accent-primary'} border px-4 py-3 rounded-xl text-xs flex items-center gap-2`}>
            {devMode ? <AlertTriangle className="w-4 h-4 flex-shrink-0" /> : <Mail className="w-4 h-4 flex-shrink-0" />}
            <span>{info}</span>
          </div>
        ) : null}

        {/* Dev mode OTP display — large, copy-able, prominent */}
        {devMode && devOtp && !expired && (
          <div className="relative bg-gradient-to-br from-amber-500/5 to-orange-500/5 border border-amber-500/30 rounded-xl p-5 text-center">
            <div className="text-[10px] uppercase tracking-widest font-bold text-amber-500/80 mb-2">
              Development OTP Code
            </div>
            <button
              type="button"
              onClick={handleCopyOtp}
              className="group flex items-center justify-center gap-3 w-full"
            >
              <span className="text-3xl font-mono font-bold tracking-[0.5em] text-amber-400 group-hover:text-amber-300 transition-colors">
                {devOtp}
              </span>
              {copied ? (
                <Check className="w-5 h-5 text-emerald-400" />
              ) : (
                <Copy className="w-5 h-5 text-amber-500/50 group-hover:text-amber-400 transition-colors" />
              )}
            </button>
            <div className="text-[10px] text-amber-500/60 mt-2 font-mono">
              Click to copy & auto-fill · Configure MAIL_BACKEND in .env for email delivery
            </div>
          </div>
        )}

        {/* Countdown timer */}
        <div className={`flex items-center justify-center gap-2 py-3 border rounded-xl transition-colors ${
          expired ? 'bg-red-500/10 border-red-500/30' :
          countdownLow ? 'bg-amber-500/10 border-amber-500/30' :
          'bg-black/20 border-border'
        }`}>
          <Timer className={`w-4 h-4 ${
            expired ? 'text-red-500' :
            countdownLow ? 'text-amber-500' : 'text-accent-primary'
          }`} />
          {expired ? (
            <span className="text-sm font-mono font-semibold text-red-500">
              Code expired — request a new one
            </span>
          ) : (
            <span className={`text-lg font-mono font-semibold tabular-nums tracking-widest ${
              countdownLow ? 'text-amber-500' : 'text-accent-primary'
            }`}>
              {minutes}:{seconds}
            </span>
          )}
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-muted uppercase tracking-wider ml-1">Authentication Code</label>
          <div className="relative">
            <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-2" />
            <AuthInput
              id="otp-input"
              type="text"
              name="otp"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              value={otp}
              onChange={async (e) => {
                const val = normalizeOtp(e.target.value);
                setOtp(val);
                if (val.length === 6) {
                  const collector = getCollector();
                  const snap = await collector.snapshot("otp_analysis");
                  const otpKeys = snap.keystroke_events.filter(k => /^[0-9]$/.test(k.key));
                  const flights = otpKeys.map(k => k.flight_time).filter(f => f > 0 && f < 10000);
                  const avgFlight = flights.length > 0 ? Math.round(flights.reduce((a, b) => a + b, 0) / flights.length) : 0;
                  const isPaste = snap.cognitive_events.some(c => c.type === 'copy_paste') || otpKeys.length < 3;
                  
                  try {
                    const csrfToken = getCsrfToken();
                    const res = await fetch("/api/v1/session/metrics", {
                      headers: { "X-CSRF-TOKEN": csrfToken }
                    });
                    if (res.ok) {
                      const data = await res.json();
                      setMlMetrics({
                        authenticityScore: Math.round((data.authenticity_score || 0) * 100),
                        riskLevel: data.risk_level || "low",
                        manual: !isPaste,
                        avgInterDigit: avgFlight
                      });
                    }
                  } catch {}
                } else {
                  setMlMetrics(null);
                }
              }}
              maxLength={6}
              required
              disabled={expired}
              className="pl-10 text-center tracking-[0.5em] font-mono text-lg"
            />
          </div>
          <div className="mt-2 flex items-center gap-2 text-[10px] text-muted font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.5)]"></span>
            Typing pattern analysis active — digit-by-digit behavior monitored
          </div>
        </div>

        {/* Submit button — hidden when expired */}
        {!expired && (
          <AuthButton type="submit" disabled={isLoading} className="w-full mt-4">
            {isLoading ? "Verifying..." : (
              <span className="flex items-center gap-2">
                Verify Token <ArrowRight className="w-4 h-4" />
              </span>
            )}
          </AuthButton>
        )}

        {/* Resend button for failed email send state */}
        {!emailSent && !timerActive && (
          <div className="flex flex-col gap-3 mt-4">
            <button
              type="button"
              onClick={handleResend}
              disabled={isLoading}
              className="w-full bg-accent-primary text-white font-medium text-sm py-3 rounded-xl hover:bg-blue-600 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              {isLoading ? 'Sending...' : 'Retry Sending OTP'}
            </button>
            <button
              type="button"
              onClick={() => router.push("/login")}
              className="w-full bg-surface-2 text-fg font-medium text-sm py-3 rounded-xl hover:bg-surface-elevated transition-colors"
            >
              Back to Login
            </button>
          </div>
        )}

        {/* Resend button — only visible after expiry */}
        {expired && (
          <button
            type="button"
            onClick={handleResend}
            className="w-full bg-accent-primary text-white font-medium text-sm py-3 rounded-xl hover:bg-blue-600 transition-colors flex items-center justify-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Resend OTP Code
          </button>
        )}

        {/* Always show a subtle resend link if not expired (for impatient users) */}
        {!expired && emailSent && (
          <button
            type="button"
            onClick={handleResend}
            className="w-full text-center text-xs text-muted hover:text-accent-primary transition-colors py-2 cursor-pointer mt-1 flex items-center justify-center gap-1"
          >
            <Mail className="w-3 h-3" />
            Didn't receive it? Resend OTP
          </button>
        )}

        <p className="text-center text-xs text-muted leading-relaxed mt-4">
          Wrong account?{" "}
          <Link href="/login" className="text-accent-primary hover:text-blue-400 transition-colors">
            Back to sign in
          </Link>
        </p>
      </form>

      {/* ML Behavioral Analysis Card */}
      {mlMetrics && (
        <div className="mt-5 bg-surface-2/50 border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-accent-primary" />
            <span className="text-[10px] uppercase tracking-widest font-bold text-accent-primary">ML Risk Assessment</span>
          </div>
          <div className="space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between">
              <span className="text-muted">Authenticity Score</span>
              <span className={mlMetrics.authenticityScore >= 70 ? "text-accent-success" : mlMetrics.authenticityScore >= 40 ? "text-accent-warning" : "text-accent-danger"}>
                {mlMetrics.authenticityScore}% match
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted">Ensemble Risk Level</span>
              <span className={mlMetrics.riskLevel === 'low' ? "text-accent-success" : mlMetrics.riskLevel === 'medium' ? "text-accent-warning" : "text-accent-danger"}>
                {mlMetrics.riskLevel.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted">Input Method</span>
              <span className={mlMetrics.manual ? "text-accent-success" : "text-accent-danger"}>
                {mlMetrics.manual ? "Human / Keystrokes" : "Paste / Autofill"}
              </span>
            </div>
          </div>
        </div>
      )}
    </AuthShell>
  );
}
