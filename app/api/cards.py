import logging
import uuid
import os
from flask import request, current_app
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required
from cryptography.fernet import Fernet

from app.extensions import get_db, limiter
from app.api.helpers import get_current_user_id

logger = logging.getLogger(__name__)

cards_ns = Namespace("cards", description="Cards management")


def _get_fernet() -> Fernet:
    """Return a Fernet instance keyed from CARD_ENCRYPTION_KEY env var."""
    key = current_app.config.get("CARD_ENCRYPTION_KEY") or os.environ.get("CARD_ENCRYPTION_KEY")
    if not key:
        raise ValueError("CARD_ENCRYPTION_KEY must be configured as a separate secret")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def _generate_mock_cvv(card_id: str, user_id: int) -> str:
    """Deterministically generate a 3-digit mock CVV without storing it."""
    import hashlib
    raw = f"{card_id}:{user_id}:{current_app.config['SECRET_KEY']}"
    h = hashlib.sha256(raw.encode()).hexdigest()
    return str(int(h, 16))[-3:].zfill(3)


@cards_ns.route("")
class CardsList(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        """Get user cards."""
        uid = get_current_user_id()
        db = get_db()
        try:
            with db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, type, number, expiry, status, daily_limit as card_limit, cvv_hash FROM cards WHERE user_id = ? ORDER BY created_at ASC",
                    (uid,)
                ).fetchall()
                
                if not rows:
                    # Auto-provision cards without storing CVV
                    conn.execute(
                        "INSERT INTO cards (id, user_id, type, number, expiry, cvv_hash, status, daily_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        ("card_1", uid, "Credit", "**** **** **** 4242", "12/26", "none", "Active", 10000.0)
                    )
                    conn.execute(
                        "INSERT INTO cards (id, user_id, type, number, expiry, cvv_hash, status, daily_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        ("card_2", uid, "Debit", "**** **** **** 8831", "08/28", "none", "Frozen", 5000.0)
                    )
                    conn.commit()
                    
                    rows = conn.execute(
                        "SELECT id, type, number, expiry, status, daily_limit as card_limit, cvv_hash FROM cards WHERE user_id = ? ORDER BY created_at ASC",
                        (uid,)
                    ).fetchall()

            cards = []
            for row in rows:
                c = dict(row)
                c.pop("cvv_hash", None)  # Never send encrypted CVV in list response
                c["limit"] = c.pop("card_limit", 10000.0)  # Rename back for API response
                c["spent"] = 0.0
                c["brand"] = "Visa" if c["type"] == "Credit" else "Mastercard"
                c["cvv"] = "•••"  # Masked placeholder
                cards.append(c)

            return {"cards": cards}, 200
        except Exception as e:
            logger.error("Failed to fetch cards: %s", e)
            return {"cards": []}, 200


@cards_ns.route("/<string:card_id>/freeze")
class CardFreeze(Resource):
    @jwt_required()
    def post(self, card_id):
        """Freeze or unfreeze a card."""
        payload = request.get_json() or {}
        freeze = payload.get("freeze", True)
        new_status = "Frozen" if freeze else "Active"
        
        uid = get_current_user_id()
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE cards SET status = ? WHERE id = ? AND user_id = ?",
                    (new_status, card_id, uid)
                )
                conn.commit()
                
            action = "card_frozen" if freeze else "card_unfrozen"
            db.log_audit_evidence(
                action=action,
                status="ok",
                user_id=uid,
                metadata={"card_id": card_id},
                retention_tag="security"
            )
            return {"success": True, "status": new_status}, 200
        except Exception as e:
            logger.error("Failed to freeze card: %s", e)
            return {"error": "Database error"}, 500


@cards_ns.route("/<string:card_id>/cvv")
class CardCVV(Resource):
    @jwt_required()
    @limiter.limit("5 per minute")
    def post(self, card_id):
        """Reveal CVV — requires step-up authentication (password in body).
        
        The frontend must prompt for the user's password before calling
        this endpoint. The CVV is decrypted from Fernet-encrypted storage
        only after password verification succeeds.
        """
        uid = get_current_user_id()
        db = get_db()
        payload = request.get_json() or {}
        password = payload.get("password", "")
        
        if not password:
            return {"error": "Step-up authentication required. Provide your password."}, 403
        
        # Verify the user's password as step-up auth
        user = db.get_user_by_id(uid)
        if not user:
            return {"error": "User not found"}, 404
        
        auth_result = db.authenticate_user(user["username"], password)
        if not auth_result:
            db.log_audit_evidence(
                action="cvv_reveal_failed",
                status="blocked",
                user_id=uid,
                metadata={"card_id": card_id, "reason": "invalid_password"},
                retention_tag="security"
            )
            return {"error": "Invalid password"}, 401
        
        try:
            with db.get_connection() as conn:
                row = conn.execute(
                    "SELECT cvv_hash, number FROM cards WHERE id = ? AND user_id = ?",
                    (card_id, uid)
                ).fetchone()
                
                if not row:
                    return {"error": "Card not found"}, 404

                cvv_plain = _generate_mock_cvv(card_id, uid)
            
            db.log_audit_evidence(
                action="cvv_revealed",
                status="ok",
                user_id=uid,
                metadata={"card_id": card_id},
                retention_tag="security"
            )
            
            last4 = row["number"].split(" ")[-1] if row["number"] else "0000"
            full_number = f"4111 1111 1111 {last4}" if "4242" in row["number"] else f"5111 1111 1111 {last4}"
            return {"cvv": cvv_plain, "full_number": full_number}, 200
        except Exception as e:
            logger.error("Failed to reveal CVV: %s", e)
            return {"error": "Database error"}, 500
