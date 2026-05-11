"use client";

import { FormEvent, useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Lock, User, ShieldCheck, ArrowRight, Activity, Keyboard } from "lucide-react";
import { motion } from "framer-motion";
import { getCollector } from "@/lib/behavioral-collector";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // ── Live keystroke telemetry state ──────────────────────────────────────
  const [keystrokeCount, setKeystrokeCount] = useState(0);
  const [avgHoldTime, setAvgHoldTime] = useState(0);
  const [avgFlightTime, setAvgFlightTime] = useState(0);

  // Start passive keystroke collection
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("LOGIN");
    collector.reset();
    collector.start();
    return () => collector.stop();
  }, []);

  // Poll collector for live stats every 300ms
  useEffect(() => {
    const interval = setInterval(() => {
      const collector = getCollector();
      const snap = collector.snapshot("login_live");
      const ks = snap.keystroke_events;
      setKeystrokeCount(ks.length);
      if (ks.length > 0) {
        const holds = ks.map(k => k.hold_time).filter(h => h > 0 && h < 2000);
        const flights = ks.map(k => k.flight_time).filter(f => f > 0 && f < 5000);
        setAvgHoldTime(holds.length > 0 ? Math.round(holds.reduce((a, b) => a + b, 0) / holds.length) : 0);
        setAvgFlightTime(flights.length > 0 ? Math.round(flights.reduce((a, b) => a + b, 0) / flights.length) : 0);
      }
    }, 300);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    const collector = getCollector();
    const behavioralData = collector.flush("login_attempt");

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
        throw new Error(data.error || "Login failed");
      }
      
      router.push("/otp");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-1 min-h-screen items-center justify-center relative font-sans p-6">
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
              <span className="text-2xl font-bold tracking-tight text-fg">NexaBank</span>
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
            <div className="flex items-center gap-3 text-xs text-muted-2 font-mono">
              <Activity size={14} className="text-accent-primary" />
              PASSIVE PROFILING ACTIVE
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
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-fg tracking-tight mb-2">Sign in to Console</h2>
              <p className="text-sm text-muted">Enter your administrative credentials.</p>
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
                    required
                    placeholder="Username or email address"
                    className="w-full bg-black/20 border border-border text-fg rounded-xl py-3 pl-11 pr-4 text-sm outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/30 transition-all placeholder:text-muted-2"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between ml-1">
                  <label className="text-xs font-semibold text-muted uppercase tracking-wider">Password</label>
                  <Link href="/forgot-password" className="text-xs font-medium text-accent-primary hover:text-blue-400 transition-colors">
                    Forgot?
                  </Link>
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

              {/* ── Live Keystroke Telemetry Counter ───────────────────────── */}
              {keystrokeCount > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="bg-accent-primary/5 border border-accent-primary/15 rounded-xl px-4 py-3"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Keyboard className="w-3.5 h-3.5 text-accent-primary" />
                    <span className="text-[10px] uppercase tracking-widest font-bold text-accent-primary">Live Keystroke Capture</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs font-mono text-muted">
                    <span>Keystrokes: <span className="text-fg font-semibold">{keystrokeCount}</span></span>
                    <span className="text-border">·</span>
                    <span>Avg hold: <span className="text-fg font-semibold">{avgHoldTime}ms</span></span>
                    <span className="text-border">·</span>
                    <span>Flight: <span className="text-fg font-semibold">{avgFlightTime}ms</span></span>
                  </div>
                </motion.div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-accent-primary hover:bg-blue-600 text-white font-medium rounded-xl py-3 mt-4 transition-colors flex items-center justify-center gap-2 group disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                ) : (
                  <>
                    Authenticate
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-8 pt-6 border-t border-border flex items-center justify-between text-xs">
              <span className="text-muted">No account yet?</span>
              <Link href="/signup" className="text-accent-primary font-medium hover:text-blue-400 transition-colors">
                Register device
              </Link>
            </div>

            {/* ── Behavioral Profiling Status Bar ──────────────────────────── */}
            <div className="mt-6 flex items-center gap-2.5 text-[10px] text-muted font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.6)]"></span>
              <span>Behavioral profiling active — keystroke dynamics being captured</span>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
