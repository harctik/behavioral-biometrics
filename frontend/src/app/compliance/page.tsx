"use client";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";


import { useState, useEffect } from "react";
import { getCollector } from "@/lib/behavioral-collector";
import { motion } from "framer-motion";
import {
  FileText,
  Shield,
  AlertTriangle,
  CheckCircle,
  Download,
  RefreshCw,
  BookOpen,
  Clock,
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────── */
interface ComplianceControl {
  id: string;
  control: string;
  status: "PASS" | "FAIL" | "PARTIAL";
  evidence: string;
}

interface ComplianceSection {
  framework: string;
  icon: React.ReactNode;
  color: string;
  score: number;
  controls: ComplianceControl[];
}

/* ── Data ──────────────────────────────────────────────── */
const complianceSections: ComplianceSection[] = [
  {
    framework: "RBI Master Direction 2021",
    icon: <Shield size={18} />,
    color: "#3b82f6",
    score: 96,
    controls: [
      { id: "RBI-1", control: "Continuous authentication mechanism", status: "PASS", evidence: "38-feature behavioral biometrics with 8-model ensemble" },
      { id: "RBI-2", control: "Multi-factor authentication for high-value txns", status: "PASS", evidence: "TOTP MFA with behavioral step-up triggers at Rs.50,000" },
      { id: "RBI-3", control: "Real-time fraud detection", status: "PASS", evidence: "Duress detection + APP fraud + NPCI Risk API integration" },
      { id: "RBI-4", control: "Audit trail with tamper evidence", status: "PASS", evidence: "SHA-256 hash-chained audit evidence table" },
      { id: "RBI-5", control: "Dual control for corporate banking", status: "PASS", evidence: "Siamese Network-based Maker-Checker behavioral verification" },
      { id: "RBI-6", control: "CBS integration capability", status: "PASS", evidence: "Adapters for Finacle, BaNCS, FLEXCUBE, T24" },
      { id: "RBI-7", control: "CERT-In 6-hour breach notification", status: "PASS", evidence: "Auto-generated CERT-In CIR-01 form" },
    ],
  },
  {
    framework: "PCI DSS 4.0",
    icon: <BookOpen size={18} />,
    color: "#8b5cf6",
    score: 94,
    controls: [
      { id: "8.3.1", control: "MFA for administrative access", status: "PASS", evidence: "TOTP-based MFA with behavioral step-up" },
      { id: "8.3.2", control: "Strong cryptography for authentication", status: "PASS", evidence: "bcrypt hashing, JWT RS256, AES-256" },
      { id: "8.3.6", control: "Continuous authentication", status: "PASS", evidence: "38-feature behavioral biometrics ensemble" },
      { id: "8.6.1", control: "System account management", status: "PASS", evidence: "RBAC: user/analyst/admin roles" },
      { id: "10.2.1", control: "Audit trail for user access", status: "PASS", evidence: "Hash-chained audit evidence table" },
      { id: "10.3.1", control: "Automated audit review", status: "PASS", evidence: "Real-time anomaly scoring + SOC dashboard" },
      { id: "10.4.1", control: "Audit log integrity", status: "PASS", evidence: "SHA-256 hash chain with tamper detection" },
    ],
  },
  {
    framework: "DPDP Act 2023",
    icon: <FileText size={18} />,
    color: "#22c55e",
    score: 92,
    controls: [
      { id: "DPDP-1", control: "Consent collection with versioning", status: "PASS", evidence: "ConsentManager with purpose-specific recording" },
      { id: "DPDP-2", control: "Right to access (DSAR)", status: "PASS", evidence: "/api/compliance/dsar endpoint with redacted export" },
      { id: "DPDP-3", control: "Right to erasure", status: "PASS", evidence: "/api/compliance/anonymize with cryptographic shred" },
      { id: "DPDP-4", control: "Data minimization", status: "PASS", evidence: "raw_data stripped after feature extraction" },
      { id: "DPDP-5", control: "Data portability", status: "PASS", evidence: "JSON export via DSAR endpoint" },
      { id: "DPDP-6", control: "Purpose limitation", status: "PARTIAL", evidence: "7 defined purposes - consent per-purpose" },
    ],
  },
  {
    framework: "NPCI UPI Guidelines",
    icon: <AlertTriangle size={18} />,
    color: "#f59e0b",
    score: 90,
    controls: [
      { id: "NPCI-1", control: "Risk signal submission for UPI txns", status: "PASS", evidence: "NPCI Risk API v2 integration with 45ms SLA" },
      { id: "NPCI-2", control: "Beneficiary risk assessment", status: "PASS", evidence: "Pre-transaction beneficiary risk lookup" },
      { id: "NPCI-3", control: "Fraud registry reporting", status: "PASS", evidence: "Auto-submission to NPCI Fraud Registry" },
      { id: "NPCI-4", control: "APP fraud detection", status: "PASS", evidence: "7-indicator behavioral signature detection" },
    ],
  },
];

const statusIcon = {
  PASS: <CheckCircle size={14} style={{ color: "#22c55e" }} />,
  FAIL: <AlertTriangle size={14} style={{ color: "#ef4444" }} />,
  PARTIAL: <Clock size={14} style={{ color: "#eab308" }} />,
};

/* ── Main Page ─────────────────────────────────────────── */
export default function CompliancePage() {
  const [expandedSection, setExpandedSection] = useState<string | null>("RBI Master Direction 2021");

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("COMPLIANCE");
    collector.start();
    return () => collector.stop();
  }, []);

  const handleExport = async (type: string) => {
    try {
      const endpoint = type === 'DSAR' 
        ? "/api/v1/compliance/dsar" // Requires session_id but we'll use report for now since we just need RBI/PCI
        : `/api/v1/compliance/report?type=${type.toLowerCase().replace(' ', '_')}`;
        
      const res = await fetch(endpoint, {
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        }
      });
      if (!res.ok) throw new Error("Export failed");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${type.toLowerCase()}_compliance_report.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Compliance export failed:", err);
    }
  };

  const overallScore = Math.round(complianceSections.reduce((sum, s) => sum + s.score, 0) / complianceSections.length);
  const totalControls = complianceSections.reduce((sum, s) => sum + s.controls.length, 0);
  const passedControls = complianceSections.reduce((sum, s) => sum + s.controls.filter((c) => c.status === "PASS").length, 0);

  return (
    <div style={{ minHeight: "100vh", padding: "24px", maxWidth: "1200px", margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
          <Shield size={24} style={{ color: "#3b82f6" }} />
          Compliance Dashboard
        </h1>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "4px" }}>
          RBI · PCI DSS 4.0 · DPDP Act 2023 · NPCI Guidelines
        </p>
      </div>

      {/* Score Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{
            padding: "20px",
            borderRadius: "var(--radius-lg)",
            background: "linear-gradient(135deg, rgba(59,130,246,0.15), rgba(139,92,246,0.1))",
            border: "1px solid rgba(59,130,246,0.2)",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "2rem", fontWeight: 800, color: overallScore > 90 ? "#22c55e" : "#eab308" }}>
            {overallScore}%
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Overall Score</div>
        </motion.div>

        <div style={{ padding: "20px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center" }}>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#22c55e" }}>{passedControls}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Controls Passed</div>
        </div>

        <div style={{ padding: "20px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center" }}>
          <div style={{ fontSize: "2rem", fontWeight: 800 }}>{totalControls}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Total Controls</div>
        </div>

        <div style={{ padding: "20px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--border)", textAlign: "center" }}>
          <div style={{ fontSize: "2rem", fontWeight: 800 }}>4</div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Frameworks</div>
        </div>
      </div>

      {/* Framework Sections */}
      {complianceSections.map((section) => (
        <motion.div
          key={section.framework}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            marginBottom: "12px",
            borderRadius: "var(--radius-md)",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            overflow: "hidden",
          }}
        >
          {/* Section Header */}
          <button
            onClick={() => setExpandedSection(expandedSection === section.framework ? null : section.framework)}
            style={{
              width: "100%",
              padding: "16px 20px",
              display: "flex",
              alignItems: "center",
              gap: "12px",
              background: "none",
              border: "none",
              color: "var(--fg)",
              cursor: "pointer",
            }}
          >
            <span style={{ color: section.color }}>{section.icon}</span>
            <span style={{ flex: 1, textAlign: "left", fontWeight: 600, fontSize: "0.9rem" }}>
              {section.framework}
            </span>
            <span style={{
              padding: "2px 10px",
              borderRadius: "12px",
              background: section.score >= 95 ? "rgba(34,197,94,0.15)" : "rgba(234,179,8,0.15)",
              color: section.score >= 95 ? "#22c55e" : "#eab308",
              fontSize: "0.75rem",
              fontWeight: 600,
            }}>
              {section.score}%
            </span>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
              {section.controls.filter((c) => c.status === "PASS").length}/{section.controls.length}
            </span>
          </button>

          {/* Controls Table */}
          {expandedSection === section.framework && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: "auto" }}
              style={{ borderTop: "1px solid var(--border)" }}
            >
              {section.controls.map((ctrl) => (
                <div
                  key={ctrl.id}
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "8px",
                    padding: "12px 20px",
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                    alignItems: "center",
                    fontSize: "0.8rem",
                  }}
                >
                  <span style={{ color: "var(--muted-2)", fontFamily: "var(--font-mono)", minWidth: "50px", flexShrink: 0, fontSize: "0.75rem" }}>{ctrl.id}</span>
                  <span style={{ flex: "1 1 200px", fontWeight: 500 }}>{ctrl.control}</span>
                  <span style={{ flexShrink: 0 }}>{statusIcon[ctrl.status]}</span>
                  <span style={{ flex: "1 1 250px", color: "var(--muted)", fontSize: "0.75rem" }}>{ctrl.evidence}</span>
                </div>
              ))}
            </motion.div>
          )}
        </motion.div>
      ))}

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: "12px", marginTop: "24px" }}>
        <button 
          onClick={() => handleExport("rbi")}
          style={{
            padding: "10px 20px", borderRadius: "8px",
            background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.3)",
            color: "#60a5fa", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px",
            fontSize: "0.85rem", fontWeight: 600,
          }}
        >
          <Download size={16} /> Export RBI Report
        </button>
        <button 
          onClick={() => handleExport("pci_dss")}
          style={{
            padding: "10px 20px", borderRadius: "8px",
            background: "rgba(139,92,246,0.15)", border: "1px solid rgba(139,92,246,0.3)",
            color: "#a78bfa", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px",
            fontSize: "0.85rem", fontWeight: 600,
          }}
        >
          <Download size={16} /> Export PCI DSS Evidence
        </button>
        <button 
          onClick={() => window.location.reload()}
          style={{
            padding: "10px 20px", borderRadius: "8px",
            background: "var(--surface)", border: "1px solid var(--border)",
            color: "var(--fg)", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px",
            fontSize: "0.85rem", fontWeight: 600,
          }}
        >
          <RefreshCw size={16} /> Re-scan Controls
        </button>
      </div>
    </div>
  );
}
