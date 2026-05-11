"use client";

import { useState, useEffect } from "react";
import { UserPlus, LogIn, Activity, Send, ShieldAlert, Shield, CheckCircle2 } from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";

// Map string icon names from artifact to actual Lucide components
const IconMap: Record<string, any> = {
  "user-plus": UserPlus,
  "log-in": LogIn,
  "activity": Activity,
  "send": Send,
  "shield-alert": ShieldAlert,
  "shield": Shield,
  "check-circle-2": CheckCircle2
};

const PHASES = [
  {
    id: 1,
    title: "Registration & Passive Enrollment",
    icon: "user-plus",
    desc: "Unlike existing systems that require a tedious calibration phase, this system uses passive enrollment. The customer never knows their behavior is being profiled - zero friction.",
    code: `POST /auth/register {username, password}
-> create_user() + generate MFA secret
-> log_audit_evidence("user_registered")

// No calibration page needed!
// Profile builds silently over the first 5 sessions.`
  },
  {
    id: 2,
    title: "Login with Behavioral Capture",
    icon: "log-in",
    desc: "Sessions 1–5 silently learn HOW the user types. Session 6+: If the typing pattern matches, MFA is automatically skipped. If behavior doesn't match (stolen credentials), Step-up MFA is enforced.",
    code: `POST /auth/login {user, pass, keystroke_data}
-> authenticate_user()
-> ingest_session_data(keystroke_features)

if (match_score > 0.7) {
  return { mfa_required: false } // Frictionless
} else {
  return { mfa_required: true } // Enforced
}`
  },
  {
    id: 3,
    title: "Continuous Session Authentication",
    icon: "activity",
    desc: "After login, the system continuously monitors behavior every 5-10 seconds. Extracts 38 features (18 keystroke, 20 mouse) to detect duress, APP fraud, account takeover, and bots.",
    code: `POST /behavioral/data {events, features}
-> score_with_ensemble(extended_features)
   // 1. CognitiveEngine
   // 2. DuressDetector (43 stress markers)
   // 3. LivenessDetector (Bot vs Human)
   
-> Returns: { ensemble_risk: 0.12, action: "allow" }`
  },
  {
    id: 4,
    title: "Transaction Risk Assessment",
    icon: "send",
    desc: "Captures HOW a user fills the transfer form. Did they copy-paste the account number? Did they hesitate? Injects cognitive analysis, daily limits, and personalized thresholds.",
    code: `POST /transaction/assess {amount, nonce, sig}
-> Verify HMAC + Velocity Check (5 txn/10min)
-> run_cognitive_analysis(features)
-> score_transaction(user, amount, type)

if (duress > 0.7) {
  // Transaction continues normally (protects user)
  // Silent SOC alert sent to bank fraud team
}`
  },
  {
    id: 5,
    title: "Silent Challenge & Escalation",
    icon: "shield-alert",
    desc: "Graduated escalation protocol. Risk < 0.6 remains Normal/Silent. Risk > 0.6 triggers Enhanced Sampling, followed by Step-Up MFA, and eventually Session Termination.",
    code: `// Escalation Protocol
streak = 0: Normal
streak = 1: Silent Monitor
streak = 2: Enhanced Sampling
streak = 3: MFA Required (Step-Up)
streak = 4: Session Terminated`
  }
];

const ENGINES = [
  { name: "CognitiveEngine", weight: "15%", purpose: "Duress, APP fraud, takeover, bot", algo: "Rule-based + statistical" },
  { name: "DuressDetector", weight: "15%", purpose: "Physical coercion detection", algo: "Gradient Boosting (43 features)" },
  { name: "LivenessDetector", weight: "10%", purpose: "Bot vs human classification", algo: "Statistical analysis" },
  { name: "InvisibleChallengeEngine", weight: "10%", purpose: "Silent human verification", algo: "Behavioral response analysis" },
  { name: "TransactionBaseline", weight: "10%", purpose: "Amount/beneficiary anomaly", algo: "Historical percentile" },
  { name: "GAN Replay Detector", weight: "10%", purpose: "Synthetic/replayed behavior", algo: "Entropy analysis" },
  { name: "PerUserFeatureSelector", weight: "10%", purpose: "Top-20 unique features/user", algo: "Feature importance ranking" },
  { name: "DeviceIntelligenceEngine", weight: "8%", purpose: "RAT, emulator, geo-velocity", algo: "Fingerprint + geo analysis" },
  { name: "PassiveEnrollment", weight: "7%", purpose: "Behavioral profile matching", algo: "Z-score + EMA profiling" },
  { name: "CompositeSignalEngine", weight: "5%", purpose: "Lie detection, multi-user", algo: "Multi-signal fusion" }
];

const COMPARISON = [
  { feature: "Authentication", old: "One-time at login (password + OTP)", new: "Continuous throughout entire session" },
  { feature: "Account Takeover", old: "Undetectable if attacker has credentials", new: "Detected mid-session via typing/mouse pattern change" },
  { feature: "APP Fraud", old: "Victim authorized it → bank can't detect", new: "Copy-paste detection + coached behavior analysis" },
  { feature: "Duress/Coercion", old: "Completely invisible to system", new: "43 stress markers detect coerced users silently" },
  { feature: "MFA Friction", old: "Always required → user fatigue", new: "Adaptive - skipped when behavior matches" },
  { feature: "Bot Attacks", old: "Rely on CAPTCHA (bypassable)", new: "Behavioral liveness - bots have zero timing variance" },
  { feature: "Compliance", old: "Manual audit logs", new: "Automated RBI, CERT-In, PCI DSS evidence" }
];

export default function ArchitectureDocsPage() {
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("COMPLIANCE");
    collector.start();
    return () => collector.stop();
  }, []);
  const [activePhase, setActivePhase] = useState(1);

  return (
    <>
      <style dangerouslySetInnerHTML={{__html: `
        .docs-theme {
          --bg: transparent;
          --surface: rgba(10, 10, 10, 0.6);
          --surface-hover: rgba(23, 23, 23, 0.8);
          --fg: oklch(98% 0.005 250);
          --muted: oklch(65% 0.01 250);
          --border: rgba(255, 255, 255, 0.1);
          --accent: oklch(65% 0.16 145);
          --accent-muted: oklch(65% 0.16 145 / 0.15);
          
          --font-display: 'Inter', system-ui, sans-serif;
          --font-body: 'Inter', system-ui, sans-serif;
          --font-mono: 'JetBrains Mono', ui-monospace, monospace;

          background-color: var(--bg);
          color: var(--fg);
          font-family: var(--font-body);
        }

        .docs-theme .font-mono { font-family: var(--font-mono); }
        .docs-theme ::-webkit-scrollbar { width: 6px; height: 6px; }
        .docs-theme ::-webkit-scrollbar-track { background: var(--bg); }
        .docs-theme ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        .docs-theme ::-webkit-scrollbar-thumb:hover { background: var(--muted); }
        
        .docs-theme .prose h2 { font-weight: 600; font-size: 1.5rem; margin-top: 2rem; margin-bottom: 1rem; letter-spacing: -0.02em; }
        .docs-theme .prose h3 { font-weight: 600; font-size: 1.125rem; margin-top: 1.5rem; margin-bottom: 0.75rem; letter-spacing: -0.01em; }
        .docs-theme .prose p { color: var(--muted); line-height: 1.6; margin-bottom: 1rem; font-size: 0.9375rem; }
      `}} />

      <div className="docs-theme flex h-full overflow-hidden text-[var(--fg)] bg-[var(--bg)]">
        {/* Sidebar Nav */}
        <aside className="w-64 bg-[var(--surface)] border-r border-[var(--border)] flex flex-col shrink-0">
          <div className="h-16 px-6 flex items-center gap-3 border-b border-[var(--border)]">
            <div className="w-6 h-6 bg-[var(--accent)] rounded flex items-center justify-center">
              <Shield className="w-3 h-3 text-[var(--bg)]" />
            </div>
            <span className="font-semibold tracking-tight text-sm">Platform Docs</span>
          </div>
          <div className="p-4 flex flex-col gap-1 overflow-y-auto">
            <div className="text-[10px] uppercase tracking-wider text-[var(--muted)] font-bold mb-2 px-3 mt-2">Architecture</div>
            <a href="#overview" className="px-3 py-2 text-sm text-[var(--muted)] hover:text-[var(--fg)] rounded-md hover:bg-[var(--bg)] transition-colors">System Overview</a>
            <a href="#cbs" className="px-3 py-2 text-sm text-[var(--muted)] hover:text-[var(--fg)] rounded-md hover:bg-[var(--bg)] transition-colors">CBS Integration</a>
            
            <div className="text-[10px] uppercase tracking-wider text-[var(--muted)] font-bold mb-2 px-3 mt-6">Working Flow</div>
            {PHASES.map(p => (
              <button 
                key={p.id}
                onClick={() => setActivePhase(p.id)}
                className={`text-left px-3 py-2 text-sm rounded-md transition-colors ${activePhase === p.id ? 'bg-[var(--bg)] text-[var(--accent)] font-medium' : 'text-[var(--muted)] hover:text-[var(--fg)] hover:bg-[var(--bg)]'}`}
              >
                Phase {p.id}: {p.title.split(' ')[0]}...
              </button>
            ))}

            <div className="text-[10px] uppercase tracking-wider text-[var(--muted)] font-bold mb-2 px-3 mt-6">Models & Data</div>
            <a href="#ensemble" className="px-3 py-2 text-sm text-[var(--muted)] hover:text-[var(--fg)] rounded-md hover:bg-[var(--bg)] transition-colors">10-Engine Ensemble</a>
            <a href="#comparison" className="px-3 py-2 text-sm text-[var(--muted)] hover:text-[var(--fg)] rounded-md hover:bg-[var(--bg)] transition-colors">Existing vs Behavioral</a>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto bg-[var(--bg)]">
          <div className="max-w-4xl mx-auto px-12 py-16 prose">
            
            {/* Header */}
            <div className="mb-12">
              <div className="flex items-center gap-2 text-[var(--accent)] text-sm font-mono mb-4">
                <CheckCircle2 className="w-4 h-4" />
                <span>RBI Master Direction 2021 Compliant</span>
              </div>
              <h1 className="text-4xl font-bold tracking-tight text-[var(--fg)] mb-4" id="overview">Behavior-Based Authentication</h1>
              <p className="text-lg text-[var(--muted)]">
                Unlike traditional systems that authenticate once at login, this system silently monitors user behavior throughout the entire net-banking session using keystroke dynamics, mouse movements, and cognitive behavioral patterns.
              </p>
              <div className="flex gap-3 mt-6" id="cbs">
                {['Finacle', 'BaNCS', 'FLEXCUBE', 'T24'].map(cbs => (
                  <span key={cbs} className="px-3 py-1 text-xs font-mono bg-[var(--surface)] border border-[var(--border)] rounded-full text-[var(--muted)]">{cbs} Adapter</span>
                ))}
              </div>
            </div>

            <hr className="border-t border-[var(--border)] my-12" />

            {/* Interactive Flow */}
            <h2 id="flow">Complete Working Flow</h2>
            <p>Select a phase below to see how the continuous authentication lifecycle operates in real-time across the banking environment.</p>

            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden mt-8 flex flex-col md:flex-row">
              <div className="w-full md:w-1/3 bg-[var(--bg)] border-r border-[var(--border)] p-4 flex flex-col gap-2">
                {PHASES.map(p => {
                  const IconComp = IconMap[p.icon];
                  return (
                    <button 
                      key={p.id}
                      onClick={() => setActivePhase(p.id)}
                      className={`text-left px-4 py-3 rounded-lg flex items-start gap-3 transition-colors ${activePhase === p.id ? 'bg-[var(--surface)] border border-[var(--border)] shadow-sm' : 'hover:bg-[var(--surface)] border border-transparent'}`}
                    >
                      <div className={`mt-0.5 ${activePhase === p.id ? 'text-[var(--accent)]' : 'text-[var(--muted)]'}`}>
                        <IconComp className="w-4 h-4" />
                      </div>
                      <div>
                        <div className={`text-sm font-medium ${activePhase === p.id ? 'text-[var(--fg)]' : 'text-[var(--muted)]'}`}>Phase {p.id}</div>
                        <div className={`text-xs mt-0.5 ${activePhase === p.id ? 'text-[var(--muted)]' : 'text-[var(--muted)] opacity-50'}`}>{p.title}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
              <div className="w-full md:w-2/3 p-8 flex flex-col">
                {PHASES.map(p => {
                  if (p.id !== activePhase) return null;
                  const IconComp = IconMap[p.icon];
                  return (
                    <div key={p.id} className="animate-in fade-in flex-1">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-8 h-8 rounded-full bg-[var(--accent-muted)] flex items-center justify-center text-[var(--accent)]">
                          <IconComp className="w-4 h-4" />
                        </div>
                        <h3 className="!m-0 text-lg">{p.title}</h3>
                      </div>
                      <p className="text-sm text-[var(--muted)] leading-relaxed mb-6">{p.desc}</p>
                      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-md p-4 overflow-x-auto">
                        <pre className="text-xs font-mono text-[var(--muted)] m-0"><code>{p.code}</code></pre>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <hr className="border-t border-[var(--border)] my-16" />

            {/* Ensemble Section */}
            <h2 id="ensemble">10-Engine ML Pipeline</h2>
            <p>The system utilizes a weighted fusion of 10 distinct machine learning engines to produce a single 0.0–1.0 risk score in real-time.</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
              {ENGINES.map((engine, i) => (
                <div key={i} className="bg-[var(--surface)] border border-[var(--border)] p-4 rounded-lg flex flex-col justify-between">
                  <div>
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-mono text-xs text-[var(--accent)]">Engine {i+1}</span>
                      <span className="text-xs font-mono text-[var(--muted)] bg-[var(--bg)] px-2 py-0.5 rounded">{engine.weight} wt</span>
                    </div>
                    <h4 className="text-sm font-semibold text-[var(--fg)] mb-1">{engine.name}</h4>
                    <p className="text-xs text-[var(--muted)] mb-4">{engine.purpose}</p>
                  </div>
                  <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider pt-3 border-t border-[var(--border)]">
                    {engine.algo}
                  </div>
                </div>
              ))}
            </div>

            <hr className="border-t border-[var(--border)] my-16" />

            {/* Comparison Table */}
            <h2 id="comparison">Existing System vs. This System</h2>
            <p>How continuous behavioral biometrics bridges the security gaps left by traditional one-time authentication systems.</p>

            <div className="mt-8 border border-[var(--border)] rounded-lg overflow-hidden bg-[var(--surface)]">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--bg)] border-b border-[var(--border)]">
                  <tr>
                    <th className="px-6 py-4 font-medium text-[var(--muted)] w-1/4">Aspect</th>
                    <th className="px-6 py-4 font-medium text-[var(--muted)] w-3/8 border-l border-[var(--border)]">Existing Banking Auth</th>
                    <th className="px-6 py-4 font-medium text-[var(--accent)] w-3/8 border-l border-[var(--border)]">Behavioral System</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {COMPARISON.map((row, i) => (
                    <tr key={i} className="hover:bg-[var(--surface-hover)] transition-colors">
                      <td className="px-6 py-4 font-medium">{row.feature}</td>
                      <td className="px-6 py-4 text-[var(--muted)] border-l border-[var(--border)]">{row.old}</td>
                      <td className="px-6 py-4 text-[var(--fg)] border-l border-[var(--border)]">{row.new}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="my-24"></div>
          </div>
        </main>
      </div>
    </>
  );
}
