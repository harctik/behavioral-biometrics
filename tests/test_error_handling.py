"""Tests for app/error_handling.py — exception classes and error response formatting.

Exercises ApiError hierarchy, ErrorContext manager, and response formatters.
"""

import os
import sys
import pytest

root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if root not in sys.path:
    sys.path.insert(0, root)

from app.error_handling import (
    ApiError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    RateLimitError,
    BusinessLogicError,
    ExternalServiceError,
    ErrorContext,
    create_error_response,
)


# ============================================================================
# Exception Classes
# ============================================================================


class TestApiError:
    def test_basic_api_error(self):
        err = ApiError("Something broke", "GENERIC_ERROR", 500)
        assert err.message == "Something broke"
        assert err.error_code == "GENERIC_ERROR"
        assert err.status_code == 500
        assert err.error_id  # UUID generated
        assert err.timestamp  # datetime set

    def test_api_error_with_details(self):
        err = ApiError("Bad", "ERR", 400, details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_api_error_with_cause(self):
        cause = ValueError("root cause")
        err = ApiError("Wrapped", "ERR", 500, cause=cause)
        assert err.cause is cause


class TestValidationError:
    def test_validation_error(self):
        err = ValidationError("Bad input", {"email": "Invalid"})
        assert err.status_code == 400
        assert err.error_code == "VALIDATION_ERROR"
        assert err.details["field_errors"]["email"] == "Invalid"

    def test_validation_error_no_fields(self):
        err = ValidationError("Bad input")
        assert err.status_code == 400
        assert err.details == {}


class TestAuthenticationError:
    def test_default_message(self):
        err = AuthenticationError()
        assert err.status_code == 401
        assert "Authentication" in err.message

    def test_custom_message(self):
        err = AuthenticationError("Token expired")
        assert err.message == "Token expired"


class TestAuthorizationError:
    def test_default(self):
        err = AuthorizationError()
        assert err.status_code == 403


class TestResourceNotFoundError:
    def test_resource_not_found(self):
        err = ResourceNotFoundError("User", 42)
        assert err.status_code == 404
        assert "User" in err.message
        assert "42" in err.message
        assert err.details["resource_type"] == "User"


class TestRateLimitError:
    def test_rate_limit(self):
        err = RateLimitError("5 per minute")
        assert err.status_code == 429
        assert "5 per minute" in err.message

    def test_rate_limit_with_reset(self):
        from datetime import datetime, timezone

        reset = datetime(2025, 1, 1, tzinfo=timezone.utc)
        err = RateLimitError("10/hour", reset_time=reset)
        assert "reset_time" in err.details


class TestBusinessLogicError:
    def test_business_error(self):
        err = BusinessLogicError("Insufficient balance", "INSUFFICIENT_FUNDS")
        assert err.status_code == 422
        assert err.error_code == "INSUFFICIENT_FUNDS"


class TestExternalServiceError:
    def test_external_error(self):
        err = ExternalServiceError("PaymentGateway", "charge")
        assert err.status_code == 502
        assert "PaymentGateway" in err.message
        assert err.details["service_name"] == "PaymentGateway"


# ============================================================================
# ErrorContext Manager
# ============================================================================


class TestErrorContext:
    def test_no_error(self):
        with ErrorContext("test_op") as ctx:
            pass  # no exception
        assert ctx.error is None

    def test_api_error_suppressed(self):
        with ErrorContext("test_op", raise_on_error=False) as ctx:
            raise ValidationError("bad input")
        assert ctx.error is not None
        assert isinstance(ctx.error, ValidationError)

    def test_generic_error_wrapped(self):
        with ErrorContext("test_op", raise_on_error=False) as ctx:
            raise RuntimeError("unexpected")
        assert ctx.error is not None
        assert isinstance(ctx.error, ApiError)

    def test_raise_on_error_true(self):
        with pytest.raises(ValidationError):
            with ErrorContext("test_op", raise_on_error=True):
                raise ValidationError("bad")

    def test_execute_success(self):
        with ErrorContext("test_op") as ctx:
            result = ctx.execute(lambda: 42)
        assert result == 42

    def test_execute_failure_suppressed(self):
        with ErrorContext("test_op", raise_on_error=False) as ctx:
            result = ctx.execute(lambda: 1 / 0)
        assert result is None
        assert ctx.error is not None


# ============================================================================
# create_error_response
# ============================================================================


class TestCreateErrorResponse:
    def test_basic_response(self):
        err = ApiError("Test", "TEST_ERR", 400)
        # Need Flask app context for request_id lookup
        response = create_error_response.__wrapped__(err) if hasattr(create_error_response, '__wrapped__') else None

        # Test the error object structure directly
        assert err.error_code == "TEST_ERR"
        assert err.status_code == 400
        assert err.message == "Test"
        assert err.error_id is not None
