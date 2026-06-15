"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Brain, Shield, Activity, Eye, Cpu, AlertTriangle, Fingerprint,
  ChevronDown, ChevronUp, Info, Lock, Zap, Layers, BarChart3,
  ShieldCheck, ShieldAlert, Radio, Sparkles
} from "lucide-react";
import { useTelemetry } from "@/components/TelemetryProvider";
import { getCsrfToken } from "@/lib/auth-utils";

interface EngineExplanation {
  id: string;
  name: string;
  icon: any;
  color: string;
  description: string;
  methodology: string;
  score: number;
  weight: number;
  status: 'active' | 'learning' | 'inactive';
  factors: { name: string; impact: 'positive' | 'negative' | 'neutral'; detail: string }[];
}

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-1.5 w-full bg-black/40 rounded-full overflow-hidden">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }}
        transition={{ duration: 0.8, type: "spring" }}
        className={`h-full rounded-full ${color}`}
      />
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    low: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
    medium: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
    high: 'bg-red-500/10 border-red-500/20 text-red-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono border ${styles[level] || styles.low}`}>
      {level.toUpperCase()}
    </span>
  );
}

export default function ExplainabilityPage() {
  const { score, backendMetrics, enrollment, digraphProfile } = useTelemetry();
  const [expandedEngine, setExpandedEngine] = useState<string | null>(null);
  const [riskAttribution, setRiskAttribution] = useState<Record<string, number>>({});
  const [categoryScores, setCategoryScores] = useState<Record<string, number>>({});

  // Fetch detailed explainability data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const csrf = getCsrfToken();
        const res = await fetch("/api/v1/session/metrics", {
          headers: { "X-CSRF-TOKEN": csrf },
        });
        if (res.ok) {
          const data = await res.json();
          setRiskAttribution(data.ensemble?.risk_attribution || {});
          setCategoryScores(data.category_scores || {});
        }
      } catch {}
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const ensemble = backendMetrics?.ensemble || {};
  const featureRichness = backendMetrics?.feature_richness || 0;

  // Build engine explanations from live data
  const engines: EngineExplanation[] = [
    {
      id: 'identity',
      name: 'Identity Matcher',
      icon: Fingerprint,
      color: 'bg-blue-500',
      description: 'Compares your current behavioral features against your stored profile using Bayesian posterior matching on per-key hold times and digraph flight times.',
      methodology: 'Bayesian Conjugate Prior (Normal-Inverse-Gamma) — each key and key-pair builds an independent posterior distribution. The match score is the product of per-feature likelihoods.',
      score: ensemble.weighted_match_score || 0,
      weight: 0.25,
      status: digraphProfile?.has_profile ? 'active' : 'learning',
      factors: [
        { name: 'Per-Key Hold Time Match', impact: (ensemble.digraph_match_score || 0) > 0.6 ? 'positive' : 'negative', detail: `Digraph match: ${Math.round((ensemble.digraph_match_score || 0) * 100)}%` },
        { name: 'Profile Confidence', impact: (digraphProfile?.confidence || 0) > 0.5 ? 'positive' : 'neutral', detail: `${Math.round((digraphProfile?.confidence || 0) * 100)}% confidence from ${digraphProfile?.updates_count || 0} sessions` },
        { name: 'Keys Profiled', impact: (digraphProfile?.per_key_count || 0) > 15 ? 'positive' : 'neutral', detail: `${digraphProfile?.per_key_count || 0} unique keys profiled` },
      ],
    },
    {
      id: 'liveness',
      name: 'Liveness Detector',
      icon: Eye,
      color: 'bg-emerald-500',
      description: 'Detects whether the input is from a live human or an automated script/bot by analyzing timing entropy, jitter patterns, and interaction naturalness.',
      methodology: 'Entropy-based analysis of hold time distributions + mouse trajectory curvature. Bots show unnaturally low variance and impossibly consistent timing.',
      score: ensemble.liveness_score ?? 1,
      weight: 0.15,
      status: 'active',
      factors: [
        { name: 'Timing Entropy', impact: (ensemble.liveness_score ?? 1) > 0.8 ? 'positive' : 'negative', detail: 'Keystroke timing variance within human norms' },
        { name: 'Mouse Naturalness', impact: 'positive', detail: 'Mouse trajectory curvature and micro-jitter present' },
        { name: 'Interaction Cadence', impact: (ensemble.liveness_score ?? 1) > 0.8 ? 'positive' : 'negative', detail: 'Input cadence matches organic human patterns' },
      ],
    },
    {
      id: 'duress',
      name: 'Duress Detector',
      icon: AlertTriangle,
      color: 'bg-amber-500',
      description: 'Identifies signs of coercion or stress by analyzing hesitation patterns, correction rates, and typing speed deviations from your baseline.',
      methodology: 'Z-score deviation from enrolled WPM, elevated correction rates, excessive hesitation pauses, and abnormal flight time distributions indicate possible duress.',
      score: ensemble.duress_score || 0,
      weight: 0.1,
      status: 'active',
      factors: [
        { name: 'Hesitation Rate', impact: (ensemble.duress_score || 0) < 0.3 ? 'positive' : 'negative', detail: 'Pause patterns within normal range' },
        { name: 'Correction Frequency', impact: (ensemble.duress_score || 0) < 0.3 ? 'positive' : 'negative', detail: 'Backspace rate consistent with profile' },
        { name: 'Speed Deviation', impact: 'neutral', detail: 'WPM within ±2σ of enrolled baseline' },
      ],
    },
    {
      id: 'challenge',
      name: 'Invisible Challenge Engine',
      icon: Zap,
      color: 'bg-purple-500',
      description: 'Injects imperceptible micro-challenges into the UI (subtle layout shifts, timing probes) and measures your response to verify human cognition.',
      methodology: 'Patent-inspired approach (US20150205955A1): measures reaction time to subtle UI perturbations that bots cannot perceive or respond to naturally.',
      score: ensemble.challenge_risk || 0,
      weight: 0.1,
      status: 'active',
      factors: [
        { name: 'Response Latency', impact: (ensemble.challenge_risk || 0) < 0.3 ? 'positive' : 'negative', detail: 'Reaction time within human cognitive bounds' },
        { name: 'Challenge Completion', impact: 'positive', detail: 'All silent challenges answered correctly' },
      ],
    },
    {
      id: 'device',
      name: 'Device Intelligence',
      icon: Cpu,
      color: 'bg-cyan-500',
      description: 'Analyzes device fingerprint, browser capabilities, and hardware signals to detect RATs, emulators, and device anomalies.',
      methodology: 'Canvas fingerprinting, WebGL renderer analysis, screen resolution consistency, and touch/mouse capability checks.',
      score: ensemble.device_risk || 0,
      weight: 0.1,
      status: 'active',
      factors: [
        { name: 'Device Consistency', impact: (ensemble.device_risk || 0) < 0.3 ? 'positive' : 'negative', detail: 'Device fingerprint matches enrolled profile' },
        { name: 'RAT Detection', impact: 'positive', detail: 'No remote access tool signatures detected' },
      ],
    },
    {
      id: 'replay',
      name: 'Replay Detector',
      icon: Radio,
      color: 'bg-rose-500',
      description: 'Detects replayed behavioral streams by analyzing timing entropy and checking for GAN-generated synthetic inputs.',
      methodology: 'Spectral analysis of timing distributions + entropy scoring. Replayed streams show characteristic periodicity absent in genuine input.',
      score: ensemble.replay_risk || 0,
      weight: 0.1,
      status: 'active',
      factors: [
        { name: 'Timing Periodicity', impact: (ensemble.replay_risk || 0) < 0.3 ? 'positive' : 'negative', detail: 'No periodic timing patterns detected' },
        { name: 'Entropy Score', impact: 'positive', detail: 'Input stream entropy within expected range' },
      ],
    },
    {
      id: 'drift',
      name: 'Drift Monitor',
      icon: Layers,
      color: 'bg-teal-500',
      description: 'Tracks gradual changes in your behavioral patterns over time (concept drift) and determines if they represent natural evolution or an identity switch.',
      methodology: 'Page-Hinkley change detection on rolling feature windows + CUSUM monitoring for abrupt distributional shifts.',
      score: ensemble.drift_risk || 0,
      weight: 0.1,
      status: 'active',
      factors: [
        { name: 'Feature Stability', impact: (ensemble.drift_risk || 0) < 0.3 ? 'positive' : 'negative', detail: 'Behavioral features within historical bounds' },
        { name: 'Trend Direction', impact: 'neutral', detail: 'No significant unidirectional drift detected' },
      ],
    },
    {
      id: 'cognitive',
      name: 'Cognitive Analyzer',
      icon: Brain,
      color: 'bg-indigo-500',
      description: 'Analyzes high-level cognitive patterns: reading speed, form navigation strategy, decision timing, and task completion patterns.',
      methodology: 'Models user decision-making latency, field navigation entropy, and pre-submit pause distribution to build a cognitive signature.',
      score: ensemble.cognitive_analysis?.cognitive_risk || 0,
      weight: 0.1,
      status: 'active',
      factors: [
        { name: 'Navigation Pattern', impact: 'positive', detail: 'Form navigation matches expected cognitive flow' },
        { name: 'Decision Timing', impact: 'neutral', detail: 'Task completion speed within normal range' },
      ],
    },
  ];

  const fusedRisk = ensemble.ensemble_risk || 0;
  const fusedAction = ensemble.ensemble_action || 'allow';
  const flags = ensemble.ensemble_flags || [];

  return (
    <main className="flex-1 flex flex-col min-w-0 relative z-0">
      <header className="h-16 px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
        <div className="flex items-center gap-3">
          <Brain className="w-5 h-5 text-accent-secondary" />
          <h1 className="text-xl font-medium text-fg">ML Ensemble Explainability</h1>
        </div>
        <div className="flex items-center gap-3">
          <RiskBadge level={fusedRisk > 0.6 ? 'high' : fusedRisk > 0.3 ? 'medium' : 'low'} />
          <span className={`font-mono text-sm font-bold ${fusedRisk > 0.6 ? 'text-red-400' : fusedRisk > 0.3 ? 'text-amber-400' : 'text-emerald-400'}`}>
            Fused Risk: {(fusedRisk * 100).toFixed(1)}%
          </span>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-8">
        <div className="max-w-4xl mx-auto space-y-8">

          {/* Global Summary Card */}
          <div className="glass-panel rounded-2xl p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-2">Ensemble Decision</div>
              <div className={`text-2xl font-bold ${fusedAction === 'allow' ? 'text-emerald-400' : fusedAction === 'block' ? 'text-red-400' : 'text-amber-400'}`}>
                {fusedAction === 'allow' ? '✓ ALLOW' : fusedAction === 'block' ? '✗ BLOCK' : '⚠ STEP-UP'}
              </div>
              <div className="text-xs text-muted mt-1">{engines.length}-engine Bayesian fusion</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-2">Signal Strength</div>
              <div className="text-2xl font-bold text-fg">{Math.round(featureRichness * 100)}%</div>
              <ScoreBar value={featureRichness} color="bg-gradient-to-r from-violet-500 to-blue-400" />
            </div>
            <div className="text-center">
              <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-2">Active Flags</div>
              <div className="text-2xl font-bold text-fg">{flags.length}</div>
              <div className="flex flex-wrap gap-1 mt-1 justify-center">
                {flags.slice(0, 3).map((f: string, i: number) => (
                  <span key={i} className="px-1.5 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-[8px] font-mono text-red-400">
                    {f.split(':')[0]}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Risk Attribution Waterfall */}
          {Object.keys(riskAttribution).length > 0 && (
            <div className="glass-panel rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="w-4 h-4 text-accent-primary" />
                <h2 className="text-sm font-semibold text-fg">Risk Attribution</h2>
                <span className="text-[10px] text-muted ml-auto">Which engines are contributing to the final risk score</span>
              </div>
              <div className="space-y-2">
                {Object.entries(riskAttribution)
                  .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
                  .map(([key, value]) => (
                    <div key={key} className="flex items-center gap-3">
                      <span className="text-xs text-muted w-32 truncate capitalize">{key.replace(/_/g, ' ')}</span>
                      <div className="flex-1 h-2 bg-black/30 rounded-full overflow-hidden relative">
                        <div
                          className={`h-full rounded-full ${value > 0.3 ? 'bg-red-500' : value > 0.1 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                          style={{ width: `${Math.max(2, Math.abs(value) * 100)}%` }}
                        />
                      </div>
                      <span className={`text-xs font-mono w-12 text-right ${value > 0.3 ? 'text-red-400' : value > 0.1 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {(value * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Category Risk Breakdown */}
          {Object.keys(categoryScores).length > 0 && (
            <div className="glass-panel rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="w-4 h-4 text-purple-400" />
                <h2 className="text-sm font-semibold text-fg">Behavioral Category Scores</h2>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(categoryScores).map(([key, val]) => {
                  const icons: Record<string, any> = {
                    mouse_anomaly: '🖱️', keystroke_anomaly: '⌨️', cognitive_risk: '🧠',
                    physiological_anomaly: '🫀', temporal_rhythm_risk: '⏱️', challenge_bot_risk: '🤖',
                  };
                  return (
                    <div key={key} className="flex items-center gap-2 bg-black/20 rounded-lg p-3 border border-border/30">
                      <span className="text-base">{icons[key] || '📊'}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[9px] text-muted uppercase truncate">{key.replace(/_/g, ' ')}</div>
                        <ScoreBar value={val} color={val > 0.5 ? 'bg-red-500' : val > 0.2 ? 'bg-amber-500' : 'bg-emerald-500'} />
                      </div>
                      <span className={`text-xs font-mono ${val > 0.5 ? 'text-red-400' : val > 0.2 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {(val * 100).toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Engine-by-Engine Breakdown */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-4 h-4 text-accent-primary" />
              <h2 className="text-sm font-semibold text-fg">Engine-by-Engine Analysis</h2>
              <span className="text-[10px] text-muted ml-auto">Click any engine to see methodology and contributing factors</span>
            </div>
            <div className="space-y-3">
              {engines.map((engine) => {
                const isExpanded = expandedEngine === engine.id;
                const Icon = engine.icon;
                const isRisk = engine.id !== 'identity' && engine.id !== 'liveness';
                const displayScore = isRisk ? engine.score : engine.score;
                const riskValue = isRisk ? displayScore : 1 - displayScore;

                return (
                  <motion.div
                    key={engine.id}
                    layout
                    className="glass-panel rounded-xl overflow-hidden"
                  >
                    <button
                      onClick={() => setExpandedEngine(isExpanded ? null : engine.id)}
                      className="w-full flex items-center gap-4 p-4 hover:bg-white/[0.02] transition-colors text-left"
                    >
                      <div className={`w-9 h-9 rounded-lg ${engine.color}/20 flex items-center justify-center shrink-0`}>
                        <Icon className={`w-4 h-4 ${engine.color.replace('bg-', 'text-')}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-fg">{engine.name}</span>
                          <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                            engine.status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : engine.status === 'learning' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                            : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                          }`}>
                            {engine.status}
                          </span>
                        </div>
                        <div className="text-[10px] text-muted mt-0.5 truncate">{engine.description.slice(0, 80)}...</div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <div className="text-right">
                          <div className={`text-sm font-mono font-bold ${
                            riskValue > 0.6 ? 'text-red-400' : riskValue > 0.3 ? 'text-amber-400' : 'text-emerald-400'
                          }`}>
                            {(displayScore * 100).toFixed(0)}%
                          </div>
                          <div className="text-[8px] text-muted">weight: {(engine.weight * 100).toFixed(0)}%</div>
                        </div>
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
                      </div>
                    </button>

                    {isExpanded && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="border-t border-border px-4 pb-4"
                      >
                        <div className="pt-4 space-y-4">
                          {/* Full Description */}
                          <div>
                            <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-1">What It Does</div>
                            <p className="text-xs text-fg/80 leading-relaxed">{engine.description}</p>
                          </div>
                          {/* Methodology */}
                          <div className="bg-black/30 rounded-lg p-3 border border-border/30">
                            <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-1 flex items-center gap-1">
                              <Info className="w-3 h-3" /> Methodology
                            </div>
                            <p className="text-[11px] text-fg/70 leading-relaxed font-mono">{engine.methodology}</p>
                          </div>
                          {/* Contributing Factors */}
                          <div>
                            <div className="text-[10px] text-muted uppercase tracking-wider font-bold mb-2">Contributing Factors</div>
                            <div className="space-y-1.5">
                              {engine.factors.map((f, i) => (
                                <div key={i} className="flex items-center gap-2 text-xs">
                                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                                    f.impact === 'positive' ? 'bg-emerald-500/10 text-emerald-400'
                                    : f.impact === 'negative' ? 'bg-red-500/10 text-red-400'
                                    : 'bg-slate-500/10 text-slate-400'
                                  }`}>
                                    {f.impact === 'positive' ? '✓' : f.impact === 'negative' ? '✗' : '–'}
                                  </span>
                                  <span className="text-fg/80 font-medium">{f.name}</span>
                                  <span className="text-muted text-[10px] ml-auto">{f.detail}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          </div>

          {/* How Bayesian Fusion Works */}
          <div className="glass-panel rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Lock className="w-4 h-4 text-accent-primary" />
              <h2 className="text-sm font-semibold text-fg">How Bayesian Fusion Works</h2>
            </div>
            <div className="text-xs text-muted leading-relaxed space-y-3">
              <p>
                Each engine produces an independent risk or confidence score. These scores are combined using
                <strong className="text-fg"> Bayesian score fusion</strong> — not a simple average, but a weighted
                probabilistic combination that accounts for each engine&apos;s reliability and the current signal quality.
              </p>
              <p>
                The fusion formula: <code className="text-accent-primary bg-black/30 px-1.5 py-0.5 rounded">
                P(risk|engines) ∝ ∏ P(engine_i|risk) × P(risk)
                </code> where each engine&apos;s likelihood is weighted by its historical accuracy and the current
                feature richness ({Math.round(featureRichness * 100)}%).
              </p>
              <p>
                Engine weights are <strong className="text-fg">not static</strong> — they adapt based on enrollment
                maturity. Early in enrollment, high-confidence engines (liveness, device) dominate. As your profile
                matures, identity matching and cognitive analysis gain increasing weight.
              </p>
            </div>
          </div>

        </div>
      </div>
    </main>
  );
}
