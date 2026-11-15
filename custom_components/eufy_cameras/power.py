"""Helpers for battery vs wired Mega cameras."""

from __future__ import annotations

from typing import Any


def on_battery_power(record: dict[str, Any] | None) -> bool:
    """Return True when the bridge says this camera is battery-powered."""
    record = record or {}
    power = record.get("power")
    if power in ("battery", "wired"):
        return power == "battery"
    caps = record.get("capabilities") or []
    props = record.get("properties") or {}
    return "battery" in caps and props.get("battery") is not None


def skip_ha_hls_worker(record: dict[str, Any] | None) -> bool:
    """Doorbells + battery cams must not use HA's HLS stream worker.

    That worker reconnects forever when a feed drops. Mega doorbell RTC and
    battery budgets drop often, which becomes Idle↔Streaming spam and drains
    batteries. Returning no Stream makes HA use go2rtc WebRTC on the RTSP URL
    instead (same approach as mega-yfue/ha-eufy-sdk).
    """
    record = record or {}
    if record.get("kind") == "doorbell":
        return True
    return on_battery_power(record)
