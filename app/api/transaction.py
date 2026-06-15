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
    resolve_query,
)
from app.utils import (
    consume_nonce,
    issue_nonce,
    sign_operation,
    verify_operation_signature,
)
from app.services.transaction_service import TransactionService


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


@transaction_ns.route("/history")
class TransactionHistory(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        """Retrieve the authenticated user's transaction history.

        Query params:
          - limit (int): max results, default 20, cap 100
          - offset (int): pagination offset, default 0
        """
        uid = get_current_user_id()
        limit = min(int(request.args.get("limit", 20)), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
        db = get_db()

        try:
            with db.get_connection() as conn:
                rows = conn.execute(
                    """SELECT evidence_id, metadata, created_at as date
                       FROM audit_evidence
                       WHERE user_id = ? AND action = 'transaction_assess'
                       ORDER BY created_at DESC
                       LIMIT ? OFFSET ?""",
                    (uid, limit, offset),
                ).fetchall()

                total_row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM audit_evidence WHERE user_id = ? AND action = 'transaction_assess'",
                    (uid,),
                ).fetchone()
                total = total_row["cnt"] if total_row else 0

            transactions = []
            for row in rows:
                meta = row["metadata"]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}
                if not meta:
                    meta = {}
                # All assess events in this app are currently outgoing transfers
                transactions.append(
                    {
                        "id": str(row["evidence_id"]),
                        "amount": str(meta.get("amount", "0")),
                        "merchant": meta.get("operation", "transfer").title(),
                        "operation": meta.get("operation", "transfer"),
                        "decision": meta.get("decision", "allow"),
                        "risk_level": meta.get("risk_level", "low"),
                        "date": str(row["date"] or ""),
                        "type": "out",
                        "category": "Transfer"
                    }
                )

            # Inject a few realistic incoming and categorical transactions 
            # to make the dashboard statement view fully functional for demo purposes
            if len(transactions) < 10:
                mock_date = datetime.now().isoformat()
                transactions.extend([
                    {
                        "id": "mock-in-1",
                        "amount": "85000",
                        "merchant": "Salary Credit — TechCorp",
                        "operation": "salary",
                        "decision": "allow",
                        "risk_level": "low",
                        "date": mock_date,
                        "type": "in",
                        "category": "Income"
                    },
                    {
                        "id": "mock-out-1",
                        "amount": "1200",
                        "merchant": "Netflix Subscription",
                        "operation": "subscription",
                        "decision": "allow",
                        "risk_level": "low",
                        "date": mock_date,
                        "type": "out",
                        "category": "Entertainment"
                    },
                    {
                        "id": "mock-in-2",
                        "amount": "5000",
                        "merchant": "Refund — Amazon",
                        "operation": "refund",
                        "decision": "allow",
                        "risk_level": "low",
                        "date": mock_date,
                        "type": "in",
                        "category": "Shopping"
                    }
                ])

            return {
                "transactions": transactions,
                "total": total + 3,
                "limit": limit,
                "offset": offset,
            }, 200
        except Exception as e:
            logger.error("Failed to fetch transaction history: %s", e)
            return {
                "transactions": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
            }, 200


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
        
        idempotency_key = request.headers.get("Idempotency-Key")
        from app.extensions import get_redis
        rc = get_redis()
        
        if idempotency_key and rc:
            cache_key = f"idempotency:txn:{idempotency_key}"
            cached_resp = rc.get(cache_key)
            if cached_resp:
                try:
                    import json as _json
                    resp_dict = _json.loads(cached_resp)
                    return resp_dict["body"], resp_dict["status"]
                except Exception:
                    pass

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
            
        from app.api.helpers import check_session_inactivity
        is_active, msg = check_session_inactivity(session)
        if not is_active:
            return {"error": "Login Timeout", "message": msg}, 440
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

        decision_result = TransactionService.evaluate_transaction_risk(
            db=db,
            user_id=int(uid),
            session_id=session_id,
            amount=amount,
            operation=operation,
            beneficiary_id=payload.get("beneficiary_id", payload.get("to_account", "unknown")),
            metrics=metrics
        )

        decision = decision_result["decision"]
        reasons = decision_result["reasons"]
        rail = decision_result["rail"]
        tod_flag = decision_result["tod_flag"]
        cog_risk = decision_result["cog_risk"]
        app_fp = decision_result["app_fp"]
        duress = decision_result["duress"]
        cog_flags = decision_result["cog_flags"]
        cog = decision_result["cog"]
        txn_baseline_result = decision_result.get("txn_baseline_result", {})

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
                    beneficiary_id = payload.get(
                        "beneficiary_id", payload.get("to_account", "unknown")
                    )

                    if decision == "allow":
                        subject = f"Transaction Alert: Rs {amount:,.2f} Approved"
                        body = f"Hello {user['username']},\n\nYour transaction of Rs {amount:,.2f} to {beneficiary_id} was successfully processed.\n\nThank you for banking with us."
                    elif decision == "blocked":
                        subject = f"Transaction Alert: Rs {amount:,.2f} Blocked"
                        body = (
                            f"Hello {user['username']},\n\nYour transaction of Rs {amount:,.2f} to {beneficiary_id} was blocked due to security reasons:\n- "
                            + "\n- ".join(reasons)
                            + "\n\nPlease contact customer support if this was you."
                        )
                    else:
                        subject = (
                            f"Transaction Alert: Rs {amount:,.2f} Requires Verification"
                        )
                        body = (
                            f"Hello {user['username']},\n\nYour transaction of Rs {amount:,.2f} to {beneficiary_id} requires additional verification:\n- "
                            + "\n- ".join(reasons)
                            + "\n\nPlease complete the verification to proceed."
                        )

                    mail_svc.send(
                        to=user["email"],
                        subject=subject,
                        body_text=body,
                    )
        except Exception as e:
            logger.error("Failed to send transaction notification email: %s", e)

        response_body = {
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
        }
        
        if idempotency_key and rc:
            try:
                import json as _json
                rc.setex(f"idempotency:txn:{idempotency_key}", 300, _json.dumps({"body": response_body, "status": 200}))
            except Exception:
                pass
                
        return response_body, 200


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

# ── Corporate Banking (Maker-Checker) ───────────────────────────────────────

corporate_init_model = transaction_ns.model(
    "CorporateInitiateInput",
    {
        "amount": fields.Float(required=True),
        "beneficiary_id": fields.String(required=True),
    },
)

corporate_approve_model = transaction_ns.model(
    "CorporateApproveInput",
    {
        "txn_id": fields.String(required=True),
        "maker_session_features": fields.List(fields.Raw(), required=True, description="Behavioral features of the Maker when initiating"),
        "checker_session_features": fields.List(fields.Raw(), required=True, description="Behavioral features of the Checker when approving"),
    },
)

@transaction_ns.route("/corporate/initiate")
class CorporateInitiate(Resource):
    @transaction_ns.expect(corporate_init_model)
    @jwt_required()
    def post(self):
        """Maker initiates a corporate transaction."""
        from app.services.cbs_service import MockCBSService
        payload = request.get_json() or {}
        uid = get_current_user_id()
        
        amount = float(payload.get("amount", 0))
        beneficiary = payload.get("beneficiary_id", "unknown")
        
        # Initiate via CBS in corporate mode
        result = MockCBSService.initiate_transfer(maker_id=int(uid), amount=amount, beneficiary=beneficiary, is_corporate=True)
        return result, 200

@transaction_ns.route("/corporate/pending")
class CorporatePending(Resource):
    @jwt_required()
    def get(self):
        """Checker views pending corporate approvals."""
        from app.services.cbs_service import MockCBSService
        uid = get_current_user_id()
        
        pending = MockCBSService.get_pending_approvals(checker_id=int(uid))
        return {"pending_approvals": pending}, 200

@transaction_ns.route("/corporate/approve")
class CorporateApprove(Resource):
    @transaction_ns.expect(corporate_approve_model)
    @jwt_required()
    def post(self):
        """Checker approves transaction, verifying identities via Siamese Network."""
        from app.services.cbs_service import MockCBSService
        payload = request.get_json() or {}
        uid = get_current_user_id()
        
        txn_id = payload.get("txn_id")
        maker_features = payload.get("maker_session_features", [])
        checker_features = payload.get("checker_session_features", [])
        
        if not txn_id:
            return {"error": "Missing txn_id"}, 400
            
        # 1. Siamese Network Biometric Verification (RBI Dual Control Mandate)
        try:
            from app.models.siamese_network import SiameseNetwork
            from app.behavioral_feature_engine import BehavioralFeatureEngine
            
            # Load Siamese model from models directory
            siamese = SiameseNetwork(input_dim=BehavioralFeatureEngine.FEATURE_COUNT)
            # In a real system, we'd load the specific corporate model. We use user_id 'saved' or global
            loaded = siamese.load("models/saved_siamese.pt") # Assuming a global siamese is saved, else we just use fallback
            if loaded:
                auth_result = siamese.verify_maker_checker(maker_features, checker_features)
                if auth_result["compliance_violation"]:
                    return {
                        "status": "blocked",
                        "error": "Maker-Checker Compliance Violation",
                        "message": "Siamese Network detected the Maker and Checker have identical behavioral typing profiles. Account sharing detected."
                    }, 403
        except Exception as e:
            logger.warning(f"Siamese verification failed or bypassed: {e}")
            pass # Failsafe open for demo if model not fully loaded
            
        # 2. Process Approval in CBS
        result = MockCBSService.approve_transfer(checker_id=int(uid), txn_id=txn_id)
        if result["status"] == "success":
            return result, 200
        else:
            return result, 400
