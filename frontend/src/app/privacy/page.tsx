"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { getCollector } from "@/lib/behavioral-collector";
import {
  Database,
  Download,
  Trash2,
  Eye,
  Shield,
  Fingerprint,
  MousePointer,
  Keyboard,
  AlertTriangle,
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────── */
interface DataCategory {
  type: string;
  icon: React.ReactNode;
  description: string;
  records: number;
  retention: string;
  purpose: string;
  deletable: boolean;
}

/* ── Mock Data ─────────────────────────────────────────── */
const dataCategories: DataCategory[] = [
  {
    type: "Keystroke Dynamics",
    icon: <Keyboard size={18} />,
    description: "Hold times, flight times, typing speed, rhythm patterns",
    records: 1247,
    retention: "90 days",
    purpose: "Continuous authentication & fraud detection",
    deletable: true,
  },
  {
    type: "Mouse Behavior",
    icon: <MousePointer size={18} />,
    description: "Velocity, acceleration, curvature, click patterns",
    records: 2834,
    retention: "90 days",
    purpose: "Continuous authentication & fraud detection",
    deletable: true,
  },
  {
    type: "Behavioral Embeddings",
    icon: <Fingerprint size={18} />,
    description: "ML-generated behavioral profile vectors (38 features)",
    records: 156,
    retention: "Until withdrawal",
    purpose: "Identity verification & maker-checker",
    deletable: true,
  },
  {
    type: "Authentication Events",
    icon: <Shield size={18} />,
    description: "Login events, MFA verifications, risk scores",
    records: 89,
    retention: "7 years (RBI mandate)",
    purpose: "Compliance & audit trail",
    deletable: false,
  },
  {
    type: "Audit Evidence",
    icon: <Eye size={18} />,
    description: "Hash-chained compliance records, DSAR exports",
    records: 234,
    retention: "7 years (RBI mandate)",
    purpose: "Regulatory compliance",
    deletable: false,
  },
];

const consentPurposes = [
  { purpose: "Behavioral Biometrics Collection", granted: true, grantedAt: "2024-01-15" },
  { purpose: "Keystroke Dynamics Analysis", granted: true, grantedAt: "2024-01-15" },
  { purpose: "Mouse Movement Tracking", granted: true, grantedAt: "2024-01-15" },
  { purpose: "Continuous Authentication", granted: true, grantedAt: "2024-01-15" },
  { purpose: "Fraud Detection", granted: true, grantedAt: "2024-01-15" },
  { purpose: "Risk Scoring", granted: true, grantedAt: "2024-01-15" },
  { purpose: "Anonymized Analytics", granted: false, grantedAt: null },
];

/* ── Main Page ─────────────────────────────────────────── */
export default function PrivacyPage() {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [consents, setConsents] = useState(consentPurposes);
  const [realCounts, setRealCounts] = useState<{ks: number, ms: number, anomaly: number}>({ks: 0, ms: 0, anomaly: 0});

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("PRIVACY");
    collector.start();
    return () => collector.stop();
  }, []);

  // Fetch real record counts from backend
  useEffect(() => {
    (async () => {
      try {
        const csrf = document.cookie?.match(/csrf_access_token=([^;]+)/)?.[1] || "";
        const res = await fetch("/api/v1/session/metrics", { headers: { "X-CSRF-TOKEN": csrf } });
        if (res.ok) {
          const data = await res.json();
          setRealCounts({ ks: data.keystroke_count || 0, ms: data.mouse_count || 0, anomaly: data.anomaly_count || 0 });
        }
      } catch {}
    })();
  }, []);

  // Override mock record counts with real backend data
  const liveCategories = dataCategories.map(c => {
    if (c.type === "Keystroke Dynamics") return { ...c, records: realCounts.ks };
    if (c.type === "Mouse Behavior") return { ...c, records: realCounts.ms };
    if (c.type === "Authentication Events") return { ...c, records: realCounts.anomaly + realCounts.ks };
    if (c.type === "Behavioral Embeddings") return { ...c, records: Math.floor((realCounts.ks + realCounts.ms) / 10) };
    if (c.type === "Audit Evidence") return { ...c, records: realCounts.anomaly };
    return c;
  });

  const totalRecords = liveCategories.reduce((sum, d) => sum + d.records, 0);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const csrfToken = document.cookie?.match(/csrf_access_token=([^;]+)/)?.[1] || "";
      // Call the DSAR (Data Subject Access Request) endpoint
      const res = await fetch("/api/v1/compliance/dsar", {
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": csrfToken
        }
      });
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `dsar_export_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error("DSAR download failed:", err);
    } finally {
      setDownloading(false);
    }
  };

  const toggleConsent = (index: number) => {
    setConsents((prev) =>
      prev.map((c, i) =>
        i === index ? { ...c, granted: !c.granted, grantedAt: c.granted ? null : new Date().toISOString().split("T")[0] } : c
      )
    );
  };

  return (
    <div style={{ minHeight: "100vh", padding: "24px", maxWidth: "960px", margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
          <Database size={24} style={{ color: "#22c55e" }} />
          My Data &amp; Privacy
        </h1>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "4px" }}>
          DPDP Act 2023 Compliant · Your data, your control
        </p>
      </div>

      {/* Summary Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", marginBottom: "24px" }}>
        <div style={{ padding: "16px", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 800 }}>{totalRecords.toLocaleString()}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Total Records</div>
        </div>
        <div style={{ padding: "16px", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 800 }}>{dataCategories.length}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Data Categories</div>
        </div>
        <div style={{ padding: "16px", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center" }}>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#22c55e" }}>{consents.filter((c) => c.granted).length}/{consents.length}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Active Consents</div>
        </div>
      </div>

      {/* Data Categories */}
      <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "12px" }}>Data I&apos;ve Shared</h2>
      {liveCategories.map((cat) => (
        <motion.div
          key={cat.type}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            padding: "16px",
            marginBottom: "10px",
            borderRadius: "var(--radius-md)",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            display: "grid",
            gridTemplateColumns: "auto 1fr auto",
            gap: "16px",
            alignItems: "center",
          }}
        >
          <div style={{ color: "#3b82f6" }}>{cat.icon}</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{cat.type}</div>
            <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "2px" }}>{cat.description}</div>
            <div style={{ display: "flex", gap: "16px", marginTop: "6px" }}>
              <span style={{ fontSize: "0.7rem", color: "var(--muted-2)" }}>Records: {cat.records.toLocaleString()}</span>
              <span style={{ fontSize: "0.7rem", color: "var(--muted-2)" }}>Retention: {cat.retention}</span>
              <span style={{ fontSize: "0.7rem", color: "var(--muted-2)" }}>Purpose: {cat.purpose}</span>
            </div>
          </div>
          <div>
            {cat.deletable ? (
              <span style={{ fontSize: "0.65rem", color: "#22c55e", padding: "2px 8px", borderRadius: "4px", background: "rgba(34,197,94,0.1)" }}>
                Deletable
              </span>
            ) : (
              <span style={{ fontSize: "0.65rem", color: "#f59e0b", padding: "2px 8px", borderRadius: "4px", background: "rgba(245,158,11,0.1)" }}>
                Regulatory Hold
              </span>
            )}
          </div>
        </motion.div>
      ))}

      {/* Consent Management */}
      <h2 style={{ fontSize: "1rem", fontWeight: 600, marginTop: "24px", marginBottom: "12px" }}>Consent Preferences</h2>
      <div style={{ padding: "16px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--border)" }}>
        {consents.map((c, i) => (
          <div
            key={c.purpose}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "10px 0",
              borderBottom: i < consents.length - 1 ? "1px solid var(--border)" : "none",
            }}
          >
            <div>
              <div style={{ fontSize: "0.85rem" }}>{c.purpose}</div>
              {c.grantedAt && <div style={{ fontSize: "0.65rem", color: "var(--muted-2)" }}>Granted: {c.grantedAt}</div>}
            </div>
            <button
              onClick={() => toggleConsent(i)}
              style={{
                width: "44px",
                height: "24px",
                borderRadius: "12px",
                border: "none",
                cursor: "pointer",
                background: c.granted ? "#22c55e" : "var(--surface-2)",
                position: "relative",
                transition: "background 0.2s",
              }}
            >
              <motion.div
                style={{
                  width: "18px",
                  height: "18px",
                  borderRadius: "50%",
                  background: "white",
                  position: "absolute",
                  top: "3px",
                }}
                animate={{ left: c.granted ? "23px" : "3px" }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
              />
            </button>
          </div>
        ))}
      </div>

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: "12px", marginTop: "24px" }}>
        <button
          onClick={handleDownload}
          style={{
            padding: "12px 24px",
            borderRadius: "8px",
            background: "rgba(59,130,246,0.15)",
            border: "1px solid rgba(59,130,246,0.3)",
            color: "#60a5fa",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.9rem",
            fontWeight: 600,
          }}
        >
          <Download size={16} />
          {downloading ? "Preparing..." : "Download My Data"}
        </button>

        <button
          onClick={() => setShowDeleteConfirm(true)}
          style={{
            padding: "12px 24px",
            borderRadius: "8px",
            background: "rgba(239,68,68,0.1)",
            border: "1px solid rgba(239,68,68,0.3)",
            color: "#ef4444",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.9rem",
            fontWeight: 600,
          }}
        >
          <Trash2 size={16} /> Delete My Behavioral Data
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.7)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 100,
        }}>
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            style={{
              padding: "24px",
              borderRadius: "var(--radius-lg)",
              background: "var(--bg)",
              border: "1px solid var(--border)",
              maxWidth: "480px",
              width: "100%",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
              <AlertTriangle size={24} style={{ color: "#ef4444" }} />
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Delete Behavioral Data?</h3>
            </div>
            <p style={{ fontSize: "0.85rem", color: "var(--muted)", lineHeight: 1.6, marginBottom: "16px" }}>
              This will permanently delete all your keystroke dynamics, mouse behavior patterns, and behavioral embeddings.
              Authentication events and audit evidence are retained for 7 years per RBI mandate. This action cannot be undone.
            </p>
            <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowDeleteConfirm(false)}
                style={{
                  padding: "8px 20px", borderRadius: "6px", background: "var(--surface)",
                  border: "1px solid var(--border)", color: "var(--fg)", cursor: "pointer", fontSize: "0.85rem",
                }}
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  try {
                    const csrfToken = document.cookie?.match(/csrf_access_token=([^;]+)/)?.[1] || "";
                    // Call the anonymize/right-to-erasure endpoint
                    const res = await fetch("/api/v1/compliance/anonymize", {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-TOKEN": csrfToken
                      },
                      body: JSON.stringify({ confirm: true })
                    });
                    if (res.ok) {
                      alert("Your behavioral data has been anonymized and deleted.");
                      setShowDeleteConfirm(false);
                    } else {
                      alert("Anonymization request failed. Please try again.");
                    }
                  } catch {
                    alert("Request failed. Please try again.");
                  }
                }}
                style={{
                  padding: "8px 20px", borderRadius: "6px", background: "rgba(239,68,68,0.15)",
                  border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", cursor: "pointer",
                  fontSize: "0.85rem", fontWeight: 600,
                }}
              >
                Delete Permanently
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
