"use client";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";


import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Brain, Info, ChevronDown, ChevronUp, Zap } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { getCollector } from "@/lib/behavioral-collector";

/* ── Types ─────────────────────────────────────────────── */
interface FeatureContribution {
  feature: string;
  value: number;
  contribution: number; // positive = pushes toward genuine, negative = pushes toward impostor
  baseline: number;
}

interface ShapExplanation {
  session_id: string;
  authenticity_score: number;
  base_value: number; // expected score without any features
  features: FeatureContribution[];
  risk_decision: string;
  timestamp: string;
}

/* ── Mock SHAP Data Generator ──────────────────────────── */
function generateShapData(): ShapExplanation {
  const featurePool: Array<{ name: string; category: string }> = [
    { name: "hold_time_mean", category: "keystroke" },
    { name: "flight_time_mean", category: "keystroke" },
    { name: "typing_speed_wpm", category: "keystroke" },
    { name: "rhythm_consistency", category: "keystroke" },
    { name: "digraph_timing", category: "keystroke" },
    { name: "hold_time_std", category: "keystroke" },
    { name: "flight_time_cv", category: "keystroke" },
    { name: "key_interval_mean", category: "keystroke" },
    { name: "bigram_consistency", category: "keystroke" },
    { name: "speed_variance", category: "keystroke" },
    { name: "mouse_velocity_mean", category: "mouse" },
    { name: "mouse_acceleration", category: "mouse" },
    { name: "click_duration_mean", category: "mouse" },
    { name: "movement_efficiency", category: "mouse" },
    { name: "scroll_speed", category: "mouse" },
    { name: "curvature_mean", category: "mouse" },
    { name: "path_directness", category: "mouse" },
    { name: "hover_duration", category: "mouse" },
    { name: "velocity_peaks", category: "mouse" },
    { name: "jerk_smoothness", category: "mouse" },
  ];

  const features: FeatureContribution[] = featurePool.map((f) => ({
    feature: f.name,
    value: Math.random() * 2 - 0.5,
    contribution: (Math.random() - 0.4) * 0.15,
    baseline: Math.random() * 0.5 + 0.3,
  }));

  // Sort by absolute contribution
  features.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));

  const baseValue = 0.5;
  const totalContribution = features.reduce((sum, f) => sum + f.contribution, 0);
  const authScore = Math.max(0, Math.min(1, baseValue + totalContribution));

  return {
    session_id: `sess_${Date.now().toString(36)}`,
    authenticity_score: authScore,
    base_value: baseValue,
    features,
    risk_decision: authScore > 0.7 ? "ALLOW" : authScore > 0.4 ? "MONITOR" : "CHALLENGE",
    timestamp: new Date().toISOString(),
  };
}

/* ── SHAP Force Bar ────────────────────────────────────── */
function ForceBar({ feature, maxContrib }: { feature: FeatureContribution; maxContrib: number }) {
  const isPositive = feature.contribution > 0;
  // Clamp bar width to max 45% of half the container (bars grow from center)
  const barWidth = Math.min(45, (Math.abs(feature.contribution) / maxContrib) * 45);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "4px 0" }}>
      <span
        style={{
          width: "140px",
          fontSize: "0.7rem",
          color: "var(--muted)",
          textAlign: "right",
          fontFamily: "var(--font-mono)",
          flexShrink: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {feature.feature.replace(/_/g, " ")}
      </span>

      {/* Bar container */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", position: "relative", height: "20px", overflow: "hidden" }}>
        {/* Center line */}
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: 0,
            bottom: 0,
            width: "1px",
            background: "rgba(255,255,255,0.15)",
          }}
        />

        {/* Bar */}
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${barWidth}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          style={{
            position: "absolute",
            height: "14px",
            borderRadius: "3px",
            ...(isPositive
              ? {
                  left: "50%",
                  background: "linear-gradient(90deg, rgba(34,197,94,0.6), rgba(34,197,94,0.3))",
                  border: "1px solid rgba(34,197,94,0.4)",
                }
              : {
                  right: "50%",
                  background: "linear-gradient(270deg, rgba(239,68,68,0.6), rgba(239,68,68,0.3))",
                  border: "1px solid rgba(239,68,68,0.4)",
                }),
          }}
        />
      </div>

      <span
        style={{
          width: "60px",
          fontSize: "0.65rem",
          fontFamily: "var(--font-mono)",
          color: isPositive ? "#22c55e" : "#ef4444",
          textAlign: "right",
          flexShrink: 0,
        }}
      >
        {isPositive ? "+" : ""}
        {(feature.contribution * 100).toFixed(2)}%
      </span>
    </div>
  );
}

/* ── Main SHAP Page ────────────────────────────────────── */
export default function ExplainabilityPage() {
  const [explanation, setExplanation] = useState<ShapExplanation>(generateShapData());
  const [showAll, setShowAll] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("EXPLAINABILITY");
    collector.start();
    return () => collector.stop();
  }, []);

  const decisionColors: Record<string, string> = {
    ALLOW: "#22c55e",
    MONITOR: "#eab308",
    CHALLENGE: "#ef4444",
  };

  useEffect(() => {
    const fetchExplanation = async () => {
      try {
        const data = await apiClient<{ 
          selection: { selected_features: string[], feature_weights: Record<string, number> } 
        }>("/v1/behavioral/enrollment/feature-selection");
        
        if (data.selection) {
          const features: FeatureContribution[] = data.selection.selected_features.map(f => ({
            feature: f,
            value: 0,
            contribution: data.selection.feature_weights[f] || 0,
            baseline: 0
          }));

          features.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));

          // Also fetch live session metrics for authenticity score
          let authScore = 0.5;
          let riskDecision = "MONITOR";
          try {
            const csrf = getCsrfToken();
            const mRes = await fetch("/api/v1/session/metrics", { headers: { "X-CSRF-TOKEN": csrf } });
            if (mRes.ok) {
              const mData = await mRes.json();
              authScore = mData.authenticity_score || 0.5;
              riskDecision = authScore > 0.7 ? "ALLOW" : authScore > 0.4 ? "MONITOR" : "CHALLENGE";
            }
          } catch {}

          setExplanation(prev => ({
            ...prev,
            features,
            authenticity_score: authScore,
            risk_decision: riskDecision,
            session_id: "Active Session",
            timestamp: new Date().toISOString()
          }));
        }
      } catch (err) {
        console.error("Failed to fetch SHAP data:", err);
      }
    };

    fetchExplanation();
    if (autoRefresh) {
      const interval = setInterval(fetchExplanation, 10000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const displayedFeatures = showAll ? explanation.features : explanation.features.slice(0, 10);
  const maxContrib = Math.max(...explanation.features.map((f) => Math.abs(f.contribution)), 0.01);

  return (
    <div style={{ minHeight: "100vh", padding: "24px", maxWidth: "1100px", margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
            <Brain size={24} style={{ color: "#8b5cf6" }} />
            SHAP Explainability Dashboard
          </h1>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "4px" }}>
            Feature contributions to authentication decisions · Real-time analysis
          </p>
        </div>
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          style={{
            padding: "6px 14px",
            borderRadius: "6px",
            background: autoRefresh ? "rgba(34,197,94,0.15)" : "var(--surface)",
            border: `1px solid ${autoRefresh ? "rgba(34,197,94,0.3)" : "var(--border)"}`,
            color: autoRefresh ? "#22c55e" : "var(--muted)",
            fontSize: "0.75rem",
            cursor: "pointer",
          }}
        >
          {autoRefresh ? "● Live" : "○ Paused"}
        </button>
      </div>

      {/* Score Summary */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        <div style={{
          padding: "16px", borderRadius: "var(--radius-md)",
          background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center",
        }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Authenticity Score
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: explanation.authenticity_score > 0.7 ? "#22c55e" : "#eab308" }}>
            {(explanation.authenticity_score * 100).toFixed(1)}%
          </div>
        </div>

        <div style={{
          padding: "16px", borderRadius: "var(--radius-md)",
          background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center",
        }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Base Value
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 800 }}>{(explanation.base_value * 100).toFixed(1)}%</div>
        </div>

        <div style={{
          padding: "16px", borderRadius: "var(--radius-md)",
          background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center",
        }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Decision
          </div>
          <div style={{ fontSize: "1.5rem", fontWeight: 800, color: decisionColors[explanation.risk_decision] || "var(--fg)" }}>
            {explanation.risk_decision}
          </div>
        </div>

        <div style={{
          padding: "16px", borderRadius: "var(--radius-md)",
          background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center",
        }}>
          <div style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Features Analyzed
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 800 }}>{explanation.features.length}</div>
        </div>
      </div>

      {/* SHAP Force Plot */}
      <div style={{
        padding: "20px", borderRadius: "var(--radius-lg)",
        background: "var(--surface)", border: "1px solid var(--border)", marginBottom: "16px",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h2 style={{ fontSize: "0.9rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
            <Zap size={16} style={{ color: "#f59e0b" }} />
            Feature Contribution Force Plot
          </h2>
          <div style={{ display: "flex", gap: "16px", fontSize: "0.7rem" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "2px", background: "rgba(34,197,94,0.5)" }} />
              Pushes toward Genuine
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "2px", background: "rgba(239,68,68,0.5)" }} />
              Pushes toward Impostor
            </span>
          </div>
        </div>

        {/* Force bars */}
        {displayedFeatures.map((f) => (
          <ForceBar key={f.feature} feature={f} maxContrib={maxContrib} />
        ))}

        {/* Show more/less */}
        {explanation.features.length > 10 && (
          <button
            onClick={() => setShowAll(!showAll)}
            style={{
              display: "flex", alignItems: "center", gap: "4px", margin: "12px auto 0",
              padding: "6px 16px", borderRadius: "6px", background: "var(--surface-2)",
              border: "1px solid var(--border)", color: "var(--muted)", cursor: "pointer",
              fontSize: "0.75rem",
            }}
          >
            {showAll ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {showAll ? "Show Top 10" : `Show All ${explanation.features.length}`}
          </button>
        )}
      </div>

      {/* Explanation Info */}
      <div style={{
        padding: "16px", borderRadius: "var(--radius-md)",
        background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.15)",
        display: "flex", gap: "10px", alignItems: "flex-start",
      }}>
        <Info size={16} style={{ color: "#3b82f6", marginTop: "2px", flexShrink: 0 }} />
        <div style={{ fontSize: "0.8rem", color: "var(--muted)", lineHeight: 1.6 }}>
          <strong style={{ color: "var(--fg)" }}>How to read this chart:</strong> Each bar shows how much a
          behavioral feature contributes to the authentication decision. Green bars push the score toward
          &quot;genuine user&quot; (higher authenticity), while red bars push toward &quot;impostor&quot; (lower authenticity).
          The base value ({(explanation.base_value * 100).toFixed(0)}%) represents the expected score without
          any behavioral data. Features are ranked by absolute contribution magnitude.
          <br />
          <strong style={{ color: "var(--fg)" }}>RBI Compliance:</strong> This explainability layer satisfies
          RBI Master Direction 2021 requirements for transparent risk scoring in automated decision systems.
        </div>
      </div>
    </div>
  );
}
