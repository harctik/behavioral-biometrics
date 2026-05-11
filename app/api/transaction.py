"""Transaction security API blueprint."""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
import json
import logging
from datetime import datetime

from app.extensions import get_db, limiter
from app.api.helpers import (
    get_session_cached,
    validate_session_context,
    require_aal,
    require_mfa,
    get_current_user_id,
    validate_session_ownership,
)
from app.utils import (
    consume_nonce,
    issue_nonce,
    sign_operation,
    verify_operation_signature,
)
from app.models.cognitive_engine import run_cognitive_analysis

logger = logging.getLogger(__name__)

# ── Banking Intelligence Constants ────────────────────────────────────────────

# Payment rail risk multiplier — UPI is instant + irrevocable = highest fraud risk
RAIL_RISK_MULTIPLIER = {
    "upi": 1.3,
    "imps": 1.2,
    "neft": 0.8,
    "rtgs": 1.0,
    "internal": 0.5,
    "transfer": 1.0,  # default
}

# Daily cumulative transfer limit (Rs) — configurable per deployment
DAILY_TRANSFER_LIMIT_DEFAULT = 200_000  # Rs 2 lakh

# Velocity: max transactions in 10-minute window
VELOCITY_MAX_10MIN = 5


def _check_velocity(db, user_id: int) -> tuple:
    """RBI-mandated velocity check — block rapid-fire transactions."""
    try:
        with db.get_connection() as conn:
            recent = conn.execute(
                """SELECT COUNT(*) as cnt FROM audit_evidence
                   WHERE user_id = ? AND action = 'transaction_assess'
                   AND created_at > datetime('now', '-10 minutes')""",
                (user_id,),
            ).fetchone()["cnt"]
        if recent >= VELOCITY_MAX_10MIN:
            return (
                False,
                f"Velocity limit: {recent} transactions in 10 minutes (max {VELOCITY_MAX_10MIN})",
            )
    except Exception as e:
        logger.error("Velocity check failed: %s", e)
        return False, "check unavailable — transaction held"
    return True, ""


def _check_daily_limit(db, user_id: int, amount: float) -> tuple:
    """Cumulative daily transfer cap — prevents account drain via many small transfers."""
    limit = current_app.config.get("DAILY_TRANSFER_LIMIT", DAILY_TRANSFER_LIMIT_DEFAULT)
    try:
        with db.get_connection() as conn:
            today_total = conn.execute(
                """SELECT COALESCE(SUM(
                       CAST(json_extract(metadata, '$.amount') AS REAL)
                   ), 0) as total
                   FROM audit_evidence
                   WHERE user_id = ? AND action = 'transaction_assess'
                   AND json_extract(metadata, '$.decision') = 'allow'
                   AND created_at > datetime('now', 'start of day')""",
                (user_id,),
            ).fetchone()["total"]
        if today_total + amount > limit:
            return (
                False,
                f"Daily limit of Rs {limit:,.0f} would be exceeded (today: Rs {today_total:,.0f})",
            )
    except Exception as e:
        logger.error("Daily limit check failed: %s", e)
        return False, "check unavailable — transaction held"
    return True, ""


def _time_of_day_risk(amount: float) -> tuple:
    """Late-night high-value transfers get friction."""
    hour = datetime.now().hour
    if 0 <= hour < 6 and amount >= 10000:
        return True, f"Late-night transaction at {hour:02d}:00 — elevated risk"
    return False, ""


def _get_personalised_threshold(db, user_id: int, floor: float = 10000.0) -> float:
    """
    Return the user's 90th percentile historical transaction amount.
    Falls back to the floor value if insufficient history exists.
    """
    try:
        with db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT json_extract(metadata, '$.amount') as amount FROM audit_evidence
                WHERE user_id = ?
                  AND action = 'transaction_assess'
                  AND json_extract(metadata, '$.decision') = 'allow'
                ORDER BY created_at DESC LIMIT 100
                """,
                (user_id,),
            ).fetchall()
        if not row or len(row) < 10:
            return floor  # not enough history, use default
        amounts = sorted([float(r["amount"]) for r in row if r["amount"] is not None])
        if not amounts:
            return floor
        p90_index = int(len(amounts) * 0.9)
        p90 = amounts[p90_index]
        # Threshold = 1.5x their 90th percentile, floored at Rs 10,000
        return max(floor, p90 * 1.5)
    except Exception as e:
        logger.warning(f"Failed to compute personalized threshold: {e}")
        return floor  # always safe to fall back


transaction_ns = Namespace(
    "transaction", description="Transaction security and behavioral scoring"
)

# ── Swagger models ───────────────────────────────────────────────────────────

assess_model = transaction_ns.model(
    "TransactionAssessInput",
    {
        "session_id": fields.String(required=True),
        "amount": fields.Float(required=True),
        "operation": fields.String(default="transfer"),
        "nonce": fields.String(required=True),
        "signature": fields.String(required=True),
    },
)

assess_response = transaction_ns.model(
    "TransactionAssessResponse",
    {
        "decision": fields.String(enum=["allow", "step_up_required", "blocked"]),
        "reasons": fields.List(fields.String()),
        "risk_level": fields.String(enum=["low", "medium", "high"]),
        "risk_score": fields.Float(),
        "authenticity_score": fields.Float(),
        "cognitive": fields.Raw(description="Cognitive engine analysis"),
    },
)


@transaction_ns.route("/nonce")
class TransactionNonce(Resource):
    @jwt_required()
    @limiter.limit("40 per minute")
    def get(self):
        """Issue a single-use nonce for transaction signing (300s TTL)."""
        return {"nonce": issue_nonce(300), "expires_in_seconds": 300}, 200


@transaction_ns.route("/sign-intent")
class TransactionSignIntent(Resource):
    @jwt_required()
    @require_mfa
    @limiter.limit("40 per minute")
    def post(self):
        """HMAC-sign a transaction intent payload."""
        payload = request.get_json() or {}
        if not {"session_id", "amount", "operation", "nonce"}.issubset(payload):
            return {"error": "Missing required intent fields"}, 400
        return {
            "signature": sign_operation(payload, current_app.config["TXN_SIGNING_KEY"])
        }, 200


@transaction_ns.route("/assess")
class TransactionAssess(Resource):
    @transaction_ns.expect(assess_model)
    @transaction_ns.response(200, "Assessment result", assess_response)
    @jwt_required()
    @require_mfa
    @limiter.limit("30 per minute")
    def post(self):
        """Full transaction risk assessment with cognitive fraud engine."""
        payload = request.get_json() or {}
        session_id = payload.get("session_id") or request.cookies.get("session_id")
        try:
            amount = float(payload.get("amount", 0))
        except Exception:
            return {"error": "Invalid amount"}, 400
        operation = payload.get("operation", "transfer")
        nonce = payload.get("nonce")
        signature = payload.get("signature", "")

        if not session_id or not nonce:
            return {"error": "Missing session_id or nonce"}, 400
        if not consume_nonce(nonce):
            return {"error": "Invalid or expired nonce"}, 409

        session = get_session_cached(session_id)
        if not session:
            return {"error": "Invalid session"}, 404
        if not validate_session_context(session):
            return {"error": "Session context mismatch"}, 403
        err = validate_session_ownership(session)
        if err:
            return err

        db = get_db()
        uid = get_current_user_id()

        if current_app.config.get("TRANSACTION_SIGNING_REQUIRED", True):
            signed = {
                "session_id": session_id,
                "amount": payload.get("amount"),
                "operation": operation,
                "nonce": nonce,
            }
            valid = verify_operation_signature(
                signed, signature, current_app.config["TXN_SIGNING_KEY"]
            )
            if not valid and current_app.config.get("TXN_SIGNING_PREVIOUS_KEY"):
                valid = verify_operation_signature(
                    signed, signature, current_app.config["TXN_SIGNING_PREVIOUS_KEY"]
                )
            if not valid:
                db.log_audit_evidence(
                    action="transaction_assess",
                    status="blocked",
                    user_id=uid,
                    session_id=session_id,
                    resource="/api/transaction/assess",
                    rationale="Invalid operation signature",
                    retention_tag="security",
                )
                return {"error": "Invalid operation signature"}, 401

        from app.api.session import _build_session_metrics

        metrics, me = _build_session_metrics(session_id)
        if me:
            return {"error": me[0]}, me[1]

        decision, reasons = "allow", []

        # ── Banking intelligence layer ──────────────────────────────────────
        # 1. Velocity check — block rapid-fire transactions
        vel_ok, vel_reason = _check_velocity(db, uid)
        if not vel_ok:
            decision = "blocked"
            reasons.append(vel_reason)

        # 2. Cumulative daily limit
        if decision == "allow":
            daily_ok, daily_reason = _check_daily_limit(db, uid, amount)
            if not daily_ok:
                decision = "blocked"
                reasons.append(daily_reason)

        # 3. Payment rail risk multiplier
        rail = operation.lower() if operation else "transfer"
        rail_mult = RAIL_RISK_MULTIPLIER.get(rail, 1.0)

        # 4. Time-of-day risk
        if decision == "allow":
            tod_flag, tod_reason = _time_of_day_risk(amount)
            if tod_flag:
                reasons.append(tod_reason)

        # ── Cognitive risk layer ────────────────────────────────────────────
        ext_feat: dict = {}
        try:
            with db.get_connection() as conn:
                row = conn.execute(
                    "SELECT features FROM behavioral_data WHERE session_id = ? AND data_type = 'extended' ORDER BY timestamp DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
                if row and row[0]:
                    ext_feat = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except Exception:
            pass

        cog = run_cognitive_analysis(ext_feat) if ext_feat else {}
        cog_risk = cog.get("cognitive_risk", 0.0) * rail_mult  # Apply rail multiplier
        app_fp = cog.get("app_fraud_probability", 0.0)
        duress = cog.get("duress_probability", 0.0)
        rec = cog.get("recommended_action", "allow")
        cog_flags = cog.get("cognitive_flags", [])

        if decision == "allow" and (rec == "block" or duress >= 0.7 or app_fp >= 0.6):
            decision = "blocked"
            reasons.append(
                "Behavioral Biometrics cognitive engine: high-confidence fraud or duress detected"
            )
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
            beneficiary_id = payload.get(
                "beneficiary_id", payload.get("to_account", "unknown")
            )
            txn_baseline_result = txn_baseline.score_transaction(
                user_id=int(uid),
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

            # Apply transaction baseline recommendation
            if decision == "allow" and txn_recommendation == "block":
                decision = "blocked"
                reasons.append(f"Transaction baseline: blocked (risk={txn_risk:.2f})")
            elif decision == "allow" and txn_recommendation in ("review", "step_up"):
                decision = "step_up_required"
                reasons.append(
                    f"Transaction baseline: step-up required (risk={txn_risk:.2f})"
                )
        except Exception as exc:
            logger.warning("TransactionHistoryBaseline scoring failed: %s", exc)

        # ── Personalised threshold ──────────────────────────────────────────
        uid = get_current_user_id()
        personalised_threshold = _get_personalised_threshold(db, int(uid))

        if amount >= personalised_threshold and decision == "allow":
            decision = "step_up_required"
            reasons.append(
                f"Transaction exceeds personalised threshold"
                f" (Rs {personalised_threshold:,.0f})"
            )
        # Time-of-day friction: escalate to step_up if flagged and still allow
        if decision == "allow" and tod_flag:
            decision = "step_up_required"

        if metrics["step_up_recommended"] and decision == "allow":
            decision = "step_up_required"
            reasons.append("Session behavioral risk requires additional verification")
        if decision == "step_up_required" and not require_aal(session, "mfa"):
            reasons.append("MFA assurance required before proceeding")
            return {"decision": "step_up_required", "reasons": reasons}, 403

        # Record completed transaction in baseline for future scoring
        if decision == "allow":
            try:
                from app.models.transaction_baseline import get_txn_baseline

                txn_baseline = get_txn_baseline()
                beneficiary_id = payload.get(
                    "beneficiary_id", payload.get("to_account", "unknown")
                )
                txn_baseline.record_transaction(
                    user_id=int(uid),
                    amount=amount,
                    beneficiary_id=str(beneficiary_id),
                    transaction_type=rail,
                )
            except Exception:
                pass  # Non-critical — don't block transaction

        db.log_audit_evidence(
            action="transaction_assess",
            status="ok",
            user_id=uid,
            session_id=session_id,
            resource="/api/transaction/assess",
            metadata={
                "amount": amount,
                "operation": operation,
                "decision": decision,
                "risk_level": metrics["risk_level"],
                "cognitive_risk": cog_risk,
                "app_fraud_prob": app_fp,
                "duress_prob": duress,
                "cognitive_flags": cog_flags,
                "txn_baseline_risk": txn_baseline_result.get("transaction_risk", 0.0),
                "txn_amount_percentile": txn_baseline_result.get(
                    "amount_percentile", 0.5
                ),
            },
            retention_tag="security",
        )
        # ── Email Notifications (RBI requirement) ───────────────────────────
        try:
            if "mail_service" in current_app.extensions:
                mail_svc = current_app.extensions["mail_service"]
                user = db.get_user(uid)
                if user and user.get("email"):
                    beneficiary_id = payload.get("beneficiary_id", payload.get("to_account", "unknown"))
                    
                    if decision == "allow":
                        subject = f"Transaction Alert: Rs {amount:,.2f} Approved"
                        body = f"Hello {user['username']},\n\nYour transaction of Rs {amount:,.2f} to {beneficiary_id} was successfully processed.\n\nThank you for banking with us."
                    elif decision == "blocked":
                        subject = f"Transaction Alert: Rs {amount:,.2f} Blocked"
                        body = f"Hello {user['username']},\n\nYour transaction of Rs {amount:,.2f} to {beneficiary_id} was blocked due to security reasons:\n- " + "\n- ".join(reasons) + "\n\nPlease contact customer support if this was you."
                    else:
                        subject = f"Transaction Alert: Rs {amount:,.2f} Requires Verification"
                        body = f"Hello {user['username']},\n\nYour transaction of Rs {amount:,.2f} to {beneficiary_id} requires additional verification:\n- " + "\n- ".join(reasons) + "\n\nPlease complete the verification to proceed."

                    mail_svc.send(
                        to=user["email"],
                        subject=subject,
                        body_text=body,
                    )
        except Exception as e:
            logger.error("Failed to send transaction notification email: %s", e)

        return {
            "decision": decision,
            "reasons": reasons or ["transaction accepted"],
            "risk_level": metrics["risk_level"],
            "risk_score": metrics["risk_score"],
            "authenticity_score": metrics["authenticity_score"],
            "cognitive": {
                "cognitive_risk": cog_risk,
                "app_fraud_probability": app_fp,
                "duress_probability": duress,
                "behavioral_state": cog.get("behavioral_state", "normal"),
                "flags": cog_flags,
            },
            "transaction_baseline": {
                "transaction_risk": txn_baseline_result.get("transaction_risk", 0.0),
                "amount_risk": txn_baseline_result.get("amount_risk", 0.0),
                "beneficiary_risk": txn_baseline_result.get("beneficiary_risk", 0.0),
                "timing_risk": txn_baseline_result.get("timing_risk", 0.0),
                "amount_percentile": txn_baseline_result.get("amount_percentile", 0.5),
            },
        }, 200


@transaction_ns.route("/behavioral-score")
class TransactionBehavioralScore(Resource):
    @jwt_required()
    @limiter.limit("60 per minute")
    def post(self):
        """Per-transaction behavioral authenticity scoring."""
        payload = request.get_json() or {}
        session_id = payload.get("session_id") or request.cookies.get("session_id")
        try:
            amount = float(payload.get("amount", 0))
        except Exception:
            return {"error": "Invalid amount"}, 400
        if not session_id:
            return {"error": "Missing session_id"}, 400
        session = get_session_cached(session_id)
        if not session:
            return {"error": "Invalid session"}, 404
        err = validate_session_ownership(session)
        if err:
            return err

        db = get_db()
        uid = get_current_user_id()
        feats = [
            r["features"]
            for r in db.get_user_behavioral_data(user_id=uid, limit=50)
            if r.get("features")
        ]
        if not feats:
            return {
                "authenticity_score": 0.5,
                "risk_score": 0.5,
                "step_up_required": amount >= 50000,
                "enrollment_phase": "bootstrap",
                "message": "Insufficient behavioral data",
            }, 200
        try:
            from app.models.ml_models import EnsembleBehavioralClassifier

            clf = EnsembleBehavioralClassifier(uid, "models")
            result = clf.predict_per_transaction(
                features=feats,
                transaction_amount=amount,
                keystroke_features=feats[-1],
                mouse_features=feats[-1],
                session_context=payload.get("session_context"),
            )
        except Exception:
            logger.exception("Per-transaction scoring failed")
            result = {
                "authenticity_score": 0.5,
                "risk_score": 0.5,
                "step_up_required": amount >= 50000,
                "enrollment_phase": "bootstrap",
            }

        db.log_audit_evidence(
            action="transaction_behavioral_score",
            status="ok",
            user_id=uid,
            session_id=session_id,
            resource="/api/v1/transaction/behavioral-score",
            metadata={
                "amount": amount,
                "risk_score": result.get("risk_score", 0),
                "step_up": result.get("step_up_required", False),
            },
            retention_tag="security",
        )
        return result, 200
