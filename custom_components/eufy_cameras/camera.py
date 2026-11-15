"""Camera entities for Eufy doorbell / indoor devices (Mega bridge)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EufyConfigEntry
from .const import ATTR_KIND, ATTR_MODEL, ATTR_SERIAL, DOMAIN
from .coordinator import EufyCamerasCoordinator
from .mega_client import EufyMegaError
from .power import skip_ha_hls_worker

if TYPE_CHECKING:
    from homeassistant.components.stream import Stream

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
    """Live video via Mega bridge for doorbell + indoor.

    Home Assistant's go2rtc registers the stream under the *entity id*
    (e.g. ``camera.doorbell``) but the *producer* must be a real URL. We feed
    HA go2rtc the bridge's raw ``/stream/<serial>`` Annex-B HTTP URL (same
    source the bridge's own go2rtc uses), not ``rtsp://…/camera.doorbell``.

    Doorbell/battery cameras skip HA's HLS worker (``async_create_stream`` →
    ``None``) so a dropped Mega session does not Idle↔Streaming-loop.
    """

    _attr_has_entity_name = True
    _attr_name = "Camera"
    _attr_entity_registry_enabled_default = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self, coordinator: EufyCamerasCoordinator, serial: str
    ) -> None:
        super().__init__(coordinator)
        Camera.__init__(self)
        self.serial = serial
        self._attr_unique_id = f"eufy_cameras_{serial}_camera"
        self._last_image: bytes | None = None
        kind = (coordinator.data.get(serial) or {}).get("kind")
        self._attr_icon = (
            "mdi:doorbell-video" if kind == "doorbell" else "mdi:cctv"
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.client.on_event(self._handle_event)
        self.hass.async_create_task(self._prefetch_still())
        if skip_ha_hls_worker(self.device_data):
            _LOGGER.info(
                "%s (%s): WebRTC via HA go2rtc → bridge /stream (HLS worker off). "
                "Disable 'Preload stream' on this entity.",
                self.name,
                self.serial,
            )

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
        client = self.coordinator.client
        host = client.media_host or client.host
        port = client.port
        return {
            ATTR_SERIAL: self.serial,
            ATTR_KIND: data.get("kind"),
            ATTR_MODEL: data.get("model"),
            "power": data.get("power"),
            "capabilities": data.get("capabilities"),
            "stream_mode": "webrtc_ffmpeg_http",
            "bridge_stream": f"http://{host}:{port}/stream/{self.serial}",
            "rtsp_url": f"rtsp://{host}:8554/{self.serial}",
            "go2rtc_stream": f"http://{host}:1984/stream.html?src={self.serial}",
            "skip_ha_hls": skip_ha_hls_worker(data),
        }

    async def stream_source(self) -> str | None:
        """Producer URL for HA's go2rtc (registered under this entity_id).

        Use ffmpeg→bridge HTTP Annex-B, not bridge RTSP. That avoids a 404 when
        HA go2rtc falls back to ``ffmpeg:camera.<name>`` after a bad RTSP hop,
        and matches how the bridge itself sources cameras.
        """
        client = self.coordinator.client
        await client.resolve_media_host()
        host = client.media_host or client.host
        port = client.port
        if host in ("127.0.0.1", "localhost", "::1"):
            _LOGGER.error(
                "Stream host is loopback (%s) — HA Core cannot reach the bridge. "
                "Set the integration host to the VM LAN IP.",
                host,
            )

        # Arm the bridge session (no-op if already streaming).
        try:
            await client.stream_urls(self.serial)
        except EufyMegaError as err:
            _LOGGER.debug("stream.start for %s: %s (continuing with HTTP path)", self.serial, err)

        path = self.device_data.get("stream_path") or f"/stream/{self.serial}"
        if not path.startswith("/"):
            path = f"/{path}"
        # #async = wall-clock DTS (HA aborts on eufy's dts jumps). #video=copy = remux only.
        source = (
            f"ffmpeg:http://{host}:{port}{path}#video=copy#async"
        )
        model = str(self.device_data.get("model") or "").upper()
        # Indoor T84xx raw H.264 is mis-probed without an explicit demuxer (bridge does the same).
        if model.startswith("T84"):
            source += "#raw=-f h264 -analyzeduration 0 -probesize 32768"
        _LOGGER.info("stream_source %s → %s", self.entity_id, source)
        return source

    async def async_create_stream(self) -> Stream | None:
        """Skip HA HLS worker for doorbell / battery (prevents reconnect spam)."""
        if skip_ha_hls_worker(self.device_data):
            return None
        return await super().async_create_stream()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch a JPEG still from the Mega bridge."""
        client = self.coordinator.client
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

        return self._last_image

    @callback
    def _handle_event(self, event: dict) -> None:
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
