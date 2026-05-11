"""
OpenAPI/Swagger documentation models and utilities for Behavior-Based Authentication API.

This module provides Pydantic models and Flask-RESTX models for comprehensive API documentation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, validator
from flask_restx import fields, Model


# ============================================================================
# Pydantic Models for Request/Response Validation
# ============================================================================


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    username: str = Field(
        ..., min_length=3, max_length=50, description="Unique username"
    )
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    phone: Optional[str] = Field(
        None, pattern=r"^\+?[1-9]\d{1,14}$", description="Phone number in E.164 format"
    )

    @validator("password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """Request model for user login."""

    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")
    device_fingerprint: Optional[str] = Field(
        None, description="Device fingerprint for behavioral analysis"
    )
    location_data: Optional[Dict[str, Any]] = Field(
        None, description="Optional location data"
    )


class MFAAuthRequest(BaseModel):
    """Request model for MFA verification."""

    user_id: int = Field(..., description="User ID")
    totp_code: str = Field(..., min_length=6, max_length=6, description="TOTP code")
    session_id: Optional[str] = Field(
        None, description="Session ID for continuous authentication"
    )


class BehavioralDataRequest(BaseModel):
    """Request model for submitting behavioral data."""

    session_id: str = Field(..., description="Session identifier")
    event_type: str = Field(
        ..., description="Type of behavioral event (keystroke, mouse, touch)"
    )
    event_data: Dict[str, Any] = Field(..., description="Event-specific data")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Event timestamp"
    )
    confidence_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence score for the data"
    )


class TransactionAssessmentRequest(BaseModel):
    """Request model for transaction risk assessment."""

    transaction_id: str = Field(..., description="Unique transaction identifier")
    amount: float = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(
        ..., min_length=3, max_length=3, description="Currency code (ISO 4217)"
    )
    recipient: str = Field(..., description="Recipient identifier")
    transaction_type: str = Field(
        ..., description="Type of transaction (transfer, payment, withdrawal)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional transaction metadata"
    )


class PasswordResetRequest(BaseModel):
    """Request model for password reset."""

    email: EmailStr = Field(..., description="User email address")
    reset_token: Optional[str] = Field(
        None, description="Reset token (for confirmation)"
    )


# ============================================================================
# Response Models
# ============================================================================


class ApiResponse(BaseModel):
    """Standard API response model."""

    success: bool = Field(..., description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Human-readable message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error_code: Optional[str] = Field(None, description="Error code if request failed")
    request_id: Optional[str] = Field(
        None, description="Request identifier for tracing"
    )


class AuthResponse(BaseModel):
    """Authentication response model."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(
        None, description="Refresh token for obtaining new access tokens"
    )
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user_id: int = Field(..., description="Authenticated user ID")
    requires_mfa: bool = Field(False, description="Whether MFA is required")
    session_id: Optional[str] = Field(
        None, description="Session identifier for behavioral tracking"
    )


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response model."""

    risk_score: float = Field(
        ..., ge=0.0, le=1.0, description="Risk score (0=low, 1=high)"
    )
    risk_level: str = Field(..., description="Risk level (low, medium, high, critical)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the assessment"
    )
    factors: List[Dict[str, Any]] = Field(
        ..., description="Factors contributing to the risk assessment"
    )
    recommendations: List[str] = Field(..., description="Recommended actions")
    requires_step_up: bool = Field(
        ..., description="Whether step-up authentication is required"
    )


class SessionMetricsResponse(BaseModel):
    """Session metrics response model."""

    session_id: str = Field(..., description="Session identifier")
    user_id: int = Field(..., description="User ID")
    start_time: datetime = Field(..., description="Session start time")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    trust_score: float = Field(..., ge=0.0, le=1.0, description="Current trust score")
    behavioral_samples: int = Field(
        ..., ge=0, description="Number of behavioral samples collected"
    )
    risk_events: int = Field(..., ge=0, description="Number of risk events detected")
    assurance_level: str = Field(
        ..., description="Current assurance level (pwd, mfa, biometric)"
    )


# ============================================================================
# Flask-RESTX Models for Swagger Documentation
# ============================================================================


def create_flask_restx_models(api):
    """Create Flask-RESTX models for Swagger documentation."""

    # Error response model
    error_model = api.model(
        "ErrorResponse",
        {
            "error_code": fields.String(required=True, description="Error code"),
            "message": fields.String(required=True, description="Error message"),
            "details": fields.Raw(description="Additional error details"),
            "request_id": fields.String(description="Request identifier"),
        },
    )

    # Register request model
    register_model = api.model(
        "RegisterRequest",
        {
            "username": fields.String(
                required=True,
                min_length=3,
                max_length=50,
                description="Unique username",
            ),
            "email": fields.String(required=True, description="Email address"),
            "password": fields.String(
                required=True, min_length=8, description="Password"
            ),
            "first_name": fields.String(description="First name"),
            "last_name": fields.String(description="Last name"),
            "phone": fields.String(description="Phone number"),
        },
    )

    # Login request model
    login_model = api.model(
        "LoginRequest",
        {
            "username": fields.String(required=True, description="Username or email"),
            "password": fields.String(required=True, description="Password"),
            "device_fingerprint": fields.String(description="Device fingerprint"),
            "location_data": fields.Raw(description="Location data"),
        },
    )

    # Auth response model
    auth_response_model = api.model(
        "AuthResponse",
        {
            "access_token": fields.String(
                required=True, description="JWT access token"
            ),
            "refresh_token": fields.String(description="Refresh token"),
            "token_type": fields.String(default="bearer", description="Token type"),
            "expires_in": fields.Integer(
                required=True, description="Token expiration in seconds"
            ),
            "user_id": fields.Integer(required=True, description="User ID"),
            "requires_mfa": fields.Boolean(
                default=False, description="MFA required flag"
            ),
            "session_id": fields.String(description="Session ID"),
        },
    )

    # MFA request model
    mfa_model = api.model(
        "MFAAuthRequest",
        {
            "user_id": fields.Integer(required=True, description="User ID"),
            "totp_code": fields.String(
                required=True, min_length=6, max_length=6, description="TOTP code"
            ),
            "session_id": fields.String(description="Session ID"),
        },
    )

    # Behavioral data model
    behavioral_model = api.model(
        "BehavioralDataRequest",
        {
            "session_id": fields.String(required=True, description="Session ID"),
            "event_type": fields.String(required=True, description="Event type"),
            "event_data": fields.Raw(required=True, description="Event data"),
            "timestamp": fields.DateTime(description="Event timestamp"),
            "confidence_score": fields.Float(description="Confidence score"),
        },
    )

    # Risk assessment model
    risk_assessment_model = api.model(
        "RiskAssessmentResponse",
        {
            "risk_score": fields.Float(required=True, description="Risk score (0-1)"),
            "risk_level": fields.String(required=True, description="Risk level"),
            "confidence": fields.Float(required=True, description="Confidence score"),
            "factors": fields.List(
                fields.Raw, required=True, description="Risk factors"
            ),
            "recommendations": fields.List(
                fields.String, required=True, description="Recommendations"
            ),
            "requires_step_up": fields.Boolean(
                required=True, description="Step-up required"
            ),
        },
    )

    # Session metrics model
    session_metrics_model = api.model(
        "SessionMetricsResponse",
        {
            "session_id": fields.String(required=True, description="Session ID"),
            "user_id": fields.Integer(required=True, description="User ID"),
            "start_time": fields.DateTime(required=True, description="Start time"),
            "last_activity": fields.DateTime(
                required=True, description="Last activity"
            ),
            "trust_score": fields.Float(required=True, description="Trust score"),
            "behavioral_samples": fields.Integer(
                required=True, description="Behavioral samples count"
            ),
            "risk_events": fields.Integer(
                required=True, description="Risk events count"
            ),
            "assurance_level": fields.String(
                required=True, description="Assurance level"
            ),
        },
    )

    return {
        "error_model": error_model,
        "register_model": register_model,
        "login_model": login_model,
        "auth_response_model": auth_response_model,
        "mfa_model": mfa_model,
        "behavioral_model": behavioral_model,
        "risk_assessment_model": risk_assessment_model,
        "session_metrics_model": session_metrics_model,
    }


# ============================================================================
# API Documentation Utilities
# ============================================================================


def generate_openapi_spec(app):
    """Generate OpenAPI specification for the Flask application."""
    # This would typically use apispec or similar library
    # For now, return a basic structure
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Behavior-Based Authentication API",
            "description": "API for continuous authentication and behavioral biometrics",
            "version": "1.0.0",
            "contact": {"name": "API Support", "email": "support@example.com"},
        },
        "servers": [
            {"url": "http://localhost:5000", "description": "Development server"},
            {"url": "https://api.example.com", "description": "Production server"},
        ],
        "tags": [
            {"name": "authentication", "description": "User authentication endpoints"},
            {"name": "sessions", "description": "Session management and monitoring"},
            {
                "name": "behavioral",
                "description": "Behavioral data collection and analysis",
            },
            {
                "name": "transactions",
                "description": "Transaction security and risk assessment",
            },
            {"name": "admin", "description": "Administrative operations"},
            {"name": "compliance", "description": "Compliance and privacy operations"},
        ],
    }


def setup_api_documentation(api):
    """Set up comprehensive API documentation with examples."""

    models = create_flask_restx_models(api)

    # Add global error responses
    @api.errorhandler(400)
    @api.errorhandler(401)
    @api.errorhandler(403)
    @api.errorhandler(404)
    @api.errorhandler(429)
    @api.errorhandler(500)
    def handle_http_errors(error):
        """Global HTTP error handler."""
        return {
            "error_code": f"HTTP_{error.code}",
            "message": error.description,
            "request_id": request.headers.get("X-Request-ID"),
        }, error.code

    # Add API documentation decorators
    def api_doc(summary=None, description=None, responses=None, tags=None):
        """Decorator to add OpenAPI documentation to endpoints."""

        def decorator(f):
            f.__doc__ = f"{summary or ''}\n\n{description or ''}"
            return f

        return decorator

    return models, api_doc
