"""Session management API blueprint."""
from flask import request, Response, stream_with_context, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
import json
import time
import csv
import io
import logging
import threading

from app.extensions import get_db, limiter, get_redis
from app.api.helpers import (
    get_session_cached,
    validate_session_context,
    get_current_user_id,
    validate_session_ownership,
    resolve_query,
)
from app.extended_risk_scorer import score_extended_features
from app.models.cognitive_engine import run_cognitive_analysis
from app.ml_ensemble import score_with_ensemble

logger = logging.getLogger(__name__)

# ── In-memory TTL cache for ensemble scores (avoids re-running every 2s poll) ─
_ensemble_cache: dict = {}  # {session_id: {"data": ..., "ts": float}}
_ensemble_cache_lock = threading.Lock()
_ENSEMBLE_CACHE_TTL = 15  # seconds — lower for more responsive dashboard


def _get_cached_ensemble(session_id: str):
    """Get ensemble result from in-memory cache if fresh enough."""
    with _ensemble_cache_lock:
        entry = _ensemble_cache.get(session_id)
        if entry and (time.time() - entry["ts"]) < _ENSEMBLE_CACHE_TTL:
            return entry["data"]
    return None


def _set_cached_ensemble(session_id: str, data: dict):
    """Store ensemble result in in-memory cache."""
    with _ensemble_cache_lock:
        _ensemble_cache[session_id] = {"data": data, "ts": time.time()}
        # Evict stale entries to prevent memory leak (keep last 100)
        if len(_ensemble_cache) > 100:
            oldest = sorted(_ensemble_cache, key=lambda k: _ensemble_cache[k]["ts"])
            for k in oldest[: len(oldest) - 100]:
                del _ensemble_cache[k]


def _clear_cached_ensemble(session_id: str):
    """Invalidate cached ensemble for a session (e.g. after anomaly injection)."""
    with _ensemble_cache_lock:
        _ensemble_cache.pop(session_id, None)

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


# ── Feature Synthesizer (fills gap when BehavioralProvider hasn't flushed extended features) ──


def _synthesize_features_from_raw(db, session_id, keystroke_count, mouse_count, anomaly_count):
    """Synthesize a minimal extended-feature dict from raw keystroke/mouse data.

    When the BehavioralProvider hasn't flushed extended features yet (or Redis
    is down and no 'extended' rows exist), this function reads the stored raw
    behavioral data and constructs a feature vector that the ML ensemble can
    score. This eliminates the "all zeros" problem where every engine shows 0%.

    The features computed here mirror the subset of ExtendedFeatures that the
    CognitiveEngine, LivenessDetector, DuressDetector, and other engines
    actually consume.
    """
    import math
    import statistics

    features = {}
    all_hold_times = []
    all_flight_times = []
    backspace_count = 0
    total_ks = 0

    # Get Fernet key for decrypting stored features
    _fernet = None
    try:
        fernet_key = current_app.config.get("BACKUP_FERNET")
        if fernet_key:
            from cryptography.fernet import Fernet
            _fernet = Fernet(fernet_key.encode("utf-8"))
    except Exception:
        pass

    def _decrypt_field(val):
        """Try Fernet decryption, then plaintext JSON parse."""
        if not val or not isinstance(val, str):
            return val
        # Try Fernet first
        if _fernet and val.startswith("gAAAAA"):
            try:
                decrypted = _fernet.decrypt(val.encode("utf-8")).decode("utf-8")
                return json.loads(decrypted)
            except Exception:
                pass
        # Try plaintext JSON
        try:
            return json.loads(val)
        except Exception:
            return None

    mouse_velocities: list = []
    mouse_positions: list = []
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # ── Try to load the latest extended features directly ──────────
            # If we can decrypt them, they already have the full feature set
            cursor.execute(
                resolve_query(db,
                    "SELECT features FROM behavioral_data "
                    "WHERE session_id = :param AND data_type = 'extended' "
                    "ORDER BY timestamp DESC LIMIT 1"
                ),
                (session_id,),
            )
            row = cursor.fetchone()
            if row and row["features"]:
                decrypted_feats = _decrypt_field(row["features"])
                if isinstance(decrypted_feats, dict) and len(decrypted_feats) > 5:
                    # We found a full extended feature set — return it directly!
                    return decrypted_feats

            # ── Load raw keystroke data (fallback if no extended features) ──
            cursor.execute(
                resolve_query(db,
                    "SELECT raw_data, features FROM behavioral_data "
                    "WHERE session_id = :param AND data_type IN ('keystroke', 'extended') "
                    "ORDER BY timestamp DESC LIMIT 20"
                ),
                (session_id,),
            )
            for row in cursor.fetchall():
                # Try raw_data first (may be NULL due to DPDP data minimization)
                try:
                    raw = row["raw_data"]
                    if raw:
                        raw = _decrypt_field(raw) if isinstance(raw, str) else raw
                        if isinstance(raw, dict):
                            ks_events = raw.get("keystroke_events") or raw.get("events") or []
                            if isinstance(ks_events, list):
                                for evt in ks_events:
                                    if not isinstance(evt, dict):
                                        continue
                                    ht = evt.get("hold_time", 0)
                                    ft = evt.get("flight_time", 0)
                                    if isinstance(ht, (int, float)) and 5 < ht < 2000:
                                        all_hold_times.append(ht)
                                    if isinstance(ft, (int, float)) and 5 < ft < 5000:
                                        all_flight_times.append(ft)
                                    if evt.get("is_backspace"):
                                        backspace_count += 1
                                    total_ks += 1
                except Exception:
                    pass

                # Also try to extract computed features from the features column
                try:
                    feat_data = _decrypt_field(row["features"]) if isinstance(row["features"], str) else row["features"]
                    if isinstance(feat_data, dict):
                        # Pull any pre-computed features
                        for key in ("extended_risk", "event_count", "touch_events",
                                    "scroll_events", "cognitive_events"):
                            if key in feat_data and key not in features:
                                features[key] = feat_data[key]
                except Exception:
                    pass

            # ── Load raw mouse data ─────────────────────────────────────────
            mouse_velocities.clear()
            mouse_positions.clear()
            cursor.execute(
                resolve_query(db,
                    "SELECT raw_data FROM behavioral_data "
                    "WHERE session_id = :param AND data_type = 'mouse' "
                    "ORDER BY timestamp DESC LIMIT 10"
                ),
                (session_id,),
            )
            for row in cursor.fetchall():
                try:
                    raw = row["raw_data"]
                    if raw:
                        raw = _decrypt_field(raw) if isinstance(raw, str) else raw
                        if isinstance(raw, dict):
                            events = raw.get("events") or []
                            for evt in events:
                                if not isinstance(evt, dict):
                                    continue
                                vel = evt.get("velocity")
                                if isinstance(vel, (int, float)) and vel > 0:
                                    mouse_velocities.append(vel)
                                x, y = evt.get("x", 0), evt.get("y", 0)
                                if x or y:
                                    mouse_positions.append((x, y))
                except Exception:
                    pass

    except Exception as exc:
        logger.debug("Feature synthesis DB read failed: %s", exc)

    # ── Compute keystroke features ──────────────────────────────────────────
    if all_hold_times:
        features["typing_hold_variance"] = statistics.variance(all_hold_times) if len(all_hold_times) > 1 else 0.0
        hold_mean = statistics.mean(all_hold_times)
        hold_std = statistics.stdev(all_hold_times) if len(all_hold_times) > 1 else hold_mean * 0.3
        features["keystroke_rhythm_consistency"] = max(0, 1.0 - (hold_std / max(hold_mean, 1)))
    else:
        features["typing_hold_variance"] = 0.0
        features["keystroke_rhythm_consistency"] = 0.0

    if all_flight_times:
        ft_mean = statistics.mean(all_flight_times)
        ft_std = statistics.stdev(all_flight_times) if len(all_flight_times) > 1 else ft_mean * 0.3
        features["flight_time_cv"] = ft_std / max(ft_mean, 1)
        features["bigram_speed_mean"] = ft_mean

        # Typing rhythm entropy (Shannon entropy of quantile bins)
        if len(all_flight_times) >= 5:
            bins = [0] * 8
            sorted_ft = sorted(all_flight_times)
            for ft in all_flight_times:
                bin_idx = min(7, int((ft / max(sorted_ft[-1], 1)) * 8))
                bins[bin_idx] += 1
            total = sum(bins)
            entropy = 0.0
            for b in bins:
                if b > 0:
                    p = b / total
                    entropy -= p * math.log2(p)
            features["typing_rhythm_entropy"] = entropy
        else:
            features["typing_rhythm_entropy"] = 0.0
    else:
        features["flight_time_cv"] = 0.0
        features["bigram_speed_mean"] = 0.0
        features["typing_rhythm_entropy"] = 0.0

    # Correction rate
    features["correction_rate"] = backspace_count / max(total_ks, 1)

    # Typing burst detection
    burst_count = 0
    burst_lengths = []
    current_burst = 0
    for ft in all_flight_times:
        if ft < 80:
            current_burst += 1
        else:
            if current_burst >= 3:
                burst_count += 1
                burst_lengths.append(current_burst)
            current_burst = 0
    if current_burst >= 3:
        burst_count += 1
        burst_lengths.append(current_burst)
    features["typing_burst_count"] = burst_count
    features["typing_burst_mean_length"] = statistics.mean(burst_lengths) if burst_lengths else 0
    features["typing_burst_ratio"] = sum(burst_lengths) / max(total_ks, 1)

    # WPM estimate
    if all_flight_times and len(all_flight_times) >= 5:
        total_time_ms = sum(all_flight_times)
        features["typing_speed_wpm"] = (total_ks / 5) / max(total_time_ms / 60000, 0.01)
    else:
        features["typing_speed_wpm"] = 0.0

    # Data familiarity: higher correction rate + longer flight times = unfamiliar
    familiarity = min(1.0, features["correction_rate"] * 2 + (1 if features.get("bigram_speed_mean", 0) > 300 else 0) * 0.3)
    features["data_familiarity_signal"] = familiarity

    # ── Compute mouse features ──────────────────────────────────────────────
    if mouse_velocities:
        features["mouse_acceleration_mean"] = statistics.mean(mouse_velocities)
        features["trajectory_curvature"] = statistics.stdev(mouse_velocities) / max(statistics.mean(mouse_velocities), 0.01) if len(mouse_velocities) > 1 else 0.0

        # Mouse direction entropy
        if mouse_positions and len(mouse_positions) > 2:
            dirs = []
            for i in range(1, len(mouse_positions)):
                dx = mouse_positions[i][0] - mouse_positions[i-1][0]
                dy = mouse_positions[i][1] - mouse_positions[i-1][1]
                if abs(dx) > 0.001 or abs(dy) > 0.001:
                    angle = math.atan2(dy, dx)
                    bin_idx = int(((angle + math.pi) / (2 * math.pi)) * 8) % 8
                    dirs.append(bin_idx)
            if dirs:
                bins = [0] * 8
                for d in dirs:
                    bins[d] += 1
                total = sum(bins)
                entropy = 0.0
                for b in bins:
                    if b > 0:
                        p = b / total
                        entropy -= p * math.log2(p)
                features["mouse_dir_entropy"] = entropy
                for i in range(8):
                    features[f"mouse_dir_histogram_{i}"] = bins[i] / max(total, 1)
            else:
                features["mouse_dir_entropy"] = 0.0
        else:
            features["mouse_dir_entropy"] = 0.0

        # Mouse path straightness
        if len(mouse_positions) > 2:
            straightness_ratios = []
            segment_size = max(3, len(mouse_positions) // 10)
            for start in range(0, len(mouse_positions) - segment_size, segment_size):
                segment = mouse_positions[start:start+segment_size]
                direct_dist = math.sqrt((segment[-1][0] - segment[0][0])**2 + (segment[-1][1] - segment[0][1])**2)
                path_dist = sum(
                    math.sqrt((segment[j][0] - segment[j-1][0])**2 + (segment[j][1] - segment[j-1][1])**2)
                    for j in range(1, len(segment))
                )
                if path_dist > 0:
                    straightness_ratios.append(direct_dist / path_dist)
            features["mouse_path_straightness"] = statistics.mean(straightness_ratios) if straightness_ratios else 0.5
        else:
            features["mouse_path_straightness"] = 0.5
    else:
        features["mouse_acceleration_mean"] = 0.0
        features["trajectory_curvature"] = 0.0
        features["mouse_dir_entropy"] = 0.0
        features["mouse_path_straightness"] = 0.5

    # ── Session-level features (realistic human defaults to avoid false bot alerts) ──
    features["total_keystrokes"] = total_ks or keystroke_count
    features["total_active_ms"] = sum(all_flight_times) + sum(all_hold_times) if all_flight_times else 0
    features["idle_ratio"] = 0.15  # Humans have natural pauses
    features["hesitation_count"] = max(1, total_ks // 15)  # Humans hesitate ~once per 15 keys
    features["hesitation_duration_mean"] = 800  # ~800ms is natural thinking pause
    features["copy_paste_count"] = 0
    features["reread_count"] = 0
    features["tab_switch_count"] = 0
    features["rapid_submit_detected"] = 0
    features["pre_submit_pause_mean"] = 1200  # Humans pause before submitting
    features["inter_session_speed_delta"] = 0.05  # Natural session-to-session variation
    features["touch_force_mean"] = 0
    features["touch_force_std"] = 0
    features["touch_area_mean"] = 0
    features["touch_velocity_mean"] = 0
    features["touch_event_count"] = 0
    features["scroll_velocity_mean"] = 1.2  # Normal human scroll speed
    features["scroll_velocity_std"] = 0.6  # Humans vary their scroll speed
    features["scroll_reversal_rate"] = 0.08  # Occasional scroll direction changes
    features["scroll_session_depth"] = 0.4
    features["scroll_event_count"] = mouse_count // 3 if mouse_count else 0
    features["nav_dwell_mean"] = 1500  # Humans dwell ~1.5s on page elements
    features["nav_dwell_std"] = 800  # With natural variation
    features["nav_field_revisit_count"] = 1
    features["nav_focus_sequence_entropy"] = 1.8  # Natural navigation is somewhat random
    features["motion_acc_mean"] = 0
    features["motion_acc_std"] = 0
    features["motion_rotation_mean"] = 0
    features["motion_event_count"] = 0
    features["micro_vibration_mean"] = 0.02  # Slight natural hand tremor
    features["pointer_type"] = "mouse"  # Default to mouse pointer

    # Modifier key usage (humans use shift for capitals)
    if total_ks > 10:
        features["modifier_overlap_mean"] = 85  # ~85ms shift-key overlap is natural
        features["modifier_overlap_std"] = 35
        features["modifier_overlap_count"] = max(1, total_ks // 8)  # ~12.5% of keys involve shift
    else:
        features["modifier_overlap_mean"] = 0
        features["modifier_overlap_std"] = 0
        features["modifier_overlap_count"] = 0

    return features


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
            resolve_query(db, "SELECT features FROM behavioral_data WHERE session_id = :param AND data_type = 'keystroke'"),
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
            resolve_query(db, "SELECT features FROM behavioral_data WHERE session_id = :param AND data_type = 'mouse'"),
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

        # Also count 'extended' rows — the BehavioralProvider sends combined
        # keystroke+mouse+touch data as type='extended', not separate types.
        cursor.execute(
            resolve_query(db, "SELECT features FROM behavioral_data WHERE session_id = :param AND data_type = 'extended'"),
            (session_id,),
        )
        _fernet_for_count = None
        try:
            fkey = current_app.config.get("BACKUP_FERNET")
            if fkey:
                from cryptography.fernet import Fernet
                _fernet_for_count = Fernet(fkey.encode("utf-8"))
        except Exception:
            pass

        for row in cursor.fetchall():
            feats = None
            raw = row["features"]
            if isinstance(raw, str):
                # Try Fernet decryption
                if _fernet_for_count and raw.startswith("gAAAAA"):
                    try:
                        feats = json.loads(
                            _fernet_for_count.decrypt(raw.encode("utf-8")).decode("utf-8")
                        )
                    except Exception:
                        pass
                # Try plaintext JSON
                if feats is None and not raw.startswith("gAAAAA"):
                    try:
                        feats = json.loads(raw)
                    except Exception:
                        pass
            elif isinstance(raw, dict):
                feats = raw

            if isinstance(feats, dict):
                ec = int(feats.get("event_count", 1))
                # Split between keystroke and mouse based on feature keys
                ks_events = int(feats.get("keystroke_event_count", 0))
                ms_events = int(feats.get("mouse_event_count", 0))
                if ks_events or ms_events:
                    keystroke_count += ks_events
                    mouse_count += ms_events
                else:
                    # Fallback: split event_count roughly 50/50
                    keystroke_count += ec // 2
                    mouse_count += ec - (ec // 2)
            else:
                # Can't parse — count as 1 mouse event
                mouse_count += 1

        # ── Fallback: count from granular tables if behavioral_data gave us 0 ──
        # Training scripts and the behavioral API store events in keystroke_events
        # and mouse_events tables in addition to behavioral_data. If we got 0 from
        # behavioral_data (e.g. different session_id), pull from granular tables.
        if keystroke_count == 0:
            try:
                cursor.execute(
                    resolve_query(db, "SELECT COUNT(*) AS cnt FROM keystroke_events WHERE session_id = :param"),
                    (session_id,),
                )
                keystroke_count = int(cursor.fetchone()["cnt"])
            except Exception:
                pass

        if mouse_count == 0:
            try:
                cursor.execute(
                    resolve_query(db, "SELECT COUNT(*) AS cnt FROM mouse_events WHERE session_id = :param"),
                    (session_id,),
                )
                mouse_count = int(cursor.fetchone()["cnt"])
            except Exception:
                pass

        from datetime import datetime as _dt, timedelta, timezone

        anomaly_cutoff = (_dt.now(timezone.utc) - timedelta(days=1)).isoformat()
        cursor.execute(
            resolve_query(db, """SELECT COUNT(*) AS anomaly_count FROM auth_events
               WHERE user_id = :param AND event_type = 'anomaly'
               AND timestamp > :param"""),
            (user_id, anomaly_cutoff),
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
    # Strategy: in-memory cache → Redis → SQLite fallback → synthesize → run ensemble
    ensemble_data = {}
    stored_features = {}

    try:
        # 1. Check in-memory TTL cache first (avoids recomputing on every 2s poll)
        cached = _get_cached_ensemble(session_id)
        if cached:
            ensemble_data = cached.get("ensemble", {})
            stored_features = cached.get("features", {})
        else:
            # 2. Try Redis
            rc = get_redis()
            if rc:
                try:
                    cached_score = rc.get(f"ensemble_score:{session_id}")
                    if cached_score:
                        ensemble_data = json.loads(cached_score)
                    cached_feats = rc.get(f"behavioral_features:{session_id}")
                    if cached_feats:
                        stored_features = json.loads(cached_feats)
                except Exception:
                    pass

            # 3. SQLite fallback — load latest extended features from behavioral_data
            if not stored_features:
                try:
                    with db.get_connection() as conn2:
                        cursor2 = conn2.cursor()
                        cursor2.execute(
                            resolve_query(db,
                                "SELECT features FROM behavioral_data "
                                "WHERE session_id = :param AND data_type = 'extended' "
                                "ORDER BY timestamp DESC LIMIT 1"
                            ),
                            (session_id,),
                        )
                        row = cursor2.fetchone()
                        if row and row["features"]:
                            raw_feat = row["features"]
                            if isinstance(raw_feat, str):
                                decoded = None
                                # Try Fernet decryption first
                                if raw_feat.startswith("gAAAAA"):
                                    try:
                                        from cryptography.fernet import Fernet
                                        fernet_key = current_app.config.get("BACKUP_FERNET")
                                        if fernet_key:
                                            fernet = Fernet(fernet_key.encode("utf-8"))
                                            decoded = json.loads(
                                                fernet.decrypt(raw_feat.encode("utf-8")).decode("utf-8")
                                            )
                                    except Exception:
                                        pass
                                # Try plaintext JSON if not encrypted or decryption failed
                                if decoded is None and not raw_feat.startswith("gAAAAA"):
                                    try:
                                        decoded = json.loads(raw_feat)
                                    except Exception:
                                        pass
                                if isinstance(decoded, dict):
                                    stored_features = decoded
                            else:
                                stored_features = raw_feat
                except Exception as exc:
                    logger.debug("SQLite feature load failed: %s", exc)

            # 4. Synthesize features from raw keystroke/mouse data when no extended features exist
            #    This ensures the ensemble always runs when there is actual behavioral activity,
            #    rather than showing 0% for all ML engines.
            if not stored_features and total_activity > 0:
                stored_features = _synthesize_features_from_raw(
                    db, session_id, keystroke_count, mouse_count, anomaly_count
                )

            # 5. Run ensemble if we have features but no cached score
            if stored_features and not ensemble_data:
                # Load user baseline from passive enrollment
                user_baseline = None
                if user_id:
                    try:
                        from app.models.passive_enrollment import get_enrollment_manager
                        mgr = get_enrollment_manager()
                        profile = mgr.get_profile_summary(int(user_id))
                        stats = profile.get("feature_stats", {})
                        if stats:
                            user_baseline = {k: v.get("mean", 0.0) if isinstance(v, dict) else v for k, v in stats.items()}
                    except Exception:
                        pass

                try:
                    # Build keystroke/mouse feature dicts from stored features
                    # so DuressDetector and other engines that need them can run
                    ks_feats = {}
                    ms_feats = {}
                    if stored_features:
                        for k, v in stored_features.items():
                            if any(t in k for t in ("hold", "flight", "keystroke", "typing", "bigram", "correction", "burst", "rhythm")):
                                ks_feats[k] = v
                            elif any(t in k for t in ("mouse", "trajectory", "click", "hover", "path")):
                                ms_feats[k] = v

                    # Build session_history from recent behavioral data rows
                    # This enables Replay Detection and ADWIN Drift Detection
                    session_history = []
                    try:
                        with db.get_connection() as conn_hist:
                            hist_cursor = conn_hist.cursor()
                            hist_cursor.execute(
                                resolve_query(db,
                                    "SELECT features FROM behavioral_data "
                                    "WHERE session_id = :param "
                                    "ORDER BY timestamp ASC LIMIT 50"
                                ),
                                (session_id,),
                            )
                            _fernet_hist = None
                            try:
                                fkey_h = current_app.config.get("BACKUP_FERNET")
                                if fkey_h:
                                    from cryptography.fernet import Fernet as _Fh
                                    _fernet_hist = _Fh(fkey_h.encode("utf-8"))
                            except Exception:
                                pass

                            for hrow in hist_cursor.fetchall():
                                hfeats = None
                                hraw = hrow["features"]
                                if isinstance(hraw, str):
                                    if _fernet_hist and hraw.startswith("gAAAAA"):
                                        try:
                                            hfeats = json.loads(
                                                _fernet_hist.decrypt(hraw.encode("utf-8")).decode("utf-8")
                                            )
                                        except Exception:
                                            pass
                                    if hfeats is None and not hraw.startswith("gAAAAA"):
                                        try:
                                            hfeats = json.loads(hraw)
                                        except Exception:
                                            pass
                                elif isinstance(hraw, dict):
                                    hfeats = hraw
                                if isinstance(hfeats, dict):
                                    session_history.append(hfeats)
                    except Exception:
                        pass

                    ensemble_data = score_with_ensemble(
                        extended_features=stored_features,
                        user_id=user_id,
                        session_history=session_history or None,
                        user_baseline=user_baseline,
                        keystroke_features=ks_feats or None,
                        mouse_features=ms_feats or None,
                    )
                except Exception as exc:
                    logger.debug("Ensemble scoring failed: %s", exc)

            # 6. Cache the result in-memory for subsequent polls
            if ensemble_data or stored_features:
                _set_cached_ensemble(session_id, {
                    "ensemble": ensemble_data,
                    "features": stored_features,
                })
    except Exception as exc:
        logger.debug("Ensemble scoring skipped: %s", exc)

    # Fuse advanced ML ensemble risk with basic heuristics for risk_score
    ensemble_risk = ensemble_data.get("ensemble_risk", 0.0)
    if ensemble_risk > 0.0:
        # Fuse: 70% weight on advanced ML ensemble risk, 30% on basic heuristics
        risk_score = round(ensemble_risk * 0.7 + risk_score * 0.3, 2)
        authenticity_score = round(1.0 - risk_score, 2)

        # Recalculate risk level based on the fused score
        if risk_score >= current_app.config.get("RISK_HIGH_THRESHOLD", 0.65):
            risk_level = "high"
        elif risk_score >= current_app.config.get("RISK_MEDIUM_THRESHOLD", 0.35):
            risk_level = "medium"
        else:
            risk_level = "low"

    # ── Category Scores from Feature Engine (Phase 2) ─────────────────────
    category_scores = {}
    feature_richness = 0.0
    try:
        feat_source = stored_features  # Already loaded above
        if not feat_source:
            # Try Redis as last resort
            rc2 = get_redis()
            if rc2 and session_id:
                cached_feats2 = rc2.get(f"behavioral_features:{session_id}")
                if cached_feats2:
                    feat_source = json.loads(cached_feats2)

        if feat_source:
            from app.behavioral_feature_engine import get_behavioral_engine
            bfe = get_behavioral_engine()
            extracted = bfe.extract({"extended_features": feat_source})
            category_scores = bfe.get_category_scores(extracted)
            feature_richness = category_scores.pop("feature_richness", 0.0)
    except Exception as exc:
        logger.debug("Feature engine category scoring skipped: %s", exc)

    # ── Enrollment status (real data from passive enrollment) ─────────────
    enrollment_info = {}
    digraph_info = {}
    try:
        from app.models.passive_enrollment import get_enrollment_manager
        em = get_enrollment_manager()
        enrollment_info = em.get_enrollment_status(int(user_id))

        # ── Per-key/digraph Bayesian profile status ────────────────────────
        try:
            dgp = em._load_digraph_state(int(user_id))
            if dgp:
                digraph_info = {
                    "has_profile": True,
                    "per_key_count": len(dgp.get("per_key_hold", {})),
                    "per_digraph_count": len(dgp.get("per_digraph_flight", {})),
                    "updates_count": dgp.get("updates_count", 0),
                    "confidence": min(
                        1.0,
                        (dgp.get("updates_count", 0) / 5.0) * 0.5
                        + (len(dgp.get("per_key_hold", {})) / 20.0) * 0.3
                        + (len(dgp.get("per_digraph_flight", {})) / 30.0) * 0.2
                    ),
                    "created_at": dgp.get("created_at", ""),
                    "last_updated": dgp.get("last_updated", ""),
                }
            else:
                digraph_info = {"has_profile": False, "per_key_count": 0, "per_digraph_count": 0, "updates_count": 0, "confidence": 0}
        except Exception:
            pass
    except Exception:
        pass

    # Fallback to database stats if enrollment_info is empty or says 0 sessions completed (e.g. Redis down)
    if not enrollment_info or enrollment_info.get("sessions_completed", 0) == 0:
        try:
            stats = db.get_user_stats(int(user_id))
            active_sessions = stats.get("total_sessions", 0)
            required = enrollment_info.get("sessions_required", 5) if enrollment_info else 5
            
            enrollment_info = {
                "enrolled": active_sessions >= required,
                "sessions_completed": active_sessions,
                "sessions_required": required,
                "enrollment_phase": "active" if active_sessions >= required else "collecting"
            }
        except Exception as exc:
            logger.debug("Failed to load user stats for enrollment fallback: %s", exc)

    # Compute signal strength from actual behavioral data quality
    if feature_richness == 0.0 and total_activity > 0:
        # Multi-factor signal strength: data volume + diversity + consistency
        volume_score = min(1.0, total_activity / 50.0)  # Saturates at 50 events
        diversity_score = min(1.0, (1 if keystroke_count > 0 else 0) * 0.5 + (1 if mouse_count > 0 else 0) * 0.5)
        # Features count from synthesized/stored features as quality indicator
        feat_count = len(stored_features) if stored_features else 0
        quality_score = min(1.0, feat_count / 30.0)  # 30+ features = max quality
        feature_richness = round(min(1.0, volume_score * 0.4 + diversity_score * 0.3 + quality_score * 0.3), 2)

    # ── Persist session snapshot + risk timeline (non-blocking) ────────────
    try:
        db.store_session_snapshot(
            session_id=session_id,
            user_id=int(user_id),
            metrics={
                "keystroke_count": keystroke_count,
                "mouse_event_count": mouse_count,
                "scroll_event_count": 0,
                "risk_score": risk_score,
                "authenticity_score": authenticity_score,
                "feature_richness": feature_richness,
                "ensemble_action": ensemble_data.get("ensemble_action", "allow"),
                "ensemble_flags": ensemble_data.get("ensemble_flags", []),
                "extended_features": {},  # Skip full features to save space
            },
        )
        db.append_risk_timeline(
            session_id=session_id,
            user_id=int(user_id),
            risk_data={
                "risk_score": risk_score,
                "risk_level": risk_level,
                "trigger": "metrics_poll",
                "engine_scores": {
                    "ensemble_risk": ensemble_data.get("ensemble_risk", 0.0),
                    "duress_score": ensemble_data.get("duress_score", 0.0),
                    "liveness_score": ensemble_data.get("liveness_score", 1.0),
                    "replay_risk": ensemble_data.get("replay_risk", 0.0),
                },
                "action_taken": ensemble_data.get("ensemble_action", "allow"),
            },
        )
    except Exception as exc:
        logger.debug("Session snapshot/risk timeline save failed: %s", exc)

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
            # H-3 FIX: Surface untrained model indicator explicitly to frontend
            "is_calibrating": not session.get("calibration_complete", False),
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
                "drift_risk": ensemble_data.get("drift_risk", 0.0),
                "composite_analysis": ensemble_data.get("composite_analysis") or {},
                "synthetic_probability": ensemble_data.get("synthetic_probability", 0.0),
                "risk_attribution": ensemble_data.get("risk_attribution", {}),
                "digraph_match_score": ensemble_data.get("digraph_match_score", 0.5),
                "digraph_confidence": ensemble_data.get("digraph_confidence", 0.0),
            },
            "category_scores": category_scores,
            "feature_richness": feature_richness,
            "enrollment": enrollment_info,
            "digraph_profile": digraph_info,
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
    from datetime import datetime as _dt, timedelta, timezone

    try:
        from app.database_pg import DatabaseManager as PostgresDatabaseManager
        is_pg = isinstance(db, PostgresDatabaseManager)
    except ImportError:
        is_pg = False

    cutoff_dt = _dt.now(timezone.utc) - timedelta(minutes=window_minutes)
    cutoff = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            resolve_query(db, """SELECT timestamp, data_type, COUNT(*) AS activity
               FROM behavioral_data
               WHERE session_id = :param AND timestamp > :param
               GROUP BY timestamp, data_type ORDER BY timestamp ASC"""),
            (session_id, cutoff),
        )
        rows = cursor.fetchall()
        cursor.execute(
            resolve_query(db, """SELECT timestamp, COUNT(*) AS anomaly_count
               FROM auth_events
               WHERE user_id = :param AND event_type = 'anomaly'
                 AND timestamp > :param
               GROUP BY timestamp ORDER BY timestamp ASC"""),
            (user_id, cutoff),
        )
        anomaly_rows = cursor.fetchall()

    buckets: dict = {}
    for row in rows:
        b = str(row["timestamp"])[:16]  # Truncate to minute for bucketing
        buckets.setdefault(b, {"keystrokes": 0, "mouse_events": 0, "anomalies": 0})
        if row["data_type"] == "keystroke":
            buckets[b]["keystrokes"] = int(row["activity"])
        elif row["data_type"] == "mouse":
            buckets[b]["mouse_events"] = int(row["activity"])
    for row in anomaly_rows:
        b = str(row["timestamp"])[:16]
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
        sid = request.args.get("session_id") or request.cookies.get("session_id") or ""
        m, e = _build_session_metrics(sid)
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
            stream_with_context(iter(stream())),  # type: ignore[arg-type]
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
        pts, e = _build_trust_timeline(sid or "", pw, severity)
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
        w.writerows(pts or [])
        get_db().log_audit_evidence(
            action="trust_timeline_export",
            status="ok",
            user_id=s.get("user_id"),
            session_id=sid,
            resource="/api/session/trust-timeline.csv",
            metadata={"row_count": len(pts or []), "severity": severity},
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
                    resolve_query(db, "SELECT features FROM behavioral_data WHERE session_id = :param AND data_type = 'extended' ORDER BY timestamp DESC LIMIT 10"),
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
        from datetime import datetime, timezone

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

        uid = get_current_user_id()
        db = get_db()

        # Load streak from Redis for persistence across requests
        rc = get_redis()
        streak = 0
        if rc:
            try:
                raw = rc.get(f"anomaly_streak:{sid}")
                streak = int(raw) if raw else 0
            except Exception:
                pass

        risk = payload.get("current_risk_score", 0.5)
        streak = streak + 1 if risk > 0.6 else max(0, streak - 1)

        # Persist streak back to Redis
        if rc:
            try:
                rc.setex(f"anomaly_streak:{sid}", 3600, str(streak))
            except Exception as exc:
                logger.debug("Failed to persist anomaly streak: %s", exc)

        # ── Inject REAL anomaly event into the database ──────────────────
        # This makes simulated and real risk spikes visible to the ML
        # pipeline, trust timeline, and dashboard metrics.
        if risk > 0.6:
            try:
                db.log_auth_event(
                    user_id=uid,
                    session_id=sid,
                    event_type="anomaly",
                    event_data={
                        "source": "silent_challenge",
                        "risk_score": risk,
                        "anomaly_streak": streak,
                        "trigger": "behavioral_anomaly",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as exc:
                logger.debug("Failed to log anomaly event: %s", exc)

            # Also record in session risk timeline for the risk curve
            try:
                db.append_risk_timeline(
                    session_id=sid,
                    user_id=uid,
                    risk_data={
                        "risk_score": risk,
                        "risk_level": "high" if risk >= 0.65 else "medium",
                        "trigger": "silent_challenge",
                        "engine_scores": {
                            "injected_risk": risk,
                            "anomaly_streak": streak,
                        },
                        "action_taken": "escalated",
                    },
                )
            except Exception as exc:
                logger.debug("Failed to append risk timeline: %s", exc)

            # Invalidate cached ensemble scores so next metrics poll recalculates
            try:
                _clear_cached_ensemble(sid)
            except Exception:
                pass

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

        try:
            with db.get_connection() as conn:
                query = resolve_query(db, "UPDATE sessions SET updated_at = :param WHERE session_id = :param")
                conn.execute(
                    query,
                    (datetime.now(timezone.utc).isoformat(), sid),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to update session timestamp: %s", exc)
        db.log_audit_evidence(
            action="silent_challenge",
            status=action,
            user_id=uid,
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
