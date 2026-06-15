"""
Behavioral Repository — Data-access layer for behavioral biometric data.

Handles CRUD for behavioral_data, session_snapshots, keystroke_events,
mouse_events, and session_risk_timeline tables.

Architecture:
    API Routes → Services → Repositories → Database (SQLAlchemy)
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BehavioralRepository:
    """Data-access layer for behavioral biometric tables.

    Accepts a ``db`` (DatabaseManager) instance via constructor injection
    so it can be unit-tested with a mock or in-memory DB.
    """

    def __init__(self, db):
        self.db = db

    # ── Behavioral data ──────────────────────────────────────────────────

    def store_behavioral_data(
        self,
        user_id: int,
        session_id: str,
        data_type: str,
        features: Dict,
        confidence_score: Optional[float] = None,
        anomaly_score: Optional[float] = None,
    ) -> None:
        """Store a behavioral data record (delegates encryption to DatabaseManager)."""
        self.db.store_behavioral_data(
            user_id=user_id,
            session_id=session_id,
            data_type=data_type,
            features=features,
            confidence_score=confidence_score,
            anomaly_score=anomaly_score,
        )

    def get_user_behavioral_data(
        self,
        user_id: int,
        data_type: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict]:
        """Retrieve behavioral data for a user with optional type filtering."""
        return self.db.get_user_behavioral_data(
            user_id=user_id,
            data_type=data_type,
            limit=limit,
        )

    def delete_user_behavioral_profile(self, user_id: int) -> Dict:
        """DPDP Right-to-Erasure: Delete all behavioral data for a user."""
        return self.db.delete_user_behavioral_profile(user_id)

    # ── Session snapshots ────────────────────────────────────────────────

    def store_session_snapshot(
        self,
        session_id: str,
        user_id: int,
        *,
        keystroke_count: int = 0,
        mouse_event_count: int = 0,
        scroll_event_count: int = 0,
        risk_score: Optional[float] = None,
        authenticity_score: Optional[float] = None,
        feature_richness: Optional[float] = None,
        ensemble_action: Optional[str] = None,
        ensemble_flags: Optional[str] = None,
        extended_features: Optional[Dict] = None,
    ) -> None:
        """Store a heartbeat-level session snapshot."""
        self.db.store_session_snapshot(
            session_id=session_id,
            user_id=user_id,
            keystroke_count=keystroke_count,
            mouse_event_count=mouse_event_count,
            scroll_event_count=scroll_event_count,
            risk_score=risk_score,
            authenticity_score=authenticity_score,
            feature_richness=feature_richness,
            ensemble_action=ensemble_action,
            ensemble_flags=ensemble_flags,
            extended_features=extended_features,
        )

    def get_session_snapshots(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[Dict]:
        """Retrieve snapshots for a session."""
        return self.db.get_session_snapshots(session_id=session_id, limit=limit)

    # ── Keystroke events ─────────────────────────────────────────────────

    def store_keystroke_events(
        self,
        session_id: str,
        user_id: int,
        events: List[Dict],
        context: str = "SESSION",
    ) -> int:
        """Batch-insert keystroke events. Returns count of rows inserted."""
        return self.db.store_keystroke_events(
            session_id=session_id,
            user_id=user_id,
            events=events,
            context=context,
        )

    def get_session_keystrokes(
        self,
        session_id: str,
        limit: int = 5000,
    ) -> List[Dict]:
        """Retrieve keystroke events for a session."""
        return self.db.get_session_keystrokes(session_id=session_id, limit=limit)

    def get_user_keystroke_stats(self, user_id: int) -> Dict:
        """Get aggregate keystroke statistics for a user."""
        return self.db.get_user_keystroke_stats(user_id)

    # ── Mouse events ─────────────────────────────────────────────────────

    def store_mouse_events(
        self,
        session_id: str,
        user_id: int,
        events: List[Dict],
        context: str = "SESSION",
    ) -> int:
        """Batch-insert mouse events. Returns count of rows inserted."""
        return self.db.store_mouse_events(
            session_id=session_id,
            user_id=user_id,
            events=events,
            context=context,
        )

    def get_session_mouse_events(
        self,
        session_id: str,
        limit: int = 5000,
    ) -> List[Dict]:
        """Retrieve mouse events for a session."""
        return self.db.get_session_mouse_events(session_id=session_id, limit=limit)

    # ── Risk timeline ────────────────────────────────────────────────────

    def append_risk_timeline(
        self,
        session_id: str,
        user_id: int,
        risk_score: float,
        *,
        risk_level: Optional[str] = None,
        trigger: Optional[str] = None,
        engine_scores: Optional[Dict] = None,
        action_taken: str = "allow",
    ) -> None:
        """Append an entry to the session risk timeline."""
        self.db.append_risk_timeline(
            session_id=session_id,
            user_id=user_id,
            risk_score=risk_score,
            risk_level=risk_level,
            trigger=trigger,
            engine_scores=engine_scores,
            action_taken=action_taken,
        )

    def get_risk_timeline(
        self,
        session_id: str,
        limit: int = 200,
    ) -> List[Dict]:
        """Retrieve the risk timeline for a session."""
        return self.db.get_risk_timeline(session_id=session_id, limit=limit)

    def get_user_risk_history(
        self,
        user_id: int,
        limit: int = 100,
    ) -> List[Dict]:
        """Retrieve the risk history across all sessions for a user."""
        return self.db.get_user_risk_history(user_id=user_id, limit=limit)
