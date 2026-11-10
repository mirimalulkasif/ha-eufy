"""Constants for Eufy Cameras."""

from datetime import timedelta

DOMAIN = "eufy_cameras"
PLATFORMS = ["binary_sensor", "switch", "camera", "sensor"]

CONF_HOST = "host"
CONF_PORT = "port"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3000
DEFAULT_SCHEMA = 13

SCAN_INTERVAL = timedelta(seconds=30)

# DeviceType values from eufy-security-client
DOORBELL_TYPES = {
    5,  # DOORBELL
    7,  # BATTERY_DOORBELL
    16,  # BATTERY_DOORBELL_2
    91,  # BATTERY_DOORBELL_PLUS
    93,  # DOORBELL_SOLO
    94,  # BATTERY_DOORBELL_PLUS_E340
    95,  # BATTERY_DOORBELL_C30
    96,  # BATTERY_DOORBELL_C31
}

INDOOR_TYPES = {
    30,  # INDOOR_CAMERA
    31,  # INDOOR_PT_CAMERA
    34,  # INDOOR_CAMERA_1080
    35,  # INDOOR_PT_CAMERA_1080
    100,  # INDOOR_COST_DOWN_CAMERA
    104,  # INDOOR_PT_CAMERA_S350
    105,  # INDOOR_PT_CAMERA_E30
    10008,  # INDOOR_PT_CAMERA_C220
    10009,  # INDOOR_PT_CAMERA_C210
    10010,  # INDOOR_PT_CAMERA_C220_V2
    10011,  # INDOOR_PT_CAMERA_C220_V3
}

ATTR_KIND = "kind"
ATTR_SERIAL = "serial"
ATTR_MODEL = "model"
