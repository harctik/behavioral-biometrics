"""Session management API blueprint."""
from flask import request, Response, stream_with_context, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
import json
import time
import csv
import io
import logging

from app.extensions import get_db, limiter
from app.api.helpers import (
    get_session_cached,
    validate_session_context,
    get_current_user_id,
    validate_session_ownership,
)
from app.extended_risk_scorer import score_extended_features
from app.models.cognitive_engine import run_cognitive_analysis
from app.ml_ensemble import score_with_ensemble

logger = logging.getLogger(__name__)

session_ns = Namespace(
    "session", description="Session management and behavioral monitoring"
)

# ── Swagger models ───────────────────────────────────────────────────────────

session_status_model = session_ns.model(
    "SessionStatus",
    {
        "session_active": fields.Boolean(description="Whether session is active"),
        "reason": fields.String(description="Reason if inactive"),
    },
)

session_metrics_model = session_ns.model(
    "SessionMetrics",
    {
        "session_active": fields.Boolean(),
        "keystroke_count": fields.Integer(description="Total keystrokes in session"),
        "mouse_count": fields.Integer(description="Total mouse events in session"),
        "anomaly_count": fields.Integer(description="Anomalies in last 24h"),
        "authenticity_score": fields.Float(
            description="Behavioral authenticity [0.02–0.99]"
        ),
        "risk_score": fields.Float(description="Risk score [0.01–0.98]"),
        "risk_level": fields.String(enum=["low", "medium", "high"]),
        "risk_reasons": fields.List(fields.String()),
        "step_up_recommended": fields.Boolean(),
    },
)

silent_challenge_input = session_ns.model(
    "SilentChallengeInput",
    {
        "session_id": fields.String(required=True),
        "current_risk_score": fields.Float(required=True, min=0.0, max=1.0),
    },
)

silent_challenge_output = session_ns.model(
    "SilentChallengeOutput",
    {
        "action": fields.String(
            enum=[
                "normal",
                "silent_monitor",
                "enhanced_sampling",
                "mfa_required",
                "terminate",
            ]
        ),
        "message": fields.String(),
        "anomaly_streak": fields.Integer(),
        "risk_score": fields.Float(),
    },
)


# ── Metrics builder ──────────────────────────────────────────────────────────


def _build_session_metrics(session_id: str):
    """Build adaptive session metrics payload for dashboards."""
    if not session_id:
        return None, ("Missing session_id", 400)

    session = get_session_cached(session_id)
    if not session:
        return None, ("Invalid session", 404)
    if not validate_session_context(session):
        return None, ("Session context mismatch", 403)

    db = get_db()
    user_id = session["user_id"]
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT features FROM behavioral_data WHERE session_id = ? AND data_type = 'keystroke'",
            (session_id,),
        )
        keystroke_count = 0
        for row in cursor.fetchall():
            try:
                feats = (
                    json.loads(row["features"])
                    if isinstance(row["features"], str)
                    else (row["features"] or {})
                )
                keystroke_count += int(feats.get("event_count", 1))
            except Exception:
                keystroke_count += 1

        cursor.execute(
            "SELECT features FROM behavioral_data WHERE session_id = ? AND data_type = 'mouse'",
            (session_id,),
        )
        mouse_count = 0
        for row in cursor.fetchall():
            try:
                feats = (
                    json.loads(row["features"])
                    if isinstance(row["features"], str)
                    else (row["features"] or {})
                )
                mouse_count += int(feats.get("event_count", 1))
            except Exception:
                mouse_count += 1
        cursor.execute(
            """SELECT COUNT(*) AS anomaly_count FROM auth_events
               WHERE user_id = ? AND event_type = 'anomaly'
               AND timestamp > datetime('now', '-1 day')""",
            (user_id,),
        )
        anomaly_count = int(cursor.fetchone()["anomaly_count"])

    total_activity = keystroke_count + mouse_count
    anomaly_penalty = min(anomaly_count * 0.18, 0.85)
    # RBI-calibrated: 10 events = minimum for login+one-action.
    # Only penalise sessions that look automated (<10 events).
    low_activity_penalty = 0.15 if total_activity < 10 else 0.0

    # Netbanking sessions are short — 30 events is a healthy session
    activity_bonus = min(total_activity / 30.0, 1.0) * 0.08

    # Imbalance only meaningful after 100+ events, threshold raised to 95%
    stream_imbalance = abs(keystroke_count - mouse_count) / max(total_activity, 1)
    imbalance_penalty = (
        0.1 if total_activity >= 100 and stream_imbalance > 0.95 else 0.0
    )

    authenticity_score = (
        1.0
        - anomaly_penalty
        - low_activity_penalty
        - imbalance_penalty
        + activity_bonus
    )
    authenticity_score = round(max(0.02, min(authenticity_score, 0.99)), 2)
    risk_score = round(1.0 - authenticity_score, 2)

    if risk_score >= current_app.config.get("RISK_HIGH_THRESHOLD", 0.65):
        risk_level = "high"
    elif risk_score >= current_app.config.get("RISK_MEDIUM_THRESHOLD", 0.35):
        risk_level = "medium"
    else:
        risk_level = "low"

    risk_reasons = []
    if anomaly_count > 0:
        risk_reasons.append(f"{anomaly_count} anomaly events in last 24h")
    if low_activity_penalty > 0:
        risk_reasons.append("insufficient live behavioral activity")
    if imbalance_penalty > 0:
        risk_reasons.append("strong imbalance between keyboard and mouse signals")
    if authenticity_score < 0.7:
        risk_reasons.append("authenticity score dropped below 0.70")
    if not risk_reasons:
        risk_reasons.append("no anomaly indicators detected")

    # ── ML Ensemble (non-blocking, best-effort) ────────────────────────────
    ensemble_data = {}
    try:
        ensemble_data = score_with_ensemble(
            extended_features={},  # populated from stored data if available
            user_id=user_id,
        )
    except Exception:
        pass  # Ensemble is advisory; never block the main response

    return (
        {
            "session_active": True,
            "keystroke_count": keystroke_count,
            "mouse_count": mouse_count,
            "anomaly_count": anomaly_count,
            "authenticity_score": authenticity_score,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_reasons": risk_reasons,
            "step_up_recommended": risk_score
            >= current_app.config.get("STEP_UP_RISK_SCORE_THRESHOLD", 0.6),
            "ensemble": {
                "ensemble_risk": ensemble_data.get("ensemble_risk", 0.0),
                "ensemble_action": ensemble_data.get("ensemble_action", "allow"),
                "duress_score": ensemble_data.get("duress_score", 0.0),
                "liveness_score": ensemble_data.get("liveness_score", 1.0),
                "challenge_risk": ensemble_data.get("challenge_risk", 0.0),
                "device_risk": ensemble_data.get("device_risk", 0.0),
                "replay_risk": ensemble_data.get("replay_risk", 0.0),
                "weighted_match_score": ensemble_data.get("weighted_match_score", 0.0),
                "ensemble_flags": ensemble_data.get("ensemble_flags", []),
                "cognitive_analysis": ensemble_data.get("cognitive_analysis") or {},
                "enrollment_status": ensemble_data.get("enrollment_status") or {},
            },
        },
        None,
    )


# ── Trust timeline builder ───────────────────────────────────────────────────


def _build_trust_timeline(session_id: str, window_minutes: int, severity: str):
    if not session_id:
        return None, ("Missing session_id", 400)
    db = get_db()
    session = db.get_session(session_id)
    if not session:
        return None, ("Invalid session", 404)
    user_id = session["user_id"]
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT strftime('%Y-%m-%dT%H:%M:00Z', timestamp) AS bucket_ts,
                      data_type,
                      COUNT(*) AS activity
               FROM behavioral_data
               WHERE session_id = ? AND timestamp > datetime('now', ?)
               GROUP BY bucket_ts, data_type ORDER BY bucket_ts ASC""",
            (session_id, f"-{window_minutes} minutes"),
        )
        rows = cursor.fetchall()
        cursor.execute(
            """SELECT strftime('%Y-%m-%dT%H:%M:00Z', timestamp) AS bucket_ts,
                      COUNT(*) AS anomaly_count
               FROM auth_events
               WHERE user_id = ? AND event_type = 'anomaly'
                 AND timestamp > datetime('now', ?)
               GROUP BY bucket_ts ORDER BY bucket_ts ASC""",
            (user_id, f"-{window_minutes} minutes"),
        )
        anomaly_rows = cursor.fetchall()

    buckets: dict = {}
    for row in rows:
        b = row["bucket_ts"]
        buckets.setdefault(b, {"keystrokes": 0, "mouse_events": 0, "anomalies": 0})
        if row["data_type"] == "keystroke":
            buckets[b]["keystrokes"] = int(row["activity"])
        elif row["data_type"] == "mouse":
            buckets[b]["mouse_events"] = int(row["activity"])
    for row in anomaly_rows:
        b = row["bucket_ts"]
        buckets.setdefault(b, {"keystrokes": 0, "mouse_events": 0, "anomalies": 0})
        buckets[b]["anomalies"] = int(row["anomaly_count"])

    points, prev = [], None
    for ts in sorted(buckets):
        ks, mc, ac = (
            buckets[ts]["keystrokes"],
            buckets[ts]["mouse_events"],
            buckets[ts]["anomalies"],
        )
        total = ks + mc
        auth = round(
            max(
                0.02,
                min(
                    1.0
                    - min(ac * 0.25, 0.9)
                    - (0.2 if total < 8 else 0.0)
                    - (
                        0.1
                        if total >= 12 and abs(ks - mc) / max(total, 1) > 0.9
                        else 0.0
                    ),
                    0.99,
                ),
            ),
            2,
        )
        rs = round(1.0 - auth, 2)
        rl = (
            "high"
            if rs >= current_app.config.get("RISK_HIGH_THRESHOLD", 0.65)
            else (
                "medium"
                if rs >= current_app.config.get("RISK_MEDIUM_THRESHOLD", 0.35)
                else "low"
            )
        )
        points.append(
            {
                "timestamp": ts,
                "keystroke_count": ks,
                "mouse_count": mc,
                "anomaly_count": ac,
                "authenticity_score": auth,
                "risk_score": rs,
                "risk_level": rl,
                "risk_transition": f"{prev}->{rl}" if prev and prev != rl else None,
            }
        )
        prev = rl

    rank = {"low": 1, "medium": 2, "high": 3}
    return [
        p for p in points[-20:] if rank.get(p["risk_level"], 1) >= rank.get(severity, 1)
    ], None


# ── Routes ───────────────────────────────────────────────────────────────────


@session_ns.route("/status")
class SessionStatus(Resource):
    @jwt_required()
    @session_ns.response(200, "Session status", session_status_model)
    @limiter.limit("30 per minute")
    def get(self):
        """Check whether a session is active."""
        sid = request.args.get("session_id") or request.cookies.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        s = get_session_cached(sid)
        if s and not validate_session_context(s):
            return {"session_active": False, "reason": "session_context_mismatch"}, 200
        return {"session_active": bool(s)}, 200


@session_ns.route("/metrics")
class SessionMetrics(Resource):
    @jwt_required()
    @session_ns.response(200, "Session metrics", session_metrics_model)
    @limiter.limit("60 per minute")
    def get(self):
        """Get real-time behavioral metrics for a session."""
        m, e = _build_session_metrics(request.args.get("session_id") or request.cookies.get("session_id"))
        return ({"error": e[0]}, e[1]) if e else (m, 200)


@session_ns.route("/metrics/stream")
class SessionMetricsStream(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        sid = request.args.get("session_id") or request.cookies.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        _, e = _build_session_metrics(sid)
        if e:
            return {"error": e[0]}, e[1]

        def stream():
            while True:
                m, err = _build_session_metrics(sid)
                if err:
                    yield f"event: error\ndata: {json.dumps({'error': err[0]})}\n\n"
                    break
                yield f"event: metrics\ndata: {json.dumps(m)}\n\n"
                time.sleep(2)

        return Response(
            stream_with_context(stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )


@session_ns.route("/trust-timeline")
class TrustTimeline(Resource):
    @jwt_required()
    @limiter.limit("45 per minute")
    def get(self):
        sid = request.args.get("session_id") or request.cookies.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        wm = request.args.get(
            "window_minutes",
            current_app.config.get("TRUST_TIMELINE_DEFAULT_WINDOW_MINUTES", 30),
        )
        severity = (request.args.get("severity") or "low").lower()
        if severity not in {"low", "medium", "high"}:
            return {"error": "Invalid severity"}, 400
        try:
            pw = int(wm)
        except Exception:
            return {"error": "Invalid window_minutes"}, 400
        mx = current_app.config.get("TRUST_TIMELINE_MAX_WINDOW_MINUTES", 180)
        if pw < 5 or pw > mx:
            return {"error": f"window_minutes must be between 5 and {mx}"}, 400
        s = get_session_cached(sid)
        if not s:
            return {"error": "Invalid session"}, 404
        pts, e = _build_trust_timeline(sid, pw, severity)
        if e:
            return {"error": e[0]}, e[1]
        get_db().log_audit_evidence(
            action="trust_timeline_view",
            status="ok",
            user_id=s.get("user_id"),
            session_id=sid,
            resource="/api/session/trust-timeline",
            metadata={"window_minutes": pw, "severity": severity},
            retention_tag="compliance",
        )
        return {"points": pts}, 200


@session_ns.route("/trust-timeline.csv")
class TrustTimelineCsv(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        sid = request.args.get("session_id") or request.cookies.get("session_id")
        s = get_session_cached(sid) if sid else None
        if not s:
            return {"error": "Invalid session"}, 404
        wm = request.args.get(
            "window_minutes",
            current_app.config.get("TRUST_TIMELINE_DEFAULT_WINDOW_MINUTES", 30),
        )
        severity = (request.args.get("severity") or "low").lower()
        if severity not in {"low", "medium", "high"}:
            return {"error": "Invalid severity"}, 400
        try:
            pw = int(wm)
        except Exception:
            return {"error": "Invalid window_minutes"}, 400
        mx = current_app.config.get("TRUST_TIMELINE_MAX_WINDOW_MINUTES", 180)
        if pw < 5 or pw > mx:
            return {"error": f"window_minutes must be between 5 and {mx}"}, 400
        pts, e = _build_trust_timeline(sid, pw, severity)
        if e:
            return {"error": e[0]}, e[1]
        buf = io.StringIO()
        w = csv.DictWriter(
            buf,
            fieldnames=[
                "timestamp",
                "keystroke_count",
                "mouse_count",
                "anomaly_count",
                "authenticity_score",
                "risk_score",
                "risk_level",
                "risk_transition",
            ],
        )
        w.writeheader()
        w.writerows(pts)
        get_db().log_audit_evidence(
            action="trust_timeline_export",
            status="ok",
            user_id=s.get("user_id"),
            session_id=sid,
            resource="/api/session/trust-timeline.csv",
            metadata={"row_count": len(pts), "severity": severity},
            retention_tag="compliance",
        )
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="trust_timeline_{sid}.csv"'
            },
        )


@session_ns.route("/cognitive-profile")
class CognitiveProfile(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        sid = request.args.get("session_id") or request.cookies.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        s = get_session_cached(sid)
        if not s:
            return {"error": "Invalid session"}, 404
        err = validate_session_ownership(s)
        if err:
            return err
        db = get_db()
        records = []
        try:
            with db.get_connection() as conn:
                for row in conn.execute(
                    "SELECT features FROM behavioral_data WHERE session_id = ? AND data_type = 'extended' ORDER BY timestamp DESC LIMIT 10",
                    (sid,),
                ).fetchall():
                    try:
                        records.append(
                            json.loads(row[0])
                            if isinstance(row[0], str)
                            else (row[0] or {})
                        )
                    except Exception:
                        pass
        except Exception as exc:
            logger.error("Failed to fetch extended features: %s", exc)
        if not records:
            return {
                "cognitive_profile": None,
                "message": "No extended behavioral data yet.",
            }, 200
        latest = records[0]
        return {
            "session_id": sid,
            "records_analyzed": len(records),
            "cognitive_profile": run_cognitive_analysis(latest),
            "signal_scores": score_extended_features(latest),
            "latest_features": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in latest.items()
                if not isinstance(v, list)
            },
        }, 200


@session_ns.route("/enrollment-status")
class EnrollmentStatus(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def get(self):
        sid = request.args.get("session_id") or request.cookies.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        s = get_session_cached(sid)
        if not s:
            return {"error": "Invalid session"}, 404
        err = validate_session_ownership(s)
        if err:
            return err
        db = get_db()
        stats = db.get_user_stats(get_current_user_id())
        total = stats.get("total_samples", 0)
        if total < 20:
            phase, progress = "bootstrap", min(int(total / 20 * 33), 33)
        elif total < 100:
            phase, progress = "building", 33 + min(int((total - 20) / 80 * 34), 34)
        else:
            phase, progress = "mature", min(67 + int((total - 100) / 100 * 33), 100)
        return {
            "phase": phase,
            "progress_pct": progress,
            "total_samples": total,
            "keystroke_samples": stats.get("keystroke_samples", 0),
            "mouse_samples": stats.get("mouse_samples", 0),
            "calibration_complete": s.get("calibration_complete", False),
            "active_models": {"bootstrap": 3, "building": 5, "mature": 6}.get(phase, 3),
        }, 200


@session_ns.route("/silent-challenge")
class SilentChallenge(Resource):
    @jwt_required()
    @limiter.limit("30 per minute")
    def post(self):
        from datetime import datetime

        payload = request.get_json() or {}
        sid = payload.get("session_id") or request.cookies.get("session_id")
        if not sid:
            return {"error": "Missing session_id"}, 400
        s = get_session_cached(sid)
        if not s:
            return {"error": "Invalid session"}, 404
        err = validate_session_ownership(s)
        if err:
            return err

        streak = s.get("anomaly_streak", 0)
        risk = payload.get("current_risk_score", 0.5)
        streak = streak + 1 if risk > 0.6 else max(0, streak - 1)

        escalation = [
            ("terminate", "Session terminated due to persistent anomalous behavior", 4),
            ("mfa_required", "Step-up authentication required", 3),
            ("enhanced_sampling", "Enhanced behavioral sampling activated", 2),
            ("silent_monitor", "Silent monitoring activated", 1),
        ]
        action, message = "normal", "Session normal"
        for act, msg, threshold in escalation:
            if streak >= threshold:
                action, message = act, msg
                break

        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                    (datetime.now(), sid),
                )
                conn.commit()
        except Exception:
            pass
        db.log_audit_evidence(
            action="silent_challenge",
            status=action,
            user_id=get_current_user_id(),
            session_id=sid,
            resource="/api/v1/session/silent-challenge",
            metadata={
                "anomaly_streak": streak,
                "current_risk": risk,
                "escalation_action": action,
            },
            retention_tag="security",
        )
        return {
            "action": action,
            "message": message,
            "anomaly_streak": streak,
            "risk_score": risk,
            "next_escalation": {
                "silent_monitor": 1,
                "enhanced_sampling": 2,
                "mfa_required": 3,
                "terminate": 4,
                "normal": 0,
            }.get(action, 0),
        }, 200
