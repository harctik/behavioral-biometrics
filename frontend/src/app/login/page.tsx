"use client";

import { FormEvent, useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Lock, User, ShieldCheck, ArrowRight, Activity, Keyboard } from "lucide-react";
import { motion } from "framer-motion";
import { getCollector } from "@/lib/behavioral-collector";
import { TypingDNA } from "@/components/behavioral/TypingDNA";
import { BiometricScanner } from "@/components/behavioral/BiometricScanner";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [remainingAttempts, setRemainingAttempts] = useState<number | null>(null);
  const [lockoutUntil, setLockoutUntil] = useState<number | null>(null); // epoch ms
  const [lockoutCountdown, setLockoutCountdown] = useState<string>("");
  
  // CAPTCHA State
  const [captchaInput, setCaptchaInput] = useState("");
  const [captchaCode, setCaptchaCode] = useState({ a: 0, b: 0 });

  // ── Live keystroke telemetry state ──────────────────────────────────────
  const [keystrokeCount, setKeystrokeCount] = useState(0);
  const [avgHoldTime, setAvgHoldTime] = useState(0);
  const [avgFlightTime, setAvgFlightTime] = useState(0);
  const [holdTimeSeries, setHoldTimeSeries] = useState<number[]>([]);
  const [flightTimeSeries, setFlightTimeSeries] = useState<number[]>([]);

  // Enrollment phase state from localStorage
  const [enrollmentState, setEnrollmentState] = useState<{completed: number, required: number} | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const completed = localStorage.getItem("bba_enrollment_completed");
    const required = localStorage.getItem("bba_enrollment_required");
    if (completed && required && parseInt(completed) < parseInt(required)) {
      setEnrollmentState({ completed: parseInt(completed), required: parseInt(required) });
    }
  }, []);

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("LOGIN");
    collector.reset();
    collector.start();
    
    // Initialize CAPTCHA
    setCaptchaCode({
      a: Math.floor(Math.random() * 10) + 1,
      b: Math.floor(Math.random() * 10) + 1
    });
    
    return () => collector.stop();
  }, []);

  // Poll collector for live stats every 300ms
  useEffect(() => {
    const interval = setInterval(async () => {
      const collector = getCollector();
      const snap = await collector.snapshot("login_live");
      const ks = snap.keystroke_events;
      setKeystrokeCount(ks.length);
      if (ks.length > 0) {
        const holds = ks.map(k => k.hold_time).filter(h => h > 0 && h < 2000);
        const flights = ks.map(k => k.flight_time).filter(f => f > 0 && f < 5000);
        setAvgHoldTime(holds.length > 0 ? Math.round(holds.reduce((a, b) => a + b, 0) / holds.length) : 0);
        setAvgFlightTime(flights.length > 0 ? Math.round(flights.reduce((a, b) => a + b, 0) / flights.length) : 0);
        setHoldTimeSeries(holds);
        setFlightTimeSeries(flights);
      }
    }, 300);
    return () => clearInterval(interval);
  }, []);

  // ── Lockout countdown timer ──────────────────────────────────────────────
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

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (lockoutUntil && lockoutUntil > Date.now()) {
      setError("Account is temporarily locked. Please wait.");
      return;
    }
    
    if (parseInt(captchaInput) !== (captchaCode.a + captchaCode.b)) {
      setError("Invalid CAPTCHA code. Please try again.");
      setCaptchaCode({
        a: Math.floor(Math.random() * 10) + 1,
        b: Math.floor(Math.random() * 10) + 1
      });
      setCaptchaInput("");
      return;
    }
    
    setError("");
    setIsLoading(true);

    const collector = getCollector();
    const behavioralData = await collector.flush("login_attempt");

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          username, 
          password,
          behavioral_data: behavioralData
        }),
      });
      const data = await res.json();
      
      if (!res.ok) {
        // Parse lockout metadata from server response (it might be in error.details)
        const details = data.error?.details || data.details || data;
        
        if (details.remaining_attempts !== undefined) {
          setRemainingAttempts(details.remaining_attempts);
        }
        if (details.lockout_until) {
          // If the backend returns ISO string, convert to epoch. If already epoch, use it.
          const isNum = typeof details.lockout_until === 'number';
          setLockoutUntil(isNum ? details.lockout_until * 1000 : new Date(details.lockout_until).getTime());
        } else if (res.status === 429 || res.status === 423) {
          // Assume 5-minute lockout for rate-limited responses
          setLockoutUntil(Date.now() + 5 * 60 * 1000);
        }
        throw new Error(data.error?.message || data.error || data.message || (res.status === 401 ? "Invalid credentials." : "An unexpected error occurred."));
      }
      
      // Reset lockout state on success
      setRemainingAttempts(null);
      setLockoutUntil(null);

      if (data.mfa_required) {
        router.push("/otp");
      } else {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Login failed. Please try again.";
      if (msg.toLowerCase().includes("fetch")) {
        setError("Network error: Could not connect to the server.");
      } else {
        setError(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-1 min-h-screen items-center justify-center relative font-sans p-6">
      {/* Cinematic biometric scanner overlay — shown during auth */}
      <BiometricScanner isVisible={isLoading} />
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="z-10 w-full max-w-6xl grid lg:grid-cols-2 gap-0 items-stretch bg-surface/40 backdrop-blur-xl border border-white/10 rounded-3xl shadow-2xl overflow-hidden"
      >
        {/* Left Side Branding */}
        <div className="hidden lg:flex flex-col justify-between p-12 bg-gradient-to-br from-surface to-surface-2 relative overflow-hidden">
          {/* Background Elements */}
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-accent-primary to-accent-secondary opacity-50" />
          <div className="absolute -top-32 -left-32 w-64 h-64 bg-accent-primary/20 rounded-full blur-[80px]" />
          
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-12">
              <div className="w-10 h-10 bg-accent-primary/10 border border-accent-primary/30 rounded-lg flex items-center justify-center text-accent-primary">
                <ShieldCheck size={24} />
              </div>
              <span className="text-2xl font-bold tracking-tight text-fg">AetherAuth</span>
            </div>
            
            <h1 className="text-4xl font-bold leading-tight text-fg mb-6">
              Industrial-grade <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-primary to-accent-secondary">
                Continuous Authentication
              </span>
            </h1>
            <p className="text-muted text-sm leading-relaxed max-w-md">
              Securely access your corporate banking console. The system continuously monitors behavioral telemetry (such as keystrokes, mouse dynamics, and cognitive patterns) to ensure session integrity.
            </p>
          </div>

          <div className="relative z-10 flex flex-col gap-4 mt-12">
            <div className="group relative flex items-center gap-3 text-xs text-muted-2 font-mono cursor-help w-max">
              <Activity size={14} className="text-accent-primary" />
              PASSIVE PROFILING ACTIVE
              {/* Tooltip */}
              <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-slate-900 border border-border rounded text-[10px] text-white shadow-xl">
                We're analyzing your typing patterns to verify it's really you. This happens completely in the background.
              </div>
            </div>
            <div className="h-px w-full bg-border" />
            <div className="flex items-center gap-4 text-xs text-muted">
              <span>RBI Compliant</span>
              <span>•</span>
              <span>PCI DSS 4.0</span>
              <span>•</span>
              <span>DPDP Act 2023</span>
            </div>
          </div>
        </div>

        {/* Right Side Login Form */}
        <div className="p-8 lg:p-12 relative flex flex-col justify-center border-l border-white/5">
          <div className="max-w-sm w-full mx-auto">


            <div className="mb-6">
              <h2 className="text-2xl font-bold text-fg tracking-tight mb-2">Netbanking Login</h2>
              <p className="text-sm text-muted">Enter your User ID and Password.</p>
            </div>
            
            {/* Phishing Banner */}
            <div className="mb-6 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
              <div className="text-xs text-blue-100/80 leading-relaxed">
                <span className="font-semibold text-blue-300">Security Advisory:</span> AetherAuth Bank will never ask for your Password, PIN, or OTP over phone, email, or SMS. Do not share your credentials with anyone.
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

            {/* Lockout countdown */}
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

            {/* Remaining attempts warning */}
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

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted ml-1 uppercase tracking-wider">Username / Email</label>
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
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between ml-1">
                  <label className="text-xs font-semibold text-muted uppercase tracking-wider">Password</label>
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
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-4 flex items-center text-muted-2 hover:text-fg transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* CAPTCHA Field */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted ml-1 uppercase tracking-wider">Security Check</label>
                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-black/40 border border-border text-fg font-mono font-bold text-lg rounded-xl py-2 px-4 flex items-center justify-center select-none tracking-widest relative overflow-hidden">
                    <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)', backgroundSize: '4px 4px' }}></div>
                    {captchaCode.a} + {captchaCode.b} = ?
                  </div>
                  <input
                    type="text"
                    value={captchaInput}
                    onChange={(e) => setCaptchaInput(e.target.value)}
                    required
                    placeholder="Result"
                    className="w-24 bg-black/20 border border-border text-fg rounded-xl py-3 px-4 text-center text-sm outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/30 transition-all font-mono"
                  />
                </div>
              </div>

              {/* ── Live Keystroke Telemetry Counter ───────────────────────── */}
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
                {/* ── Biometric DNA Visualization ── */}
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
                disabled={isLoading}
                className="w-full bg-accent-primary hover:bg-blue-600 text-white font-medium rounded-xl mt-4 transition-colors relative overflow-hidden group disabled:opacity-90 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <div className="w-full relative h-12 flex items-center justify-center gap-3">
                    <div className="absolute inset-0 bg-blue-600/50">
                      <motion.div 
                        initial={{ width: "0%" }} 
                        animate={{ width: "100%" }} 
                        transition={{ duration: 2.5, ease: "easeInOut" }} 
                        className="h-full bg-blue-500/50" 
                      />
                    </div>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin relative z-10"></div>
                    <span className="text-sm relative z-10 font-medium">Analyzing behavioral session...</span>
                  </div>
                ) : (
                  <div className="w-full h-12 flex items-center justify-center gap-2">
                    Authenticate
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                )}
              </button>
              
            </form>

            <div className="mt-8 pt-6 border-t border-border flex items-center justify-between text-xs">
              <span className="text-muted">No account yet?</span>
              <Link href="/signup" className="text-accent-primary font-medium hover:text-blue-400 transition-colors">
                Create account
              </Link>
            </div>

            {/* ── Behavioral Profiling Status Bar ──────────────────────────── */}
            <div className="mt-6 flex items-center justify-between">
              <div className="flex items-center gap-2.5 text-[10px] text-muted font-mono">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.6)]"></span>
                <span>Behavioral profiling active</span>
              </div>
              {enrollmentState && (
                <div className="bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-[10px] px-2 py-1 rounded font-mono">
                  Profile building: session {enrollmentState.completed + 1} of {enrollmentState.required}
                </div>
              )}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
