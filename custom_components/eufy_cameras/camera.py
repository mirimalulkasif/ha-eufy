"""Camera entities for Eufy doorbell / indoor devices (Mega bridge)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
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
    devices = list(coordinator.data)
    _LOGGER.info("Setting up %s camera entit(y/ies)", len(devices))
    entities: list[EufyCamera] = []
    for serial in devices:
        try:
            entities.append(EufyCamera(coordinator, serial))
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to create camera entity for %s", serial)
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.warning("No camera entities were created")


class EufyCamera(CoordinatorEntity[EufyCamerasCoordinator], Camera):
    """Indoor: live RTSP via go2rtc. Doorbell: push/stored stills (no broken live)."""

    _attr_has_entity_name = True
    # Explicit name so the device page shows a row labeled "Camera"
    # (name=None makes the entity inherit only the device name and is easy to miss).
    _attr_name = "Camera"
    _attr_entity_registry_enabled_default = True

    def __init__(
        self, coordinator: EufyCamerasCoordinator, serial: str
    ) -> None:
        # CoordinatorEntity does not call Entity/Camera __init__ — must init Camera.
        super().__init__(coordinator)
        Camera.__init__(self)
        self.serial = serial
        self._attr_unique_id = f"eufy_cameras_{serial}_camera"
        self._last_image: bytes | None = None
        kind = (coordinator.data.get(serial) or {}).get("kind")
        # Doorbells (T82xx): stills only — live Mega feeds are often black.
        if kind == "doorbell":
            self._attr_supported_features = CameraEntityFeature(0)
            self._attr_icon = "mdi:doorbell-video"
            self._stills_only = True
        else:
            self._attr_supported_features = CameraEntityFeature.STREAM
            self._attr_icon = "mdi:cctv"
            self._stills_only = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.client.on_event(self._handle_event)
        # Warm the first still so the entity is not stuck on "Idle / no image".
        self.hass.async_create_task(self._prefetch_still())

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
            "stream_mode": "stills" if self._stills_only else "live",
        }

    @property
    def is_streaming(self) -> bool:
        if self._stills_only:
            return False
        return bool(self.device_data.get("streaming"))

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch a JPEG still from the Mega bridge."""
        client = self.coordinator.client
        # Re-probe media host if earlier snapshots never worked.
        if self._last_image is None:
            await client.resolve_media_host()

        for mode in ("stored", "", "live"):
            try:
                data = await client.fetch_snapshot(self.serial, mode=mode)
            except EufyMegaError as err:
                _LOGGER.debug(
                    "Snapshot %s mode=%r failed: %s",
                    self.serial,
                    mode or "auto",
                    err,
                )
                continue
            if data:
                self._last_image = data
                return data

        try:
            data = await client.fetch_event_image(self.serial)
            if data:
                self._last_image = data
                return data
        except EufyMegaError as err:
            _LOGGER.debug("event-image failed for %s: %s", self.serial, err)

        try:
            await client.command("event.refresh", sn=self.serial)
            data = await client.fetch_snapshot(self.serial, mode="stored")
            if data:
                self._last_image = data
                return data
            data = await client.fetch_event_image(self.serial)
            if data:
                self._last_image = data
                return data
        except EufyMegaError as err:
            _LOGGER.debug(
                "event.refresh/snapshot failed for %s: %s", self.serial, err
            )

        if self._last_image is None:
            _LOGGER.warning(
                "No still for %s from %s — trigger motion/ring once, or set the "
                "integration host to the VM LAN IP (not 127.0.0.1) so HA can reach "
                "bridge snapshots",
                self.serial,
                client.base_url,
            )
        return self._last_image

    async def stream_source(self) -> str | None:
        """Return RTSP URL from the bridge / go2rtc (indoor / live devices only)."""
        if self._stills_only:
            return None
        try:
            result = await self.coordinator.client.stream_urls(self.serial)
        except EufyMegaError as err:
            _LOGGER.debug("stream.start failed for %s: %s", self.serial, err)
            return None
        rtsp = result.get("rtsp")
        if rtsp:
            return self._rewrite_loopback_host(str(rtsp))
        path = result.get("path") or self.device_data.get("stream_path")
        if path:
            host = self.coordinator.client.host
            port = self.coordinator.client.port
            return f"http://{host}:{port}{path}"
        return None

    def _rewrite_loopback_host(self, url: str) -> str:
        """Point RTSP at a host HA Core can reach, not the bridge's 127.0.0.1."""
        parsed = urlparse(url)
        if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            return url
        host = self.coordinator.client.media_host or self.coordinator.client.host
        if not host:
            return url
        port = parsed.port
        netloc = f"{host}:{port}" if port else host
        return urlunparse(parsed._replace(netloc=netloc))

    @callback
    def _handle_event(self, event: dict) -> None:
        """Refresh stills when motion or ring push arrives."""
        if self.hass is None:
            return
        serial = (
            event.get("serialNumber")
            or event.get("deviceSn")
            or event.get("device")
        )
        if serial != self.serial:
            return
        name = str(event.get("eventName") or event.get("event") or "").lower()
        if name in (
            "motion",
            "persondetected",
            "doorbellpress",
            "eventimageupdated",
        ) or "motion" in name or "doorbell" in name:
            self._last_image = None
            self.hass.async_create_task(self._prefetch_still())

    async def _prefetch_still(self) -> None:
        try:
            await self.coordinator.client.command(
                "event.refresh", sn=self.serial
            )
        except EufyMegaError:
            pass
        image = await self.async_camera_image()
        if image:
            self.async_write_ha_state()
