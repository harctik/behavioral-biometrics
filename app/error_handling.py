"""
Error handling middleware and utilities for Behavior-Based Authentication API.

This module provides standardized error responses, exception classes, and middleware
for consistent error handling across the application.
"""

import traceback
import uuid
from typing import Optional, Dict, Any, Type
from datetime import datetime, timezone
from flask import request, jsonify, Response
from werkzeug.exceptions import HTTPException


# ============================================================================
# Custom Exception Classes
# ============================================================================


class ApiError(Exception):
    """Base class for all API errors."""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now(timezone.utc)
        self.error_id = str(uuid.uuid4())


class ValidationError(ApiError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field_errors: Optional[Dict[str, str]] = None,
        error_code: str = "VALIDATION_ERROR",
    ):
        details = {"field_errors": field_errors} if field_errors else {}
        super().__init__(message, error_code, 400, details)


class AuthenticationError(ApiError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: str = "AUTHENTICATION_ERROR",
    ):
        super().__init__(message, error_code, 401)


class AuthorizationError(ApiError):
    """Raised when authorization fails."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        error_code: str = "AUTHORIZATION_ERROR",
    ):
        super().__init__(message, error_code, 403)


class ResourceNotFoundError(ApiError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: Any,
        error_code: str = "RESOURCE_NOT_FOUND",
    ):
        message = f"{resource_type} with ID {resource_id} not found"
        details = {"resource_type": resource_type, "resource_id": str(resource_id)}
        super().__init__(message, error_code, 404, details)


class RateLimitError(ApiError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        limit: str,
        reset_time: Optional[datetime] = None,
        error_code: str = "RATE_LIMIT_EXCEEDED",
    ):
        message = f"Rate limit exceeded: {limit}"
        details = {"limit": limit}
        if reset_time:
            details["reset_time"] = reset_time.isoformat()
        super().__init__(message, error_code, 429, details)


class BusinessLogicError(ApiError):
    """Raised when business logic validation fails."""

    def __init__(
        self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, 422, details)


class ExternalServiceError(ApiError):
    """Raised when an external service call fails."""

    def __init__(
        self,
        service_name: str,
        operation: str,
        cause: Optional[Exception] = None,
        error_code: str = "EXTERNAL_SERVICE_ERROR",
    ):
        message = f"Error calling {service_name} service during {operation}"
        details = {"service_name": service_name, "operation": operation}
        super().__init__(message, error_code, 502, details, cause)


# ============================================================================
# Error Response Format
# ============================================================================


def create_error_response(
    error: ApiError, include_traceback: bool = False, request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary.

    Args:
        error: The ApiError instance
        include_traceback: Whether to include stack trace (for debugging)
        request_id: Optional request identifier for correlation

    Returns:
        Dictionary with standardized error format
    """
    response = {
        "error": {
            "id": error.error_id,
            "code": error.error_code,
            "message": error.message,
            "timestamp": error.timestamp.isoformat(),
            "status_code": error.status_code,
            "details": error.details,
        },
        "request_id": request_id or request.headers.get("X-Request-ID"),
    }

    if include_traceback and error.cause:
        response["error"]["traceback"] = traceback.format_exception(
            type(error.cause), error.cause, error.cause.__traceback__
        )

    return response


def make_error_response(
    error_code: str,
    message: str,
    status: int = 500,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Response:
    """
    Create a Flask Response with standardized error format.

    Args:
        error_code: Machine-readable error code
        message: Human-readable error message
        status: HTTP status code
        details: Additional error details
        request_id: Request identifier for correlation

    Returns:
        Flask Response object
    """
    error = ApiError(
        message=message,
        error_code=error_code,
        status_code=status,
        details=details or {},
    )
    response_data = create_error_response(error, request_id=request_id)
    return response_data, status


# ============================================================================
# Error Handling Middleware
# ============================================================================


class ErrorHandler:
    """Error handling middleware for Flask application."""

    def __init__(self, app=None, debug: bool = False):
        self.debug = debug
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize error handlers for the Flask app."""

        @app.errorhandler(ApiError)
        def handle_api_error(error: ApiError):
            """Handle custom API errors."""
            response_data = create_error_response(
                error,
                include_traceback=self.debug,
                request_id=request.headers.get("X-Request-ID"),
            )
            return jsonify(response_data), error.status_code

        @app.errorhandler(HTTPException)
        def handle_http_exception(error: HTTPException):
            """Handle Werkzeug HTTP exceptions."""
            api_error = ApiError(
                message=error.description or "HTTP error occurred",
                error_code=f"HTTP_{error.code}",
                status_code=error.code,
                details={"original_error": error.name},
            )
            response_data = create_error_response(
                api_error,
                include_traceback=self.debug,
                request_id=request.headers.get("X-Request-ID"),
            )
            return jsonify(response_data), error.code

        @app.errorhandler(Exception)
        def handle_generic_exception(error: Exception):
            """Handle all other uncaught exceptions."""
            logger = app.logger if hasattr(app, "logger") else None
            if logger:
                logger.error(f"Unhandled exception: {error}", exc_info=True)

            api_error = ApiError(
                message="Internal server error",
                error_code="INTERNAL_SERVER_ERROR",
                status_code=500,
                cause=error,
            )

            include_traceback = self.debug
            response_data = create_error_response(
                api_error,
                include_traceback=include_traceback,
                request_id=request.headers.get("X-Request-ID"),
            )

            # Don't expose internal details in production
            if not self.debug:
                response_data["error"]["message"] = "Internal server error"
                if "traceback" in response_data["error"]:
                    del response_data["error"]["traceback"]

            return jsonify(response_data), 500

        # Add request ID middleware
        @app.before_request
        def assign_request_id():
            """Assign a unique request ID to each request for correlation."""
            if not request.headers.get("X-Request-ID"):
                request.environ["X-Request-ID"] = str(uuid.uuid4())

        @app.after_request
        def add_request_id_header(response: Response):
            """Add request ID to response headers."""
            request_id = request.environ.get("X-Request-ID")
            if request_id:
                response.headers["X-Request-ID"] = request_id
            return response


# ============================================================================
# Validation Utilities
# ============================================================================


def validate_request_data(
    data: Dict[str, Any],
    required_fields: Optional[list] = None,
    field_validators: Optional[Dict[str, callable]] = None,
) -> None:
    """
    Validate request data and raise ValidationError if invalid.

    Args:
        data: Request data dictionary
        required_fields: List of required field names
        field_validators: Dictionary mapping field names to validation functions

    Raises:
        ValidationError: If validation fails
    """
    field_errors = {}

    # Check required fields
    if required_fields:
        for field in required_fields:
            if field not in data or data[field] is None:
                field_errors[field] = "This field is required"

    # Run field validators
    if field_validators:
        for field, validator_func in field_validators.items():
            if field in data and data[field] is not None:
                try:
                    validator_func(data[field])
                except ValueError as e:
                    field_errors[field] = str(e)

    if field_errors:
        raise ValidationError(
            message="Request validation failed", field_errors=field_errors
        )


def validate_email_format(email: str) -> None:
    """Validate email format."""
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValueError("Invalid email format")


def validate_password_strength(password: str) -> None:
    """Validate password strength."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")


# ============================================================================
# Context Manager for Error Handling
# ============================================================================


class ErrorContext:
    """
    Context manager for handling errors in a specific context.

    Example:
        with ErrorContext("user_registration", raise_on_error=True) as ctx:
            ctx.execute(register_user, user_data)
    """

    def __init__(
        self,
        operation: str,
        raise_on_error: bool = True,
        default_error_code: str = "OPERATION_ERROR",
    ):
        self.operation = operation
        self.raise_on_error = raise_on_error
        self.default_error_code = default_error_code
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if isinstance(exc_val, ApiError):
                self.error = exc_val
                return not self.raise_on_error
            else:
                self.error = ApiError(
                    message=f"Error during {self.operation}: {str(exc_val)}",
                    error_code=self.default_error_code,
                    status_code=500,
                    cause=exc_val,
                )
                return not self.raise_on_error
        return True

    def execute(self, func, *args, **kwargs):
        """Execute a function within the error context."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if self.raise_on_error:
                raise
            else:
                self.error = e
                return None
