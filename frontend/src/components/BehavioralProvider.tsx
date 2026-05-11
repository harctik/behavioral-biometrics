"use client";

import { useEffect, useRef } from "react";
import { getCollector } from "@/lib/behavioral-collector";

/**
 * Global behavioral data collection provider.
 *
 * Mounts once in the root layout and:
 *  1. Starts the BehavioralCollector on mount (keyboard, mouse, touch, scroll,
 *     navigation, device motion, and cognitive pattern listeners).
 *  2. Flushes collected signals to the backend every 10 seconds while the
 *     user has an active session (identified by csrf_access_token cookie).
 *  3. Stops collection on unmount.
 *
 * This is the single integration point that wires the 667-line collector
 * into the live application.
 */
export function BehavioralProvider() {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const collector = getCollector();
    collector.start();

    // Send device fingerprint on mount
    setTimeout(async () => {
      if (typeof document === "undefined" || !document.cookie.includes("csrf_access_token=")) return;
      const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";
      if (collector.deviceFingerprint && csrfToken) {
        try {
          await fetch("/api/v1/behavioral/device-intel", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrfToken },
            body: JSON.stringify(collector.deviceFingerprint),
          });
        } catch {}
      }
    }, 1000);

    // Flush behavioral data to the backend every 10 seconds
    intervalRef.current = setInterval(async () => {
      // Check if logged in via non-HttpOnly CSRF token
      if (typeof document === "undefined" || !document.cookie.includes("csrf_access_token=")) {
        return;
      }

      const payload = collector.flush("session");

      // Only send if there's meaningful data
      const hasData =
        payload.keystroke_events.length > 0 ||
        payload.mouse_events.length > 0 ||
        payload.touch_events.length > 0;

      if (!hasData) return;

      const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1] || "";

      try {
        // 1. Flush behavioral telemetry
        await fetch("/api/v1/behavioral/data", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": csrfToken
          },
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

        // 2. Check session status
        const statusRes = await fetch("/api/v1/session/status", {
          headers: { "X-CSRF-TOKEN": csrfToken }
        });
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          if (!statusData.session_active) {
            window.location.href = "/login";
            return;
          }
        }

        // 3. Run silent-challenge escalation engine
        const metricsRes = await fetch("/api/v1/session/metrics", {
          headers: { "X-CSRF-TOKEN": csrfToken }
        });
        if (metricsRes.ok) {
          const metrics = await metricsRes.json();
          if (metrics.risk_score > 0.4) {
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
      } catch {
        // Silently fail - behavioral data is supplementary, never block UX
      }
    }, 10_000);

    return () => {
      collector.stop();
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return null; // Invisible provider - no UI
}
