"""Constants for Eufy Cameras."""

from datetime import timedelta

DOMAIN = "eufy_cameras"
PLATFORMS = ["binary_sensor", "switch", "camera", "sensor"]

CONF_HOST = "host"
CONF_PORT = "port"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3000

# Mega SDK bridge WebSocket path (ha-eufy-sdk-bridge)
WS_PATH = "/ws"

SCAN_INTERVAL = timedelta(seconds=30)

ATTR_KIND = "kind"
ATTR_SERIAL = "serial"
ATTR_MODEL = "model"

# Model prefixes used by the Homebridge plugin for the same devices.
DOORBELL_MODEL_PREFIXES = ("T82",)
INDOOR_MODEL_PREFIXES = ("T84",)
