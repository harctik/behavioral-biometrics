"""Authentication API blueprint.

Handles registration, login, logout, MFA verification, password reset.
All responses follow a standardised envelope: ``{"data": {...}}`` on success,
``{"error": {...}}`` on failure.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from pydantic import BaseModel, EmailStr, ValidationError, field_validator, StringConstraints
import re
import hashlib
import logging
import uuid
import datetime
from typing import Annotated, Optional

from app.extensions import get_db, get_redis, limiter
from app.error_handling import make_error_response
import pyotp

logger = logging.getLogger(__name__)

auth_ns = Namespace("auth", description="Authentication operations")

# ── Swagger models (OpenAPI documentation) ──────────────────────────────────

register_model = auth_ns.model(
    "RegisterRequest",
    {
        "username": fields.String(
            required=True, min_length=3, max_length=50, example="john_doe"
        ),
        "email": fields.String(required=True, example="john@example.com"),
        "password": fields.String(
            required=True, min_length=8, example="StrongPass123!"
        ),
    },
)

login_model = auth_ns.model(
    "LoginRequest",
    {
        "username": fields.String(required=True, example="john_doe"),
        "password": fields.String(required=True, example="StrongPass123!"),
    },
)

mfa_model = auth_ns.model(
    "MFAVerifyRequest",
    {
        "session_id": fields.String(required=True),
        "otp": fields.String(
            required=True, min_length=6, max_length=6, example="123456"
        ),
    },
)

forgot_pw_model = auth_ns.model(
    "ForgotPasswordRequest",
    {
        "username": fields.String(required=True, example="john_doe"),
    },
)

reset_pw_model = auth_ns.model(
    "ResetPasswordRequest",
    {
        "token": fields.String(required=True),
        "new_password": fields.String(required=True, min_length=8),
    },
)

logout_model = auth_ns.model(
    "LogoutRequest",
    {
        "session_id": fields.String(required=False),
    },
)

auth_success = auth_ns.model(
    "AuthSuccess",
    {
        "data": fields.Raw(description="Response payload"),
    },
)

auth_error = auth_ns.model(
    "AuthError",
    {
        "error": fields.Raw(description="Structured error object"),
    },
)


# ── Pydantic validation schemas ─────────────────────────────────────────────


class RegisterSchema(BaseModel):
    username: Annotated[str, StringConstraints(min_length=3, max_length=50)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8)]

    @field_validator("password")
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


class LoginSchema(BaseModel):
    username: str
    password: str
    keystroke_data: list = []
    device_fingerprint: dict = {}


class ForgotPasswordSchema(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: Annotated[str, StringConstraints(min_length=8)]

    @field_validator("new_password")
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


class MFAVerifySchema(BaseModel):
    session_id: str
    otp: Annotated[str, StringConstraints(min_length=6, max_length=6)]


# ── Routes ───────────────────────────────────────────────────────────────────


@auth_ns.route("/register")
class Register(Resource):
    @auth_ns.expect(register_model)
    @auth_ns.response(200, "Registration successful", auth_success)
    @auth_ns.response(400, "Validation error or user exists", auth_error)
    @limiter.limit("3 per minute")
    def post(self):
        """Register a new user account with MFA secret generation."""
        try:
            data = RegisterSchema(**request.get_json() or {})
        except ValidationError as e:
            logger.warning("Registration validation failed")
            return make_error_response("VALIDATION_ERROR", str(e), status=400)

        db = get_db()
        result = db.create_user(data.username, data.email, data.password)
        if not result:
            logger.warning("Registration failed - user exists: %s", data.username)
            return make_error_response("USER_EXISTS", "User already exists", status=400)

        user_id, mfa_secret = result
        logger.info("New user registered: %s (ID: %d)", data.username, user_id)
        
        verify_token = str(uuid.uuid4())
        try:
            from app.mail import MailService
            if "mail_service" in current_app.extensions:
                mail_service: MailService = current_app.extensions["mail_service"]
                mail_service.send_email_verification(
                    to=data.email,
                    username=data.username,
                    verify_token=verify_token
                )
        except Exception as exc:
            logger.error("Failed to send verification email: %s", exc)

        # ── Session 0: Initialize behavioral profile from signup ─────────
        enrollment_result = None
        try:
            raw_json = request.get_json() or {}
            enrollment_seed = raw_json.get("enrollment_seed") or {}
            behavioral_data = raw_json.get("behavioral_data") or {}
            
            # Extract keystroke features from enrollment seed
            keystroke_events = enrollment_seed.get("keystroke_events") or behavioral_data.get("keystroke_events") or []
            
            if keystroke_events and len(keystroke_events) >= 5:
                from app.models.passive_enrollment import get_enrollment_manager
                enrollment_mgr = get_enrollment_manager()
                
                # Extract timing features from raw keystroke events
                hold_times = [e.get("hold_time", 0) for e in keystroke_events if e.get("hold_time")]
                flight_times = [e.get("flight_time", 0) for e in keystroke_events if e.get("flight_time")]
                
                signup_features = {}
                if hold_times:
                    import statistics
                    signup_features["hold_time_mean"] = statistics.mean(hold_times)
                    signup_features["hold_time_std"] = statistics.stdev(hold_times) if len(hold_times) > 1 else 0.0
                    signup_features["hold_time_median"] = statistics.median(hold_times)
                    signup_features["hold_time_cv"] = signup_features["hold_time_std"] / max(signup_features["hold_time_mean"], 1e-6)
                
                if flight_times:
                    import statistics
                    signup_features["flight_time_mean"] = statistics.mean(flight_times)
                    signup_features["flight_time_std"] = statistics.stdev(flight_times) if len(flight_times) > 1 else 0.0
                    signup_features["flight_time_median"] = statistics.median(flight_times)
                    signup_features["flight_time_cv"] = signup_features["flight_time_std"] / max(signup_features["flight_time_mean"], 1e-6)
                
                # WPM from total keystrokes over session duration
                elapsed_ms = max(1, enrollment_seed.get("window_end", 0) - enrollment_seed.get("window_start", 0))
                if elapsed_ms == 0 and behavioral_data:
                    elapsed_ms = max(1, behavioral_data.get("window_end", 0) - behavioral_data.get("window_start", 0))
                typing_speed_wpm = (len(keystroke_events) / 5.0) / max(elapsed_ms / 60000.0, 0.01)
                signup_features["typing_speed_wpm"] = min(typing_speed_wpm, 200)
                
                # Correction/backspace analysis
                backspaces = [e for e in keystroke_events if e.get("is_backspace")]
                correction_rate = len(backspaces) / max(len(keystroke_events), 1)
                signup_features["burst_ratio"] = 1.0 - correction_rate
                
                # Rhythm consistency (CV of hold times)
                if hold_times and len(hold_times) > 2:
                    h_mean = statistics.mean(hold_times)
                    h_std = statistics.stdev(hold_times)
                    signup_features["rhythm_consistency"] = max(0, 1.0 - (h_std / max(h_mean, 1e-6)))
                
                # Digraph consistency from consecutive key pairs
                digraph_times = []
                for i in range(len(keystroke_events) - 1):
                    ft = keystroke_events[i + 1].get("flight_time", 0)
                    if ft and 0 < ft < 2000:
                        digraph_times.append(ft)
                if digraph_times and len(digraph_times) > 2:
                    d_mean = statistics.mean(digraph_times)
                    d_std = statistics.stdev(digraph_times)
                    signup_features["digraph_consistency"] = max(0, 1.0 - (d_std / max(d_mean, 1e-6)))
                
                # Mouse features from enrollment seed
                mouse_events = enrollment_seed.get("mouse_events") or behavioral_data.get("mouse_events") or []
                if mouse_events:
                    velocities = [e.get("velocity", 0) for e in mouse_events if e.get("velocity")]
                    if velocities:
                        signup_features["velocity_mean"] = statistics.mean(velocities)
                        signup_features["velocity_std"] = statistics.stdev(velocities) if len(velocities) > 1 else 0.0
                
                # Feed Session 0 into enrollment manager
                if signup_features:
                    enrollment_result = enrollment_mgr.ingest_session_data(
                        user_id=user_id,
                        keystroke_features=signup_features,
                        source="registration",
                    )
                    logger.info(
                        "Session 0 enrollment seed for user %d: %d features, %d keystrokes, "
                        "prompt_accuracy=%d%%, action=%s",
                        user_id,
                        len(signup_features),
                        len(keystroke_events),
                        enrollment_seed.get("match_accuracy", 0),
                        enrollment_result.get("action", "unknown"),
                    )
        except Exception:
            logger.error("Session 0 enrollment seed processing failed", exc_info=True)

        db.log_audit_evidence(
            action="user_registered",
            status="ok",
            user_id=user_id,
            resource="/api/v1/auth/register",
            metadata={
                "username": data.username,
                "enrollment_seed": bool(enrollment_result),
                "session_0_action": enrollment_result.get("action") if enrollment_result else None,
            },
            retention_tag="security",
        )
        import pyotp
        provisioning_uri = pyotp.totp.TOTP(mfa_secret).provisioning_uri(
            name=data.username,
            issuer_name="BehaviorAuth"
        )

        return {
            "data": {
                "user_id": user_id,
                "mfa_secret": mfa_secret,
                "mfa_provisioning_uri": provisioning_uri,
                "enrollment": enrollment_result,
            }
        }, 200


def _is_known_device(db, user_id: int, device_id: str) -> bool:
    """
    Check if this device_id has successfully logged in before
    for this user. Returns False for new/unknown devices.
    """
    if not device_id:
        return False
    try:
        with db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as cnt FROM sessions
                WHERE user_id = ?
                  AND device_id = ?
                  AND created_at < datetime('now', '-5 minutes')
                LIMIT 1
                """,
                (user_id, device_id),
            ).fetchone()
        return row["cnt"] > 0 if row else False
    except Exception:
        return False  # safe default: treat unknown as new


@auth_ns.route("/login")
class Login(Resource):
    @auth_ns.expect(login_model)
    @auth_ns.response(200, "Login successful", auth_success)
    @auth_ns.response(401, "Invalid credentials", auth_error)
    @limiter.limit("10 per minute")
    def post(self):
        """Authenticate with username and password. Returns JWT + session ID."""
        try:
            data = LoginSchema(**request.get_json() or {})
        except ValidationError as e:
            return make_error_response("MISSING_CREDENTIALS", str(e), status=400)

        db = get_db()
        user = db.authenticate_user(data.username, data.password)
        if not user:
            logger.warning("Failed login attempt for user: %s", data.username)
            db.log_audit_evidence(
                action="login_failed",
                status="blocked",
                user_id=0,
                resource="/api/v1/auth/login",
                metadata={"username": data.username, "ip": request.remote_addr},
                retention_tag="security",
            )
            return make_error_response(
                "INVALID_CREDENTIALS", "Invalid credentials", status=401
            )

        ip_address = request.remote_addr or "127.0.0.1"
        user_agent = request.headers.get("User-Agent", "")
        device_id = request.headers.get("X-Device-Id") or request.cookies.get("device_id") or str(uuid.uuid4())

        session_id = db.create_session(user["user_id"], ip_address, user_agent)
        if device_id:
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE sessions SET device_id = ? WHERE session_id = ?",
                    (device_id, session_id),
                )
                conn.commit()

        access_token = create_access_token(
            identity=str(user["user_id"]),
            additional_claims={"session_id": session_id, "aal": "pwd"},
            expires_delta=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
        )

        logger.info("User logged in: %s (Session: %s)", data.username, session_id)
        db.log_audit_evidence(
            action="login_success",
            status="ok",
            user_id=user["user_id"],
            session_id=session_id,
            resource="/api/v1/auth/login",
            metadata={"ip": ip_address, "device_id": device_id},
            retention_tag="security",
        )

        # Store login keystroke data as behavioral baseline
        if data.keystroke_data:
            db.store_behavioral_data(
                user_id=user["user_id"],
                session_id=session_id,
                data_type="keystroke",
                features={
                    "event_count": len(data.keystroke_data),
                    "source": "login",  # tag as login-time data
                    "login_anxiety_flag": True,  # downweight in scoring
                },
                raw_data={"keystroke_events": data.keystroke_data[:100]},
                confidence_score=float(min(len(data.keystroke_data) / 100.0, 1.0)),
                anomaly_score=None,
            )

        # ── Passive Enrollment: feed login keystrokes into profile ──────────
        enrollment_status = None
        enrollment_result = None
        try:
            from app.models.passive_enrollment import get_enrollment_manager

            enrollment_mgr = get_enrollment_manager()

            # Extract keystroke features from login data for enrollment
            login_features = {}
            if data.keystroke_data and len(data.keystroke_data) >= 2:
                try:
                    hold_times = [
                        e.get("hold_time", 0)
                        for e in data.keystroke_data
                        if e.get("hold_time")
                    ]
                    flight_times = [
                        e.get("flight_time", 0)
                        for e in data.keystroke_data
                        if e.get("flight_time")
                    ]
                    if hold_times:
                        login_features["hold_time_mean"] = sum(hold_times) / len(
                            hold_times
                        )
                        login_features["hold_time_std"] = (
                            sum(
                                (h - login_features["hold_time_mean"]) ** 2
                                for h in hold_times
                            )
                            / len(hold_times)
                        ) ** 0.5
                    if flight_times:
                        login_features["flight_time_mean"] = sum(flight_times) / len(
                            flight_times
                        )
                        login_features["flight_time_std"] = (
                            sum(
                                (f - login_features["flight_time_mean"]) ** 2
                                for f in flight_times
                            )
                            / len(flight_times)
                        ) ** 0.5
                except Exception:
                    pass

            if login_features:
                enrollment_result = enrollment_mgr.ingest_session_data(
                    user_id=user["user_id"],
                    keystroke_features=login_features,
                    source="login",
                )
                enrollment_status = enrollment_mgr.get_enrollment_status(
                    user["user_id"]
                )
        except Exception as exc:
            logger.error("Passive enrollment update at login failed", exc_info=True)

        # Check if this is a known device for this user
        device_known = _is_known_device(db, user["user_id"], device_id)
        device_new = not device_known

        if device_new:
            db.log_audit_evidence(
                action="new_device_login",
                status="flagged",
                user_id=user["user_id"],
                session_id=session_id,
                resource="/api/v1/auth/login",
                metadata={"device_id": device_id, "ip": ip_address},
                retention_tag="security",
            )

        mfa_required = user.get("mfa_enabled", False)
        
        if enrollment_status and enrollment_status.get("enrolled"):
            match_score = enrollment_result.get("match_score", 0.0) if enrollment_result else 0.5
            if match_score > 0.7:
                mfa_required = False
            elif match_score < 0.5:
                # Step up logic triggers email OTP on frontend
                mfa_required = True

        return {
            "data": {
                "access_token": access_token,
                "session_id": session_id,
                "mfa_required": mfa_required,
                "device_new": device_new,
                "enrollment": enrollment_status,
            }
        }, 200


@auth_ns.route("/forgot-password")
class ForgotPassword(Resource):
    @auth_ns.expect(forgot_pw_model)
    @auth_ns.response(200, "Request accepted")
    @limiter.limit("3 per minute")
    def post(self):
        """Initiate password reset flow. Always returns 200 to prevent user enumeration."""
        try:
            data = ForgotPasswordSchema(**request.get_json() or {})
        except ValidationError as e:
            return make_error_response("VALIDATION_ERROR", str(e), status=400)

        db = get_db()
        user = None
        if data.email:
            user = db.get_user_by_email(data.email)
        elif data.username:
            user = db.get_user_by_username(data.username)
        else:
            return make_error_response("VALIDATION_ERROR", "Must provide username or email", status=400)
            
        if not user:
            return {
                "success": True,
                "message": "If the user exists, a reset email will be sent.",
            }, 200

        token = str(uuid.uuid4())
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = datetime.datetime.now() + datetime.timedelta(minutes=15)

        # Persist hashed token in DB (authoritative store)
        db.issue_password_reset_token(user["user_id"], token_hash, expires_at)

        # Cache in Redis as fast-path lookup (optional)
        redis_client = get_redis()
        if redis_client:
            redis_client.setex(f"pwd_reset:{token_hash}", 900, user["user_id"])

        # Deliver the raw token via email — never log it
        from flask import current_app

        mail_svc = current_app.extensions.get("mail_service")
        if mail_svc:
            reset_url_base = current_app.config.get(
                "RESET_URL_BASE", "http://localhost:3000/reset-password"
            )
            mail_svc.send_password_reset(
                to=user["email"],
                username=user["username"],
                reset_token=token,
                reset_url_base=reset_url_base,
            )

        logger.info("Password reset flow initiated for user %s", user["username"])

        db.log_audit_evidence(
            action="password_reset_requested",
            status="ok",
            user_id=user["user_id"],
            resource="/api/v1/auth/forgot-password",
            retention_tag="security",
        )
        return {
            "success": True,
            "message": "If the user exists, a reset email will be sent.",
        }, 200


@auth_ns.route("/password-reset/confirm")
class ResetPasswordConfirm(Resource):
    @auth_ns.expect(reset_pw_model)
    @auth_ns.response(200, "Password updated")
    @auth_ns.response(400, "Invalid or expired token", auth_error)
    @limiter.limit("3 per minute")
    def post(self):
        """Confirm password reset with token and new password."""
        try:
            data = ResetPasswordSchema(**request.get_json() or {})
        except ValidationError as e:
            return make_error_response("VALIDATION_ERROR", str(e), status=400)

        db = get_db()
        token_hash = hashlib.sha256(data.token.encode("utf-8")).hexdigest()

        # Try Redis fast-path first, fall back to DB
        user_id = None
        redis_client = get_redis()
        if redis_client:
            user_id = redis_client.get(f"pwd_reset:{token_hash}")

        if user_id:
            user_id = int(user_id)
            redis_client.delete(f"pwd_reset:{token_hash}")
            # Also mark consumed in DB
            db.consume_password_reset_token(token_hash)
        else:
            # DB fallback — works even when Redis is unavailable
            user_id = db.consume_password_reset_token(token_hash)

        if not user_id:
            return make_error_response(
                "INVALID_TOKEN", "Invalid or expired reset token", status=400
            )

        db.update_user_password(int(user_id), data.new_password)

        logger.info("Password reset successful for user ID: %s", user_id)
        db.log_audit_evidence(
            action="password_reset_confirmed",
            status="ok",
            user_id=int(user_id),
            resource="/api/v1/auth/password-reset/confirm",
            retention_tag="security",
        )
        return {"success": True}, 200


@auth_ns.route("/send-otp-email")
class SendOtpEmail(Resource):
    @jwt_required()
    @limiter.limit("3 per minute")
    def post(self):
        """Generate a random 6-digit OTP, store it in the database, and email it."""
        db = get_db()
        user_id = int(get_jwt_identity())
        user = db.get_user_for_mfa(user_id)
        if not user:
            return make_error_response("USER_NOT_FOUND", "User not found", status=400)

        email = user.get("email")
        username = user.get("username", "User")
        if not email:
            return make_error_response("NO_EMAIL", "No email address on file", status=400)

        # Generate a cryptographically random 6-digit OTP
        import secrets as _secrets
        otp_code = ''.join([str(_secrets.choice(range(10))) for _ in range(6)])

        # Store in database with 60-second TTL
        OTP_TTL_SECONDS = 60
        db.store_otp(user_id, otp_code, ttl_seconds=OTP_TTL_SECONDS)

        # Send via the configured mail service
        try:
            mail_service = current_app.extensions.get("mail_service")
            if not mail_service:
                return make_error_response("MAIL_NOT_CONFIGURED", "Email service not available", status=500)

            subject = "Your Login OTP — BehaviorAuth"
            body_text = (
                f"Hello {username},\n\n"
                f"Your one-time authentication code is:\n\n"
                f"    {otp_code}\n\n"
                f"This code expires in {OTP_TTL_SECONDS} seconds.\n\n"
                f"If you did not request this, please secure your account immediately.\n\n"
                f"— BehaviorAuth Security Team"
            )
            body_html = (
                f"<h2>Your Login OTP</h2>"
                f"<p>Hello <strong>{username}</strong>,</p>"
                f"<p>Your one-time authentication code is:</p>"
                f"<div style='text-align:center;margin:24px 0'>"
                f"<span style='font-size:32px;font-family:monospace;letter-spacing:8px;"
                f"padding:16px 32px;background:#1e293b;color:#60a5fa;border-radius:12px;"
                f"display:inline-block'>{otp_code}</span></div>"
                f"<p><small>This code expires in {OTP_TTL_SECONDS} seconds.</small></p>"
                f"<p>If you did not request this, please secure your account immediately.</p>"
                f"<hr><p style='color:#888;font-size:12px'>BehaviorAuth Security Team</p>"
            )

            sent = mail_service.send(email, subject, body_text, body_html)
            if not sent:
                logger.warning("Failed to send OTP email to %s", email)

        except Exception as e:
            logger.error("OTP email delivery error: %s", e)

        # Always return success to prevent email enumeration
        return {"success": True, "message": "OTP sent to registered email"}, 200


@auth_ns.route("/mfa/verify")
class MFAVerify(Resource):
    @auth_ns.expect(mfa_model)
    @auth_ns.response(200, "MFA verification successful", auth_success)
    @auth_ns.response(401, "Invalid OTP", auth_error)
    @jwt_required()
    @limiter.limit("5 per minute")
    def post(self):
        """Verify OTP code against the database and elevate session assurance to MFA level."""
        try:
            data = MFAVerifySchema(**request.get_json() or {})
        except ValidationError as e:
            return make_error_response("VALIDATION_ERROR", str(e), status=400)

        db = get_db()
        user_id = int(get_jwt_identity())

        # Verify OTP against database (real-time, not TOTP)
        otp_valid = db.verify_otp(user_id, data.otp)
        if not otp_valid:
            logger.warning("Failed MFA verification for user %d", user_id)
            db.log_audit_evidence(
                action="mfa_failed",
                status="blocked",
                user_id=user_id,
                session_id=data.session_id,
                resource="/api/v1/auth/mfa/verify",
                retention_tag="security",
            )
            return make_error_response("INVALID_OTP", "Invalid or expired OTP", status=401)

        db.update_session_assurance(data.session_id, "mfa")
        new_token = create_access_token(
            identity=str(user_id),
            additional_claims={"session_id": data.session_id, "aal": "mfa"},
            expires_delta=current_app.config.get(
                "JWT_REFRESH_TOKEN_EXPIRES", datetime.timedelta(hours=8)
            ),
        )

        logger.info("MFA verified for user %d", user_id)
        db.log_audit_evidence(
            action="mfa_verified",
            status="ok",
            user_id=user_id,
            session_id=data.session_id,
            resource="/api/v1/auth/mfa/verify",
            retention_tag="security",
        )
        return {"success": True, "data": {"access_token": new_token}}, 200


@auth_ns.route("/logout")
class Logout(Resource):
    @auth_ns.expect(logout_model)
    @auth_ns.response(200, "Logged out")
    @jwt_required()
    def post(self):
        """Terminate the active session, blocklist the JWT, and clear cached state."""
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id") or request.cookies.get("session_id")
        user_id = int(get_jwt_identity())
        if session_id:
            get_db().end_session(session_id)
            redis_client = get_redis()
            if redis_client:
                redis_client.delete(f"session:{session_id}")

        # Blocklist the JWT so it cannot be reused for its remaining TTL
        redis_client = get_redis()
        if redis_client:
            try:
                jwt_data = get_jwt()
                jti = jwt_data.get("jti")
                exp = jwt_data.get("exp", 0)
                if jti:
                    remaining_ttl = max(
                        int(exp - datetime.datetime.now().timestamp()), 1
                    )
                    redis_client.setex(f"jwt_blocklist:{jti}", remaining_ttl, "1")
            except Exception:
                logger.warning("Failed to blocklist JWT on logout")

        logger.info("User logged out (User: %d, Session: %s)", user_id, session_id)
        get_db().log_audit_evidence(
            action="logout",
            status="ok",
            user_id=user_id,
            session_id=session_id,
            resource="/api/v1/auth/logout",
            retention_tag="security",
        )
        return {"success": True}, 200


@auth_ns.route("/csrf-token")
class CSRFToken(Resource):
    @limiter.limit("30 per minute")
    def get(self):
        """Return a signed, time-limited CSRF token for the frontend."""
        from itsdangerous import URLSafeTimedSerializer
        from flask import g

        serializer = URLSafeTimedSerializer(
            current_app.config["SECRET_KEY"], salt="csrf-token"
        )
        token = serializer.dumps({"rid": getattr(g, "request_id", "")})
        return {"csrf_token": token}, 200


@auth_ns.route("/me")
class AuthMe(Resource):
    @jwt_required()
    @limiter.limit("60 per minute")
    def get(self):
        """Return current authenticated user info for frontend auth checks."""
        user_id = int(get_jwt_identity())
        db = get_db()
        user = db.get_user_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404

        # Get active session
        session_id = request.cookies.get("session_id", "")

        return {
            "user_id": user.get("user_id"),
            "username": user.get("username", ""),
            "email": user.get("email", ""),
            "role": user.get("role", "user"),
            "session_id": session_id,
        }, 200


@auth_ns.route("/mfa-verify")
class MFAVerifyAlias(Resource):
    """Alias for /mfa/verify — frontend calls this path with a dash."""
    @auth_ns.expect(mfa_model)
    @jwt_required()
    @limiter.limit("10 per minute")
    def post(self):
        """Verify MFA OTP code (alias route for frontend compatibility)."""
        # Delegate to the same logic as MFAVerify
        return MFAVerify().post()

