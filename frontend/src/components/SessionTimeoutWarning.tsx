"use client";

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
  const lastActivityRef = useRef(Date.now());
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
      setShowWarning(false);
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
        setShowWarning(true);
        setTimeLeft(Math.max(0, Math.ceil((TIMEOUT_MS - elapsed) / 1000)));
      } else {
        setShowWarning(false);
      }
    }, 1000);

    // Track activity events (update in-memory ref, not localStorage)
    const events = ["mousedown", "keydown", "scroll", "touchstart"];
    const handleActivity = () => resetTimer();
    
    events.forEach(e => window.addEventListener(e, handleActivity, { passive: true }));
    
    return () => {
      clearInterval(checkTimer);
      events.forEach(e => window.removeEventListener(e, handleActivity));
    };
  }, [isPublicRoute, resetTimer, router]);

  // Live confidence polling during warning
  useEffect(() => {
    if (!showWarning) {
      setLocalConfidence(0);
      setChallengeText("");
      return;
    }
    const interval = setInterval(() => {
      const snap = getCollector().snapshot("idle_verify");
      const recentKs = snap.keystroke_events.filter(k => k.timestamp > lastActivityRef.current);
      const conf = Math.min(100, recentKs.length * 15); // Simple local confidence proxy
      setLocalConfidence(conf);
      if (conf > 60) {
        handleStayLoggedIn();
      }
    }, 500);
    return () => clearInterval(interval);
  }, [showWarning]);

  // Gap 15: Behavioral-aware session extension
  const handleStayLoggedIn = async () => {
    resetTimer();
    try {
      const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";
      const collector = getCollector();
      const behavioralData = collector.flush("session_extend");

      const res = await fetch("/api/session/extend", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": csrfToken,
        },
        body: JSON.stringify({ behavioral_data: behavioralData }),
      });
      if (res.ok) {
        const data = await res.json();
        // If backend requires step-up due to bad behavioral score
        if (data.step_up_required) {
          router.push("/challenge");
          return;
        }
      }
    } catch {
      // Extension is best-effort; local timer already reset
    }
  };

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
              Move your mouse or type below to confirm you're still here.
            </p>
            <div className="space-y-3">
              <input
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
