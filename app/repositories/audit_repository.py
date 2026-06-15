"""
Audit Repository — Tamper-evident compliance logging.

Handles writing immutable audit evidence with SHA-256 hash chains,
querying audit trails, and verifying chain integrity.
RBI/DPDP Act compliant audit trail implementation.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.api.helpers import resolve_query

logger = logging.getLogger(__name__)


class AuditRepository:
    """Data-access layer for the `audit_evidence` table.
    
    Implements tamper-evident hash-chaining: each new entry includes
    the hash of the previous entry, creating a verifiable audit chain.
    """

    def __init__(self, db):
        self.db = db

    def log(
        self,
        action: str,
        status: str,
        user_id: int = 0,
        session_id: Optional[str] = None,
        resource: Optional[str] = None,
        metadata: Optional[Dict] = None,
        rationale: Optional[str] = None,
        retention_tag: str = "standard",
    ):
        """Write a tamper-evident audit evidence entry with hash chaining."""
        metadata_str = json.dumps(metadata) if metadata else None

        # Build hash chain
        prev_hash = self._get_last_hash()
        entry_data = f"{action}|{status}|{user_id}|{session_id}|{metadata_str}|{prev_hash}"
        entry_hash = hashlib.sha256(entry_data.encode("utf-8")).hexdigest()

        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """INSERT INTO audit_evidence
                       (user_id, session_id, action, resource, status,
                        rationale, metadata, retention_tag,
                        prev_hash, entry_hash, created_at)
                       VALUES (:param, :param, :param, :param, :param,
                               :param, :param, :param,
                               :param, :param, :param)""")
                conn.execute(query, (
                    user_id, session_id, action, resource, status,
                    rationale, metadata_str, retention_tag,
                    prev_hash, entry_hash,
                    datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
        except Exception:
            logger.exception("AuditRepository.log failed for action=%s", action)

    def get_by_user(
        self,
        user_id: int,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit evidence for a specific user, optionally filtered by action."""
        try:
            with self.db.get_connection() as conn:
                if action:
                    query = resolve_query(self.db,
                        """SELECT * FROM audit_evidence
                           WHERE user_id = :param AND action = :param
                           ORDER BY created_at DESC LIMIT :param""")
                    return conn.execute(query, (user_id, action, limit)).fetchall()
                else:
                    query = resolve_query(self.db,
                        """SELECT * FROM audit_evidence
                           WHERE user_id = :param
                           ORDER BY created_at DESC LIMIT :param""")
                    return conn.execute(query, (user_id, limit)).fetchall()
        except Exception:
            logger.exception("AuditRepository.get_by_user failed")
            return []

    def verify_chain(self, limit: int = 1000) -> Dict[str, Any]:
        """Verify tamper-evidence by replaying the hash chain.
        
        Returns integrity report with chain_valid, entries_checked,
        and any broken links.
        """
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """SELECT evidence_id, action, status, user_id, session_id,
                              metadata, prev_hash, entry_hash
                       FROM audit_evidence
                       ORDER BY evidence_id ASC LIMIT :param""")
                rows = conn.execute(query, (limit,)).fetchall()

            if not rows:
                return {"chain_valid": True, "entries_checked": 0, "broken_links": []}

            broken = []
            for i, row in enumerate(rows):
                expected_prev = rows[i - 1]["entry_hash"] if i > 0 else None
                if expected_prev and row.get("prev_hash") != expected_prev:
                    broken.append({
                        "evidence_id": row["evidence_id"],
                        "expected_prev_hash": expected_prev,
                        "actual_prev_hash": row.get("prev_hash"),
                    })

            return {
                "chain_valid": len(broken) == 0,
                "entries_checked": len(rows),
                "broken_links": broken,
            }
        except Exception:
            logger.exception("AuditRepository.verify_chain failed")
            return {"chain_valid": False, "entries_checked": 0, "error": "verification failed"}

    def _get_last_hash(self) -> Optional[str]:
        """Get the entry_hash of the most recent audit entry for chain linking."""
        try:
            with self.db.get_connection() as conn:
                query = resolve_query(self.db,
                    """SELECT entry_hash FROM audit_evidence
                       ORDER BY evidence_id DESC LIMIT 1""")
                row = conn.execute(query).fetchone()
                return row["entry_hash"] if row else None
        except Exception:
            return None
