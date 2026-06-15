import logging
import re
from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required
from pydantic import BaseModel, EmailStr, ValidationError, field_validator, StringConstraints
from typing import Optional, Annotated
import bcrypt

from app.extensions import get_db, limiter
from app.api.helpers import get_current_user_id

logger = logging.getLogger(__name__)

user_ns = Namespace("user", description="User profile operations")

# ── Explicit allowlist of columns that may be updated via /profile ───────────
_PROFILE_ALLOWED_COLUMNS = {"email"}


class ProfileUpdateSchema(BaseModel):
    """Validates profile update payloads with proper email validation."""
    email: Optional[EmailStr] = None


class PasswordChangeSchema(BaseModel):
    """Enforces the same password policy as registration and reset."""
    currentPassword: str
    newPassword: Annotated[str, StringConstraints(min_length=8)]

    @field_validator("newPassword")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        if not re.search(r"[@$!%*?&]", v):
            raise ValueError("Password must contain a special character")
        return v


@user_ns.route("/profile")
class UserProfile(Resource):
    @jwt_required()
    @limiter.limit("10 per minute")
    def put(self):
        """Update user profile (email, full name)."""
        uid = get_current_user_id()
        payload = request.get_json() or {}

        # Validate with Pydantic (H-8: proper email validation)
        try:
            data = ProfileUpdateSchema(**payload)
        except ValidationError as e:
            return {"error": str(e)}, 400
        
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # C-2: Build query ONLY from the explicit allowlist — never from
            # request data. Even if a future developer adds fields to the
            # payload, only _PROFILE_ALLOWED_COLUMNS can appear in the query.
            updates = []
            params = []
            if data.email:
                if "email" in _PROFILE_ALLOWED_COLUMNS:
                    updates.append("email = ?")
                    params.append(str(data.email))
                
            if not updates:
                return {"success": True, "message": "No changes requested"}, 200
                
            query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
            params.append(uid)
            
            cursor.execute(query, tuple(params))
            
            if hasattr(conn, "commit"):
                conn.commit()
                
            # Log audit
            db.log_audit_evidence(
                action="profile_updated",
                status="ok",
                user_id=uid,
                metadata={"updated_fields": [u.split(" = ")[0] for u in updates]},
                retention_tag="security"
            )
            
        return {"success": True, "message": "Profile updated successfully"}, 200


@user_ns.route("/password")
class UserPassword(Resource):
    @jwt_required()
    @limiter.limit("5 per minute")
    def put(self):
        """Change user password (enforces full password policy)."""
        uid = get_current_user_id()
        payload = request.get_json() or {}

        # H-7: Validate with full password policy — same as registration
        try:
            data = PasswordChangeSchema(**payload)
        except ValidationError as e:
            return {"error": str(e)}, 400
            
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Fetch current hash
            cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                return {"error": "User not found"}, 404
                
            if not bcrypt.checkpw(data.currentPassword.encode('utf-8'), str(row['password_hash']).encode('utf-8')):
                return {"error": "Incorrect current password"}, 401
                
            # Hash new password
            new_hash = bcrypt.hashpw(data.newPassword.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Update password
            cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, uid))
            
            if hasattr(conn, "commit"):
                conn.commit()
                
            # Log audit
            db.log_audit_evidence(
                action="password_changed",
                status="ok",
                user_id=uid,
                retention_tag="security"
            )
            
        return {"success": True, "message": "Password changed successfully"}, 200


@user_ns.route("/security-hint")
class SecurityHint(Resource):
    @jwt_required()
    @limiter.limit("10 per minute")
    def get(self):
        """Return a masked version of the user's recovery email as a security hint."""
        uid = get_current_user_id()
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            if not row or not row["email"]:
                return {"hint": "No email configured"}, 200

            email = row["email"]
            local, domain = email.split("@", 1) if "@" in email else (email, "")
            masked_local = local[0] + "***" + (local[-1] if len(local) > 1 else "")
            return {"hint": f"{masked_local}@{domain}"}, 200


@user_ns.route("/sessions")
class UserSessions(Resource):
    @jwt_required()
    @limiter.limit("10 per minute")
    def get(self):
        """Return the user's active sessions."""
        uid = get_current_user_id()
        db = get_db()
        try:
            with db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT session_id, ip_address, user_agent, created_at, last_activity "
                    "FROM sessions WHERE user_id = ? AND is_active = 1 "
                    "ORDER BY last_activity DESC LIMIT 10",
                    (uid,)
                ).fetchall()

            sessions = []
            for row in rows:
                s = dict(row)
                ua = s.get("user_agent", "")
                # Extract a human-readable browser label
                if "Chrome" in ua:
                    s["browser"] = "Chrome"
                elif "Firefox" in ua:
                    s["browser"] = "Firefox"
                elif "Safari" in ua:
                    s["browser"] = "Safari"
                else:
                    s["browser"] = "Unknown"
                sessions.append(s)
            return {"sessions": sessions}, 200
        except Exception as e:
            logger.error("Failed to fetch user sessions: %s", e)
            return {"sessions": []}, 200
