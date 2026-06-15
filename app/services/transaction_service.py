import logging
from datetime import datetime, timezone, timedelta
import json
from flask import current_app
from app.extensions import get_db
from app.api.helpers import resolve_query
from app.models.cognitive_engine import run_cognitive_analysis

logger = logging.getLogger(__name__)

# ── Banking Intelligence Constants ────────────────────────────────────────────
RAIL_RISK_MULTIPLIER = {
    "upi": 1.3,
    "imps": 1.2,
    "neft": 0.8,
    "rtgs": 1.0,
    "internal": 0.5,
    "transfer": 1.0,  # default
}

DAILY_TRANSFER_LIMIT_DEFAULT = 200_000  # Rs 2 lakh
VELOCITY_MAX_10MIN = 5


class TransactionService:
    @staticmethod
    def _check_velocity(db, user_id: int) -> tuple:
        """RBI-mandated velocity check — block rapid-fire transactions."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        try:
            with db.get_connection() as conn:
                query = resolve_query(
                    db,
                    """SELECT evidence_id FROM audit_evidence
                       WHERE user_id = :param AND action = 'transaction_assess'
                       AND created_at > :param""",
                )
                cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
                rows = conn.execute(query, (user_id, cutoff_str)).fetchall()
                recent = len(rows)
            if recent >= VELOCITY_MAX_10MIN:
                return (
                    False,
                    f"Velocity limit: {recent} transactions in 10 minutes (max {VELOCITY_MAX_10MIN})",
                )
        except Exception as e:
            logger.error("Velocity check failed: %s", e)
            return True, ""
        return True, ""

    @staticmethod
    def _check_daily_limit(db, user_id: int, amount: float) -> tuple:
        """Cumulative daily transfer cap — prevents account drain via many small transfers."""
        limit = current_app.config.get("DAILY_TRANSFER_LIMIT", DAILY_TRANSFER_LIMIT_DEFAULT)
        now = datetime.now(timezone.utc)
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            from app.database_pg import DatabaseManager as PostgresDatabaseManager
            is_pg = isinstance(db, PostgresDatabaseManager)
        except ImportError:
            is_pg = False

        try:
            with db.get_connection() as conn:
                cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
                if is_pg:
                    row = conn.execute(
                        """SELECT SUM(CAST(metadata::json->>'amount' AS NUMERIC)) as total
                           FROM audit_evidence
                           WHERE user_id = %s 
                           AND action = 'transaction_assess'
                           AND created_at > %s
                           AND metadata::json->>'decision' = 'allow'""",
                        (user_id, cutoff_str),
                    ).fetchone()
                    today_total = float(row["total"] or 0.0) if row else 0.0
                else:
                    rows = conn.execute(
                        """SELECT metadata FROM audit_evidence
                           WHERE user_id = ? 
                           AND action = 'transaction_assess'
                           AND created_at > ?""",
                        (user_id, cutoff_str),
                    ).fetchall()
                    today_total = 0.0
                    for r in rows:
                        meta = r["metadata"]
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except (json.JSONDecodeError, TypeError):
                                continue
                        if meta and meta.get("decision") == "allow" and meta.get("amount") is not None:
                            today_total += float(meta["amount"])

            if today_total + amount > limit:
                return (
                    False,
                    f"Daily limit of Rs {limit:,.0f} would be exceeded (today: Rs {today_total:,.0f})",
                )
        except Exception as e:
            logger.error("Daily limit check failed: %s", e)
            return True, ""
        return True, ""

    @staticmethod
    def _time_of_day_risk(amount: float) -> tuple:
        """Late-night high-value transfers get friction."""
        hour = datetime.now().hour
        if 0 <= hour < 6 and amount >= 10000:
            return True, f"Late-night transaction at {hour:02d}:00 — elevated risk"
        return False, ""

    @staticmethod
    def _get_personalised_threshold(db, user_id: int, floor: float = 10000.0) -> float:
        """Return the user's 90th percentile historical transaction amount."""
        try:
            with db.get_connection() as conn:
                query = resolve_query(
                    db,
                    """SELECT metadata FROM audit_evidence
                       WHERE user_id = :param AND action = 'transaction_assess'
                       ORDER BY created_at DESC LIMIT 100""",
                )
                rows = conn.execute(query, (user_id,)).fetchall()
            if not rows or len(rows) < 10:
                return floor

            amounts = []
            for r in rows:
                meta = r["metadata"]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if meta and meta.get("decision") == "allow" and meta.get("amount") is not None:
                    amounts.append(float(meta["amount"]))

            if len(amounts) < 10:
                return floor
            amounts.sort()
            p90_index = int(len(amounts) * 0.9)
            p90 = amounts[p90_index]
            return max(floor, p90 * 1.5)
        except Exception as e:
            logger.warning("Failed to compute personalized threshold: %s", e)
            return floor

    @classmethod
    def evaluate_transaction_risk(cls, db, user_id: int, session_id: str, amount: float, operation: str, beneficiary_id: str, metrics: dict):
        """Core logic for risk assessment: Banking + Cognitive + Baseline."""
        decision, reasons = "allow", []
        
        vel_ok, vel_reason = cls._check_velocity(db, user_id)
        if not vel_ok:
            decision = "blocked"
            reasons.append(vel_reason)

        if decision == "allow":
            daily_ok, daily_reason = cls._check_daily_limit(db, user_id, amount)
            if not daily_ok:
                decision = "blocked"
                reasons.append(daily_reason)

        rail = operation.lower() if operation else "transfer"
        rail_mult = RAIL_RISK_MULTIPLIER.get(rail, 1.0)

        tod_flag = False
        if decision == "allow":
            tod_flag, tod_reason = cls._time_of_day_risk(amount)
            if tod_flag:
                reasons.append(tod_reason)

        ext_feat: dict = {}
        try:
            with db.get_connection() as conn:
                query = resolve_query(
                    db,
                    "SELECT features FROM behavioral_data WHERE session_id = :param AND data_type = 'extended' ORDER BY timestamp DESC LIMIT 1",
                )
                row = conn.execute(query, (session_id,)).fetchone()
                if row and row[0]:
                    ext_feat = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except Exception:
            pass

        cog = run_cognitive_analysis(ext_feat) if ext_feat else {}
        cog_risk = cog.get("cognitive_risk", 0.0) * rail_mult
        app_fp = cog.get("app_fraud_probability", 0.0)
        duress = cog.get("duress_probability", 0.0)
        rec = cog.get("recommended_action", "allow")
        cog_flags = cog.get("cognitive_flags", [])

        if decision == "allow" and (rec == "block" or duress >= 0.7 or app_fp >= 0.6):
            decision = "blocked"
            reasons.append("Behavioral Biometrics cognitive engine: high-confidence fraud or duress detected")
            if duress >= 0.7:
                reasons.append(f"Duress probability: {duress:.0%}")
            if app_fp >= 0.6:
                reasons.append(f"APP fraud probability: {app_fp:.0%}")
        elif decision == "allow" and rec in ("step_up", "silent_challenge"):
            decision = "step_up_required"
            reasons.append(f"Cognitive risk score: {cog_risk:.2f}")

        # ── Transaction History Baseline (BioCatch-style) ───────────────────
        txn_baseline_result = {}
        try:
            from app.models.transaction_baseline import get_txn_baseline
            txn_baseline = get_txn_baseline()
            txn_baseline_result = txn_baseline.score_transaction(
                user_id=int(user_id),
                amount=amount,
                beneficiary_id=str(beneficiary_id),
                transaction_type=rail,
                behavioral_risk=cog_risk,
            )
            txn_risk = txn_baseline_result.get("transaction_risk", 0.0)
            txn_flags = txn_baseline_result.get("flags", [])
            txn_recommendation = txn_baseline_result.get("recommendation", "allow")

            if txn_flags:
                reasons.extend(txn_flags)
                cog_flags.extend(txn_flags)

            if decision == "allow" and txn_recommendation == "block":
                decision = "blocked"
                reasons.append(f"Transaction baseline: blocked (risk={txn_risk:.2f})")
            elif decision == "allow" and txn_recommendation in ("review", "step_up"):
                decision = "step_up_required"
                reasons.append(f"Transaction baseline: step-up required (risk={txn_risk:.2f})")
        except Exception as exc:
            logger.warning("TransactionHistoryBaseline scoring failed: %s", exc)

        # ── Personalised threshold ──────────────────────────────────────────
        personalised_threshold = cls._get_personalised_threshold(db, int(user_id))

        if amount >= personalised_threshold and decision == "allow":
            decision = "step_up_required"
            reasons.append(f"Transaction exceeds personalised threshold (Rs {personalised_threshold:,.0f})")

        if decision == "allow" and tod_flag:
            decision = "step_up_required"

        if metrics and metrics.get("step_up_recommended") and decision == "allow":
            decision = "step_up_required"
            reasons.append("Session behavioral risk requires additional verification")

        return {
            "decision": decision,
            "reasons": reasons,
            "rail": rail,
            "tod_flag": tod_flag,
            "cog_risk": cog_risk,
            "app_fp": app_fp,
            "duress": duress,
            "cog_flags": cog_flags,
            "cog": cog,
            "txn_baseline_result": txn_baseline_result
        }
