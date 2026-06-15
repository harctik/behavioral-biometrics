"use client";

import { useEffect, useState, useRef } from "react";
import { motion, useSpring, useTransform } from "framer-motion";

interface RiskGaugeProps {
  /** Risk score from 0 (safe) to 1 (dangerous) */
  value: number;
  /** Size in pixels */
  size?: number;
  /** Label shown below the score */
  label?: string;
  /** Whether to show the animated glow */
  showGlow?: boolean;
}

/**
 * Premium animated SVG arc gauge for risk visualization.
 * - Smooth spring animation on score changes
 * - Color transitions: emerald → amber → red
 * - Glassmorphism card with risk-level glow
 * - Pulsing dot for "LIVE" indicator
 */
export function RiskGauge({ value, size = 200, label = "Risk Score", showGlow = true }: RiskGaugeProps) {
  const clampedValue = Math.max(0, Math.min(1, value));
  const percentage = Math.round(clampedValue * 100);
  
  // Spring animation for smooth value transitions
  const springValue = useSpring(clampedValue, { stiffness: 80, damping: 20 });
  const [displayValue, setDisplayValue] = useState(percentage);
  
  useEffect(() => {
    springValue.set(clampedValue);
  }, [clampedValue, springValue]);
  
  useEffect(() => {
    const unsubscribe = springValue.on("change", (latest) => {
      setDisplayValue(Math.round(latest * 100));
    });
    return unsubscribe;
  }, [springValue]);

  // Arc geometry
  const cx = size / 2;
  const cy = size / 2;
  const strokeWidth = size * 0.08;
  const radius = (size - strokeWidth * 2) / 2;
  const startAngle = 135;
  const endAngle = 405;
  const totalAngle = endAngle - startAngle; // 270 degrees
  
  const polarToCartesian = (angle: number) => {
    const rad = ((angle - 90) * Math.PI) / 180;
    return {
      x: cx + radius * Math.cos(rad),
      y: cy + radius * Math.sin(rad),
    };
  };
  
  const describeArc = (start: number, end: number) => {
    const s = polarToCartesian(start);
    const e = polarToCartesian(end);
    const largeArc = end - start > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${largeArc} 1 ${e.x} ${e.y}`;
  };
  
  // Background arc (full)
  const bgArc = describeArc(startAngle, endAngle);
  
  // Value arc
  const valueAngle = startAngle + totalAngle * clampedValue;
  const valueArc = clampedValue > 0.001 ? describeArc(startAngle, Math.min(valueAngle, endAngle - 0.1)) : "";
  
  // Color based on risk level
  const getColor = (v: number) => {
    if (v < 0.35) return { main: "#10b981", glow: "rgba(16, 185, 129, 0.3)", label: "LOW", bg: "rgba(16, 185, 129, 0.08)" };
    if (v < 0.65) return { main: "#f59e0b", glow: "rgba(245, 158, 11, 0.3)", label: "MEDIUM", bg: "rgba(245, 158, 11, 0.08)" };
    return { main: "#ef4444", glow: "rgba(239, 68, 68, 0.3)", label: "HIGH", bg: "rgba(239, 68, 68, 0.08)" };
  };
  
  const color = getColor(clampedValue);
  const authenticity = Math.round((1 - clampedValue) * 100);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="relative flex flex-col items-center"
    >
      {/* Glow background */}
      {showGlow && (
        <div
          className="absolute inset-0 rounded-full blur-3xl opacity-30 transition-colors duration-1000"
          style={{ background: color.glow, transform: "scale(0.6)" }}
        />
      )}
      
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="drop-shadow-lg">
        {/* Gradient definitions */}
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#10b981" />
            <stop offset="50%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>
          <filter id="gaugeShadow">
            <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor={color.main} floodOpacity="0.5" />
          </filter>
        </defs>
        
        {/* Background track */}
        <path
          d={bgArc}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        
        {/* Tick marks */}
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const angle = startAngle + totalAngle * tick;
          const outer = polarToCartesian(angle);
          const innerRadius = radius - strokeWidth * 0.8;
          const rad = ((angle - 90) * Math.PI) / 180;
          const inner = {
            x: cx + innerRadius * Math.cos(rad),
            y: cy + innerRadius * Math.sin(rad),
          };
          return (
            <line
              key={tick}
              x1={outer.x}
              y1={outer.y}
              x2={inner.x}
              y2={inner.y}
              stroke="rgba(255,255,255,0.15)"
              strokeWidth={1.5}
            />
          );
        })}
        
        {/* Value arc */}
        {valueArc && (
          <motion.path
            d={valueArc}
            fill="none"
            stroke={color.main}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            filter="url(#gaugeShadow)"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        )}
        
        {/* Center text */}
        <text
          x={cx}
          y={cy - size * 0.06}
          textAnchor="middle"
          className="font-mono"
          fill="white"
          fontSize={size * 0.2}
          fontWeight="bold"
        >
          {displayValue}%
        </text>
        <text
          x={cx}
          y={cy + size * 0.08}
          textAnchor="middle"
          fill={color.main}
          fontSize={size * 0.075}
          fontWeight="600"
          letterSpacing="0.1em"
        >
          {color.label}
        </text>
        <text
          x={cx}
          y={cy + size * 0.18}
          textAnchor="middle"
          fill="rgba(255,255,255,0.4)"
          fontSize={size * 0.055}
        >
          {label}
        </text>
      </svg>
      
      {/* Authenticity badge below */}
      <div className="mt-2 flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span
            className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60"
            style={{ backgroundColor: color.main }}
          />
          <span
            className="relative inline-flex rounded-full h-2.5 w-2.5"
            style={{ backgroundColor: color.main }}
          />
        </span>
        <span className="text-xs font-medium text-slate-400">
          Authenticity: <span className="text-white font-bold">{authenticity}%</span>
        </span>
      </div>
    </motion.div>
  );
}
