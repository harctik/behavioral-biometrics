"use client";

import { FormEvent, useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Fingerprint, ShieldCheck, AlertTriangle, CheckCircle, Keyboard } from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";
import { TypingDNA } from "@/components/behavioral/TypingDNA";

const RECOVERY_PROMPTS = [
  "The quick brown fox jumps over the lazy dog",
  "Pack my box with five dozen liquor jugs",
  "A secure system operates invisibly but effectively",
];

function AccountRecoveryInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const recoveryToken = searchParams.get("token") || "";

  const [currentPromptIdx, setCurrentPromptIdx] = useState(0);
  const [typedText, setTypedText] = useState("");
  const [completedSamples, setCompletedSamples] = useState<string[]>([]);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [failed, setFailed] = useState(false);
  const typingAreaRef = useRef<HTMLTextAreaElement>(null);

  // Telemetry
  const [keystrokeCount, setKeystrokeCount] = useState(0);
  const [holdTimeSeries, setHoldTimeSeries] = useState<number[]>([]);
  const [flightTimeSeries, setFlightTimeSeries] = useState<number[]>([]);

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("RECOVERY");
    collector.reset();
    collector.start();
    return () => collector.stop();
  }, []);

  useEffect(() => {
    const interval = setInterval(async () => {
      const collector = getCollector();
      const snap = await collector.snapshot("recovery_live");
      const ks = snap.keystroke_events;
      setKeystrokeCount(ks.length);
      if (ks.length > 0) {
        setHoldTimeSeries(ks.map((k: { hold_time: number }) => k.hold_time).filter((h: number) => h > 0 && h < 2000));
        setFlightTimeSeries(ks.map((k: { flight_time: number }) => k.flight_time).filter((f: number) => f > 0 && f < 5000));
      }
    }, 300);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (typingAreaRef.current) {
      setTimeout(() => typingAreaRef.current?.focus(), 300);
    }
  }, [currentPromptIdx]);

  if (!recoveryToken) {
    return (
      <div className="flex flex-1 min-h-screen items-center justify-center p-4">
        <div className="max-w-md bg-surface/40 backdrop-blur-xl border border-red-500/20 rounded-3xl p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-fg mb-2">Invalid Recovery Link</h2>
          <p className="text-sm text-muted mb-4">This recovery link is missing or expired.</p>
          <button
            onClick={() => router.push("/login")}
            className="bg-accent-primary hover:bg-blue-600 text-white font-medium rounded-xl px-6 py-3 text-sm transition-colors"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  const handleNextSample = async (e: FormEvent) => {
    e.preventDefault();
    const newSamples = [...completedSamples, typedText];
    setCompletedSamples(newSamples);
    setTypedText("");

    // Reset collector for next sample
    const collector = getCollector();
    collector.reset();
    collector.start();
    setKeystrokeCount(0);
    setHoldTimeSeries([]);
    setFlightTimeSeries([]);

    if (newSamples.length < RECOVERY_PROMPTS.length) {
      setCurrentPromptIdx(currentPromptIdx + 1);
    } else {
      // All 3 samples collected — submit for verification
      setIsVerifying(true);
      setError("");

      const behavioralData = await collector.flush("recovery_verify");

      try {
        const res = await fetch("/api/auth/account-recovery", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            recovery_token: recoveryToken,
            typed_texts: newSamples,
            behavioral_data: behavioralData,
          }),
        });
        const data = await res.json();

        if (!res.ok) {
          if (res.status === 401) {
            setFailed(true);
          } else {
            setError(data.error || "Recovery verification failed.");
          }
          return;
        }

        setSuccess(true);
      } catch {
        setError("Network error. Please try again.");
      } finally {
        setIsVerifying(false);
      }
    }
  };

  return (
    <div className="flex flex-1 min-h-screen items-center justify-center relative font-sans p-4">
      <AnimatePresence mode="wait">
        {/* ── Success Screen ── */}
        {success && (
          <motion.div
            key="success"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="z-10 w-full max-w-md bg-surface/40 backdrop-blur-xl border border-emerald-500/20 rounded-3xl shadow-2xl overflow-hidden"
          >
            <div className="h-1 bg-gradient-to-r from-emerald-500 to-green-500" />
            <div className="p-8 text-center">
              <div className="w-16 h-16 mx-auto mb-6 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-emerald-400" />
              </div>
              <h2 className="text-2xl font-bold text-fg mb-2">Account Unlocked!</h2>
              <p className="text-sm text-muted mb-6">Your identity has been verified and your account is now unlocked.</p>
              <button
                onClick={() => router.push("/login")}
                className="w-full h-12 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl text-sm transition-colors"
              >
                Return to Login
              </button>
            </div>
          </motion.div>
        )}

        {/* ── Failed Screen ── */}
        {failed && (
          <motion.div
            key="failed"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="z-10 w-full max-w-md bg-surface/40 backdrop-blur-xl border border-red-500/20 rounded-3xl shadow-2xl overflow-hidden"
          >
            <div className="h-1 bg-gradient-to-r from-red-500 to-orange-500" />
            <div className="p-8 text-center">
              <div className="w-16 h-16 mx-auto mb-6 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center justify-center">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-2xl font-bold text-fg mb-2">Verification Failed</h2>
              <p className="text-sm text-muted mb-6">Your typing patterns didn&apos;t match your profile. You may have limited recovery attempts remaining.</p>
              <div className="flex flex-col gap-3">
                <button
                  onClick={() => router.push("/login")}
                  className="w-full h-11 bg-white/5 hover:bg-white/10 border border-white/10 text-fg font-medium rounded-xl text-sm transition-colors"
                >
                  Back to Login
                </button>
                <p className="text-xs text-muted">
                  Still having trouble? Contact support at <span className="text-accent-primary">support@aetherauth.com</span>
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── Typing Challenge ── */}
        {!success && !failed && (
          <motion.div
            key="typing"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="z-10 w-full max-w-lg bg-surface/40 backdrop-blur-xl border border-white/10 rounded-3xl shadow-2xl overflow-hidden"
          >
            <div className="h-1 bg-gradient-to-r from-amber-500 to-orange-500" />
            <div className="p-8 lg:p-10">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-fg tracking-tight">Account Recovery</h2>
                  <p className="text-xs text-muted">Verify your identity by typing {RECOVERY_PROMPTS.length} prompts</p>
                </div>
              </div>

              {/* Progress */}
              <div className="flex items-center gap-2 mb-6">
                {RECOVERY_PROMPTS.map((_, i) => (
                  <div key={i} className="flex-1">
                    <div className={`h-1.5 rounded-full transition-all duration-500 ${
                      i < completedSamples.length ? "bg-emerald-400" :
                      i === currentPromptIdx ? "bg-amber-400" :
                      "bg-white/10"
                    }`} />
                    <div className={`text-[9px] mt-1 text-center font-mono ${
                      i < completedSamples.length ? "text-emerald-400" :
                      i === currentPromptIdx ? "text-amber-400" :
                      "text-muted"
                    }`}>
                      {i < completedSamples.length ? "✓" : `Prompt ${i + 1}`}
                    </div>
                  </div>
                ))}
              </div>

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

              <form onSubmit={handleNextSample} className="space-y-5">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-muted ml-1 uppercase tracking-wider flex items-center gap-2">
                    <Keyboard className="w-3.5 h-3.5" />
                    Prompt {currentPromptIdx + 1} of {RECOVERY_PROMPTS.length}
                  </label>
                  <div className="bg-black/30 border border-amber-500/20 rounded-xl p-4 font-mono text-sm text-amber-300 leading-relaxed select-none">
                    {RECOVERY_PROMPTS[currentPromptIdx]}
                  </div>
                </div>

                <textarea
                  ref={typingAreaRef}
                  value={typedText}
                  onChange={(e) => setTypedText(e.target.value)}
                  onPaste={(e) => e.preventDefault()}
                  onCopy={(e) => e.preventDefault()}
                  rows={3}
                  placeholder="Type the text above..."
                  className="w-full bg-black/20 border border-border text-fg rounded-xl py-3 px-4 text-sm outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500/30 transition-all placeholder:text-muted-2 font-mono resize-none"
                />

                {keystrokeCount > 0 && (
                  <div className="bg-amber-500/5 border border-amber-500/15 rounded-xl px-4 py-2">
                    <TypingDNA holdTimes={holdTimeSeries} flightTimes={flightTimeSeries} height={28} />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isVerifying || typedText.length < 10}
                  className="w-full h-12 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-medium rounded-xl transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isVerifying ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                      <span className="text-sm font-medium">Verifying...</span>
                    </>
                  ) : currentPromptIdx < RECOVERY_PROMPTS.length - 1 ? (
                    <>Next Prompt →</>
                  ) : (
                    <>
                      <Fingerprint className="w-4 h-4" />
                      Verify & Unlock Account
                    </>
                  )}
                </button>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function AccountRecoveryPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-1 min-h-screen items-center justify-center">
        <div className="w-8 h-8 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
      </div>
    }>
      <AccountRecoveryInner />
    </Suspense>
  );
}
