"use client";

import React, { useRef, useEffect, useMemo } from "react";

interface TypingDNAProps {
  /** Array of keystroke hold times (ms) — drives bar heights */
  holdTimes: number[];
  /** Array of keystroke flight times (ms) — drives bar opacity/color shift */
  flightTimes: number[];
  /** Max bars to display */
  maxBars?: number;
  /** CSS height */
  height?: number;
  className?: string;
}

/**
 * Renders a real-time "DNA soundwave" visualization of the user's typing rhythm.
 * Each bar represents one keystroke — height = hold time, color intensity = flight time.
 * The wave scrolls left as new keystrokes arrive, creating a unique visual fingerprint.
 */
export function TypingDNA({
  holdTimes,
  flightTimes,
  maxBars = 32,
  height = 48,
  className = "",
}: TypingDNAProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Slice to last N values
  const holds = useMemo(() => holdTimes.slice(-maxBars), [holdTimes, maxBars]);
  const flights = useMemo(() => flightTimes.slice(-maxBars), [flightTimes, maxBars]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Retina support
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    ctx.clearRect(0, 0, w, h);

    if (holds.length === 0) {
      // Draw idle wave placeholder
      ctx.strokeStyle = "rgba(59, 130, 246, 0.15)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = 0; x < w; x++) {
        const y = h / 2 + Math.sin(x * 0.05 + Date.now() * 0.001) * 4;
        x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.stroke();
      return;
    }

    const barW = Math.max(2, (w - (holds.length - 1) * 1.5) / holds.length);
    const maxHold = Math.max(250, ...holds);
    const centerY = h / 2;

    holds.forEach((hold, i) => {
      const flight = flights[i] || 0;
      const normHold = Math.min(1, hold / maxHold);
      const barH = Math.max(2, normHold * (h * 0.9));

      // Color: blue for short holds, purple for long holds
      const hue = 220 + Math.min(60, (hold / 200) * 60); // 220 (blue) → 280 (purple)
      const saturation = 70 + Math.min(30, (flight / 300) * 30);
      const lightness = 55;
      const alpha = 0.5 + normHold * 0.5;

      const x = i * (barW + 1.5);
      const topY = centerY - barH / 2;

      // Glow effect
      ctx.shadowColor = `hsla(${hue}, ${saturation}%, ${lightness}%, 0.4)`;
      ctx.shadowBlur = 4;

      // Bar
      ctx.fillStyle = `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`;
      ctx.beginPath();
      ctx.roundRect(x, topY, barW, barH, 1.5);
      ctx.fill();

      // Bright center line
      ctx.shadowBlur = 0;
      ctx.fillStyle = `hsla(${hue}, 90%, 75%, ${alpha * 0.6})`;
      ctx.fillRect(x + barW * 0.3, centerY - 0.5, barW * 0.4, 1);
    });
  }, [holds, flights, height]);

  return (
    <div className={`relative overflow-hidden rounded-lg ${className}`} style={{ height }}>
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ width: "100%", height: "100%" }}
      />
      {holds.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[9px] text-muted-2 font-mono uppercase tracking-widest animate-pulse">
            Awaiting biometric input...
          </span>
        </div>
      )}
    </div>
  );
}
