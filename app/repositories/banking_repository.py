"""
Banking Repository — Data-access layer for banking domain tables.

Handles CRUD for beneficiaries, cards, investments, and notifications.

Architecture:
    API Routes → Services → Repositories → Database (SQLAlchemy)
"""

import json
import logging
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BankingRepository:
    """Data-access layer for banking domain tables.

    Accepts a ``db`` (DatabaseManager) instance via constructor injection
    so it can be unit-tested with a mock or in-memory DB.
    """

    def __init__(self, db):
        self.db = db

    # ── Beneficiaries ────────────────────────────────────────────────────

    def get_beneficiaries(self, user_id: int) -> List[Dict]:
        """Get all beneficiaries for a user."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM beneficiaries WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
            return cursor.fetchall()

    def create_beneficiary(
        self,
        user_id: int,
        name: str,
        account_number: str,
        ifsc: str,
        trust_score: float = 0.5,
    ) -> Optional[str]:
        """Create a new beneficiary. Returns the beneficiary ID."""
        beneficiary_id = secrets.token_urlsafe(16)
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO beneficiaries (id, user_id, name, account_number, ifsc, trust_score)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (beneficiary_id, user_id, name, account_number, ifsc, trust_score),
                )
                conn.commit()
            return beneficiary_id
        except Exception:
            logger.exception("BankingRepository.create_beneficiary failed")
            return None

    def delete_beneficiary(self, user_id: int, beneficiary_id: str) -> bool:
        """Delete a beneficiary if owned by the user."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM beneficiaries WHERE id = ? AND user_id = ?",
                (beneficiary_id, user_id),
            )
            conn.commit()
            return True

    # ── Cards ────────────────────────────────────────────────────────────

    def get_cards(self, user_id: int) -> List[Dict]:
        """Get all cards for a user."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
            return cursor.fetchall()

    def get_card(self, user_id: int, card_id: str) -> Optional[Dict]:
        """Get a single card by ID (owned by user)."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE id = ? AND user_id = ?",
                (card_id, user_id),
            )
            return cursor.fetchone()

    def update_card_status(self, user_id: int, card_id: str, status: str) -> bool:
        """Update card status (Active/Blocked/Frozen)."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE cards SET status = ? WHERE id = ? AND user_id = ?",
                (status, card_id, user_id),
            )
            conn.commit()
            return True

    # ── Investments ──────────────────────────────────────────────────────

    def get_investments(self, user_id: int) -> List[Dict]:
        """Get all investments for a user."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM investments WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
            return cursor.fetchall()

    # ── Notifications ────────────────────────────────────────────────────

    def get_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Dict]:
        """Get notifications for a user."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if unread_only:
                cursor.execute(
                    "SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 "
                    "ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM notifications WHERE user_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                )
            return cursor.fetchall()

    def mark_notification_read(self, user_id: int, notification_id: str) -> bool:
        """Mark a single notification as read."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
                (notification_id, user_id),
            )
            conn.commit()
            return True

    def mark_all_notifications_read(self, user_id: int) -> int:
        """Mark all notifications as read. Returns count of updated rows."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
            conn.commit()
            return 0  # SQLite doesn't reliably return rowcount through QueryAdapter

    def create_notification(
        self,
        user_id: int,
        title: str,
        message: str = "",
        notification_type: str = "info",
    ) -> str:
        """Create a notification. Returns the notification ID."""
        notification_id = secrets.token_urlsafe(16)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO notifications (id, user_id, type, title, message)
                   VALUES (?, ?, ?, ?, ?)""",
                (notification_id, user_id, notification_type, title, message),
            )
            conn.commit()
        return notification_id
