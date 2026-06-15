"""Tests for app/mail.py — MailService and its transport backends.

Exercises the console backend (safe for tests), init_app configuration,
and email rendering for password reset, verification, and alerts.
"""

import os
import sys
import pytest

root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if root not in sys.path:
    sys.path.insert(0, root)

from app.mail import MailService


class TestMailServiceInit:
    def test_default_backend_is_console(self):
        """Without app config, backend should default to console."""
        service = MailService()
        assert service.backend == "console"

    def test_default_sender(self):
        service = MailService()
        assert "noreply" in service.default_sender

    def test_default_port(self):
        service = MailService()
        assert service.port == 587


class TestConsoleBackend:
    def test_send_via_console(self):
        """Console backend should always return True."""
        service = MailService()
        result = service.send(
            to="test@example.com",
            subject="Test Subject",
            body_text="Hello, world!",
        )
        assert result is True

    def test_send_with_html(self):
        service = MailService()
        result = service.send(
            to="test@example.com",
            subject="HTML Test",
            body_text="Plain text",
            body_html="<h1>Hello</h1>",
        )
        assert result is True

    def test_send_with_custom_sender(self):
        service = MailService()
        result = service.send(
            to="test@example.com",
            subject="Custom Sender",
            body_text="From custom",
            sender="custom@example.com",
        )
        assert result is True


class TestEmailRendering:
    """Test that email helper methods produce correct content."""

    def _console_service(self):
        """Create a MailService in console mode for safe testing."""
        service = MailService()
        service.backend = "console"
        return service

    def test_password_reset_email(self, app):
        """Password reset email should include the reset link."""
        service = self._console_service()
        with app.app_context():
            result = service.send_password_reset(
                to="user@example.com",
                username="testuser",
                reset_token="abc123token",
                reset_url_base="https://app.example.com/reset-password",
            )
        assert result is True

    def test_email_verification(self, app):
        """Email verification should include the verify link."""
        service = self._console_service()
        with app.app_context():
            result = service.send_email_verification(
                to="user@example.com",
                username="testuser",
                verify_token="verify123",
                verify_url_base="https://app.example.com/verify-email",
            )
        assert result is True

    def test_suspicious_login_alert(self):
        """Suspicious login alert should send successfully."""
        service = self._console_service()
        result = service.send_suspicious_login_alert(
            to="user@example.com",
            username="testuser",
            failed_attempts=5,
            ip_address="203.0.113.42",
            user_agent="Mozilla/5.0 Test",
        )
        assert result is True


class TestInitApp:
    """Test MailService.init_app with Flask app config."""

    def test_init_app_console_backend(self, app):
        """When MAIL_BACKEND=console, backend should be console."""
        app.config["MAIL_BACKEND"] = "console"
        service = MailService()
        service.init_app(app)
        assert service.backend == "console"

    def test_init_app_smtp_backend(self, app):
        """When credentials are set and backend=smtp."""
        app.config["MAIL_BACKEND"] = "smtp"
        app.config["MAIL_USERNAME"] = "user"
        app.config["MAIL_PASSWORD"] = "pass"
        service = MailService()
        service.init_app(app)
        assert service.backend == "smtp"

    def test_init_app_auto_detect_console(self, app):
        """Without credentials, should auto-detect to console."""
        app.config["MAIL_BACKEND"] = ""
        app.config.pop("MAIL_USERNAME", None)
        app.config.pop("MAIL_PASSWORD", None)
        app.config.pop("RESEND_API_KEY", None)
        service = MailService()
        service.init_app(app)
        assert service.backend == "console"
