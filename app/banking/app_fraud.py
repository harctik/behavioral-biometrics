"""
APP (Authorised Push Payment) Fraud Detection via Behavioral Signatures.

Detects social engineering fraud where victims are manipulated into
voluntarily initiating payments to fraudsters. Indian banks lost
Rs. 7,488 crore to digital fraud in FY2023 (RBI Annual Report).

Behavioral Indicators:
- Extended hesitation before entering beneficiary details
- Copy-paste detection for account numbers (coached by fraudster)
- Abnormal session duration (3-5x baseline — phone call coaching)
- Multiple beneficiary additions in single session
- Transaction amount patterns (round numbers, escalating amounts)
"""

import numpy as np
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class APPFraudDetector:
    """Detects Authorised Push Payment fraud via behavioral analysis."""

    def __init__(self):
        self.fraud_threshold = 0.65
        self.session_baselines: Dict[int, Dict] = {}

    def set_user_baseline(self, user_id: int, baseline: Dict):
        """Set normal session behavior baseline for a user."""
        self.session_baselines[user_id] = baseline

    def analyze_session(
        self,
        user_id: int,
        session_data: Dict,
        transaction_data: Optional[Dict] = None,
    ) -> Dict:
        """Analyze current session for APP fraud behavioral signatures."""
        baseline = self.session_baselines.get(user_id, {})
        indicators = []
        score = 0.0

        # 1. Session duration anomaly (coaching sessions are 3-5x longer)
        duration = session_data.get("duration_seconds", 0)
        baseline_duration = baseline.get("avg_session_duration", duration)
        if baseline_duration > 0 and duration > baseline_duration * 2.5:
            score += 0.20
            indicators.append(
                {
                    "type": "extended_session",
                    "detail": f"Session {duration}s vs baseline {baseline_duration}s",
                    "severity": "high",
                }
            )

        # 2. Hesitation before beneficiary entry
        beneficiary_hesitation = session_data.get("beneficiary_entry_pause_ms", 0)
        if beneficiary_hesitation > 8000:  # >8s pause before entering beneficiary
            score += 0.15
            indicators.append(
                {
                    "type": "beneficiary_hesitation",
                    "detail": f"Pause of {beneficiary_hesitation}ms before beneficiary entry",
                    "severity": "medium",
                }
            )

        # 3. Copy-paste detection (fraudster dictating account numbers)
        if session_data.get("account_number_pasted", False):
            score += 0.15
            indicators.append(
                {
                    "type": "copy_paste_account",
                    "detail": "Account number entered via paste (coaching indicator)",
                    "severity": "high",
                }
            )

        # 4. Multiple new beneficiaries in single session
        new_beneficiaries = session_data.get("new_beneficiary_count", 0)
        if new_beneficiaries >= 2:
            score += 0.10
            indicators.append(
                {
                    "type": "multiple_beneficiaries",
                    "detail": f"{new_beneficiaries} new beneficiaries added",
                    "severity": "medium",
                }
            )

        # 5. Transaction amount patterns
        if transaction_data:
            amount = transaction_data.get("amount", 0)
            # Round number detection (coached amounts are often round)
            if amount > 0 and amount % 1000 == 0 and amount >= 10000:
                score += 0.05
                indicators.append(
                    {
                        "type": "round_amount",
                        "detail": f"Round amount: Rs. {amount}",
                        "severity": "low",
                    }
                )
            # Amount exceeds typical pattern
            avg_amount = baseline.get("avg_transaction_amount", amount)
            if avg_amount > 0 and amount > avg_amount * 3:
                score += 0.15
                indicators.append(
                    {
                        "type": "unusual_amount",
                        "detail": f"Rs. {amount} vs avg Rs. {avg_amount}",
                        "severity": "high",
                    }
                )

        # 6. Typing pattern suggests dictation (slow, methodical, no corrections)
        error_rate = session_data.get("error_rate", 0.05)
        if error_rate < 0.01 and duration > 120:  # Suspiciously perfect typing
            score += 0.10
            indicators.append(
                {
                    "type": "dictation_pattern",
                    "detail": "Unusually precise input — possible dictation",
                    "severity": "medium",
                }
            )

        # 7. Time-of-day risk
        hour = datetime.now().hour
        if hour < 6 or hour > 22:
            score += 0.05
            indicators.append(
                {
                    "type": "unusual_hours",
                    "detail": f"Transaction at {hour}:00",
                    "severity": "low",
                }
            )

        fraud_probability = min(score, 1.0)
        is_suspicious = fraud_probability >= self.fraud_threshold

        return {
            "app_fraud_score": round(fraud_probability, 4),
            "is_suspicious": is_suspicious,
            "alert_level": "critical"
            if fraud_probability > 0.8
            else "high"
            if fraud_probability > 0.6
            else "medium"
            if fraud_probability > 0.4
            else "low",
            "indicators": indicators,
            "indicator_count": len(indicators),
            "recommendation": self._get_recommendation(fraud_probability, indicators),
            "timestamp": datetime.now().isoformat(),
        }

    def _get_recommendation(self, score: float, indicators: List) -> str:
        if score > 0.8:
            return "BLOCK transaction and alert fraud team immediately"
        elif score > 0.6:
            return "Hold transaction for manual review. Contact customer via registered phone."
        elif score > 0.4:
            return "Add friction: require re-authentication and cooling period"
        else:
            return "Monitor — no immediate action required"
