"""Banking-grade API blueprint (APP fraud, maker-checker, CBS health)."""
from flask import request, current_app
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required
import logging

from app.extensions import get_db, limiter
from app.api.helpers import (
    get_session_cached,
    require_role,
    require_mfa,
    get_current_user_id,
    validate_session_ownership,
    resolve_query,
)
import json

logger = logging.getLogger(__name__)

banking_ns = Namespace("banking", description="Banking-grade operations")


@banking_ns.route("/balance")
class AccountBalance(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        """Return the authenticated user's current account balance.

        The balance is derived from transaction audit records.
        In a real deployment, this would query the Core Banking System (CBS).
        """
        uid = get_current_user_id()
        db = get_db()

        # Detect database backend
        try:
            from app.database_pg import DatabaseManager as PostgresDatabaseManager
            is_pg = isinstance(db, PostgresDatabaseManager)
        except ImportError:
            is_pg = False

        # Real deployment: query the Core Banking System (CBS)
        try:
            from app.banking.cbs_adapters import get_cbs_adapter
            cbs = get_cbs_adapter("finacle")
            profile = cbs.get_customer_risk_profile(str(uid))
            initial_balance = profile.get("averageTransactionAmount", 50000.00) * 5.0
        except Exception:
            initial_balance = 247500.00  # Realistic Indian savings account

        try:
            with db.get_connection() as conn:
                if is_pg:
                    row = conn.execute(
                        """SELECT SUM(CAST(metadata::json->>'amount' AS NUMERIC)) as total_out
                           FROM audit_evidence
                           WHERE user_id = %s AND action = 'transaction_assess'
                           AND metadata::json->>'decision' = 'allow'""",
                        (uid,),
                    ).fetchone()
                    total_out = float(row["total_out"] or 0.0) if row else 0.0
                else:
                    # SQLite fallback
                    rows = conn.execute(
                        """SELECT metadata FROM audit_evidence
                           WHERE user_id = ? AND action = 'transaction_assess'""",
                        (uid,),
                    ).fetchall()
                    total_out = 0.0
                    for r in rows:
                        meta = r["metadata"]
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except (json.JSONDecodeError, TypeError):
                                continue
                        if (
                            meta
                            and meta.get("decision") == "allow"
                            and meta.get("amount") is not None
                        ):
                            total_out += float(meta["amount"])
        except Exception as e:
            logger.error("Balance query failed: %s", e)
            total_out = 0.0

        balance = max(0, initial_balance - total_out)
        return {
            "balance": round(balance, 2),
            "currency": "INR",
            "account_type": "savings",
            "as_of": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }, 200


@banking_ns.route("/app-fraud-check")
class APPFraudCheck(Resource):
    @jwt_required()
    @require_mfa
    @limiter.limit("30 per minute")
    def post(self):
        payload = request.get_json() or {}
        sid = payload.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        s = get_session_cached(sid)
        if not s:
            return {"error": "Invalid session"}, 404
        err = validate_session_ownership(s)
        if err:
            return err

        uid = get_current_user_id()
        try:
            from app.banking.app_fraud import APPFraudDetector

            result = APPFraudDetector().analyze_session(
                user_id=uid,
                session_data=payload.get("session_data", {}),
                transaction_data=payload.get("transaction_data"),
            )
        except Exception:
            logger.exception("APP fraud check failed")
            result = {
                "app_fraud_score": 1.0,
                "is_suspicious": True,
                "alert_level": "high",
            }

        get_db().log_audit_evidence(
            action="app_fraud_check",
            status="ok",
            user_id=uid,
            session_id=sid,
            resource="/api/v1/banking/app-fraud-check",
            metadata={"score": result.get("app_fraud_score", 0)},
            retention_tag="security",
        )
        return result, 200


@banking_ns.route("/maker-checker")
class MakerChecker(Resource):
    @jwt_required()
    @require_mfa
    @limiter.limit("15 per minute")
    def post(self):
        if not require_role("admin", "analyst"):
            return {"error": "Forbidden"}, 403
        payload = request.get_json() or {}
        msid, csid = payload.get("maker_session_id"), payload.get("checker_session_id")
        if not msid or not csid:
            return {"error": "Missing maker/checker session IDs"}, 400
        ms, cs = get_session_cached(msid), get_session_cached(csid)
        if not ms or not cs:
            return {"error": "Invalid session"}, 404

        db = get_db()
        mf = [
            r["features"]
            for r in db.get_user_behavioral_data(user_id=ms["user_id"], limit=50)
            if r.get("features")
        ]
        cf = [
            r["features"]
            for r in db.get_user_behavioral_data(user_id=cs["user_id"], limit=50)
            if r.get("features")
        ]

        try:
            from app.models.siamese_network import SiameseNetwork

            result = SiameseNetwork(
                input_dim=38, embedding_dim=64
            ).verify_maker_checker(mf, cf)
        except Exception:
            logger.exception("Maker-checker verification failed")
            result = {
                "maker_checker_verified": False,
                "behavioral_similarity": 0.0,
                "compliance_violation": True,
                "confidence": 0.0,
                "error": "Maker-checker verification system is temporarily unavailable",
            }

        db.log_audit_evidence(
            action="maker_checker_verify",
            status="ok" if not result.get("compliance_violation") else "violation",
            user_id=get_current_user_id(),
            resource="/api/v1/banking/maker-checker",
            metadata={
                "similarity": result.get("behavioral_similarity", 0),
                "violation": result.get("compliance_violation", False),
            },
            retention_tag="compliance",
        )
        return result, 200


@banking_ns.route("/cbs-health")
class CBSHealth(Resource):
    @jwt_required()
    @require_mfa
    @limiter.limit("10 per minute")
    def get(self):
        if not require_role("admin"):
            return {"error": "Forbidden"}, 403
        try:
            from app.banking.cbs_adapters import get_cbs_adapter

            results = {
                p: get_cbs_adapter(p).health_check()
                for p in ["finacle", "bancs", "flexcube", "t24"]
            }
        except Exception:
            logger.exception("CBS health check failed")
            results = {"error": "CBS adapters unavailable"}
        return {"cbs_status": results}, 200

@banking_ns.route("/statements")
class AccountStatements(Resource):
    @jwt_required()
    @limiter.limit("20 per minute")
    def get(self):
        """Retrieve monthly account statements."""
        uid = get_current_user_id()
        db = get_db()
        statements = []
        try:
            from app.database_pg import PostgresDatabaseManager
            is_pg = isinstance(db, PostgresDatabaseManager)
        except ImportError:
            is_pg = False
        try:
            with db.get_connection() as conn:
                if is_pg:
                    # Group by month (YYYY-MM) using PostgreSQL syntax
                    rows = conn.execute(
                        """SELECT 
                              TO_CHAR(created_at, 'YYYY-MM') as month_str,
                              SUM(CAST(metadata::json->>'amount' AS NUMERIC)) as total_out
                           FROM audit_evidence
                           WHERE user_id = %s 
                           AND action = 'transaction_assess'
                           AND metadata::json->>'decision' = 'allow'
                           GROUP BY TO_CHAR(created_at, 'YYYY-MM')
                           ORDER BY month_str DESC
                           LIMIT 12""",
                        (uid,)
                    ).fetchall()
                    rows_parsed = [{"month_str": r["month_str"], "total_out": float(r["total_out"] or 0.0)} for r in rows]
                else:
                    # SQLite fallback
                    db_rows = conn.execute(
                        """SELECT metadata, created_at FROM audit_evidence
                           WHERE user_id = ? 
                           AND action = 'transaction_assess'
                           ORDER BY created_at DESC""",
                        (uid,)
                    ).fetchall()
                    
                    months_data = {}
                    for r in db_rows:
                        meta = r["metadata"]
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except (json.JSONDecodeError, TypeError):
                                continue
                        if (
                            meta
                            and meta.get("decision") == "allow"
                            and meta.get("amount") is not None
                        ):
                            created_at = r["created_at"]
                            if hasattr(created_at, "isoformat"):
                                date_str = created_at.isoformat()
                            else:
                                date_str = str(created_at)
                            month_str = date_str[:7]
                            months_data[month_str] = months_data.get(month_str, 0.0) + float(meta["amount"])
                            
                    sorted_months = sorted(months_data.keys(), reverse=True)[:12]
                    rows_parsed = [{"month_str": m, "total_out": months_data[m]} for m in sorted_months]
                
                import uuid
                import datetime
                
                initial_balance = 50000.00
                running_balance = initial_balance
                for row in reversed(rows_parsed):
                    m_out = float(row["total_out"] or 0)
                    running_balance -= m_out
                    
                    month_str = row["month_str"]
                    year, month = month_str.split('-')
                    month_name = datetime.date(int(year), int(month), 1).strftime('%B %Y')
                    
                    m_in = 75000.00  # Simulated monthly salary credit
                    running_balance += m_in
                    
                    statements.insert(0, {
                        "id": str(uuid.uuid4())[:8],
                        "month": month_name,
                        "date": f"{month_str}-28",  # Statement generation date
                        "amount_in": round(m_in, 2),
                        "amount_out": round(m_out, 2),
                        "closing_balance": round(running_balance, 2),
                        "document_url": f"/api/v1/banking/statements/{uid}/download?month={month_str}"
                    })
        except Exception as e:
            logger.error("Failed to generate statements: %s", e)
            
        return {"statements": statements}, 200
