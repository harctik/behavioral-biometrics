"""
Device Intelligence Engine — RAT/Emulator/Spoofing Detection.

Processes Category 7 device signals for:
- Remote Access Tool (RAT) detection via latency anomalies
- Emulator detection via hardware fingerprint
- Device spoofing detection
- Geo-velocity (impossible travel)
- Agentic browser detection (AI agent vs human)
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DeviceIntelligenceEngine:
    """Scores device & contextual signals for fraud indicators."""

    # Known suspicious WebGL renderers
    EMULATOR_RENDERERS = {
        "swiftshader",
        "llvmpipe",
        "mesa",
        "generic",
        "virgl",
        "softpipe",
        "lavapipe",
    }

    def __init__(self):
        self.device_history: Dict[int, list] = {}  # user_id -> device records
        self.session_geos: Dict[int, list] = {}  # user_id -> geo+time records

    def analyze(
        self,
        device_features: Dict[str, Any],
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Full device intelligence analysis.

        Returns:
            {
                "device_risk": float,
                "rat_score": float,
                "emulator_score": float,
                "spoofing_score": float,
                "new_device": bool,
                "device_trust_score": float,
                "time_anomaly": bool,
                "geo_velocity_risk": float,
                "agentic_browser_score": float,
                "flags": list[str],
            }
        """
        flags: list[str] = []

        rat_score = self._detect_rat(device_features, flags)
        emulator_score = self._detect_emulator(device_features, flags)
        spoofing_score = self._detect_spoofing(device_features, flags)
        time_anomaly = self._check_time_anomaly(device_features, user_id, flags)
        geo_risk = self._check_geo_velocity(user_id, ip_address, flags)
        new_device = self._check_new_device(device_features, user_id, flags)
        agentic_score = self._detect_agentic_browser(device_features, flags)

        # Device trust score (built over time)
        trust = self._compute_trust(user_id, device_features)

        # Combined device risk
        device_risk = (
            max(rat_score, emulator_score, spoofing_score, geo_risk) * 0.7
            + (1 - trust) * 0.15
            + (0.15 if new_device else 0)
            + agentic_score * 0.1
        )

        # Store device record for future comparisons
        if user_id:
            self._store_device_record(user_id, device_features, ip_address)

        return {
            "device_risk": round(min(1.0, device_risk), 4),
            "rat_score": round(rat_score, 4),
            "emulator_score": round(emulator_score, 4),
            "spoofing_score": round(spoofing_score, 4),
            "new_device": new_device,
            "device_trust_score": round(trust, 4),
            "time_anomaly": time_anomaly,
            "geo_velocity_risk": round(geo_risk, 4),
            "agentic_browser_score": round(agentic_score, 4),
            "flags": flags,
        }

    def _detect_rat(self, f: Dict, flags: list) -> float:
        """Detect Remote Access Tools via latency and behavioral mismatch."""
        risk = 0.0
        rat_latency = f.get("rat_latency_score", 0)

        if rat_latency > 0.6:
            risk += 0.7
            flags.append(f"device:high_rat_latency({rat_latency:.2f})")
        elif rat_latency > 0.3:
            risk += 0.3
            flags.append(f"device:elevated_rat_latency({rat_latency:.2f})")

        # RTT anomaly from connection info
        rtt = f.get("connection_rtt", 0)
        if rtt > 500:  # >500ms RTT = suspicious
            risk += 0.2
            flags.append(f"device:high_rtt({rtt}ms)")

        return min(1.0, risk)

    def _detect_emulator(self, f: Dict, flags: list) -> float:
        """Detect emulated environments."""
        risk = f.get("emulator_score", 0)

        renderer = (f.get("webgl_renderer", "") or "").lower()
        if any(emu in renderer for emu in self.EMULATOR_RENDERERS):
            risk = max(risk, 0.7)
            flags.append(f"device:emulator_renderer({renderer[:40]})")

        # Zero device memory = suspicious
        if f.get("device_memory", 0) == 0 and f.get("max_touch_points", 0) > 0:
            risk += 0.2
            flags.append("device:zero_memory_mobile — emulator?")

        return min(1.0, risk)

    def _detect_spoofing(self, f: Dict, flags: list) -> float:
        """Detect user-agent or device fingerprint spoofing."""
        risk = 0.0
        ua = f.get("user_agent", "")
        platform = f.get("platform", "")
        touch = f.get("max_touch_points", 0)

        # Mobile UA but no touch points
        if ("Mobile" in ua or "Android" in ua) and touch == 0:
            risk += 0.4
            flags.append("device:mobile_ua_no_touch — spoofed UA")

        # Desktop UA but has touch points > 1
        if "Windows" in ua and touch > 5:
            risk += 0.3
            flags.append("device:desktop_ua_high_touch — spoofed device")

        # Canvas hash mismatch (would compare to stored)
        canvas = f.get("canvas_hash", "")
        if canvas == "0":
            risk += 0.2
            flags.append("device:canvas_blocked — privacy mode or bot")

        return min(1.0, risk)

    def _check_time_anomaly(self, f: Dict, user_id: Optional[int], flags: list) -> bool:
        """Check if login is at an unusual time for this user."""
        hour = f.get("login_hour", datetime.now().hour)
        # Simple: 1-5 AM is suspicious for most users
        if 1 <= hour <= 5:
            flags.append(f"device:unusual_hour({hour}:00)")
            return True

        if user_id and user_id in self.device_history:
            history = self.device_history[user_id]
            hours = [h.get("login_hour", 12) for h in history[-20:]]
            if hours:
                mean_hour = sum(hours) / len(hours)
                if abs(hour - mean_hour) > 6:
                    flags.append(
                        f"device:time_deviation(current={hour}, "
                        f"usual={mean_hour:.0f})"
                    )
                    return True
        return False

    def _check_geo_velocity(
        self, user_id: Optional[int], ip: Optional[str], flags: list
    ) -> float:
        """Check for impossible travel between sessions."""
        if not user_id or not ip:
            return 0.0

        # Would use IP geolocation in production
        # For now, flag if IP changes rapidly between sessions
        if user_id in self.session_geos:
            recent = self.session_geos[user_id]
            if recent and recent[-1].get("ip") != ip:
                time_diff = time.time() - recent[-1].get("time", 0)
                if time_diff < 300:  # <5 min between different IPs
                    flags.append("device:impossible_travel — IP changed too fast")
                    return 0.7

        # Store for future comparison
        if user_id not in self.session_geos:
            self.session_geos[user_id] = []
        self.session_geos[user_id].append({"ip": ip, "time": time.time()})
        if len(self.session_geos[user_id]) > 50:
            self.session_geos[user_id] = self.session_geos[user_id][-30:]

        return 0.0

    def _check_new_device(self, f: Dict, user_id: Optional[int], flags: list) -> bool:
        """Check if this is a never-before-seen device for the user."""
        if not user_id:
            return True

        fingerprint = self._compute_fingerprint(f)
        history = self.device_history.get(user_id, [])
        known_fps = {h.get("fingerprint") for h in history}

        if fingerprint not in known_fps:
            flags.append("device:new_device — never seen before")
            return True
        return False

    def _detect_agentic_browser(self, f: Dict, flags: list) -> float:
        """Detect AI agent/automated browser behavior (2026 feature)."""
        risk = 0.0
        ua = f.get("user_agent", "")

        # Known agent signatures
        agent_markers = [
            "HeadlessChrome",
            "Puppeteer",
            "Playwright",
            "PhantomJS",
            "Selenium",
            "WebDriver",
        ]
        for marker in agent_markers:
            if marker.lower() in ua.lower():
                risk += 0.8
                flags.append(f"device:agentic_browser({marker})")
                break

        # Zero concurrent = webdriver
        if f.get("hardware_concurrency", 0) == 0:
            risk += 0.3
            flags.append("device:zero_concurrency — headless?")

        return min(1.0, risk)

    def _compute_trust(self, user_id: Optional[int], f: Dict) -> float:
        """Compute device trust score from history."""
        if not user_id or user_id not in self.device_history:
            return 0.3  # New device = low trust

        fingerprint = self._compute_fingerprint(f)
        history = self.device_history.get(user_id, [])
        matches = sum(1 for h in history if h.get("fingerprint") == fingerprint)

        # More logins from same device = higher trust
        if matches >= 10:
            return 0.95
        elif matches >= 5:
            return 0.8
        elif matches >= 2:
            return 0.6
        return 0.4

    def _compute_fingerprint(self, f: Dict) -> str:
        """Generate device fingerprint hash."""
        components = [
            str(f.get("screen_width", "")),
            str(f.get("screen_height", "")),
            str(f.get("screen_depth", "")),
            str(f.get("hardware_concurrency", "")),
            str(f.get("device_memory", "")),
            str(f.get("timezone", "")),
            str(f.get("language", "")),
            str(f.get("webgl_renderer", "")),
            str(f.get("canvas_hash", "")),
        ]
        raw = "|".join(components)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _store_device_record(self, user_id: int, f: Dict, ip: Optional[str]):
        """Store device fingerprint for future comparison."""
        if user_id not in self.device_history:
            self.device_history[user_id] = []

        self.device_history[user_id].append(
            {
                "fingerprint": self._compute_fingerprint(f),
                "login_hour": f.get("login_hour", 0),
                "login_day": f.get("login_day", 0),
                "ip": ip,
                "time": time.time(),
            }
        )

        # Keep last 100 records
        if len(self.device_history[user_id]) > 100:
            self.device_history[user_id] = self.device_history[user_id][-70:]


# ── Singleton ─────────────────────────────────────────────────────────────────
_device_engine: DeviceIntelligenceEngine | None = None


def get_device_engine() -> DeviceIntelligenceEngine:
    global _device_engine
    if _device_engine is None:
        _device_engine = DeviceIntelligenceEngine()
    return _device_engine
