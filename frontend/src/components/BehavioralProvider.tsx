"use client";

import { useEffect, useRef } from "react";
import { getCollector, DeviceFingerprint } from "@/lib/behavioral-collector";

// Export for sensitive pages to call immediately
export async function flushBehavioralDataNow() {
  if (typeof document === "undefined" || !document.cookie.includes("csrf_access_token=")) return;
  const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";
  const collector = getCollector();
  const payload = await collector.flush("session");
  const hasData = payload.keystroke_events.length > 0 || payload.mouse_events.length > 0 || payload.touch_events.length > 0;
  if (!hasData) return;

  try {
    await fetch("/api/v1/behavioral/data", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
      body: JSON.stringify({
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

  useEffect(() => {
    const collector = getCollector();
    collector.start();

    const checkAndFlush = async () => {
      if (typeof document === "undefined" || !document.cookie.includes("csrf_access_token=")) {
        scheduleNext(10_000);
        return;
      }
      const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";

      // Device Fingerprint diffing
      const currentFp = collector.deviceFingerprint;
      if (currentFp && diffFingerprint(lastFingerprintRef.current, currentFp)) {
        try {
          await fetch("/api/v1/behavioral/device-intel", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
            body: JSON.stringify(currentFp),
          });
          lastFingerprintRef.current = { ...currentFp };
        } catch {}
      }

      const payload = await collector.flush("session");
      const hasData = payload.keystroke_events.length > 0 || payload.mouse_events.length > 0 || payload.touch_events.length > 0;

      if (!hasData) {
        scheduleNext(10_000);
        return;
      }

      try {
        await fetch("/api/v1/behavioral/data", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
          body: JSON.stringify({
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

        failureCountRef.current = 0;

        const statusRes = await fetch("/api/v1/session/status", { headers: { "X-CSRF-TOKEN": csrfToken } });
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          if (!statusData.session_active) {
            window.location.href = "/login";
            return;
          }
        }

        const metricsRes = await fetch("/api/v1/session/metrics", { headers: { "X-CSRF-TOKEN": csrfToken } });
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

  return null;
}
