"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { ShieldAlert, X, AlertTriangle, Clipboard } from "lucide-react";

/**
 * Global Copy-Paste Warning System
 *
 * Renders a prominent animated warning banner at the top of the viewport
 * whenever a paste event is detected. This is a security feature that:
 *  - Alerts the user that paste was detected and logged
 *  - Shows which field was targeted
 *  - Tracks cumulative paste count per session
 *  - Applies risk escalation styling (yellow → orange → red)
 *  - Cannot be suppressed by the user (behavioral data still logged)
 */

interface PasteAlert {
  id: number;
  timestamp: number;
  field: string;
  charCount: number;
  type: "paste" | "cut" | "autofill";
}

export function GlobalPasteWarning() {
  const [alerts, setAlerts] = useState<PasteAlert[]>([]);
  const [totalPastes, setTotalPastes] = useState(0);
  const [showBanner, setShowBanner] = useState(false);
  const [latestAlert, setLatestAlert] = useState<PasteAlert | null>(null);
  const alertIdRef = useRef(0);
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handlePaste = useCallback((e: ClipboardEvent) => {
    const target = e.target as HTMLInputElement | HTMLTextAreaElement;
    const fieldName =
      target?.id ||
      target?.name ||
      target?.getAttribute("aria-label") ||
      target?.placeholder ||
      target?.tagName?.toLowerCase() ||
      "unknown";

    const text = e.clipboardData?.getData("text") || "";

    const alert: PasteAlert = {
      id: ++alertIdRef.current,
      timestamp: Date.now(),
      field: fieldName,
      charCount: text.length,
      type: "paste",
    };

    setAlerts((prev) => [...prev, alert]);
    setTotalPastes((prev) => prev + 1);
    setLatestAlert(alert);
    setShowBanner(true);

    // Auto-dismiss after 10 seconds
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    dismissTimerRef.current = setTimeout(() => setShowBanner(false), 10000);
  }, []);

  const handleCut = useCallback((e: ClipboardEvent) => {
    const target = e.target as HTMLInputElement;
    if (target?.type === "password") return;

    const alert: PasteAlert = {
      id: ++alertIdRef.current,
      timestamp: Date.now(),
      field: target?.id || target?.name || "unknown",
      charCount: 0,
      type: "cut",
    };

    setAlerts((prev) => [...prev, alert]);
    setTotalPastes((prev) => prev + 1);
    setLatestAlert(alert);
    setShowBanner(true);

    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    dismissTimerRef.current = setTimeout(() => setShowBanner(false), 10000);
  }, []);

  useEffect(() => {
    document.addEventListener("paste", handlePaste as EventListener, { capture: true });
    document.addEventListener("cut", handleCut as EventListener, { capture: true });
    return () => {
      document.removeEventListener("paste", handlePaste as EventListener, { capture: true });
      document.removeEventListener("cut", handleCut as EventListener, { capture: true });
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    };
  }, [handlePaste, handleCut]);

  if (!showBanner || !latestAlert) return null;

  // Escalating severity
  const severity = totalPastes >= 4 ? "critical" : totalPastes >= 2 ? "high" : "warning";
  const colors = {
    warning: {
      bg: "rgba(245, 158, 11, 0.08)",
      border: "rgba(245, 158, 11, 0.4)",
      text: "#f59e0b",
      glow: "0 0 30px rgba(245, 158, 11, 0.15)",
      label: "PASTE DETECTED",
    },
    high: {
      bg: "rgba(249, 115, 22, 0.1)",
      border: "rgba(249, 115, 22, 0.5)",
      text: "#f97316",
      glow: "0 0 40px rgba(249, 115, 22, 0.2)",
      label: "MULTIPLE PASTES DETECTED",
    },
    critical: {
      bg: "rgba(239, 68, 68, 0.12)",
      border: "rgba(239, 68, 68, 0.6)",
      text: "#ef4444",
      glow: "0 0 50px rgba(239, 68, 68, 0.25)",
      label: "⚠ CLIPBOARD ABUSE DETECTED",
    },
  };

  const c = colors[severity];

  return (
    <div
      className="fixed top-4 left-1/2 -translate-x-1/2 z-[10000] w-[calc(100vw-32px)] max-w-[520px]"
      style={{ animation: "slideDown 0.3s ease-out" }}
    >
      <style>{`
        @keyframes slideDown {
          from { transform: translate(-50%, -100%); opacity: 0; }
          to { transform: translate(-50%, 0); opacity: 1; }
        }
        @keyframes warningPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        @keyframes scanline {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
      <div
        className="relative rounded-xl overflow-hidden"
        style={{
          background: c.bg,
          border: `1px solid ${c.border}`,
          backdropFilter: "blur(24px) saturate(1.5)",
          boxShadow: c.glow,
        }}
      >
        {/* Animated scanline */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `linear-gradient(90deg, transparent, ${c.text}15, transparent)`,
            animation: "scanline 2s ease-in-out infinite",
          }}
        />

        <div className="relative px-4 py-3 flex items-start gap-3">
          {/* Icon */}
          <div
            className="shrink-0 mt-0.5"
            style={{ animation: "warningPulse 1.5s ease-in-out infinite" }}
          >
            {severity === "critical" ? (
              <AlertTriangle className="w-5 h-5" style={{ color: c.text }} />
            ) : (
              <Clipboard className="w-5 h-5" style={{ color: c.text }} />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div
              className="text-[11px] font-bold uppercase tracking-[0.15em]"
              style={{ color: c.text }}
            >
              {c.label}
            </div>
            <div className="text-[10px] text-white/70 mt-1 leading-relaxed">
              {latestAlert.type === "paste" ? (
                <>
                  Clipboard content pasted into{" "}
                  <span className="font-mono text-white/90 bg-white/10 px-1 rounded">
                    {latestAlert.field}
                  </span>
                  {latestAlert.charCount > 0 && (
                    <span className="text-white/50">
                      {" "}({latestAlert.charCount} characters)
                    </span>
                  )}
                </>
              ) : (
                <>
                  Content cut from{" "}
                  <span className="font-mono text-white/90 bg-white/10 px-1 rounded">
                    {latestAlert.field}
                  </span>
                </>
              )}
            </div>
            <div className="text-[9px] text-white/40 mt-1.5 flex items-center gap-3">
              <span>
                Session total:{" "}
                <span style={{ color: c.text }} className="font-mono font-bold">
                  {totalPastes}×
                </span>{" "}
                paste events
              </span>
              <span>•</span>
              <span>Behavioral risk: {severity === "critical" ? "ELEVATED" : severity === "high" ? "MODERATE" : "NOTED"}</span>
            </div>
          </div>

          {/* Dismiss */}
          <button
            onClick={() => setShowBanner(false)}
            className="shrink-0 p-1 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-3.5 h-3.5 text-white/40 hover:text-white/80" />
          </button>
        </div>

        {/* Severity bar at bottom */}
        <div className="h-0.5 w-full" style={{ background: `linear-gradient(90deg, transparent, ${c.text}, transparent)` }} />
      </div>
    </div>
  );
}
