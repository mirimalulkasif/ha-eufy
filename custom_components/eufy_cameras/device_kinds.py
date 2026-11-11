"""Classify Mega bridge devices as doorbell / indoor (same rules as hb-eufy)."""

from __future__ import annotations

from typing import Any

from .const import DOORBELL_MODEL_PREFIXES, INDOOR_MODEL_PREFIXES


def classify_device(device: dict[str, Any]) -> str | None:
    """Return 'doorbell' | 'indoor' | None for unsupported devices."""
    model = str(device.get("model") or "").upper()
    name = str(device.get("name") or "").lower()
    codec = str(device.get("codec") or "").lower()
    caps = {str(c).lower() for c in (device.get("capabilities") or [])}

    if any(model.startswith(p) for p in DOORBELL_MODEL_PREFIXES) or "doorbell" in name:
        return "doorbell"
    if "doorbell" in caps and codec in ("camera", "doorbell", ""):
        return "doorbell"

    if any(model.startswith(p) for p in INDOOR_MODEL_PREFIXES):
        return "indoor"
    if "indoor" in name or "pan" in name:
        return "indoor"
    if codec == "camera" and ("camera" in caps or "video" in caps or "snapshot" in caps):
        # Generic Mega camera — treat as indoor for this lean integration.
        return "indoor"
    return None
