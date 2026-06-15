"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { Activity } from "lucide-react";

interface TimelinePoint {
  timestamp: string;
  risk_score: number;
  risk_level: string;
  keystroke_count?: number;
  mouse_count?: number;
  anomaly_count?: number;
}

interface TrustTimelineChartProps {
  /** Array of timeline data points */
  points: TimelinePoint[];
  /** Chart width */
  width?: number;
  /** Chart height */
  height?: number;
  /** Auto-refresh interval in ms (0 = disabled) */
  refreshInterval?: number;
  /** Callback to fetch new data */
  onRefresh?: () => void;
}

/**
 * Real-time SVG trust timeline area chart.
 * - Smooth path transitions with SVG animations
 * - Color-coded risk zones (green/amber/red gradient fill)
 * - Hover tooltip with per-point details
 * - Pulsing "LIVE" indicator
 */
export function TrustTimelineChart({
  points,
  width = 600,
  height = 200,
  refreshInterval = 5000,
  onRefresh,
}: TrustTimelineChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  
  // Auto-refresh
  useEffect(() => {
    if (refreshInterval <= 0 || !onRefresh) return;
    const interval = setInterval(onRefresh, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval, onRefresh]);

  // Chart geometry
  const padding = { top: 20, right: 20, bottom: 30, left: 40 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  
  // Scale functions
  const xScale = useCallback((i: number) => {
    if (points.length <= 1) return chartWidth / 2;
    return (i / (points.length - 1)) * chartWidth;
  }, [points.length, chartWidth]);
  
  const yScale = useCallback((v: number) => {
    return chartHeight - (v * chartHeight);
  }, [chartHeight]);

  // Build area path
  const buildAreaPath = () => {
    if (points.length === 0) return "";
    const line = points.map((p, i) => {
      const x = xScale(i);
      const y = yScale(1 - p.risk_score); // invert: higher authenticity = higher on chart
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    }).join(" ");
    
    // Close the area
    return `${line} L ${xScale(points.length - 1)} ${chartHeight} L ${xScale(0)} ${chartHeight} Z`;
  };

  const buildLinePath = () => {
    if (points.length === 0) return "";
    return points.map((p, i) => {
      const x = xScale(i);
      const y = yScale(1 - p.risk_score);
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    }).join(" ");
  };

  // Get risk color for gradient
  const getGradientColor = (riskScore: number) => {
    if (riskScore < 0.35) return "#10b981";
    if (riskScore < 0.65) return "#f59e0b";
    return "#ef4444";
  };

  const latestRisk = points.length > 0 ? points[points.length - 1].risk_score : 0;
  const latestColor = getGradientColor(latestRisk);
  const avgRisk = points.length > 0 
    ? points.reduce((sum, p) => sum + p.risk_score, 0) / points.length 
    : 0;

  // Y-axis labels
  const yLabels = [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="glass-panel rounded-2xl p-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-semibold text-white">Trust Timeline</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
          </span>
          <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Live</span>
        </div>
      </div>

      {/* Chart */}
      <svg
        ref={svgRef}
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        className="overflow-visible"
      >
        <defs>
          {/* Area fill gradient */}
          <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={latestColor} stopOpacity="0.3" />
            <stop offset="100%" stopColor={latestColor} stopOpacity="0.02" />
          </linearGradient>
          {/* Line glow filter */}
          <filter id="lineGlow">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Risk zone bands */}
          <linearGradient id="riskZoneGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity="0.05" />
            <stop offset="35%" stopColor="#f59e0b" stopOpacity="0.03" />
            <stop offset="65%" stopColor="#10b981" stopOpacity="0.03" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.05" />
          </linearGradient>
        </defs>

        <g transform={`translate(${padding.left}, ${padding.top})`}>
          {/* Risk zone background */}
          <rect
            x="0" y="0"
            width={chartWidth} height={chartHeight}
            fill="url(#riskZoneGradient)"
            rx="4"
          />

          {/* Grid lines */}
          {yLabels.map((v) => (
            <g key={v}>
              <line
                x1="0" y1={yScale(v)}
                x2={chartWidth} y2={yScale(v)}
                stroke="rgba(255,255,255,0.06)"
                strokeDasharray="4 4"
              />
              <text
                x="-8" y={yScale(v) + 3}
                textAnchor="end"
                fill="rgba(255,255,255,0.3)"
                fontSize="9"
                fontFamily="monospace"
              >
                {Math.round(v * 100)}%
              </text>
            </g>
          ))}

          {/* Area fill */}
          {points.length > 0 && (
            <motion.path
              d={buildAreaPath()}
              fill="url(#areaGradient)"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8 }}
            />
          )}

          {/* Line */}
          {points.length > 0 && (
            <motion.path
              d={buildLinePath()}
              fill="none"
              stroke={latestColor}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#lineGlow)"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.5, ease: "easeOut" }}
            />
          )}

          {/* Data points */}
          {points.map((p, i) => {
            const x = xScale(i);
            const y = yScale(1 - p.risk_score);
            const pointColor = getGradientColor(p.risk_score);
            return (
              <g key={i}>
                <circle
                  cx={x} cy={y} r={hoveredIndex === i ? 5 : 3}
                  fill={pointColor}
                  stroke="rgba(0,0,0,0.3)"
                  strokeWidth="1"
                  className="cursor-pointer transition-all duration-200"
                  onMouseEnter={() => setHoveredIndex(i)}
                  onMouseLeave={() => setHoveredIndex(null)}
                />
                {/* Last point pulse */}
                {i === points.length - 1 && (
                  <circle
                    cx={x} cy={y} r="6"
                    fill="none"
                    stroke={pointColor}
                    strokeWidth="1.5"
                    opacity="0.4"
                  >
                    <animate attributeName="r" values="4;10;4" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite" />
                  </circle>
                )}
              </g>
            );
          })}

          {/* X-axis time labels */}
          {points.length > 0 && (
            <>
              <text x="0" y={chartHeight + 18} fill="rgba(255,255,255,0.3)" fontSize="9" fontFamily="monospace">
                {points[0].timestamp?.slice(11, 16) || "start"}
              </text>
              <text x={chartWidth} y={chartHeight + 18} textAnchor="end" fill="rgba(255,255,255,0.3)" fontSize="9" fontFamily="monospace">
                {points[points.length - 1].timestamp?.slice(11, 16) || "now"}
              </text>
            </>
          )}

          {/* Hover tooltip */}
          {hoveredIndex !== null && points[hoveredIndex] && (() => {
            const p = points[hoveredIndex];
            const x = Math.min(Math.max(xScale(hoveredIndex), 70), chartWidth - 70);
            const y = yScale(1 - p.risk_score) - 50;
            return (
              <g>
                <rect
                  x={x - 65} y={y - 5}
                  width="130" height="42"
                  rx="6"
                  fill="rgba(0,0,0,0.85)"
                  stroke="rgba(255,255,255,0.1)"
                />
                <text x={x} y={y + 10} textAnchor="middle" fill="white" fontSize="10" fontWeight="600">
                  Risk: {Math.round(p.risk_score * 100)}% • {p.risk_level.toUpperCase()}
                </text>
                <text x={x} y={y + 26} textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="9">
                  KS:{p.keystroke_count || 0} MS:{p.mouse_count || 0} AN:{p.anomaly_count || 0}
                </text>
              </g>
            );
          })()}
        </g>
      </svg>

      {/* Stats footer */}
      <div className="flex items-center justify-between mt-3 text-[10px] text-slate-500">
        <span>Avg Risk: <span className="text-slate-300 font-mono">{(avgRisk * 100).toFixed(1)}%</span></span>
        <span>{points.length} data points</span>
        <span>Latest: <span style={{ color: latestColor }} className="font-bold">{(latestRisk * 100).toFixed(0)}%</span></span>
      </div>
    </motion.div>
  );
}
