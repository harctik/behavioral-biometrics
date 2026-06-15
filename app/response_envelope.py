"""Standardized API response envelope.

Every API response should follow this structure:
{
  "success": true/false,
  "data": { ... },         # Actual payload (on success)
  "error": { "code": "...", "message": "..." },  # Error info (on failure)
  "meta": {                # Always present
    "request_id": "...",
    "timestamp": "...",
    "version": "1.0.0"
  }
}
"""
import datetime
import os
from flask import g, jsonify, make_response
from typing import Any, Dict, Optional

APP_VERSION = os.environ.get("APP_VERSION", "2.0.0")


def success_response(data: Any = None, status: int = 200, meta: Optional[Dict] = None) -> tuple:
    """Build a standardized success response."""
    envelope = {
        "success": True,
        "data": data,
        "meta": {
            "request_id": getattr(g, "request_id", ""),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "version": APP_VERSION,
            **(meta or {}),
        },
    }
    return envelope, status


def error_response(
    code: str, message: str, status: int = 400, details: Any = None
) -> tuple:
    """Build a standardized error response."""
    envelope = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            **({"details": details} if details else {}),
        },
        "meta": {
            "request_id": getattr(g, "request_id", ""),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "version": APP_VERSION,
        },
    }
    return envelope, status


def paginated_response(
    items: list, total: int, page: int = 1, per_page: int = 20
) -> tuple:
    """Build a paginated list response."""
    return success_response(
        data=items,
        meta={
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": max(1, (total + per_page - 1) // per_page),
            }
        },
    )
