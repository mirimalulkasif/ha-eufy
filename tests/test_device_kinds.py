"""Unit tests for Mega device classification."""

from custom_components.eufy_cameras.device_kinds import classify_device


def test_doorbell_t8224():
    assert (
        classify_device(
            {
                "model": "T8224",
                "modelName": "Video Doorbell Dual",
                "name": "Front Door",
                "codec": "camera",
                "capabilities": ["video", "snapshot", "motion", "doorbell"],
            }
        )
        == "doorbell"
    )


def test_indoor_t8400():
    assert (
        classify_device(
            {
                "model": "T8400",
                "modelName": "Indoor Cam C210",
                "name": "Living Room",
                "codec": "camera",
                "capabilities": ["video", "snapshot", "motion", "camera"],
            }
        )
        == "indoor"
    )


def test_sensor_skipped():
    assert (
        classify_device(
            {
                "model": "T8900",
                "codec": "sensor",
                "capabilities": ["contact", "battery"],
            }
        )
        is None
    )
