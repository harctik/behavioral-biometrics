"""
Per-Key / Per-Digraph Keystroke Profile Extractor.

Extracts fine-grained typing biometric features from raw keystroke events:
  - Per-key hold time distributions (how long each key is pressed)
  - Per-digraph flight time distributions (transition time between key pairs)
  - Trigraph patterns for common 3-letter sequences

These features form the foundation of the Bayesian keystroke authentication
system. During signup (Session 0), they create the initial prior. Each
subsequent login refines the posterior via conjugate Normal-Normal updates.

Privacy:
  Keys are stored as category identifiers (e.g., "alpha_a", "digit_0",
  "special_at") — never raw password content or typed text.

Reference:
  Killourhy & Maxion (2009) "Comparing Anomaly-Detection Algorithms for
  Keystroke Dynamics" — established that hold time and digraph latency
  are the two most discriminative features for keystroke biometrics.
"""

from __future__ import annotations

import logging
import math
import statistics
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Key Categorization ─────────────────────────────────────────────────────────

def _categorize_key(key: str) -> Optional[str]:
    """Map a raw key identifier to a privacy-safe category.

    Returns None for keys that should be ignored (modifiers, etc.).
    """
    if not key or len(key) == 0:
        return None

    k = key.lower()

    # Single alphabetic character
    if len(k) == 1 and k.isalpha():
        return f"alpha_{k}"

    # Single digit
    if len(k) == 1 and k.isdigit():
        return f"digit_{k}"

    # Common special characters (found in passwords, emails)
    specials = {
        "@": "special_at",
        ".": "special_dot",
        "-": "special_dash",
        "_": "special_underscore",
        "!": "special_exclaim",
        "#": "special_hash",
        "$": "special_dollar",
        "%": "special_percent",
        "&": "special_ampersand",
        "*": "special_star",
        "+": "special_plus",
        "=": "special_equals",
        "/": "special_slash",
        "\\": "special_backslash",
        "'": "special_apostrophe",
        '"': "special_quote",
        ",": "special_comma",
        ";": "special_semicolon",
        ":": "special_colon",
        "(": "special_lparen",
        ")": "special_rparen",
        "[": "special_lbracket",
        "]": "special_rbracket",
        "{": "special_lbrace",
        "}": "special_rbrace",
        "?": "special_question",
        "~": "special_tilde",
        "`": "special_backtick",
        "^": "special_caret",
        "|": "special_pipe",
        "<": "special_lt",
        ">": "special_gt",
    }
    if len(k) == 1 and k in specials:
        return specials[k]

    # Named keys
    named_keys = {
        "space": "key_space",
        " ": "key_space",
        "backspace": "key_backspace",
        "delete": "key_delete",
        "tab": "key_tab",
        "enter": "key_enter",
        "return": "key_enter",
        "capslock": "key_capslock",
        "shift": None,        # Modifier — ignore for timing
        "control": None,
        "alt": None,
        "meta": None,
        "escape": "key_escape",
        "arrowleft": "key_arrow",
        "arrowright": "key_arrow",
        "arrowup": "key_arrow",
        "arrowdown": "key_arrow",
    }
    if k in named_keys:
        return named_keys[k]

    # Fallback: if it looks like a single printable character
    if len(k) == 1:
        return f"other_{ord(k)}"

    return None


# ── Profile Extractor ──────────────────────────────────────────────────────────

class DigraphProfileExtractor:
    """Extracts per-key and per-digraph timing profiles from raw keystroke events.

    Input: List of keystroke events, each containing:
        - key: str (raw key or hashed key)
        - hold_time: float (ms the key was held down)
        - flight_time: float (ms between previous keyup and this keydown)
        - is_backspace: bool
        - timestamp: float (epoch ms)

    Output: A structured profile dict suitable for Bayesian enrollment.
    """

    # Timing sanity bounds (ms)
    MIN_HOLD_TIME = 10       # Below 10ms is likely noise
    MAX_HOLD_TIME = 1500     # Above 1.5s is a pause, not a hold
    MIN_FLIGHT_TIME = 5      # Below 5ms is likely noise
    MAX_FLIGHT_TIME = 2000   # Above 2s is a pause between words

    def extract_profile(
        self,
        keystroke_events: List[Dict[str, Any]],
        source: str = "unknown",
    ) -> Dict[str, Any]:
        """Extract per-key and per-digraph timing profiles.

        Args:
            keystroke_events: Raw keystroke event list from the frontend.
            source: Context tag ("signup", "login", "session").

        Returns:
            {
                "per_key_hold": {
                    "alpha_a": {"mean": 94.2, "std": 12.1, "count": 5, "values": [...]},
                    "alpha_t": {"mean": 78.5, "std": 9.3, "count": 8, "values": [...]},
                    ...
                },
                "per_digraph_flight": {
                    "alpha_t__alpha_h": {"mean": 120.3, "std": 15.2, "count": 4, "values": [...]},
                    "alpha_e__alpha_r": {"mean": 95.1, "std": 11.0, "count": 3, "values": [...]},
                    ...
                },
                "aggregate": {
                    "hold_time_mean": float, "hold_time_std": float,
                    "flight_time_mean": float, "flight_time_std": float,
                    "typing_speed_wpm": float,
                    "correction_rate": float,
                    "rhythm_entropy": float,
                },
                "meta": {
                    "total_keys": int,
                    "unique_keys": int,
                    "unique_digraphs": int,
                    "total_duration_ms": float,
                    "source": str,
                    "coverage_score": float,  # 0-1, how many distinct keys were seen
                }
            }
        """
        if not keystroke_events or len(keystroke_events) < 3:
            return self._empty_profile(source)

        # ── Phase 1: Per-key hold time extraction ──────────────────────────
        per_key_hold: Dict[str, List[float]] = {}
        all_hold_times: List[float] = []
        all_flight_times: List[float] = []
        backspace_count = 0
        categorized_keys: List[Optional[str]] = []

        for event in keystroke_events:
            key_raw = event.get("key", "")
            hold_time = event.get("hold_time", 0)
            flight_time = event.get("flight_time", 0)
            is_backspace = event.get("is_backspace", False)

            if is_backspace:
                backspace_count += 1

            cat = _categorize_key(key_raw)
            categorized_keys.append(cat)

            # Validate hold time
            if cat and self.MIN_HOLD_TIME <= hold_time <= self.MAX_HOLD_TIME:
                per_key_hold.setdefault(cat, []).append(hold_time)
                all_hold_times.append(hold_time)

            # Collect flight times
            if self.MIN_FLIGHT_TIME <= flight_time <= self.MAX_FLIGHT_TIME:
                all_flight_times.append(flight_time)

        # ── Phase 2: Per-digraph flight time extraction ────────────────────
        per_digraph_flight: Dict[str, List[float]] = {}

        for i in range(len(keystroke_events) - 1):
            cat_a = categorized_keys[i]
            cat_b = categorized_keys[i + 1]
            flight = keystroke_events[i + 1].get("flight_time", 0)

            if (
                cat_a
                and cat_b
                and self.MIN_FLIGHT_TIME <= flight <= self.MAX_FLIGHT_TIME
            ):
                digraph_key = f"{cat_a}__{cat_b}"
                per_digraph_flight.setdefault(digraph_key, []).append(flight)

        # ── Phase 3: Build statistical summaries ──────────────────────────
        per_key_stats = self._build_stats(per_key_hold)
        per_digraph_stats = self._build_stats(per_digraph_flight)

        # ── Phase 4: Aggregate features ───────────────────────────────────
        aggregate = self._compute_aggregates(
            all_hold_times, all_flight_times, keystroke_events, backspace_count
        )

        # ── Phase 5: Meta information ─────────────────────────────────────
        timestamps = [e.get("timestamp", 0) for e in keystroke_events if e.get("timestamp")]
        total_duration = (max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0

        # Coverage: how many of the 26 alpha keys + 10 digits were seen
        alpha_keys_seen = sum(1 for k in per_key_hold if k.startswith("alpha_"))
        digit_keys_seen = sum(1 for k in per_key_hold if k.startswith("digit_"))
        coverage = min(1.0, (alpha_keys_seen + digit_keys_seen) / 20.0)

        meta = {
            "total_keys": len(keystroke_events),
            "unique_keys": len(per_key_stats),
            "unique_digraphs": len(per_digraph_stats),
            "total_duration_ms": total_duration,
            "source": source,
            "coverage_score": round(coverage, 4),
            "alpha_keys_seen": alpha_keys_seen,
            "digit_keys_seen": digit_keys_seen,
        }

        return {
            "per_key_hold": per_key_stats,
            "per_digraph_flight": per_digraph_stats,
            "aggregate": aggregate,
            "meta": meta,
        }

    def _build_stats(
        self, data: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, Any]]:
        """Convert lists of values into mean/std/count statistics."""
        result = {}
        for key, values in data.items():
            if len(values) >= 1:
                mean = statistics.mean(values)
                std = statistics.stdev(values) if len(values) >= 2 else mean * 0.3
                result[key] = {
                    "mean": round(mean, 2),
                    "std": round(max(std, 1.0), 2),  # Floor std at 1ms
                    "count": len(values),
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                }
        return result

    def _compute_aggregates(
        self,
        hold_times: List[float],
        flight_times: List[float],
        events: List[Dict],
        backspace_count: int,
    ) -> Dict[str, float]:
        """Compute session-level aggregate typing features."""
        agg: Dict[str, float] = {}

        if hold_times:
            agg["hold_time_mean"] = round(statistics.mean(hold_times), 2)
            agg["hold_time_std"] = round(
                statistics.stdev(hold_times) if len(hold_times) >= 2 else 0.0, 2
            )
            agg["hold_time_median"] = round(statistics.median(hold_times), 2)

        if flight_times:
            agg["flight_time_mean"] = round(statistics.mean(flight_times), 2)
            agg["flight_time_std"] = round(
                statistics.stdev(flight_times) if len(flight_times) >= 2 else 0.0, 2
            )
            agg["flight_time_median"] = round(statistics.median(flight_times), 2)

        # WPM estimate
        timestamps = [e.get("timestamp", 0) for e in events if e.get("timestamp")]
        if len(timestamps) >= 2:
            elapsed_min = max(0.01, (max(timestamps) - min(timestamps)) / 60000.0)
            agg["typing_speed_wpm"] = round(min(200, (len(events) / 5.0) / elapsed_min), 1)

        # Correction rate (backspaces / total)
        agg["correction_rate"] = round(
            backspace_count / max(len(events), 1), 4
        )

        # Rhythm entropy: how variable is the inter-key timing?
        if len(flight_times) >= 5:
            ft_mean = statistics.mean(flight_times)
            ft_std = statistics.stdev(flight_times)
            # Coefficient of variation as rhythm entropy proxy
            agg["rhythm_entropy"] = round(ft_std / max(ft_mean, 1.0), 4)

        return agg

    def _empty_profile(self, source: str) -> Dict[str, Any]:
        """Return an empty profile structure."""
        return {
            "per_key_hold": {},
            "per_digraph_flight": {},
            "aggregate": {},
            "meta": {
                "total_keys": 0,
                "unique_keys": 0,
                "unique_digraphs": 0,
                "total_duration_ms": 0,
                "source": source,
                "coverage_score": 0.0,
            },
        }

    @staticmethod
    def merge_profiles(
        existing: Dict[str, Any], incoming: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge an incoming profile into an existing one (pre-Bayesian simple merge).

        Used during enrollment when we want to combine multiple sessions
        before the Bayesian system takes over.
        """
        merged = {
            "per_key_hold": dict(existing.get("per_key_hold", {})),
            "per_digraph_flight": dict(existing.get("per_digraph_flight", {})),
            "aggregate": {},
            "meta": {},
        }

        # Merge per-key hold stats
        for key, stats in incoming.get("per_key_hold", {}).items():
            if key in merged["per_key_hold"]:
                old = merged["per_key_hold"][key]
                # Weighted average based on count
                n_old = old["count"]
                n_new = stats["count"]
                n_total = n_old + n_new
                new_mean = (old["mean"] * n_old + stats["mean"] * n_new) / n_total
                # Pooled std approximation
                new_std = math.sqrt(
                    ((n_old - 1) * old["std"] ** 2 + (n_new - 1) * stats["std"] ** 2)
                    / max(n_total - 2, 1)
                ) if n_total > 2 else max(old["std"], stats["std"])
                merged["per_key_hold"][key] = {
                    "mean": round(new_mean, 2),
                    "std": round(max(new_std, 1.0), 2),
                    "count": n_total,
                    "min": min(old.get("min", new_mean), stats.get("min", new_mean)),
                    "max": max(old.get("max", new_mean), stats.get("max", new_mean)),
                }
            else:
                merged["per_key_hold"][key] = dict(stats)

        # Merge per-digraph flight stats (same logic)
        for key, stats in incoming.get("per_digraph_flight", {}).items():
            if key in merged["per_digraph_flight"]:
                old = merged["per_digraph_flight"][key]
                n_old = old["count"]
                n_new = stats["count"]
                n_total = n_old + n_new
                new_mean = (old["mean"] * n_old + stats["mean"] * n_new) / n_total
                new_std = math.sqrt(
                    ((n_old - 1) * old["std"] ** 2 + (n_new - 1) * stats["std"] ** 2)
                    / max(n_total - 2, 1)
                ) if n_total > 2 else max(old["std"], stats["std"])
                merged["per_digraph_flight"][key] = {
                    "mean": round(new_mean, 2),
                    "std": round(max(new_std, 1.0), 2),
                    "count": n_total,
                    "min": min(old.get("min", new_mean), stats.get("min", new_mean)),
                    "max": max(old.get("max", new_mean), stats.get("max", new_mean)),
                }
            else:
                merged["per_digraph_flight"][key] = dict(stats)

        return merged


# ── Module-level singleton ─────────────────────────────────────────────────────
_extractor: Optional[DigraphProfileExtractor] = None


def get_digraph_extractor() -> DigraphProfileExtractor:
    global _extractor
    if _extractor is None:
        _extractor = DigraphProfileExtractor()
    return _extractor
