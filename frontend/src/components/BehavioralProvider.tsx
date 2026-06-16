"use client";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";


import { useEffect, useRef, useState, useCallback } from "react";
import { usePathname } from "next/navigation";
import { getCollector, DeviceFingerprint } from "@/lib/behavioral-collector";

// Export for sensitive pages to call immediately
export async function flushBehavioralDataNow() {
  if (typeof document === "undefined" || !document.cookie.includes("csrf_access_token=")) return;
  const csrfToken = getCsrfToken();
  const sessionId = getSessionId();
  if (!sessionId) return; // Can't send behavioral data without a session
  const collector = getCollector();
  const payload = await collector.flush("session");
  const hasData = payload.keystroke_events.length > 0 || payload.mouse_events.length > 0 || payload.touch_events.length > 0;
  if (!hasData) return;

  try {
    await fetch("/api/v1/behavioral/data", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
      body: JSON.stringify({
        session_id: sessionId,
        type: "extended",
        event_count: payload.keystroke_events.length + payload.mouse_events.length + payload.touch_events.length,
        keystroke_events: payload.keystroke_events.slice(0, 200),
        events: payload.mouse_events.slice(0, 200),
        touch_events: payload.touch_events.slice(0, 200),
        scroll_events: payload.scroll_events.slice(0, 200),
        navigation_events: payload.navigation_events.slice(0, 200),
        cognitive_events: payload.cognitive_events.slice(0, 200),
        extended_features: payload.extended_features,
      }),
    });
  } catch (err) {
    console.error("Immediate flush failed", err);
  }
}

function diffFingerprint(oldFp: DeviceFingerprint | null, newFp: DeviceFingerprint | null) {
  if (!oldFp || !newFp) return true;
  return oldFp.screen_width !== newFp.screen_width ||
         oldFp.connection_type !== newFp.connection_type ||
         oldFp.pointer_type !== newFp.pointer_type;
}

export function BehavioralProvider() {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const failureCountRef = useRef(0);
  const lastFingerprintRef = useRef<DeviceFingerprint | null>(null);
  const pathname = usePathname();
  const prevPathnameRef = useRef(pathname);
  const [pasteWarning, setPasteWarning] = useState<{ show: boolean; count: number; field: string }>({ show: false, count: 0, field: "" });
  const pasteCountRef = useRef(0);
  const pasteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Copy-paste detection with visual warning
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const target = e.target as HTMLInputElement;
      const fieldName = target?.name || target?.id || target?.placeholder || "input field";
      const isSensitive = ["password", "amount", "account", "ifsc", "beneficiary", "otp", "pin"]
        .some(s => fieldName.toLowerCase().includes(s) || (target?.type || "").toLowerCase().includes(s));

      pasteCountRef.current += 1;
      const count = pasteCountRef.current;

      // Show warning toast
      setPasteWarning({ show: true, count, field: fieldName });

      // Auto-dismiss after 5 seconds
      if (pasteTimerRef.current) clearTimeout(pasteTimerRef.current);
      pasteTimerRef.current = setTimeout(() => {
        setPasteWarning(prev => ({ ...prev, show: false }));
      }, 5000);

      // For sensitive fields, log as high-risk cognitive event
      if (isSensitive) {
        console.warn(`[BehavioralAuth] ⚠️ Paste detected in sensitive field: ${fieldName}`);
      }
    };

    document.addEventListener("paste", handlePaste as EventListener);
    return () => {
      document.removeEventListener("paste", handlePaste as EventListener);
      if (pasteTimerRef.current) clearTimeout(pasteTimerRef.current);
    };
  }, []);

  // Flush behavioral data on route transitions (Gap 97)
  useEffect(() => {
    if (prevPathnameRef.current !== pathname && prevPathnameRef.current) {
      // Route changed — flush collected data for the previous page
      flushBehavioralDataNow().catch(console.error);
    }
    prevPathnameRef.current = pathname;
  }, [pathname]);

  useEffect(() => {
    const collector = getCollector();
    collector.start();

    const checkAndFlush = async () => {
      if (typeof document === "undefined" || !document.cookie.includes("csrf_access_token=")) {
        scheduleNext(10_000);
        return;
      }
      const csrfToken = getCsrfToken();

      // Read session_id from cookie for backend validation
      const sessionId = getSessionId();
      if (!sessionId) {
        // No session yet (e.g. on login page) — skip behavioral flush
        scheduleNext(10_000);
        return;
      }

      // Device Fingerprint diffing — endpoint may not exist, fail silently
      const currentFp = collector.deviceFingerprint;
      if (currentFp && diffFingerprint(lastFingerprintRef.current, currentFp)) {
        try {
          const fpRes = await fetch("/api/v1/behavioral/device-intel", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
            body: JSON.stringify({ ...currentFp, session_id: sessionId }),
          });
          if (fpRes.ok) lastFingerprintRef.current = { ...currentFp };
        } catch { /* device-intel is optional */ }
      }

      const payload = await collector.flush("session");
      const hasData = payload.keystroke_events.length > 0 || payload.mouse_events.length > 0 || payload.touch_events.length > 0;

      if (!hasData) {
        scheduleNext(10_000);
        return;
      }

      try {
        // Extract in-session keystroke profile for continuous digraph verification
        let sessionKeystrokeProfile = {};
        try {
          sessionKeystrokeProfile = collector.getKeystrokeProfile();
        } catch { /* keystroke profile is optional enhancement */ }

        await fetch("/api/v1/behavioral/data", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
          body: JSON.stringify({
            session_id: sessionId,
            type: "extended",
            event_count: payload.keystroke_events.length + payload.mouse_events.length + payload.touch_events.length,
            keystroke_events: payload.keystroke_events.slice(0, 200),
            events: payload.mouse_events.slice(0, 200),
            mouse_events: payload.mouse_events.slice(0, 200),
            touch_events: payload.touch_events.slice(0, 200),
            scroll_events: payload.scroll_events.slice(0, 200),
            navigation_events: payload.navigation_events.slice(0, 200),
            cognitive_events: payload.cognitive_events.slice(0, 200),
            extended_features: payload.extended_features,
            keystroke_profile: sessionKeystrokeProfile,
          }),
        });

        failureCountRef.current = 0;

        // Session/metrics checks — log failures but NEVER redirect to login
        // The session_id cookie is sufficient for dashboard access
        const statusRes = await fetch("/api/v1/session/status", { headers: { "X-CSRF-TOKEN": csrfToken } });
        if (!statusRes.ok) {
          console.warn("Session status check failed:", statusRes.status);
        }

        const metricsRes = await fetch("/api/v1/session/metrics", { headers: { "X-CSRF-TOKEN": csrfToken } });
        if (!metricsRes.ok) {
          console.warn("Metrics check failed:", metricsRes.status);
        }
        if (metricsRes.ok) {
          const metrics = await metricsRes.json();
          // Fixed threshold: only escalate if risk > 0.65 and enrollment is mature enough
          if (metrics.risk_score > 0.65 && (metrics.enrollment_progress || 0) >= 0.5) {
            const challengeRes = await fetch("/api/v1/session/silent-challenge", {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
              body: JSON.stringify({ current_risk_score: metrics.risk_score }),
            });
            if (challengeRes.ok) {
              const challenge = await challengeRes.json();
              if (challenge.action === "mfa_required" || challenge.action === "terminate") {
                window.location.href = "/challenge?reason=behavioral_anomaly&score=" + metrics.risk_score.toFixed(2);
              }
            }
          }
        }
        scheduleNext(10_000);
      } catch {
        failureCountRef.current += 1;
        // Exponential backoff: 10s, 30s, 60s, max 120s
        const backoff = Math.min(120_000, 10_000 * Math.pow(2, failureCountRef.current - 1));
        scheduleNext(backoff);
      }
    };

    const scheduleNext = (delay: number) => {
      timeoutRef.current = setTimeout(checkAndFlush, delay);
    };

    scheduleNext(1000); // initial flush/fingerprint

    return () => {
      collector.stop();
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  // Copy-paste security warning toast
  if (!pasteWarning.show) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 20,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 99999,
        animation: "slideDown 0.3s ease-out",
      }}
    >
      <div
        style={{
          background: "linear-gradient(135deg, rgba(220, 38, 38, 0.95), rgba(185, 28, 28, 0.95))",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(239, 68, 68, 0.5)",
          borderRadius: 12,
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          gap: 12,
          boxShadow: "0 8px 32px rgba(220, 38, 38, 0.4), 0 0 0 1px rgba(0,0,0,0.1)",
          maxWidth: 520,
          color: "white",
          fontFamily: "'Inter', -apple-system, sans-serif",
        }}
      >
        <div style={{
          width: 36, height: 36, borderRadius: 8,
          background: "rgba(255,255,255,0.15)",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: 0.5, marginBottom: 2, textTransform: "uppercase" }}>
            ⚠ Copy-Paste Detected
          </div>
          <div style={{ fontSize: 12, opacity: 0.9, lineHeight: 1.4 }}>
            Paste #{pasteWarning.count} flagged by behavioral security.
            This action has been logged and may trigger additional verification.
          </div>
        </div>
        <button
          onClick={() => setPasteWarning(prev => ({ ...prev, show: false }))}
          style={{
            background: "rgba(255,255,255,0.2)",
            border: "none",
            borderRadius: 6,
            width: 28, height: 28,
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer",
            color: "white",
            fontSize: 16,
            flexShrink: 0,
          }}
        >
          ✕
        </button>
      </div>
      <style>{`
        @keyframes slideDown {
          from { opacity: 0; transform: translateX(-50%) translateY(-20px); }
          to { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
      `}</style>
    </div>
  );
}

