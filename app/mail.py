"""Transactional email service for the Behavior-Based Authentication system.

Supports SMTP (default) and Amazon SES transports, with a console fallback
for development/testing environments where no mail server is configured.

Configuration (via environment / Settings):
    MAIL_SERVER          SMTP host (default: localhost)
    MAIL_PORT            SMTP port (default: 587)
    MAIL_USE_TLS         Enable STARTTLS (default: true)
    MAIL_USERNAME        SMTP auth username (optional)
    MAIL_PASSWORD        SMTP auth password (optional)
    MAIL_DEFAULT_SENDER  From address (default: noreply@behaviorauth.local)
    MAIL_BACKEND         'smtp' | 'ses' | 'console' (default: auto-detect)
    AWS_REGION           SES region (only when MAIL_BACKEND=ses)
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class MailService:
    """Lightweight transactional email abstraction."""

    def __init__(self, app=None):
        self.server: str = "localhost"
        self.port: int = 587
        self.use_tls: bool = True
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.default_sender: str = "noreply@behaviorauth.local"
        self.backend: str = "console"  # safe default
        self.aws_region: str = "us-east-1"
        self.resend_api_key: Optional[str] = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Configure from Flask app config."""
        self.server = app.config.get("MAIL_SERVER", self.server)
        self.port = int(app.config.get("MAIL_PORT", self.port))
        self.use_tls = app.config.get("MAIL_USE_TLS", self.use_tls)
        self.username = app.config.get("MAIL_USERNAME") or None
        self.password = app.config.get("MAIL_PASSWORD") or None
        self.default_sender = app.config.get("MAIL_DEFAULT_SENDER", self.default_sender)
        self.aws_region = app.config.get("AWS_REGION", self.aws_region)
        self.resend_api_key = app.config.get("RESEND_API_KEY") or None

        # Auto-detect backend
        explicit = app.config.get("MAIL_BACKEND", "").lower()
        if explicit in ("smtp", "ses", "console", "resend"):
            self.backend = explicit
        elif self.resend_api_key:
            self.backend = "resend"
        elif self.username and self.password:
            self.backend = "smtp"
        else:
            self.backend = "console"
            if not app.debug:
                logger.warning(
                    "No MAIL_USERNAME/MAIL_PASSWORD set — email delivery "
                    "falling back to console logger. Password reset tokens "
                    "will NOT be delivered to users."
                )

        if self.backend == "resend" and self.resend_api_key:
            logger.info("Mail backend: Resend (API key configured)")

        app.extensions["mail_service"] = self

    # ── Public API ──────────────────────────────────────────────────────────

    def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        sender: Optional[str] = None,
    ) -> bool:
        """Send a transactional email.

        Returns ``True`` on success, ``False`` on failure (logged, never raises).
        """
        sender = sender or self.default_sender
        if self.backend == "resend":
            return self._send_resend(to, subject, body_text, body_html, sender)
        if self.backend == "ses":
            return self._send_ses(to, subject, body_text, body_html, sender)
        if self.backend == "smtp":
            return self._send_smtp(to, subject, body_text, body_html, sender)
        return self._send_console(to, subject, body_text, sender)

    def send_password_reset(
        self,
        to: str,
        username: str,
        reset_token: str,
        reset_url_base: str = "",
    ) -> bool:
        """Send a password-reset email with the one-time token.

        Args:
            to:             Recipient email address.
            username:       Display name for the greeting.
            reset_token:    Raw reset token (will be embedded in the link).
            reset_url_base: Base URL for the reset page (e.g.
                            ``https://app.example.com/reset-password``).
        """
        if not reset_url_base:
            # Derive from Flask app config → RESET_URL_BASE → FRONTEND_URL
            from flask import current_app
            reset_url_base = current_app.config.get("RESET_URL_BASE", "") or \
                (current_app.config.get("FRONTEND_URL", "").rstrip("/") + "/reset-password" if current_app.config.get("FRONTEND_URL") else "")
            if not reset_url_base:
                reset_url_base = "http://localhost:3000/reset-password"
                logger.warning("RESET_URL_BASE and FRONTEND_URL not set — using localhost fallback for password reset link")

        reset_link = f"{reset_url_base}?token={reset_token}"

        subject = "Password Reset — BehaviorAuth"
        body_text = (
            f"Hello {username},\n\n"
            f"A password reset was requested for your account.\n\n"
            f"Use this link to set a new password (expires in 15 minutes):\n"
            f"{reset_link}\n\n"
            f"If you did not request this, you can safely ignore this email.\n\n"
            f"— BehaviorAuth Security Team"
        )
        body_html = (
            f"<h2>Password Reset</h2>"
            f"<p>Hello <strong>{username}</strong>,</p>"
            f"<p>A password reset was requested for your account.</p>"
            f'<p><a href="{reset_link}" '
            f'style="padding:12px 24px;background:#2563eb;color:#fff;'
            f'border-radius:6px;text-decoration:none;display:inline-block">'
            f"Reset Password</a></p>"
            f"<p><small>This link expires in 15 minutes.</small></p>"
            f"<p>If you did not request this, ignore this email.</p>"
            f"<hr><p style='color:#888;font-size:12px'>"
            f"BehaviorAuth Security Team</p>"
        )
        return self.send(to, subject, body_text, body_html)

    def send_email_verification(
        self,
        to: str,
        username: str,
        verify_token: str,
        verify_url_base: str = "",
    ) -> bool:
        """Send an email verification link.

        Args:
            to:             Recipient email address.
            username:       Display name for the greeting.
            verify_token:   Raw verification token.
            verify_url_base: Base URL for the verify page.
        """
        if not verify_url_base:
            # Derive from Flask app config → VERIFY_URL_BASE → FRONTEND_URL
            from flask import current_app
            verify_url_base = current_app.config.get("VERIFY_URL_BASE", "") or \
                (current_app.config.get("FRONTEND_URL", "").rstrip("/") + "/verify-email" if current_app.config.get("FRONTEND_URL") else "")
            if not verify_url_base:
                verify_url_base = "http://localhost:3000/verify-email"
                logger.warning("VERIFY_URL_BASE and FRONTEND_URL not set — using localhost fallback for email verification link")

        verify_link = f"{verify_url_base}?token={verify_token}"

        subject = "Verify Your Email — BehaviorAuth"
        body_text = (
            f"Hello {username},\n\n"
            f"Welcome to BehaviorAuth! Please verify your email address.\n\n"
            f"Use this link to verify your email:\n"
            f"{verify_link}\n\n"
            f"If you did not register, please ignore this email.\n\n"
            f"— BehaviorAuth Security Team"
        )
        body_html = (
            f"<h2>Verify Your Email</h2>"
            f"<p>Hello <strong>{username}</strong>,</p>"
            f"<p>Welcome to BehaviorAuth! Please verify your email address.</p>"
            f'<p><a href="{verify_link}" '
            f'style="padding:12px 24px;background:#2563eb;color:#fff;'
            f'border-radius:6px;text-decoration:none;display:inline-block">'
            f"Verify Email</a></p>"
            f"<p>If you did not register, ignore this email.</p>"
            f"<hr><p style='color:#888;font-size:12px'>"
            f"BehaviorAuth Security Team</p>"
        )
        return self.send(to, subject, body_text, body_html)

    def send_suspicious_login_alert(
        self,
        to: str,
        username: str,
        failed_attempts: int,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> bool:
        """Send a suspicious-login-activity alert to the account owner.

        Triggered after repeated failed login attempts against a username,
        warning the real user that someone may be trying to access their account.

        Args:
            to:              Recipient email address.
            username:        Account username being targeted.
            failed_attempts: Total consecutive failed attempts so far.
            ip_address:      Source IP of the failed attempt(s).
            user_agent:      Browser / client User-Agent string.
        """
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        subject = "⚠️ Suspicious Login Activity — BehaviorAuth"
        body_text = (
            f"Hello {username},\n\n"
            f"We detected {failed_attempts} failed login attempt(s) on your account.\n\n"
            f"Details:\n"
            f"  • Time:       {timestamp}\n"
            f"  • IP Address: {ip_address}\n"
            f"  • Device:     {user_agent[:80]}\n\n"
            f"If this was you, you can ignore this message.\n"
            f"If you did NOT attempt to log in, we strongly recommend:\n"
            f"  1. Change your password immediately.\n"
            f"  2. Enable Multi-Factor Authentication (MFA).\n"
            f"  3. Review your recent account activity.\n\n"
            f"— BehaviorAuth Security Team"
        )
        body_html = (
            f"<div style='font-family:Inter,system-ui,sans-serif;max-width:560px;"
            f"margin:0 auto;padding:24px'>"
            f"<div style='background:#1a1a2e;border-radius:12px;padding:24px;"
            f"border:1px solid rgba(255,255,255,0.06)'>"
            f"<h2 style='color:#f87171;margin:0 0 16px'>⚠️ Suspicious Login Activity</h2>"
            f"<p style='color:#e2e8f0'>Hello <strong>{username}</strong>,</p>"
            f"<p style='color:#e2e8f0'>We detected <strong style='color:#f87171'>"
            f"{failed_attempts} failed login attempt(s)</strong> on your account.</p>"
            f"<div style='background:rgba(248,113,113,0.08);border:1px solid "
            f"rgba(248,113,113,0.2);border-radius:8px;padding:16px;margin:16px 0'>"
            f"<table style='width:100%;color:#cbd5e1;font-size:14px'>"
            f"<tr><td style='padding:4px 8px;color:#94a3b8'>Time</td>"
            f"<td style='padding:4px 8px'>{timestamp}</td></tr>"
            f"<tr><td style='padding:4px 8px;color:#94a3b8'>IP Address</td>"
            f"<td style='padding:4px 8px;font-family:monospace'>{ip_address}</td></tr>"
            f"<tr><td style='padding:4px 8px;color:#94a3b8'>Device</td>"
            f"<td style='padding:4px 8px;font-size:12px'>{user_agent[:80]}</td></tr>"
            f"</table></div>"
            f"<p style='color:#e2e8f0'>If this was <strong>not you</strong>, "
            f"we strongly recommend:</p>"
            f"<ol style='color:#cbd5e1;padding-left:20px'>"
            f"<li>Change your password immediately</li>"
            f"<li>Enable Multi-Factor Authentication (MFA)</li>"
            f"<li>Review your recent account activity</li></ol>"
            f"<p style='color:#64748b;font-size:12px;margin-top:20px'>"
            f"If this was you, you can safely ignore this email.</p>"
            f"</div></div>"
        )
        return self.send(to, subject, body_text, body_html)

    # ── Transport backends ──────────────────────────────────────────────────

    def _send_smtp(
        self, to: str, subject: str, text: str, html: Optional[str], sender: str
    ) -> bool:
        """Deliver via SMTP/STARTTLS."""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = sender
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(text, "plain", "utf-8"))
            if html:
                msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP(self.server, self.port, timeout=10) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.sendmail(sender, [to], msg.as_string())

            logger.info("Email sent via SMTP to %s (subject=%s)", to, subject)
            return True
        except Exception:
            logger.exception("SMTP delivery failed to %s", to)
            return False

    def _send_ses(
        self, to: str, subject: str, text: str, html: Optional[str], sender: str
    ) -> bool:
        """Deliver via Amazon SES (boto3)."""
        try:
            import boto3  # type: ignore

            client = boto3.client("ses", region_name=self.aws_region)
            body: dict = {"Text": {"Charset": "UTF-8", "Data": text}}
            if html:
                body["Html"] = {"Charset": "UTF-8", "Data": html}

            client.send_email(
                Source=sender,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Charset": "UTF-8", "Data": subject},
                    "Body": body,
                },
            )
            logger.info("Email sent via SES to %s (subject=%s)", to, subject)
            return True
        except Exception:
            logger.exception("SES delivery failed to %s", to)
            return False

    def _send_resend(
        self, to: str, subject: str, text: str, html: Optional[str], sender: str
    ) -> bool:
        """Deliver via Resend API."""
        try:
            import resend

            logger.info("Resend API Key prefix configured as: %s", str(self.resend_api_key)[:7] if self.resend_api_key else "None")
            resend.api_key = self.resend_api_key
            params: dict = {
                "from": sender,
                "to": [to],
                "subject": subject,
                "text": text,
            }
            if html:
                params["html"] = html

            response = resend.Emails.send(params)
            logger.info(
                "Email sent via Resend to %s (subject=%s, id=%s)",
                to, subject, response.get("id", "unknown"),
            )
            return True
        except Exception:
            logger.exception("Resend delivery failed to %s", to)
            return False

    def _send_console(self, to: str, subject: str, text: str, sender: str) -> bool:
        """Log email to console (development/testing fallback)."""
        logger.info(
            "[CONSOLE MAIL] From=%s To=%s Subject=%s\n%s",
            sender,
            to,
            subject,
            text,
        )
        return True
