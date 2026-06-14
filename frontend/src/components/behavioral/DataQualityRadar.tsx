"use client";

import React, { useRef, useEffect } from "react";

interface DataQualityRadarProps {
  /** Number of unique digraph pairs captured */
  digraphs: number;
  /** Typing consistency score 0-100 (inverse of correction rate) */
  consistency: number;
  /** Rhythm quality 0-100 (based on hold/flight time variance stability) */
  rhythm: number;
  /** Volume: total keystrokes as percentage of target (e.g. 40 target) */
  volume: number;
  /** Accuracy of typed text match 0-100 */
  accuracy: number;
  /** CSS class */
  className?: string;
  /** Size in px */
  size?: number;
}

/**
 * Radar/spider chart showing 5 dimensions of enrollment data quality.
 * Renders on a canvas for crisp visuals at any size.
 */
export function DataQualityRadar({
  digraphs,
  consistency,
  rhythm,
  volume,
  accuracy,
  className = "",
  size = 160,
}: DataQualityRadarProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Normalize all values to 0-1
  const axes = [
    { label: "Digraphs", value: Math.min(1, digraphs / 25) },
    { label: "Consistency", value: Math.min(1, consistency / 100) },
    { label: "Rhythm", value: Math.min(1, rhythm / 100) },
    { label: "Volume", value: Math.min(1, volume / 100) },
    { label: "Accuracy", value: Math.min(1, accuracy / 100) },
  ];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, size, size);

    const cx = size / 2;
    const cy = size / 2;
    const maxR = size / 2 - 24;
    const n = axes.length;
    const angleStep = (Math.PI * 2) / n;
    const startAngle = -Math.PI / 2; // Top

    // Draw grid rings
    for (let ring = 1; ring <= 4; ring++) {
      const r = (ring / 4) * maxR;
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        const angle = startAngle + i * angleStep;
        const x = cx + Math.cos(angle) * r;
        const y = cy + Math.sin(angle) * r;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = ring === 4 ? "rgba(255,255,255,0.1)" : "rgba(255,255,255,0.05)";
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }

    // Draw axis lines
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(angle) * maxR, cy + Math.sin(angle) * maxR);
      ctx.strokeStyle = "rgba(255,255,255,0.06)";
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }

    // Draw data polygon
    ctx.beginPath();
    axes.forEach((axis, i) => {
      const angle = startAngle + i * angleStep;
      const r = axis.value * maxR;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath();

    // Fill
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR);
    grad.addColorStop(0, "rgba(59, 130, 246, 0.25)");
    grad.addColorStop(1, "rgba(139, 92, 246, 0.1)");
    ctx.fillStyle = grad;
    ctx.fill();

    // Stroke
    ctx.strokeStyle = "rgba(59, 130, 246, 0.6)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Draw data points
    axes.forEach((axis, i) => {
      const angle = startAngle + i * angleStep;
      const r = axis.value * maxR;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;

      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fillStyle = axis.value > 0.6 ? "rgba(16, 185, 129, 0.9)" : "rgba(245, 158, 11, 0.9)";
      ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.3)";
      ctx.lineWidth = 0.5;
      ctx.stroke();
    });

    // Draw labels
    ctx.font = "9px ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    axes.forEach((axis, i) => {
      const angle = startAngle + i * angleStep;
      const labelR = maxR + 16;
      const x = cx + Math.cos(angle) * labelR;
      const y = cy + Math.sin(angle) * labelR;
      ctx.fillStyle = axis.value > 0.6 ? "rgba(148, 163, 184, 0.9)" : "rgba(148, 163, 184, 0.5)";
      ctx.fillText(axis.label, x, y);
    });
  }, [axes, size]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width: size, height: size }}
    />
  );
}
