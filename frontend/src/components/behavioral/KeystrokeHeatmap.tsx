"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { getCollector } from "@/lib/behavioral-collector";

// ── QWERTY Keyboard Layout ─────────────────────────────────────────────────
const ROWS = [
  ["q","w","e","r","t","y","u","i","o","p"],
  ["a","s","d","f","g","h","j","k","l"],
  ["z","x","c","v","b","n","m"],
];

const SPECIAL_ROW = ["Shift","Space","Backspace"];

interface KeyStats {
  holdMean: number;
  holdCount: number;
  lastActive: number; // timestamp
}

interface DigraphArc {
  from: string;
  to: string;
  flightTime: number;
  timestamp: number;
}

interface HeatmapData {
  keys: Record<string, KeyStats>;
  digraphs: DigraphArc[];
  totalKeys: number;
  uniqueKeys: number;
  wpm: number;
}

// ── Color interpolation ────────────────────────────────────────────────────
function holdTimeToColor(holdMs: number): string {
  // Fast typists: 60-80ms (cool blue), Slow: 150-300ms (hot red)
  const t = Math.min(1, Math.max(0, (holdMs - 50) / 200));
  // Blue → Cyan → Green → Yellow → Orange → Red
  if (t < 0.2) return `hsl(210, 90%, ${55 + t * 50}%)`;
  if (t < 0.4) return `hsl(${210 - (t - 0.2) * 500}, 85%, 55%)`;
  if (t < 0.6) return `hsl(${110 - (t - 0.4) * 350}, 80%, 50%)`;
  if (t < 0.8) return `hsl(${40 - (t - 0.6) * 150}, 90%, 50%)`;
  return `hsl(${10 - (t - 0.8) * 50}, 95%, 48%)`;
}

function holdTimeToGlow(holdMs: number): string {
  const t = Math.min(1, Math.max(0, (holdMs - 50) / 200));
  if (t < 0.3) return "rgba(59, 130, 246, 0.4)";
  if (t < 0.6) return "rgba(16, 185, 129, 0.4)";
  return "rgba(239, 68, 68, 0.4)";
}

export function KeystrokeHeatmap() {
  const [heatmap, setHeatmap] = useState<HeatmapData>({
    keys: {},
    digraphs: [],
    totalKeys: 0,
    uniqueKeys: 0,
    wpm: 0,
  });
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const activeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Poll the collector buffer for live keystroke data
  useEffect(() => {
    const collector = getCollector();
    
    const interval = setInterval(() => {
      const snap = collector.getBufferSnapshot();
      const ks = snap.keystroke_events || [];
      if (ks.length === 0) return;

      const keyMap: Record<string, KeyStats> = {};
      const arcs: DigraphArc[] = [];
      let totalKeys = 0;

      for (let i = 0; i < ks.length; i++) {
        const evt = ks[i];
        const rawKey = (evt.key || "").toLowerCase();
        if (!rawKey || rawKey.length > 12) continue;
        
        // Map to display key
        let displayKey = rawKey;
        if (rawKey === " " || rawKey === "space") displayKey = "Space";
        else if (rawKey === "backspace") displayKey = "Backspace";
        else if (rawKey === "shift") displayKey = "Shift";
        else if (rawKey.length > 1) continue; // Skip other special keys

        totalKeys++;
        const holdTime = evt.hold_time || 0;
        
        if (!keyMap[displayKey]) {
          keyMap[displayKey] = { holdMean: holdTime, holdCount: 1, lastActive: Date.now() };
        } else {
          const prev = keyMap[displayKey];
          prev.holdMean = (prev.holdMean * prev.holdCount + holdTime) / (prev.holdCount + 1);
          prev.holdCount++;
          prev.lastActive = Date.now();
        }

        // Build digraph arcs (last 8 for visual clarity)
        if (i > 0) {
          const prevKey = (ks[i-1].key || "").toLowerCase();
          if (prevKey && prevKey.length === 1 && rawKey.length === 1) {
            arcs.push({
              from: prevKey,
              to: rawKey,
              flightTime: evt.flight_time || 0,
              timestamp: Date.now(),
            });
          }
        }
      }

      // WPM estimate
      const flights = ks.map((k: any) => k.flight_time).filter((f: number) => f > 0 && f < 5000);
      const wpm = flights.length >= 3
        ? Math.round((totalKeys / 5) / (flights.reduce((a: number, b: number) => a + b, 0) / 60000))
        : 0;

      // Track last typed key for pulse animation
      if (ks.length > 0) {
        const lastKey = (ks[ks.length - 1].key || "").toLowerCase();
        let displayLast = lastKey;
        if (lastKey === " " || lastKey === "space") displayLast = "Space";
        else if (lastKey === "backspace") displayLast = "Backspace";
        
        setActiveKey(displayLast);
        if (activeTimeoutRef.current) clearTimeout(activeTimeoutRef.current);
        activeTimeoutRef.current = setTimeout(() => setActiveKey(null), 600);
      }

      setHeatmap({
        keys: keyMap,
        digraphs: arcs.slice(-8),
        totalKeys,
        uniqueKeys: Object.keys(keyMap).length,
        wpm,
      });
    }, 400);

    return () => {
      clearInterval(interval);
      if (activeTimeoutRef.current) clearTimeout(activeTimeoutRef.current);
    };
  }, []);

  // ── Key position lookup for digraph arcs ──────────────────────────────
  const getKeyPosition = useCallback((key: string): { x: number; y: number } | null => {
    for (let row = 0; row < ROWS.length; row++) {
      const col = ROWS[row].indexOf(key);
      if (col !== -1) {
        const offset = row === 1 ? 0.5 : row === 2 ? 1.0 : 0;
        return {
          x: (col + offset) * 36 + 18,
          y: row * 40 + 20,
        };
      }
    }
    return null;
  }, []);

  const renderKey = (key: string, isSpecial = false) => {
    const stats = heatmap.keys[key];
    const isActive = activeKey === key;
    const hasData = !!stats;
    
    const bgColor = hasData ? holdTimeToColor(stats.holdMean) : "transparent";
    const glowColor = hasData ? holdTimeToGlow(stats.holdMean) : "transparent";
    const borderOpacity = hasData ? Math.min(1, stats.holdCount / 5) : 0.15;
    
    return (
      <div
        key={key}
        className={`
          relative flex items-center justify-center rounded-lg
          transition-all duration-200 select-none
          ${isSpecial ? "px-4 min-w-[72px]" : "w-[32px]"}
          h-[32px] text-[10px] font-mono uppercase tracking-wide
          ${isActive ? "scale-110 z-10" : ""}
        `}
        style={{
          background: hasData
            ? `linear-gradient(135deg, ${bgColor}, ${bgColor}dd)`
            : "rgba(255,255,255,0.03)",
          border: `1.5px solid rgba(255,255,255,${borderOpacity})`,
          boxShadow: isActive
            ? `0 0 20px ${glowColor}, 0 0 40px ${glowColor}50, inset 0 1px 0 rgba(255,255,255,0.1)`
            : hasData
            ? `0 0 8px ${glowColor}40, inset 0 1px 0 rgba(255,255,255,0.05)`
            : "inset 0 1px 0 rgba(255,255,255,0.03)",
          transform: isActive ? "scale(1.15) translateY(-2px)" : "scale(1)",
          color: hasData ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.25)",
        }}
        title={hasData ? `${key}: ${Math.round(stats.holdMean)}ms avg hold · ${stats.holdCount} presses` : key}
      >
        {isSpecial ? (key === "Space" ? "━━━" : key === "Backspace" ? "⌫" : "⇧") : key}
        
        {/* Sample count badge */}
        {hasData && stats.holdCount >= 2 && (
          <span
            className="absolute -top-1 -right-1 w-3 h-3 rounded-full flex items-center justify-center text-[6px] font-bold"
            style={{
              background: "rgba(0,0,0,0.7)",
              border: "1px solid rgba(255,255,255,0.2)",
              color: "rgba(255,255,255,0.7)",
            }}
          >
            {stats.holdCount}
          </span>
        )}
        
        {/* Active pulse ring */}
        {isActive && (
          <span
            className="absolute inset-0 rounded-lg animate-ping opacity-30"
            style={{ border: `2px solid ${bgColor || "#3b82f6"}` }}
          />
        )}
      </div>
    );
  };

  return (
    <div ref={containerRef} className="glass-panel rounded-2xl p-5 border border-accent-primary/15 bg-gradient-to-br from-accent-primary/5 to-purple-500/5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent-primary/10 flex items-center justify-center border border-accent-primary/20">
            <span className="text-sm">⌨</span>
          </div>
          <div>
            <div className="text-sm font-semibold text-fg">Live Keystroke Heatmap</div>
            <div className="text-[10px] text-muted">Per-key hold time fingerprint · Type anywhere to see your pattern</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {heatmap.wpm > 0 && (
            <div className="bg-black/30 rounded-lg px-2.5 py-1 border border-border/30">
              <div className="text-lg font-bold text-cyan-400 font-mono">{heatmap.wpm}</div>
              <div className="text-[7px] text-muted uppercase tracking-wider">WPM</div>
            </div>
          )}
          <div className="bg-black/30 rounded-lg px-2.5 py-1 border border-border/30">
            <div className="text-lg font-bold text-accent-primary font-mono">{heatmap.uniqueKeys}</div>
            <div className="text-[7px] text-muted uppercase tracking-wider">Keys</div>
          </div>
        </div>
      </div>

      {/* Keyboard Layout */}
      <div className="relative bg-black/30 rounded-xl p-4 border border-border/20">
        {/* Digraph arcs (SVG overlay) */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-20" style={{ overflow: "visible" }}>
          {heatmap.digraphs.slice(-5).map((arc, i) => {
            const from = getKeyPosition(arc.from);
            const to = getKeyPosition(arc.to);
            if (!from || !to) return null;
            const opacity = 0.15 + (i / 5) * 0.4;
            const midX = (from.x + to.x) / 2;
            const midY = Math.min(from.y, to.y) - 15;
            return (
              <g key={`${arc.from}-${arc.to}-${i}`}>
                <path
                  d={`M ${from.x + 16} ${from.y + 16} Q ${midX + 16} ${midY} ${to.x + 16} ${to.y + 16}`}
                  fill="none"
                  stroke={`rgba(139, 92, 246, ${opacity})`}
                  strokeWidth="1.5"
                  strokeDasharray="4 2"
                />
                <text
                  x={midX + 16}
                  y={midY - 2}
                  textAnchor="middle"
                  fill={`rgba(139, 92, 246, ${opacity + 0.2})`}
                  fontSize="7"
                  fontFamily="monospace"
                >
                  {Math.round(arc.flightTime)}ms
                </text>
              </g>
            );
          })}
        </svg>

        {/* Row 1: Q-P */}
        <div className="flex justify-center gap-1 mb-1 relative z-10">
          {ROWS[0].map(k => renderKey(k))}
        </div>
        {/* Row 2: A-L (offset) */}
        <div className="flex justify-center gap-1 mb-1 pl-4 relative z-10">
          {ROWS[1].map(k => renderKey(k))}
        </div>
        {/* Row 3: Z-M (offset more) */}
        <div className="flex justify-center gap-1 mb-1 pl-8 relative z-10">
          {ROWS[2].map(k => renderKey(k))}
        </div>
        {/* Special row */}
        <div className="flex justify-center gap-1 mt-2 relative z-10">
          {SPECIAL_ROW.map(k => renderKey(k, true))}
        </div>
      </div>

      {/* Legend + Stats */}
      <div className="flex items-center justify-between mt-3">
        <div className="flex items-center gap-2">
          <span className="text-[8px] text-muted uppercase tracking-wider">Hold Time:</span>
          <div className="flex items-center gap-0.5">
            {[50, 80, 110, 140, 180, 220, 260].map((ms, i) => (
              <div
                key={i}
                className="w-3 h-2 rounded-sm"
                style={{ background: holdTimeToColor(ms) }}
                title={`${ms}ms`}
              />
            ))}
          </div>
          <span className="text-[7px] text-muted font-mono">50ms → 260ms+</span>
        </div>
        <div className="text-[8px] text-muted font-mono">
          {heatmap.totalKeys > 0 
            ? `${heatmap.totalKeys} keystrokes · ${heatmap.digraphs.length} digraph pairs captured`
            : "Start typing to build your fingerprint..."}
        </div>
      </div>
    </div>
  );
}
