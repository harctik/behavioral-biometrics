"""
Utility for creating a minimal CERT‑In style alert.

In a production environment you would replace the file‑write with an email,
Slack webhook, or integration with the Indian Computer Emergency Response Team
(CERT‑IN) API.  This implementation keeps the repo self‑contained and works on
any system that can write to the local filesystem.
"""

import os
import json
from datetime import datetime
from pathlib import Path

# Directory where alerts will be stored – configurable via env var.
ALERT_DIR = os.getenv("CERT_IN_ALERT_DIR", "alerts")
Path(ALERT_DIR).mkdir(parents=True, exist_ok=True)


def _format_alert(event: dict) -> str:
    """Create a plain‑text report from the *event* dictionary.

    The *event* dict is expected to contain at least the following keys:
        - ``timestamp`` (ISO‑8601 string) – when the auth attempt happened
        - ``user_id`` (int)
        - ``ip_address`` (str)
        - ``event_type`` ("failed_login" | "high_anomaly")
        - ``detail`` (str) – free‑form description of what triggered the alert
    Additional keys are appended verbatim.
    """
    lines = [
        f"CERT‑In Alert – {event.get('timestamp', datetime.utcnow().isoformat())}",
        f"User ID      : {event.get('user_id', 'N/A')}",
        f"IP Address   : {event.get('ip_address', 'N/A')}",
        f"Event Type   : {event.get('event_type', 'N/A')}",
        f"Detail       : {event.get('detail', 'N/A')}",
        "--- Additional Data ---",
    ]
    # Append any extra information (e.g., anomaly_score)
    for k, v in event.items():
        if k in {"timestamp", "user_id", "ip_address", "event_type", "detail"}:
            continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def send_cert_in_alert(event: dict) -> Path:
    """Write a CERT‑In style alert to ``ALERT_DIR`` and return the file path.

    The function is fire‑and‑forget – any IO error is logged to stdout but
    does not raise an exception, ensuring the auth flow is never blocked.
    """
    try:
        # Ensure a timestamp is present for the filename
        event.setdefault("timestamp", datetime.utcnow().isoformat())
        filename = (
            f"cert_in_{event['user_id']}_{int(datetime.utcnow().timestamp())}.txt"
        )
        filepath = Path(ALERT_DIR) / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(_format_alert(event))
        print(f"[CERT‑In] Alert written to {filepath}")
        return filepath
    except Exception as exc:  # pragma: no cover – defensive logging only
        print(f"[CERT‑In] Failed to write alert: {exc}")
        return Path()
