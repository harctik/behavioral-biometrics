"""
Transaction History Baseline — Behavioral Risk Scoring for Transactions.

BioCatch cross-references behavioral signals with transaction history
to detect unusual patterns. This module implements:

  1. Transaction amount profiling per user (mean, std, percentiles)
  2. Beneficiary familiarity scoring (known vs new recipients)
  3. Transaction frequency baseline (time-of-day, day-of-week)
  4. Anomaly detection for unusual amounts, recipients, or timing
  5. Combined transaction behavioral risk score

RBI Compliance: Master Direction on Digital Payment Security Controls
mandates real-time transaction monitoring with behavioral analysis.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class TransactionHistoryBaseline:
    """Maintains per-user transaction baselines for anomaly detection.

    BioCatch monitors transaction patterns in conjunction with behavioral
    signals. A large transaction to a new beneficiary with unusual typing
    patterns is much higher risk than the same transaction with normal behavior.
    """

    # Default thresholds
    AMOUNT_ZSCORE_THRESHOLD = 2.5  # Flag amounts > 2.5σ from mean
    NEW_BENEFICIARY_RISK = 0.3  # Base risk for new recipient
    UNUSUAL_TIME_RISK = 0.2  # Base risk for unusual transaction time
    MIN_HISTORY_FOR_SCORING = 5  # Minimum transactions before scoring

    def __init__(self):
        # Per-user transaction history
        self._user_history: Dict[int, List[Dict]] = {}
        # Per-user amount statistics
        self._user_amount_stats: Dict[int, Dict] = {}
        # Per-user beneficiary set
        self._user_beneficiaries: Dict[int, Dict[str, int]] = {}
        # Per-user time-of-day distribution
        self._user_time_dist: Dict[int, Dict[int, int]] = {}

    def record_transaction(
        self,
        user_id: int,
        amount: float,
        beneficiary_id: str,
        transaction_type: str = "transfer",
        timestamp: Optional[datetime] = None,
    ):
        """Record a completed transaction for baseline building.

        Called AFTER a transaction is successfully completed.
        """
        ts = timestamp or datetime.now()

        record = {
            "amount": amount,
            "beneficiary_id": beneficiary_id,
            "type": transaction_type,
            "timestamp": ts.isoformat(),
            "hour": ts.hour,
            "day_of_week": ts.weekday(),
        }

        if user_id not in self._user_history:
            self._user_history[user_id] = []
        self._user_history[user_id].append(record)

        # Keep last 200 transactions
        if len(self._user_history[user_id]) > 200:
            self._user_history[user_id] = self._user_history[user_id][-200:]

        # Update amount statistics
        self._update_amount_stats(user_id)

        # Update beneficiary map
        if user_id not in self._user_beneficiaries:
            self._user_beneficiaries[user_id] = {}
        bene = self._user_beneficiaries[user_id]
        bene[beneficiary_id] = bene.get(beneficiary_id, 0) + 1

        # Update time distribution
        if user_id not in self._user_time_dist:
            self._user_time_dist[user_id] = defaultdict(int)
        self._user_time_dist[user_id][ts.hour] += 1

    def score_transaction(
        self,
        user_id: int,
        amount: float,
        beneficiary_id: str,
        transaction_type: str = "transfer",
        behavioral_risk: float = 0.0,
    ) -> Dict[str, Any]:
        """Score a pending transaction against user's historical baseline.

        Called BEFORE a transaction is authorized to assess risk.

        Args:
            user_id: The user initiating the transaction.
            amount: Transaction amount.
            beneficiary_id: Recipient identifier.
            transaction_type: Type of transaction.
            behavioral_risk: Current session behavioral risk score (0–1).

        Returns:
            {
                "transaction_risk": float,       # 0–1 combined risk
                "amount_risk": float,            # 0–1 amount anomaly
                "beneficiary_risk": float,       # 0–1 beneficiary novelty
                "timing_risk": float,            # 0–1 unusual time
                "behavioral_modifier": float,    # risk amplification from behavior
                "flags": list[str],
                "recommendation": str,           # "allow"|"step_up"|"review"|"block"
                "amount_percentile": float,      # where this amount falls in history
            }
        """
        flags: list[str] = []
        history = self._user_history.get(user_id, [])

        if len(history) < self.MIN_HISTORY_FOR_SCORING:
            # Not enough history — return neutral score
            return {
                "transaction_risk": 0.1 if behavioral_risk < 0.3 else 0.4,
                "amount_risk": 0.0,
                "beneficiary_risk": self.NEW_BENEFICIARY_RISK,
                "timing_risk": 0.0,
                "behavioral_modifier": behavioral_risk,
                "flags": ["txn:insufficient_history"],
                "recommendation": "allow",
                "amount_percentile": 0.5,
            }

        # 1. Amount anomaly scoring
        amount_risk, amount_percentile = self._score_amount(user_id, amount, flags)

        # 2. Beneficiary familiarity
        beneficiary_risk = self._score_beneficiary(user_id, beneficiary_id, flags)

        # 3. Timing risk
        timing_risk = self._score_timing(user_id, flags)

        # 4. Behavioral risk modifier
        # When behavioral signals are abnormal, transaction risk is amplified
        behavioral_modifier = self._compute_behavioral_modifier(
            behavioral_risk, amount_risk, beneficiary_risk
        )

        # 5. Combined transaction risk
        base_risk = (
            amount_risk * 0.35
            + beneficiary_risk * 0.30
            + timing_risk * 0.15
            + behavioral_modifier * 0.20
        )

        # Amplify if multiple risk factors coincide
        risk_factors = sum(
            [
                amount_risk > 0.5,
                beneficiary_risk > 0.5,
                timing_risk > 0.3,
                behavioral_risk > 0.4,
            ]
        )

        if risk_factors >= 3:
            base_risk = min(1.0, base_risk * 1.5)
            flags.append(f"txn:multi_factor_risk({risk_factors} factors)")
        elif risk_factors >= 2:
            base_risk = min(1.0, base_risk * 1.2)

        transaction_risk = round(min(1.0, base_risk), 4)

        # Determine recommendation
        if transaction_risk >= 0.8:
            recommendation = "block"
        elif transaction_risk >= 0.6:
            recommendation = "review"
        elif transaction_risk >= 0.4:
            recommendation = "step_up"
        else:
            recommendation = "allow"

        return {
            "transaction_risk": transaction_risk,
            "amount_risk": round(amount_risk, 4),
            "beneficiary_risk": round(beneficiary_risk, 4),
            "timing_risk": round(timing_risk, 4),
            "behavioral_modifier": round(behavioral_modifier, 4),
            "flags": flags,
            "recommendation": recommendation,
            "amount_percentile": round(amount_percentile, 4),
        }

    def _score_amount(
        self, user_id: int, amount: float, flags: list
    ) -> tuple[float, float]:
        """Score transaction amount against user's historical pattern."""
        stats = self._user_amount_stats.get(user_id, {})
        if not stats:
            return 0.0, 0.5

        mean = stats.get("mean", amount)
        std = stats.get("std", 1.0)
        p75 = stats.get("p75", amount)
        p95 = stats.get("p95", amount)
        max_amount = stats.get("max", amount)

        # Z-score
        z = abs(amount - mean) / (std + 1e-6)

        # Percentile estimation
        amounts = sorted(stats.get("values", [amount]))
        rank = sum(1 for a in amounts if a <= amount)
        percentile = rank / len(amounts)

        risk = 0.0

        # Large deviation from mean
        if z > self.AMOUNT_ZSCORE_THRESHOLD:
            risk += 0.5
            flags.append(
                f"txn:unusual_amount(₹{amount:,.0f}, " f"z={z:.1f}σ, mean=₹{mean:,.0f})"
            )

        # Above 95th percentile
        if amount > p95:
            risk += 0.3
            flags.append(f"txn:above_p95(amount=₹{amount:,.0f}, p95=₹{p95:,.0f})")

        # First time exceeding historical max
        if amount > max_amount * 1.5:
            risk += 0.2
            flags.append(
                f"txn:exceeds_max(amount=₹{amount:,.0f}, "
                f"historical_max=₹{max_amount:,.0f})"
            )

        return min(1.0, risk), percentile

    def _score_beneficiary(
        self, user_id: int, beneficiary_id: str, flags: list
    ) -> float:
        """Score beneficiary familiarity and AML network risk.

        BioCatch Link parity: Evaluates beneficiary against known money mule
        networks and cross-institution fraud graphs.
        """
        known = self._user_beneficiaries.get(user_id, {})
        risk = 0.0

        if beneficiary_id not in known:
            flags.append(f"txn:new_beneficiary({beneficiary_id[:8]}...)")
            risk += self.NEW_BENEFICIARY_RISK
        else:
            count = known[beneficiary_id]
            if count < 2:
                risk += 0.15
            elif count < 5:
                risk += 0.05

        # ── AML Network Graph Proxy (BioCatch Link) ──
        # Simulate network-level mule detection (in production this queries a graph DB)
        # Check if beneficiary matches known high-risk mule patterns
        is_known_mule = (
            beneficiary_id.startswith("mule_") or "crypto" in beneficiary_id.lower()
        )
        if is_known_mule:
            risk += 0.6
            flags.append(f"txn:aml_network_risk(known_mule_cluster)")

        # Receive-and-forward mule pattern detection
        # High velocity of incoming funds immediately followed by outgoing transfers
        history = self._user_history.get(user_id, [])
        if len(history) >= 2:
            last_txn = history[-1]
            if (
                datetime.now() - datetime.fromisoformat(last_txn["timestamp"])
            ).total_seconds() < 300:
                if last_txn["type"] == "deposit" and beneficiary_id not in known:
                    risk += 0.4
                    flags.append("txn:mule_pattern(rapid_forwarding)")

        return min(1.0, risk)

    def _score_timing(self, user_id: int, flags: list) -> float:
        """Score current time against user's transaction time pattern."""
        current_hour = datetime.now().hour
        time_dist = self._user_time_dist.get(user_id, {})

        if not time_dist:
            return 0.0

        total = sum(time_dist.values())
        hour_count = time_dist.get(current_hour, 0)
        hour_frequency = hour_count / total if total > 0 else 0

        # If user has never transacted at this hour
        if hour_count == 0:
            # Late night is especially suspicious
            if 0 <= current_hour < 6:
                flags.append(
                    f"txn:unusual_hour({current_hour}:00, never_seen + late_night)"
                )
                return 0.6
            flags.append(f"txn:unusual_hour({current_hour}:00, never_seen)")
            return self.UNUSUAL_TIME_RISK

        # Very rare hour (< 5% of transactions)
        if hour_frequency < 0.05:
            flags.append(f"txn:rare_hour({current_hour}:00, freq={hour_frequency:.1%})")
            return 0.15

        return 0.0

    def _compute_behavioral_modifier(
        self,
        behavioral_risk: float,
        amount_risk: float,
        beneficiary_risk: float,
    ) -> float:
        """Compute how behavioral signals modify transaction risk.

        BioCatch's key insight: behavioral risk AMPLIFIES transaction risk.
        Normal behavior + unusual amount = moderate risk.
        Abnormal behavior + unusual amount = very high risk.
        """
        if behavioral_risk < 0.2:
            return 0.0  # Normal behavior — no amplification

        # Behavioral risk increases when combined with transaction anomalies
        modifier = behavioral_risk

        # Amplify if there are also transaction anomalies
        if amount_risk > 0.3 and behavioral_risk > 0.3:
            modifier *= 1.5
        if beneficiary_risk > 0.2 and behavioral_risk > 0.4:
            modifier *= 1.3

        return min(1.0, modifier)

    def _update_amount_stats(self, user_id: int):
        """Recompute amount statistics for a user."""
        history = self._user_history.get(user_id, [])
        amounts = [h["amount"] for h in history if h.get("amount", 0) > 0]

        if len(amounts) < 2:
            return

        arr = np.array(amounts, dtype=np.float64)
        self._user_amount_stats[user_id] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "median": float(np.median(arr)),
            "p25": float(np.percentile(arr, 25)),
            "p75": float(np.percentile(arr, 75)),
            "p95": float(np.percentile(arr, 95)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "count": len(arr),
            "values": amounts[-50:],  # Keep last 50 for percentile calculation
        }

    def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Get transaction profile summary for a user."""
        history = self._user_history.get(user_id, [])
        stats = self._user_amount_stats.get(user_id, {})
        beneficiaries = self._user_beneficiaries.get(user_id, {})
        time_dist = self._user_time_dist.get(user_id, {})

        return {
            "total_transactions": len(history),
            "amount_stats": {
                "mean": round(stats.get("mean", 0), 2),
                "std": round(stats.get("std", 0), 2),
                "median": round(stats.get("median", 0), 2),
                "p95": round(stats.get("p95", 0), 2),
                "max": round(stats.get("max", 0), 2),
            },
            "unique_beneficiaries": len(beneficiaries),
            "top_beneficiaries": sorted(
                beneficiaries.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5],
            "peak_hours": sorted(
                time_dist.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3],
        }


# ── Singleton ──────────────────────────────────────────────────────────────────
_txn_baseline: TransactionHistoryBaseline | None = None


def get_txn_baseline() -> TransactionHistoryBaseline:
    global _txn_baseline
    if _txn_baseline is None:
        _txn_baseline = TransactionHistoryBaseline()
    return _txn_baseline
