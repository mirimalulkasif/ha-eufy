"""Camera entities for Eufy doorbell / indoor devices (Mega bridge)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EufyConfigEntry
from .const import ATTR_KIND, ATTR_MODEL, ATTR_SERIAL, DOMAIN
from .coordinator import EufyCamerasCoordinator
from .mega_client import EufyMegaError

_LOGGER = logging.getLogger(__name__)


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
    """Camera with Mega-bridge snapshots and RTSP stream source."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self, coordinator: EufyCamerasCoordinator, serial: str
    ) -> None:
        super().__init__(coordinator)
        Camera.__init__(self)
        self.serial = serial
        self._attr_unique_id = f"eufy_cameras_{serial}_camera"
        self._last_image: bytes | None = None

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
        model_name = data.get("model_name")
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=data.get("name") or self.serial,
            manufacturer="Eufy",
            model=str(model_name or data.get("model") or kind),
            serial_number=self.serial,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.device_data
        return {
            ATTR_SERIAL: self.serial,
            ATTR_KIND: data.get("kind"),
            ATTR_MODEL: data.get("model"),
            "power": data.get("power"),
            "capabilities": data.get("capabilities"),
        }

    @property
    def is_streaming(self) -> bool:
        return bool(self.device_data.get("streaming"))

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch a JPEG still from the Mega bridge."""
        try:
            data = await self.coordinator.client.fetch_snapshot(
                self.serial, mode="stored"
            )
        except EufyMegaError as err:
            _LOGGER.debug("Snapshot failed for %s: %s", self.serial, err)
            return self._last_image
        if data:
            self._last_image = data
            return data
        return self._last_image

    async def stream_source(self) -> str | None:
        """Return RTSP URL from the bridge / go2rtc."""
        try:
            result = await self.coordinator.client.stream_urls(self.serial)
        except EufyMegaError as err:
            _LOGGER.debug("stream.start failed for %s: %s", self.serial, err)
            return None
        rtsp = result.get("rtsp")
        if rtsp:
            return str(rtsp)
        # Fall back to rewriting the HTTP path against the configured host
        path = result.get("path") or self.device_data.get("stream_path")
        if path:
            host = self.coordinator.client.host
            port = self.coordinator.client.port
            return f"http://{host}:{port}{path}"
        return None
