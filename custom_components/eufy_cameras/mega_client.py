"""WebSocket client for mega-yfue ha-eufy-sdk-bridge (Mega / v6 cloud)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urljoin

import aiohttp

from .const import WS_PATH
from .device_kinds import classify_device

_LOGGER = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class EufyMegaError(Exception):
    """Bridge / command failure."""


class EufyMegaClient:
    """Talk to a running ha-eufy-sdk-bridge (Mega SDK)."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
    ) -> None:
        self.host = host
        self.port = port
        self.session = session
        self.base_url = f"http://{host}:{port}"
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._futures: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._next_id = 1
        self._listen_task: asyncio.Task | None = None
        self._event_callbacks: list[EventCallback] = []
        self.devices: dict[str, dict[str, Any]] = {}
        self.auth_state: str | None = None
        self.bridge_id: str | None = None
        self.schema_version: int | None = None
        self._ready = asyncio.Event()

    def on_event(self, callback: EventCallback) -> None:
        self._event_callbacks.append(callback)

    async def connect(self) -> None:
        url = f"ws://{self.host}:{self.port}{WS_PATH}"
        self._ws = await self.session.ws_connect(url, heartbeat=20)
        self._listen_task = asyncio.create_task(self._reader())

        try:
            await asyncio.wait_for(self._ready.wait(), timeout=20)
        except asyncio.TimeoutError:
            # Some builds still answer commands before ready; probe auth.
            status = await self.command("auth.status")
            auth = status.get("auth") or {}
            self.auth_state = auth.get("state")
            self.bridge_id = status.get("bridgeId") or self.bridge_id
            if self.auth_state == "ok":
                self._ready.set()
            else:
                raise EufyMegaError(
                    f"Mega bridge auth state is {self.auth_state!r} — "
                    "complete 2FA/captcha on the bridge first"
                )

        if self.auth_state and self.auth_state not in ("ok", None):
            # ready may fire while reauth recovers; require ok for device cmds
            if self.auth_state != "ok":
                raise EufyMegaError(
                    f"Mega bridge auth state is {self.auth_state!r} — "
                    "complete 2FA/captcha on the bridge first"
                )

        await self.refresh()

    async def disconnect(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        self._ready.clear()

    async def refresh(self) -> None:
        result = await self.command("devices.list")
        loaded: dict[str, dict[str, Any]] = {}
        for device in result.get("devices") or []:
            if not isinstance(device, dict) or device.get("error"):
                continue
            sn = str(device.get("sn") or "")
            if not sn:
                continue
            kind = classify_device(device)
            if not kind:
                _LOGGER.debug(
                    "Skipping Mega device %s model=%s codec=%s",
                    sn,
                    device.get("model"),
                    device.get("codec"),
                )
                continue
            state = dict(device.get("state") or {})
            loaded[sn] = {
                "serial": sn,
                "kind": kind,
                "name": device.get("name") or sn,
                "model": device.get("model") or kind,
                "model_name": device.get("modelName"),
                "capabilities": list(device.get("capabilities") or []),
                "properties": state,
                "stream_path": device.get("stream"),
                "streaming": bool(device.get("streaming")),
                "power": device.get("power"),
                "views": device.get("views") or [],
                "raw": device,
            }
        self.devices = loaded
        _LOGGER.info(
            "Loaded %s doorbell/indoor device(s) from Mega bridge",
            len(self.devices),
        )

    async def set_property(self, serial: str, name: str, value: Any) -> None:
        await self.command("device.set", sn=serial, name=name, value=value)

    async def set_enabled(self, serial: str, enabled: bool) -> None:
        """Best-effort enable/privacy toggle used by the Enabled switch."""
        props = (self.devices.get(serial) or {}).get("properties") or {}
        if "enabled" in props:
            await self.set_property(serial, "enabled", enabled)
            return
        if "privacy" in props:
            # privacy on == camera disabled
            await self.set_property(serial, "privacy", not enabled)
            return
        # Fall back to enabled even if not in the last snapshot (may still work).
        await self.set_property(serial, "enabled", enabled)

    async def stream_urls(self, serial: str) -> dict[str, Any]:
        return await self.command("stream.start", sn=serial)

    async def fetch_snapshot(
        self, serial: str, *, mode: str = "stored"
    ) -> bytes | None:
        """GET /snapshot/<sn> from the bridge."""
        modes = [mode] if mode else ["stored", ""]
        if mode == "stored":
            modes = ["stored", ""]
        elif not mode:
            modes = [""]

        for attempt in modes:
            path = f"/snapshot/{serial}"
            if attempt:
                path = f"{path}?mode={attempt}"
            url = urljoin(self.base_url + "/", path.lstrip("/"))
            try:
                async with self.session.get(
                    url, timeout=aiohttp.ClientTimeout(total=25)
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(
                            "Snapshot %s mode=%r → HTTP %s",
                            serial,
                            attempt or "default",
                            resp.status,
                        )
                        continue
                    data = await resp.read()
                    if data:
                        return data
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("Snapshot %s error: %s", serial, err)
        return None

    async def command(self, cmd: str, **params: Any) -> dict[str, Any]:
        if not self._ws or self._ws.closed:
            raise EufyMegaError("Websocket not connected")
        msg_id = self._next_id
        self._next_id += 1
        payload = {"id": msg_id, "cmd": cmd, **params}
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._futures[msg_id] = future
        await self._ws.send_json(payload)
        try:
            result = await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError as err:
            self._futures.pop(msg_id, None)
            raise EufyMegaError(f"Timeout waiting for {cmd}") from err
        return result

    async def _reader(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    if msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        break
                    continue
                data = msg.json()
                await self._handle_message(data)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Mega bridge reader crashed")
        finally:
            for fut in self._futures.values():
                if not fut.done():
                    fut.set_exception(EufyMegaError("Connection closed"))
            self._futures.clear()

    async def _handle_message(self, data: dict[str, Any]) -> None:
        # Command replies
        if "id" in data and ("ok" in data or "error" in data):
            msg_id = int(data["id"])
            future = self._futures.pop(msg_id, None)
            if not future or future.done():
                return
            if data.get("ok"):
                future.set_result(data)
            else:
                future.set_exception(
                    EufyMegaError(str(data.get("error") or "command_failed"))
                )
            return

        event = data.get("event")
        if not event:
            return

        if event == "hello":
            self.auth_state = (data.get("auth") or {}).get("state")
            self.bridge_id = data.get("bridgeId") or self.bridge_id
            self.schema_version = data.get("schemaVersion")
            _LOGGER.info(
                "Mega bridge hello schema=%s auth=%s bridgeId=%s",
                self.schema_version,
                self.auth_state,
                self.bridge_id,
            )
            if self.auth_state == "ok":
                self._ready.set()
            return

        if event == "auth":
            self.auth_state = data.get("state")
            _LOGGER.info("Mega bridge auth → %s", self.auth_state)
            if self.auth_state == "ok":
                self._ready.set()
            return

        if event == "ready":
            self.schema_version = data.get("schemaVersion") or self.schema_version
            _LOGGER.info("Mega bridge ready schema=%s", self.schema_version)
            self._ready.set()
            return

        device_sn = data.get("deviceSn") or data.get("sn")
        if device_sn and device_sn in self.devices:
            props = self.devices[device_sn].setdefault("properties", {})
            if event == "propertyChanged":
                name = data.get("property") or data.get("name")
                if name is not None and ("value" in data or "to" in data):
                    props[name] = data["value"] if "value" in data else data.get("to")
                elif name is not None and data.get("value") is not None:
                    props[name] = data.get("value")
            elif event == "batteryLevel":
                to_val = data.get("to", data.get("value"))
                if to_val is not None:
                    try:
                        props["battery"] = int(to_val)
                    except (TypeError, ValueError):
                        props["battery"] = to_val
            elif event == "motion":
                props["motion"] = True
            elif event == "personDetected":
                props["person"] = True
                props["motion"] = True
            elif event == "doorbellPress":
                props["ring"] = True
            elif event == "streamState":
                self.devices[device_sn]["streaming"] = bool(data.get("active"))
            elif event == "smartLightState":
                if "on" in data:
                    props["light"] = data.get("on")

        for callback in self._event_callbacks:
            payload = dict(data)
            payload.setdefault("eventName", event)
            payload.setdefault("serialNumber", device_sn)
            result = callback(payload)
            if asyncio.iscoroutine(result):
                await result
