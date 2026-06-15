"""
Enrollment Repository — Data-access layer for enrollment and profiling data.

Handles CRUD for enrollment_state, enrollment_history, digraph_profiles,
and device_fingerprints tables.

Architecture:
    API Routes → Services → Repositories → Database (SQLAlchemy)
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EnrollmentRepository:
    """Data-access layer for enrollment, digraph, and device fingerprint tables.

    Accepts a ``db`` (DatabaseManager) instance via constructor injection
    so it can be unit-tested with a mock or in-memory DB.
    """

    def __init__(self, db):
        self.db = db

    # ── Enrollment state ─────────────────────────────────────────────────

    def save_enrollment_state(self, user_id: int, state: Dict) -> None:
        """Persist durable enrollment state (upsert)."""
        self.db.save_enrollment_state(user_id, state)

    def load_enrollment_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Load enrollment state for a user."""
        return self.db.load_enrollment_state(user_id)

    # ── Enrollment history ───────────────────────────────────────────────

    def save_enrollment_event(
        self,
        user_id: int,
        session_id: Optional[str],
        phase: str,
        *,
        sessions_completed: int = 0,
        feature_count: int = 0,
        match_score: Optional[float] = None,
        action: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """Log an enrollment progression event."""
        self.db.save_enrollment_event(
            user_id=user_id,
            session_id=session_id,
            phase=phase,
            sessions_completed=sessions_completed,
            feature_count=feature_count,
            match_score=match_score,
            action=action,
            message=message,
        )

    def get_enrollment_history(
        self,
        user_id: int,
        limit: int = 50,
    ) -> List[Dict]:
        """Retrieve enrollment history for a user."""
        return self.db.get_enrollment_history(user_id=user_id, limit=limit)

    # ── Digraph profiles ─────────────────────────────────────────────────

    def save_digraph_profile(
        self,
        user_id: int,
        profile_data: Dict,
    ) -> None:
        """Persist or update the Bayesian digraph profile for a user.

        The ``profile_data`` dict should contain ``updates_count``,
        ``confidence``, ``per_key_hold``, and ``per_digraph_flight`` keys —
        DatabaseManager extracts metadata from these internally.
        """
        self.db.save_digraph_profile(
            user_id=user_id,
            profile_data=profile_data,
        )

    def load_digraph_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Load the digraph profile for a user."""
        return self.db.load_digraph_profile(user_id)

    # ── Device fingerprints ──────────────────────────────────────────────

    def register_device(
        self,
        user_id: int,
        device_hash: str,
        *,
        user_agent: Optional[str] = None,
        screen_resolution: Optional[str] = None,
        canvas_hash: Optional[str] = None,
        webgl_renderer: Optional[str] = None,
        timezone: Optional[str] = None,
        language: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> Dict:
        """Register or update a device fingerprint. Returns device info."""
        return self.db.register_device(
            user_id=user_id,
            device_hash=device_hash,
            user_agent=user_agent,
            screen_resolution=screen_resolution,
            canvas_hash=canvas_hash,
            webgl_renderer=webgl_renderer,
            timezone=timezone,
            language=language,
            platform=platform,
        )

    def get_user_devices(self, user_id: int) -> List[Dict]:
        """Get all known devices for a user."""
        return self.db.get_user_devices(user_id)

    def is_known_device(self, user_id: int, device_hash: str) -> bool:
        """Check if a device fingerprint is recognized for a user."""
        return self.db.is_known_device(user_id, device_hash)
