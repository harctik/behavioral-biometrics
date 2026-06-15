"""Authentication API blueprint.

Handles registration, login, logout, MFA verification, password reset.
All responses follow a standardised envelope: ``{"data": {...}}`` on success,
``{"error": {...}}`` on failure.
"""
from flask import request, current_app, make_response, jsonify
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
)
from pydantic import ValidationError
from app.schemas.auth_schemas import (
    RegisterSchema,
    LoginSchema,
    ForgotPasswordSchema,
    ResetPasswordSchema,
    MFAVerifySchema,
    VerifyEmailSchema
)
import re
import hashlib
import logging
import uuid
import datetime
from typing import Annotated, Optional

from app.extensions import get_db, get_redis, limiter
from app.error_handling import make_error_response
from app.api.helpers import resolve_query
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

password_verify_model = auth_ns.model(
    "PasswordVerifyRequest",
    {
        "password": fields.String(required=True),
        "behavioral_data": fields.Raw(required=False),
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

        # ── Pre-check for existing user ──────────────────────────────────────────
        existing = db.get_user_by_username(data.username)
        if existing:
            return make_error_response(
                "USERNAME_TAKEN",
                "This username is already taken. Try logging in or resetting your password.",
                status=409,
            )
        existing = db.get_user_by_email(data.email)
        if existing:
            return make_error_response(
                "EMAIL_TAKEN",
                "An account with this email already exists. Try logging in or resetting your password.",
                status=409,
            )

        result = db.create_user(data.username, data.email, data.password)
        if not result:
            logger.warning("Registration failed - user exists: %s", data.username)
            return make_error_response("USER_EXISTS", "User already exists", status=400)

        user_id, mfa_secret = result
        logger.info("New user registered: %s (ID: %d)", data.username, user_id)

        # ── Auto-verify all users (email verification disabled) ────────────
        db.set_email_verified(user_id)

        db.log_audit_evidence(
            action="user_registered",
            status="ok",
            user_id=user_id,
            resource="/api/v1/auth/register",
            metadata={"username": data.username, "auto_verified": True},
            retention_tag="security",
        )

        # ── Session 0: Initialize behavioral profile from signup ─────────
        enrollment_result = None
        try:
            raw_json = request.get_json() or {}
            enrollment_seed = raw_json.get("enrollment_seed") or {}
            behavioral_data = raw_json.get("behavioral_data") or {}

            keystroke_events = (
                enrollment_seed.get("keystroke_events")
                or behavioral_data.get("keystroke_events")
                or []
            )

            if keystroke_events and len(keystroke_events) >= 5:
                from app.services.behavioral_enrollment import (
                    behavioral_enrollment_service,
                )

                enrollment_result = behavioral_enrollment_service.process_session_zero(
                    user_id=user_id,
                    enrollment_seed=enrollment_seed,
                    behavioral_data=behavioral_data,
                    source="registration",
                )
        except Exception:
            logger.error("Session 0 enrollment seed processing failed", exc_info=True)

        # ── Save the user's assigned typing prompt for login verification ──
        try:
            raw_json = request.get_json() or {}
            enrollment_seed = raw_json.get("enrollment_seed") or {}
            typed_prompt = enrollment_seed.get("typed_prompt", "")
            if typed_prompt:
                db.set_typing_prompt(user_id, typed_prompt)
        except Exception:
            logger.error("Failed to save typing prompt", exc_info=True)

        import pyotp

        provisioning_uri = None
        if mfa_secret:
            provisioning_uri = pyotp.totp.TOTP(mfa_secret).provisioning_uri(
                name=data.username, issuer_name="BehaviorAuth"
            )

        resp_data = {
            "user_id": user_id,
            "requires_verification": False,
            "email": data.email,
            "enrollment": enrollment_result,
            "mfa_provisioning_uri": provisioning_uri,
        }

        return {"data": resp_data}, 200


from app.services.auth_service import AuthService
from app.schemas.auth_schemas import LoginVerifySchema, AccountRecoveryVerifySchema


# ── Typing prompts for users without an assigned prompt ──────────────────
_FALLBACK_PROMPTS = [
    "The quick brown fox jumps over the lazy dog",
    "Pack my box with five dozen liquor jugs",
    "A secure system operates invisibly but effectively",
    "Every keystroke reveals the person behind the screen",
    "Banking security requires vigilant user behavior",
]


@auth_ns.route("/login")
class Login(Resource):
    @auth_ns.expect(login_model)
    @auth_ns.response(200, "Credentials valid — challenge issued", auth_success)
    @auth_ns.response(401, "Invalid credentials", auth_error)
    @limiter.limit("10 per minute")
    def post(self):
        """Phase 1: Validate credentials and issue a typing challenge.

        Returns a challenge_token + typing_prompt. Does NOT issue a JWT yet.
        The client must complete Phase 2 (/login/verify) with behavioral data.
        """
        try:
            data = LoginSchema(**request.get_json() or {})
        except ValidationError as e:
            return make_error_response("MISSING_CREDENTIALS", str(e), status=400)

        ip_address = request.remote_addr or "127.0.0.1"

        # 1. Credential Stuffing Check
        stuffing_ok, stuffing_msg = AuthService.check_credential_stuffing(ip_address)
        if not stuffing_ok:
            return make_error_response("RATE_LIMIT_EXCEEDED", stuffing_msg, status=429)

        # 2. Account Lockout Check
        lockout_ok, remaining, lockout_until = AuthService.check_account_lockout(data.username)
        if not lockout_ok:
            err_result = make_error_response("ACCOUNT_LOCKED", "Account locked due to too many failed attempts.", status=423)
            if isinstance(err_result, tuple):
                resp, status_code = err_result
                resp["error"]["details"] = {"lockout_until": lockout_until, "remaining_attempts": 0}
                return resp, status_code
            return err_result

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
            AuthService.increment_credential_stuffing(ip_address)
            rem, until = AuthService.increment_account_lockout(data.username)

            # ── Suspicious login alert email ────────────────────────────
            ALERT_THRESHOLD = current_app.config.get("SUSPICIOUS_LOGIN_ALERT_THRESHOLD", 3)
            try:
                target_user = db.get_user_by_username(data.username)
                if not target_user:
                    target_user = db.get_user_by_email(data.username)

                if target_user and target_user.get("email"):
                    failed_count = target_user.get("failed_attempts", 0)
                    if failed_count >= ALERT_THRESHOLD:
                        cooldown_key = f"login_alert_cd:{data.username}"
                        rc = get_redis()
                        should_send = True
                        if rc:
                            try:
                                if rc.exists(cooldown_key):
                                    should_send = False
                                else:
                                    rc.setex(cooldown_key, 600, 1)
                            except Exception:
                                pass
                        if should_send:
                            mail_svc = current_app.extensions.get("mail_service")
                            if mail_svc:
                                mail_svc.send_suspicious_login_alert(
                                    to=target_user["email"],
                                    username=target_user["username"],
                                    failed_attempts=failed_count,
                                    ip_address=ip_address,
                                    user_agent=request.headers.get("User-Agent", "unknown"),
                                )
            except Exception:
                logger.error("Failed to send suspicious login alert", exc_info=True)

            err_result = make_error_response("INVALID_CREDENTIALS", "Invalid credentials", status=401)
            if isinstance(err_result, tuple):
                resp, status_code = err_result
                resp["error"]["details"] = {"remaining_attempts": rem, "lockout_until": until}
                return resp, status_code
            return err_result

        AuthService.reset_account_lockout(data.username)

        # ── Check behavioral block ─────────────────────────────────────────
        if AuthService.is_user_blocked(user["user_id"]):
            return make_error_response(
                "BEHAVIORAL_BLOCKED",
                "Account temporarily locked due to unusual activity. Check your email for a recovery link.",
                status=403,
            )

        # ── Generate challenge token ───────────────────────────────────────
        challenge_token = AuthService.create_login_challenge(user["user_id"])

        # ── Get user's typing prompt ───────────────────────────────────────
        typing_prompt = db.get_typing_prompt(user["user_id"])
        if not typing_prompt:
            # Assign a deterministic prompt based on user_id (no randomness)
            import hashlib
            idx = int(hashlib.md5(str(user["user_id"]).encode()).hexdigest(), 16) % len(_FALLBACK_PROMPTS)
            typing_prompt = _FALLBACK_PROMPTS[idx]
            db.set_typing_prompt(user["user_id"], typing_prompt)

        # ── Get enrollment status ──────────────────────────────────────────
        enrollment_info = {"sessions_completed": 0, "sessions_required": 3, "enrolled": False}
        try:
            from app.models.passive_enrollment import get_enrollment_manager
            enrollment_mgr = get_enrollment_manager()
            enrollment_info = enrollment_mgr.get_enrollment_status(user["user_id"])
        except Exception:
            pass

        logger.info(
            "Login Phase 1 passed for user %s — challenge issued (enrollment: %s)",
            data.username, enrollment_info.get("enrollment_phase", "unknown"),
        )

        return {
            "data": {
                "challenge_token": challenge_token,
                "typing_prompt": typing_prompt,
                "enrollment_phase": enrollment_info.get("enrollment_phase", "collecting"),
                "sessions_completed": enrollment_info.get("sessions_completed", 0),
                "sessions_required": enrollment_info.get("sessions_required", 3),
                "username": data.username,
            }
        }, 200


@auth_ns.route("/login/verify")
class LoginVerify(Resource):
    @auth_ns.response(200, "Login successful", auth_success)
    @auth_ns.response(401, "Challenge invalid or expired", auth_error)
    @auth_ns.response(403, "Behavioral anomaly — access denied", auth_error)
    @limiter.limit("10 per minute")
    def post(self):
        """Phase 2: Verify behavioral biometrics from typing challenge.

        Compares the user's typing pattern against their enrolled profile
        and makes a grant/step_up/block decision.
        """
        try:
            data = LoginVerifySchema(**request.get_json() or {})
        except ValidationError as e:
            return make_error_response("VALIDATION_ERROR", str(e), status=400)

        # ── Validate challenge token ───────────────────────────────────────
        user_id = AuthService.validate_login_challenge(data.challenge_token)
        if user_id is None:
            return make_error_response(
                "CHALLENGE_EXPIRED",
                "Challenge token expired or invalid. Please start login again.",
                status=401,
            )

        db = get_db()
        user = db.get_user_by_id(user_id)
        if not user:
            return make_error_response("USER_NOT_FOUND", "User not found", status=401)

        ip_address = request.remote_addr or "127.0.0.1"
        user_agent = request.headers.get("User-Agent", "")
        device_id = (
            request.headers.get("X-Device-Id")
            or request.cookies.get("device_id")
            or str(uuid.uuid4())
        )

        # ── Extract behavioral features from typing data ───────────────────
        behavioral_data = data.behavioral_data or {}
        keystroke_events = behavioral_data.get("keystroke_events", [])
        keystroke_profile = data.keystroke_profile or {}

        # ── Get enrollment status ──────────────────────────────────────────
        enrollment_phase = True
        enrollment_status = None
        match_score = 1.0  # Default for enrollment
        enrollment_result = None
        digraph_result = None

        try:
            from app.models.passive_enrollment import get_enrollment_manager
            enrollment_mgr = get_enrollment_manager()
            enrollment_status = enrollment_mgr.get_enrollment_status(user_id)
            enrollment_phase = not enrollment_status.get("enrolled", False)

            # Extract aggregate features
            login_features = {}
            if keystroke_events and len(keystroke_events) >= 2:
                try:
                    hold_times = [e.get("hold_time", 0) for e in keystroke_events if e.get("hold_time")]
                    flight_times = [e.get("flight_time", 0) for e in keystroke_events if e.get("flight_time")]
                    if hold_times:
                        login_features["hold_time_mean"] = sum(hold_times) / len(hold_times)
                        login_features["hold_time_std"] = (
                            sum((h - login_features["hold_time_mean"]) ** 2 for h in hold_times) / len(hold_times)
                        ) ** 0.5
                    if flight_times:
                        login_features["flight_time_mean"] = sum(flight_times) / len(flight_times)
                        login_features["flight_time_std"] = (
                            sum((f - login_features["flight_time_mean"]) ** 2 for f in flight_times) / len(flight_times)
                        ) ** 0.5
                except Exception:
                    pass

            # Ingest into aggregate profile
            if login_features:
                enrollment_result = enrollment_mgr.ingest_session_data(
                    user_id=user_id,
                    keystroke_features=login_features,
                    source="login",
                )

            # ── Per-key/digraph Bayesian profile update ────────────────────
            digraph_profile = None
            if keystroke_profile and keystroke_profile.get("per_key_hold"):
                digraph_profile = keystroke_profile
            elif keystroke_events and len(keystroke_events) >= 3:
                try:
                    from app.models.digraph_profile import get_digraph_extractor
                    extractor = get_digraph_extractor()
                    digraph_profile = extractor.extract_profile(keystroke_events, source="login")
                except Exception:
                    pass

            if digraph_profile and digraph_profile.get("meta", {}).get("unique_keys", 0) >= 2:
                try:
                    digraph_result = enrollment_mgr.ingest_digraph_profile(
                        user_id=user_id,
                        digraph_profile=digraph_profile,
                        source="login",
                    )
                except Exception:
                    logger.error("Digraph profile update at login failed", exc_info=True)

            # ── Compute combined match score ───────────────────────────────
            if not enrollment_phase:
                agg_score = enrollment_result.get("match_score", 0.5) if enrollment_result else 0.5
                dig_score = digraph_result.get("match_score", 0.5) if digraph_result else 0.5

                # Weighted: 60% digraph (more discriminative), 40% aggregate
                if digraph_result and enrollment_result:
                    match_score = 0.4 * agg_score + 0.6 * dig_score
                elif digraph_result:
                    match_score = dig_score
                elif enrollment_result:
                    match_score = agg_score
                else:
                    match_score = 0.5

                logger.info(
                    "Login Phase 2 for user %d: agg=%.3f dig=%.3f combined=%.3f",
                    user_id, agg_score, dig_score, match_score,
                )

            # Refresh enrollment status after ingestion
            enrollment_status = enrollment_mgr.get_enrollment_status(user_id)

        except Exception:
            logger.error("Behavioral verification failed", exc_info=True)

        # ── Make decision ──────────────────────────────────────────────────
        device_known = AuthService.is_known_device(db, user_id, device_id)
        decision = AuthService.evaluate_behavioral_decision(
            match_score=match_score,
            enrollment_phase=enrollment_phase,
            is_known_device=device_known,
        )

        logger.info(
            "Login Phase 2 decision for user %d: decision=%s score=%.3f enrollment=%s device_known=%s",
            user_id, decision, match_score, enrollment_phase, device_known,
        )

        # ── Handle BLOCK decision ──────────────────────────────────────────
        if decision == "block":
            AuthService.block_user(user_id)

            db.log_audit_evidence(
                action="behavioral_block",
                status="blocked",
                user_id=user_id,
                resource="/api/v1/auth/login/verify",
                metadata={"match_score": match_score, "device_id": device_id, "ip": ip_address},
                retention_tag="security",
            )

            # Send alert email + recovery link
            try:
                recovery_token = AuthService.create_recovery_token(user_id)
                mail_svc = current_app.extensions.get("mail_service")
                user_detail = db.get_user_by_id(user_id)
                if mail_svc and user_detail and user_detail.get("email"):
                    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:3000")
                    recovery_url = f"{frontend_url}/account-recovery?token={recovery_token}"
                    mail_svc.send_suspicious_login_alert(
                        to=user_detail["email"],
                        username=user_detail["username"],
                        failed_attempts=0,
                        ip_address=ip_address,
                        user_agent=request.headers.get("User-Agent", "unknown"),
                    )
                    logger.info("Behavioral block alert sent to user %d", user_id)
            except Exception:
                logger.error("Failed to send behavioral block alert", exc_info=True)

            return make_error_response(
                "BEHAVIORAL_BLOCKED",
                "Access denied — unusual typing pattern detected. A recovery link has been sent to your email.",
                status=403,
            )

        # ── Create session + JWT (for grant, step_up, and enroll) ──────────
        session_id = db.create_session(user_id, ip_address, user_agent)
        if device_id:
            with db.get_connection() as conn:
                query = resolve_query(db, "UPDATE sessions SET device_id = :param WHERE session_id = :param")
                conn.execute(query, (device_id, session_id))
                conn.commit()

        mfa_required = decision == "step_up"

        access_token = create_access_token(
            identity=str(user_id),
            additional_claims={"session_id": session_id, "aal": "pwd"},
            expires_delta=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
        )

        db.log_audit_evidence(
            action="login_success",
            status="ok",
            user_id=user_id,
            session_id=session_id,
            resource="/api/v1/auth/login/verify",
            metadata={
                "ip": ip_address,
                "device_id": device_id,
                "decision": decision,
                "match_score": round(match_score, 4),
            },
            retention_tag="security",
        )

        if not device_known:
            db.log_audit_evidence(
                action="new_device_login",
                status="flagged",
                user_id=user_id,
                session_id=session_id,
                resource="/api/v1/auth/login/verify",
                metadata={"device_id": device_id, "ip": ip_address},
                retention_tag="security",
            )

        logger.info("User %d logged in via Phase 2: decision=%s session=%s", user_id, decision, session_id)

        resp_data = {
            "data": {
                "access_token": access_token,
                "session_id": session_id,
                "mfa_required": mfa_required,
                "decision": decision,
                "match_score": round(match_score, 4),
                "device_new": not device_known,
                "enrollment": enrollment_status,
            }
        }
        resp = make_response(jsonify(resp_data), 200)
        set_access_cookies(resp, access_token)
        resp.set_cookie(
            "session_id", session_id,
            httponly=False, samesite="Lax", path="/",
            max_age=int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
        )
        return resp


@auth_ns.route("/account-recovery/verify")
class AccountRecoveryVerify(Resource):
    @auth_ns.response(200, "Account unlocked")
    @auth_ns.response(401, "Recovery failed")
    @limiter.limit("5 per minute")
    def post(self):
        """Verify identity via multiple typing samples to unlock a blocked account."""
        try:
            data = AccountRecoveryVerifySchema(**request.get_json() or {})
        except ValidationError as e:
            return make_error_response("VALIDATION_ERROR", str(e), status=400)

        user_id = AuthService.validate_recovery_token(data.recovery_token)
        if user_id is None:
            return make_error_response(
                "RECOVERY_EXPIRED",
                "Recovery token expired, invalid, or max attempts exceeded.",
                status=401,
            )

        # ── Compare typing samples against stored profile ──────────────
        db = get_db()
        match_count = 0
        total_score = 0.0

        try:
            from app.models.passive_enrollment import get_enrollment_manager
            enrollment_mgr = get_enrollment_manager()

            # Get stored profile for comparison
            for _idx, _typed_text in enumerate(data.typed_texts):
                # Use the behavioral data to compute a match score
                behavioral_data = data.behavioral_data or {}
                keystroke_events = behavioral_data.get("keystroke_events", [])

                if keystroke_events and len(keystroke_events) >= 3:
                    try:
                        from app.models.digraph_profile import get_digraph_extractor
                        extractor = get_digraph_extractor()
                        digraph_profile = extractor.extract_profile(keystroke_events, source="recovery")
                        if digraph_profile and digraph_profile.get("meta", {}).get("unique_keys", 0) >= 2:
                            # Compare without ingesting
                            stored = enrollment_mgr._load_digraph_state(user_id)
                            if stored and stored.get("per_key_hold"):
                                score = enrollment_mgr._compute_digraph_match_score(stored, digraph_profile)
                                total_score += score
                                if score >= 0.6:
                                    match_count += 1
                    except Exception:
                        logger.error("Recovery sample %d comparison failed", _idx, exc_info=True)

        except Exception:
            logger.error("Recovery verification failed", exc_info=True)

        # ── Decision: 2 out of 3 samples must match ────────────────────
        # If we couldn't compute scores (no profile yet), be lenient
        if match_count >= 2 or (total_score == 0 and len(data.typed_texts) >= 3):
            AuthService.unblock_user(user_id)
            AuthService.consume_recovery_token(data.recovery_token)

            db.log_audit_evidence(
                action="account_recovered",
                status="ok",
                user_id=user_id,
                resource="/api/v1/auth/account-recovery/verify",
                metadata={"match_count": match_count, "total_score": round(total_score, 4)},
                retention_tag="security",
            )

            logger.info("Account recovered for user %d: %d/3 samples matched", user_id, match_count)
            return {"message": "Account unlocked successfully"}, 200
        else:
            db.log_audit_evidence(
                action="account_recovery_failed",
                status="blocked",
                user_id=user_id,
                resource="/api/v1/auth/account-recovery/verify",
                metadata={"match_count": match_count, "total_score": round(total_score, 4)},
                retention_tag="security",
            )

            logger.warning("Account recovery failed for user %d: %d/3 samples matched", user_id, match_count)
            return make_error_response(
                "RECOVERY_FAILED",
                "Your typing patterns did not match. Recovery attempts remaining: check your email.",
                status=401,
            )


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
            return make_error_response(
                "VALIDATION_ERROR", "Must provide username or email", status=400
            )

        if not user:
            return {
                "success": True,
                "message": "If the user exists, a reset email will be sent.",
            }, 200

        token = str(uuid.uuid4())
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)

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
            reset_url_base = current_app.config.get("RESET_URL_BASE", "") or \
                (current_app.config.get("FRONTEND_URL", "").rstrip("/") + "/reset-password" if current_app.config.get("FRONTEND_URL") else "http://localhost:3000/reset-password")
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


@auth_ns.route("/verify-email")
class VerifyEmail(Resource):
    @limiter.limit("5 per minute")
    def post(self):
        """Verify user's email with OTP code or legacy token."""
        try:
            data = VerifyEmailSchema(**request.get_json() or {})
        except ValidationError as e:
            return make_error_response("VALIDATION_ERROR", str(e), status=400)

        db = get_db()
        user_id = None

        # ── Path 1: Code + user_id (OTP-based flow) ─────────────────
        if data.code and data.user_id:
            if not db.verify_otp(data.user_id, data.code):
                return make_error_response(
                    "INVALID_CODE", "Invalid or expired verification code", status=400
                )
            user_id = data.user_id

        # ── Path 2: Token (legacy link-based flow) ──────────────────
        elif data.token:
            token_hash = hashlib.sha256(data.token.encode("utf-8")).hexdigest()
            redis_client = get_redis()
            if redis_client:
                cached = redis_client.get(f"email_verify:{token_hash}")
                if cached:
                    user_id = int(cached)
                    redis_client.delete(f"email_verify:{token_hash}")

            if not user_id:
                return make_error_response(
                    "INVALID_TOKEN", "Invalid or expired verification token", status=400
                )
        else:
            return make_error_response(
                "VALIDATION_ERROR", "Provide either 'code' + 'user_id' or 'token'", status=400
            )

        db.set_email_verified(user_id)

        user = db.get_user_for_mfa(user_id)
        mfa_secret = user.get("mfa_secret") if user else None

        provisioning_uri = None
        if mfa_secret:
            import pyotp

            provisioning_uri = pyotp.totp.TOTP(mfa_secret).provisioning_uri(
                name=user.get("username", "User"), issuer_name="BehaviorAuth"
            )

        db.log_audit_evidence(
            action="email_verified",
            status="ok",
            user_id=user_id,
            resource="/api/v1/auth/verify-email",
            retention_tag="security",
        )

        return {
            "success": True,
            "data": {
                "mfa_secret": mfa_secret,
                "mfa_provisioning_uri": provisioning_uri,
            },
        }, 200


@auth_ns.route("/resend-verification")
class ResendVerification(Resource):
    @limiter.limit("2 per minute")
    def post(self):
        """Resend email verification OTP code."""
        raw = request.get_json() or {}
        req_user_id = raw.get("user_id")
        if not req_user_id:
            return make_error_response("VALIDATION_ERROR", "user_id is required", status=400)

        db = get_db()
        user = db.get_user_by_id(int(req_user_id))
        if not user:
            return make_error_response("USER_NOT_FOUND", "User not found", status=404)

        if user.get("email_verified"):
            return {"success": True, "message": "Email already verified"}, 200

        # Generate new 6-digit code
        import secrets as _secrets
        verification_code = "".join([str(_secrets.choice(range(10))) for _ in range(6)])
        db.store_otp(int(req_user_id), verification_code, ttl_seconds=600)

        mail_svc = current_app.extensions.get("mail_service")
        has_real_mail = mail_svc and getattr(mail_svc, "backend", "console") != "console"

        if has_real_mail:
            try:
                subject = "Your Verification Code — AetherAuth"
                body_text = (
                    f"Hello {user['username']},\n\n"
                    f"Your new verification code is:\n\n"
                    f"    {verification_code}\n\n"
                    f"This code expires in 10 minutes.\n\n"
                    f"\u2014 AetherAuth Security Team"
                )
                body_html = (
                    f"<h2>Verify Your Email</h2>"
                    f"<p>Hello <strong>{user['username']}</strong>,</p>"
                    f"<p>Your new verification code is:</p>"
                    f"<div style='text-align:center;margin:24px 0'>"
                    f"<span style='font-size:32px;font-family:monospace;letter-spacing:8px;"
                    f"padding:16px 32px;background:#1e293b;color:#60a5fa;border-radius:12px;"
                    f"display:inline-block'>{verification_code}</span></div>"
                    f"<p><small>This code expires in 10 minutes.</small></p>"
                    f"<hr><p style='color:#888;font-size:12px'>AetherAuth Security Team</p>"
                )
                mail_svc.send(user["email"], subject, body_text, body_html)
            except Exception as exc:
                logger.error("Failed to resend verification email: %s", exc)

        response = {"success": True, "message": "Verification code sent"}
        if not has_real_mail:
            response["verification_code"] = verification_code
            response["dev_mode"] = True

        return response, 200


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
            if redis_client:
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
            return make_error_response(
                "NO_EMAIL", "No email address on file", status=400
            )

        # Generate a cryptographically random 6-digit OTP
        import secrets as _secrets

        otp_code = "".join([str(_secrets.choice(range(10))) for _ in range(6)])

        # Store in database with 120-second TTL (synced with frontend timer)
        OTP_TTL_SECONDS = 120
        db.store_otp(user_id, otp_code, ttl_seconds=OTP_TTL_SECONDS)

        # Determine if we have a real mail backend
        mail_service = current_app.extensions.get("mail_service")
        is_console_mode = not mail_service or getattr(mail_service, "backend", "console") == "console"

        # Send via the configured mail service
        email_sent = False
        try:
            if mail_service and not is_console_mode:
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
                email_sent = mail_service.send(email, subject, body_text, body_html)
                if not email_sent:
                    logger.warning("Failed to send OTP email to %s", email)
        except Exception as e:
            logger.error("OTP email delivery error: %s", e)

        # Build response
        response = {
            "success": True,
            "message": "OTP sent to registered email",
            "ttl_seconds": OTP_TTL_SECONDS,
        }

        # In console/dev mode, return the OTP directly so the frontend can display it
        # This is ONLY for development — in production, mail_service.backend != "console"
        if is_console_mode:
            response["otp_code"] = otp_code
            response["dev_mode"] = True
            response["message"] = "OTP generated (dev mode — no email service configured)"
            logger.info("[DEV OTP] User %d OTP: %s (console backend, code returned in response)", user_id, otp_code)

        return response, 200


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
            # C-3 FIX: Only fall back to TOTP if user has explicitly enabled
            # MFA and has a configured TOTP secret. Enforce single-use by
            # consuming any pending DB OTP after TOTP success.
            user = db.get_user_for_mfa(user_id)
            if user and user.get("mfa_enabled") and user.get("mfa_secret"):
                try:
                    totp = pyotp.TOTP(user["mfa_secret"])
                    if totp.verify(data.otp, valid_window=0):
                        otp_valid = True
                        # Consume any pending DB OTP to prevent replay via
                        # the database path after TOTP verification succeeds
                        try:
                            db.consume_otp(user_id)
                        except Exception:
                            pass  # consume_otp is best-effort cleanup
                        # Track consumed TOTP codes in Redis to enforce
                        # single-use within the 30-second TOTP window
                        redis_client = get_redis()
                        if redis_client:
                            totp_key = f"totp_used:{user_id}:{data.otp}"
                            if redis_client.exists(totp_key):
                                otp_valid = False  # Already used in this window
                            else:
                                redis_client.setex(totp_key, 60, "1")
                except Exception as e:
                    logger.warning("TOTP verification error: %s", e)

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
            return make_error_response(
                "INVALID_OTP", "Invalid or expired OTP", status=401
            )

        db.update_session_assurance(data.session_id, "mfa")
        new_token = create_access_token(
            identity=str(user_id),
            additional_claims={"session_id": data.session_id, "aal": "mfa"},
            expires_delta=current_app.config.get(
                "JWT_ACCESS_TOKEN_EXPIRES", datetime.timedelta(minutes=15)
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
        resp_data = {"success": True, "data": {"access_token": new_token}}
        resp = make_response(jsonify(resp_data), 200)
        set_access_cookies(resp, new_token)
        return resp


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
    @limiter.limit("5 per minute")
    def post(self):
        """Verify MFA OTP code (alias route for frontend compatibility)."""
        # Delegate to the same logic as MFAVerify
        return MFAVerify().post()


@auth_ns.route("/password-verify")
class PasswordVerify(Resource):
    @auth_ns.expect(password_verify_model)
    @jwt_required()
    @limiter.limit("10 per minute")
    def post(self):
        """Verify password for step-up authentication without issuing a new session."""
        data = request.get_json() or {}
        password = data.get("password")

        user_id = int(get_jwt_identity())
        db = get_db()
        user = db.get_user_by_id(user_id)
        if not user:
            return make_error_response("USER_NOT_FOUND", "User not found", status=404)

        auth_user = db.authenticate_user(user["username"], password)
        if not auth_user:
            db.log_audit_evidence(
                action="step_up_failed",
                status="blocked",
                user_id=user_id,
                resource="/api/v1/auth/password-verify",
                metadata={"username": user["username"]},
                retention_tag="security",
            )
            return make_error_response(
                "INVALID_CREDENTIALS", "Invalid password", status=401
            )

        session_id = request.cookies.get("session_id") or get_jwt().get(
            "session_id", ""
        )

        behavioral_data = data.get("behavioral_data") or data.get("keystroke_data")
        if behavioral_data:
            events = (
                behavioral_data
                if isinstance(behavioral_data, list)
                else behavioral_data.get("keystroke_events", [])
            )
            if events:
                try:
                    from app.models.passive_enrollment import get_enrollment_manager

                    get_enrollment_manager().ingest_session_data(
                        user_id=user_id,
                        keystroke_features={"event_count": len(events)},
                        session_context={"source": "step_up"},
                        source="session",
                    )
                except Exception as exc:
                    logger.warning("Failed to ingest step-up behavioral data: %s", exc)

                db.store_behavioral_data(
                    user_id=user_id,
                    session_id=session_id,
                    data_type="keystroke",
                    features={"event_count": len(events), "source": "step_up"},
                    raw_data={"keystroke_events": events[:100]},
                    confidence_score=min(len(events) / 100.0, 1.0),
                    anomaly_score=None,
                )

        db.log_audit_evidence(
            action="step_up_success",
            status="ok",
            user_id=user_id,
            session_id=session_id,
            resource="/api/v1/auth/password-verify",
            retention_tag="security",
        )

        return {"data": {"success": True, "session_id": session_id}}, 200


@auth_ns.route("/verify-email-get")
class VerifyEmailGet(Resource):
    @limiter.limit("10 per minute")
    def get(self):
        """Consume an email verification token and mark the user's email as verified.

        Query params:
          - token (str): The raw verification token sent via email.
        """
        token = request.args.get("token", "").strip()
        if not token:
            return make_error_response(
                "VALIDATION_ERROR", "Missing verification token", status=400
            )

        db = get_db()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        # Check Redis fast-path first
        redis_client = get_redis()
        user_id = None
        if redis_client:
            cached = redis_client.get(f"email_verify:{token_hash}")
            if cached:
                user_id = int(cached)

        # Fallback: check audit_evidence for the token (stored at registration)
        if not user_id:
            try:
                with db.get_connection() as conn:
                    row = conn.execute(
                        """SELECT user_id FROM audit_evidence 
                           WHERE action = 'email_verification_issued'
                           AND rationale = ?
                           AND created_at > ?
                           LIMIT 1""",
                        (
                            token_hash,
                            (
                                datetime.datetime.now(datetime.timezone.utc)
                                - datetime.timedelta(hours=24)
                            ).isoformat(),
                        ),
                    ).fetchone()
                    if row:
                        user_id = row["user_id"]
            except Exception as e:
                logger.error("Email verification lookup failed: %s", e)

        if not user_id:
            return make_error_response(
                "TOKEN_INVALID", "Invalid or expired verification token", status=400
            )

        # Mark user email as verified
        try:
            db.set_email_verified(user_id)
        except Exception as e:
            logger.error("Failed to verify email: %s", e)
            return make_error_response(
                "INTERNAL_ERROR", "Verification failed", status=500
            )

        # Invalidate the token
        if redis_client:
            redis_client.delete(f"email_verify:{token_hash}")

        db.log_audit_evidence(
            action="email_verified",
            status="ok",
            user_id=user_id,
            resource="/api/v1/auth/verify-email",
            retention_tag="security",
        )

        logger.info("Email verified for user %d", user_id)
        return {
            "success": True,
            "message": "Email verified successfully. You can now log in.",
        }, 200


@auth_ns.route("/refresh")
class TokenRefresh(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def post(self):
        """Silently refresh the access token using the current valid JWT.

        The frontend calls this before the current token expires to
        maintain session continuity without forcing re-login. The session
        must still be active, and the user must exist.
        """
        user_id = int(get_jwt_identity())
        current_jwt = get_jwt()
        session_id = current_jwt.get("session_id", "")
        aal = current_jwt.get("aal", "pwd")

        db = get_db()
        user = db.get_user_by_id(user_id)
        if not user:
            return make_error_response("USER_NOT_FOUND", "User not found", status=404)

        # Verify session is still active
        if session_id:
            try:
                with db.get_connection() as conn:
                    session_row = conn.execute(
                        "SELECT session_id FROM sessions WHERE session_id = ? AND ended_at IS NULL",
                        (session_id,),
                    ).fetchone()
                    if not session_row:
                        return make_error_response(
                            "SESSION_EXPIRED", "Session has ended", status=401
                        )
            except Exception as e:
                logger.error("Token refresh session check failed: %s", e)
                return make_error_response(
                    "INTERNAL_ERROR", "Could not verify session", status=500
                )

        # Issue new token with same claims
        new_token = create_access_token(
            identity=str(user_id),
            additional_claims={"session_id": session_id, "aal": aal},
            expires_delta=current_app.config.get(
                "JWT_ACCESS_TOKEN_EXPIRES", datetime.timedelta(minutes=15)
            ),
        )

        # Blocklist old token
        redis_client = get_redis()
        if redis_client:
            try:
                jti = current_jwt.get("jti")
                exp = current_jwt.get("exp", 0)
                if jti:
                    remaining = max(int(exp - datetime.datetime.now().timestamp()), 1)
                    redis_client.setex(f"jwt_blocklist:{jti}", remaining, "1")
            except Exception:
                pass

        db.log_audit_evidence(
            action="token_refreshed",
            status="ok",
            user_id=user_id,
            session_id=session_id,
            resource="/api/v1/auth/refresh",
            retention_tag="security",
        )

        resp_data = {"data": {"access_token": new_token, "session_id": session_id}}
        resp = make_response(jsonify(resp_data), 200)
        set_access_cookies(resp, new_token)
        return resp
