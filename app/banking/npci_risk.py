"""
NPCI Risk API v2 Integration (Simulation Layer).

Performance SLA: Response within 45ms for real-time decisioning.
"""

import time
import hashlib
import logging
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class NPCIRiskClient:
    """NPCI Risk Information Repository client — behavioral risk signals for UPI/IMPS."""

    def __init__(self, config: Dict = None):
        config = config or {}
        self.psp_id = config.get("psp_id", "BEHAVIORAL_BIOMETRICS_PSP")
        self.sla_threshold_ms = 45

    def assess_upi_transaction(
        self,
        upi_txn_ref: str,
        payer_vpa: str,
        payee_vpa: str,
        amount: float,
        behavioral_score: float,
        duress_score: float,
        session_freshness: float = 1.0,
        device_trust: float = 1.0,
        cross_channel_flag: bool = False,
    ) -> Dict:
        """Assess UPI transaction risk with behavioral overlay."""
        start = time.time()
        score = self._compute_score(
            behavioral_score, duress_score, amount, session_freshness, device_trust
        )

        if score > 85:
            cat, rec = "CRITICAL", "DECLINE"
        elif score > 65:
            cat, rec = "HIGH", "HOLD"
        elif score > 40:
            cat, rec = "MEDIUM", "REVIEW"
        else:
            cat, rec = "LOW", "ALLOW"

        if amount >= 50000 and score > 30:
            rec = "REVIEW"
        if duress_score > 0.75:
            rec, cat = "HOLD", "CRITICAL"

        ms = (time.time() - start) * 1000
        return {
            "txnRef": upi_txn_ref,
            "pspId": self.psp_id,
            "riskSignal": {
                "riskScore": score,
                "riskCategory": cat,
                "recommendation": rec,
                "behavioralConfidence": round(1.0 - behavioral_score, 4),
                "duressIndicator": duress_score > 0.75,
                "duressConfidence": round(duress_score, 4),
                "sessionFreshness": round(session_freshness, 4),
                "deviceTrust": round(device_trust, 4),
                "crossChannelFlag": cross_channel_flag,
            },
            "metadata": {
                "amount": amount,
                "currency": "INR",
                "timestamp": datetime.now().isoformat(),
                "processingTimeMs": round(ms, 2),
                "slaCompliant": ms <= self.sla_threshold_ms,
            },
        }

    def submit_fraud_report(
        self, txn_ref: str, fraud_type: str, evidence: Dict
    ) -> Dict:
        """Submit fraud report to NPCI Fraud Registry (mock)."""
        rid = hashlib.sha256(f"{txn_ref}:{time.time()}".encode()).hexdigest()[:16]
        logger.warning(f"[NPCI] Fraud report {rid} type={fraud_type}")
        return {
            "reportId": rid,
            "txnRef": txn_ref,
            "fraudType": fraud_type,
            "status": "submitted",
        }

    def query_beneficiary_risk(self, payee_vpa: str) -> Dict:
        """Query NPCI beneficiary risk database (mock)."""
        return {
            "payeeVPA": payee_vpa[:2] + "****",
            "riskLevel": "LOW",
            "fraudReports": 0,
        }

    def _compute_score(self, bs, ds, amt, sf, dt) -> int:
        risk = (
            bs * 0.35
            + ds * 0.25
            + (1 - sf) * 0.15
            + (1 - dt) * 0.15
            + min(amt / 500000, 1.0) * 0.10
        )
        return min(int(risk * 100), 100)
