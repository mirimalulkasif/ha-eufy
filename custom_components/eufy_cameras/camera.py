"""Camera entities for Eufy doorbell / indoor devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EufyConfigEntry
from .const import ATTR_KIND, ATTR_MODEL, ATTR_SERIAL, DOMAIN
from .coordinator import EufyCamerasCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        EufyCamera(coordinator, serial) for serial in coordinator.data
    )


class EufyCamera(CoordinatorEntity[EufyCamerasCoordinator], Camera):
    """Placeholder camera entity representing the Eufy device.

    Live RTSP/WebRTC streaming is left to the eufy-security-ws add-on /
    go2rtc when configured. This entity exposes the device in the camera
    domain so automations and dashboards can reference it.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature(0)

    def __init__(
        self, coordinator: EufyCamerasCoordinator, serial: str
    ) -> None:
        super().__init__(coordinator)
        Camera.__init__(self)
        self.serial = serial
        self._attr_unique_id = f"eufy_cameras_{serial}_camera"

    @property
    def device_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self.serial, {})

    @property
    def available(self) -> bool:
        return self.serial in self.coordinator.data and super().available

    @property
    def device_info(self) -> DeviceInfo:
        data = self.device_data
        kind = data.get("kind", "camera")
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=data.get("name") or self.serial,
            manufacturer="Eufy",
            model=str(data.get("model") or kind),
            serial_number=self.serial,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.device_data
        return {
            ATTR_SERIAL: self.serial,
            ATTR_KIND: data.get("kind"),
            ATTR_MODEL: data.get("model"),
        }

    @property
    def is_streaming(self) -> bool:
        return False

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """No snapshot API in this lean client — return None."""
        return None
