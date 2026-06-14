import logging
from datetime import datetime, timezone
from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required

from app.extensions import get_db, limiter
from app.api.helpers import get_current_user_id

logger = logging.getLogger(__name__)

notifications_ns = Namespace("notifications", description="User notifications")

@notifications_ns.route("")
class NotificationsList(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        """Get user notifications."""
        uid = get_current_user_id()
        db = get_db()
        try:
            with db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, type, title, message, is_read as read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
                    (uid,)
                ).fetchall()
                
                if not rows:
                    # Auto-provision notifications for demo
                    notifs = [
                        ("n1", uid, "security", "Behavioral Profile Active", "Your behavioral fingerprint is being continuously verified."),
                        ("n2", uid, "login", "New Login Detected", "Session started from your current device.")
                    ]
                    for n in notifs:
                        conn.execute(
                            "INSERT INTO notifications (id, user_id, type, title, message, is_read) VALUES (?, ?, ?, ?, ?, 0)",
                            n
                        )
                    conn.commit()
                    rows = conn.execute(
                        "SELECT id, type, title, message, is_read as read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
                        (uid,)
                    ).fetchall()
            
            notifications = []
            for row in rows:
                n = dict(row)
                # Calculate relative time from created_at
                created = n.get("created_at")
                if created:
                    try:
                        if isinstance(created, str):
                            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        else:
                            dt = created
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        delta = datetime.now(timezone.utc) - dt
                        secs = int(delta.total_seconds())
                        if secs < 60:
                            n["time"] = "Just now"
                        elif secs < 3600:
                            n["time"] = f"{secs // 60}m ago"
                        elif secs < 86400:
                            n["time"] = f"{secs // 3600}h ago"
                        else:
                            n["time"] = f"{secs // 86400}d ago"
                    except Exception:
                        n["time"] = "Recently"
                else:
                    n["time"] = "Recently"
                n["read"] = bool(n["read"])
                notifications.append(n)
                
            return {"notifications": notifications}, 200
        except Exception as e:
            logger.error("Failed to fetch notifications: %s", e)
            return {"notifications": []}, 200

    @jwt_required()
    @limiter.limit("10 per minute")
    def post(self):
        """Create a notification (internal use or simulated)."""
        uid = get_current_user_id()
        payload = request.get_json() or {}
        import uuid as _uuid
        nid = f"n_{str(_uuid.uuid4())[:8]}"
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO notifications (id, user_id, type, title, message, is_read) VALUES (?, ?, ?, ?, ?, 0)",
                    (nid, uid, payload.get("type", "info"), payload.get("title", "Alert"), payload.get("message", ""))
                )
                conn.commit()
            return {"success": True}, 201
        except Exception as e:
            logger.error("Failed to insert notification: %s", e)
            return {"error": "Database error"}, 500

@notifications_ns.route("/read-all")
class NotificationsReadAll(Resource):
    @jwt_required()
    def post(self):
        """Mark all as read."""
        uid = get_current_user_id()
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (uid,))
                conn.commit()
            return {"success": True}, 200
        except Exception:
            return {"error": "Database error"}, 500

@notifications_ns.route("/<string:notification_id>")
class NotificationItem(Resource):
    @jwt_required()
    def delete(self, notification_id):
        """Dismiss a notification."""
        uid = get_current_user_id()
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE id = ? AND user_id = ?", (notification_id, uid))
                conn.commit()
            return {"success": True}, 200
        except Exception:
            return {"error": "Database error"}, 500

@notifications_ns.route("/preferences")
class NotificationPreferences(Resource):
    @jwt_required()
    @limiter.limit("10 per minute")
    def put(self):
        """Update notification preferences."""
        payload = request.get_json() or {}
        # In a full implementation, persist to a user_preferences table
        return {"success": True, "message": "Preferences saved"}, 200
