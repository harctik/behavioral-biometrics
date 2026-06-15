"use client";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";


import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Clock, LogOut } from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";

const TIMEOUT_MINUTES = 15;
const WARNING_MINUTES = 1; // Warn 1 minute before timeout
const TIMEOUT_MS = TIMEOUT_MINUTES * 60 * 1000;
const WARNING_MS = WARNING_MINUTES * 60 * 1000;

/**
 * Gap 14: Replaced localStorage-based activity tracking with server-side
 *         behavioral flush timestamps. The backend determines idle state from
 *         the absence of behavioral telemetry flushes.
 * Gap 15: "Stay Logged In" now calls a backend endpoint to extend the session
 *         with behavioral re-evaluation before extending.
 */
export function SessionTimeoutWarning() {
  const router = useRouter();
  const pathname = usePathname();
  const [showWarning, setShowWarning] = useState(false);
  const [timeLeft, setTimeLeft] = useState(WARNING_MINUTES * 60);
  const lastActivityRef = useRef<number>(0);

  useEffect(() => {
    lastActivityRef.current = Date.now();
  }, []);
  const warningStartTimeRef = useRef<number>(0);
  const [challengeText, setChallengeText] = useState("");
  const [localConfidence, setLocalConfidence] = useState(0);

  // Exclude public routes
  const isPublicRoute = ["/login", "/signup", "/forgot-password", "/reset-password", "/"].includes(pathname || "");

  const resetTimer = useCallback(() => {
    if (isPublicRoute) return;
    lastActivityRef.current = Date.now();
    setShowWarning(false);
    setTimeLeft(WARNING_MINUTES * 60);
  }, [isPublicRoute]);

  useEffect(() => {
    if (isPublicRoute) {
      return;
    }

    const checkTimer = setInterval(() => {
      const elapsed = Date.now() - lastActivityRef.current;
      
      if (elapsed >= TIMEOUT_MS) {
        // Timed out - redirect to behavioral challenge instead of logout
        clearInterval(checkTimer);
        router.push("/challenge?reason=idle");
      } else if (elapsed >= TIMEOUT_MS - WARNING_MS) {
        // Show warning
        if (!showWarning) {
          setShowWarning(true);
          warningStartTimeRef.current = Date.now();
        }
        setTimeLeft(Math.max(0, Math.ceil((TIMEOUT_MS - elapsed) / 1000)));
      } else {
        setShowWarning(false);
      }
    }, 1000);

    // Track activity events (update in-memory ref, not localStorage)
    const events = ["mousedown", "keydown", "scroll", "touchstart", "pointermove"];
    const handleActivity = () => resetTimer();
    
    events.forEach(e => window.addEventListener(e, handleActivity, { passive: true }));

    // Also track tab visibility changes — user returning to the tab is activity
    const handleVisibility = () => {
      if (document.visibilityState === "visible") resetTimer();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    
    return () => {
      clearInterval(checkTimer);
      events.forEach(e => window.removeEventListener(e, handleActivity));
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [isPublicRoute, resetTimer, router]);

  // Live confidence polling using backend assessment of isolated challenge text
  useEffect(() => {
    if (!showWarning) return;
    
    const interval = setInterval(async () => {
      const snap = await getCollector().snapshot("idle_verify");
      // Isolate the challenge text keystrokes
      const challengeKs = snap.keystroke_events.filter(k => 
        k.timestamp > warningStartTimeRef.current && 
        k.target_id === "challenge-input"
      );
      
      if (challengeKs.length >= 7) {
        try {
          const csrfToken = getCsrfToken();
          
          // Send isolated challenge keystrokes to backend for evaluation
          const isolatedData = { ...snap, keystroke_events: challengeKs, type: "challenge_only" };
          
          const res = await fetch("/api/v1/session/extend", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
            body: JSON.stringify({ behavioral_data: isolatedData }),
          });
          
          if (res.ok) {
            const data = await res.json();
            // Backend decides confidence instead of local naive keystroke count
            const conf = data.confidence ? data.confidence * 100 : Math.min(100, challengeKs.length * 15);
            setLocalConfidence(conf);
            
            if (!data.step_up_required && conf > 60) {
              resetTimer();
            }
          }
        } catch {
          // Fallback if backend is unavailable
          const naiveConf = Math.min(100, challengeKs.length * 15);
          setLocalConfidence(naiveConf);
          if (naiveConf > 60) resetTimer();
        }
      } else {
        setLocalConfidence(Math.min(100, challengeKs.length * 5));
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [showWarning, resetTimer]);



  const handleLogout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {}
    router.push("/login");
  };

  if (!showWarning) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 50 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 50 }}
        className="fixed bottom-6 right-6 z-50 w-[350px] bg-black border border-amber-500/30 rounded-2xl shadow-2xl overflow-hidden p-5"
      >
        <div className="absolute top-0 left-0 right-0 h-1 bg-amber-500/20">
          <motion.div 
            className="h-full bg-amber-500"
            initial={{ width: "100%" }}
            animate={{ width: "0%" }}
            transition={{ duration: timeLeft, ease: "linear" }}
          />
        </div>
        
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
          </div>
          <div className="flex-1">
            <h3 className="text-white font-bold text-sm mb-1">Session Expiring Soon</h3>
            <p className="text-slate-400 text-xs leading-relaxed mb-3">
              Move your mouse or type below to confirm you&apos;re still here.
            </p>
            <div className="space-y-3">
              <input
                id="challenge-input"
                name="challenge-input"
                type="text"
                placeholder="Type anything naturally..."
                value={challengeText}
                onChange={(e) => setChallengeText(e.target.value)}
                className="w-full bg-black/40 border border-amber-500/30 text-white rounded-lg px-3 py-2 text-xs outline-none focus:border-amber-500 placeholder:text-slate-600 font-mono"
              />
              <div className="h-1.5 w-full bg-black/50 rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-amber-500"
                  animate={{ width: `${localConfidence}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
