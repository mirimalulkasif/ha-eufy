"""Minimal websocket client for eufy-security-ws."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .const import (
    DEFAULT_SCHEMA,
    DOORBELL_TYPES,
    INDOOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class EufyWsError(Exception):
    """Websocket / command failure."""


class EufyWsClient:
    """Talk to a running eufy-security-ws server."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
        schema: int = DEFAULT_SCHEMA,
    ) -> None:
        self.host = host
        self.port = port
        self.session = session
        self.schema = schema
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._futures: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._listen_task: asyncio.Task | None = None
        self._event_callbacks: list[EventCallback] = []
        self.devices: dict[str, dict[str, Any]] = {}

    def on_event(self, callback: EventCallback) -> None:
        self._event_callbacks.append(callback)

    async def connect(self) -> None:
        url = f"ws://{self.host}:{self.port}"
        self._ws = await self.session.ws_connect(url, heartbeat=20)
        self._listen_task = asyncio.create_task(self._reader())
        # Wait briefly for version frame
        await asyncio.sleep(0.2)
        await self._command("set_api_schema", schemaVersion=self.schema)
        state = await self._command("start_listening")
        await self._load_devices(state.get("state", {}))

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

    async def refresh(self) -> None:
        await self._command("driver.poll_refresh")
        # Re-fetch properties for known devices
        for serial in list(self.devices):
            try:
                props = await self._command(
                    "device.get_properties",
                    serialNumber=serial,
                )
                self.devices[serial]["properties"] = props.get("properties", {})
            except EufyWsError as err:
                _LOGGER.debug("refresh %s failed: %s", serial, err)

    async def set_enabled(self, serial: str, enabled: bool) -> None:
        await self._command(
            "device.set_property",
            serialNumber=serial,
            name="enabled",
            value=enabled,
        )

    async def _load_devices(self, state: dict[str, Any]) -> None:
        serials = state.get("devices") or []
        loaded: dict[str, dict[str, Any]] = {}
        for serial in serials:
            try:
                props_msg = await self._command(
                    "device.get_properties",
                    serialNumber=serial,
                )
            except EufyWsError as err:
                _LOGGER.warning("Skipping %s: %s", serial, err)
                continue
            props = props_msg.get("properties") or {}
            dtype = int(props.get("type") or props.get("deviceType") or 0)
            kind = None
            if dtype in DOORBELL_TYPES:
                kind = "doorbell"
            elif dtype in INDOOR_TYPES:
                kind = "indoor"
            if not kind:
                continue
            loaded[serial] = {
                "serial": serial,
                "kind": kind,
                "properties": props,
                "name": props.get("name") or serial,
                "model": props.get("model") or kind,
            }
        self.devices = loaded
        _LOGGER.info(
            "Loaded %s doorbell/indoor device(s) from eufy-security-ws",
            len(self.devices),
        )

    async def _command(self, command: str, **params: Any) -> dict[str, Any]:
        if not self._ws or self._ws.closed:
            raise EufyWsError("Websocket not connected")
        message_id = str(uuid.uuid4())
        payload = {"messageId": message_id, "command": command, **params}
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._futures[message_id] = future
        await self._ws.send_json(payload)
        try:
            result = await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError as err:
            self._futures.pop(message_id, None)
            raise EufyWsError(f"Timeout waiting for {command}") from err
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
            _LOGGER.exception("eufy-security-ws reader crashed")
        finally:
            for fut in self._futures.values():
                if not fut.done():
                    fut.set_exception(EufyWsError("Connection closed"))
            self._futures.clear()

    async def _handle_message(self, data: dict[str, Any]) -> None:
        msg_type = data.get("type")
        if msg_type == "version":
            _LOGGER.debug(
                "eufy-security-ws %s / driver %s",
                data.get("serverVersion"),
                data.get("driverVersion"),
            )
            return

        if msg_type == "result":
            message_id = str(data.get("messageId"))
            future = self._futures.pop(message_id, None)
            if not future or future.done():
                return
            if data.get("success"):
                future.set_result(data.get("result") or {})
            else:
                future.set_exception(
                    EufyWsError(str(data.get("errorCode") or "command_failed"))
                )
            return

        if msg_type == "event":
            event = data.get("event") or data
            serial = event.get("serialNumber") or event.get("device")
            event_name = event.get("eventName") or event.get("name")
            if serial and serial in self.devices:
                # Merge property updates
                if event_name in ("property changed", "device property changed"):
                    name = event.get("name")
                    value = event.get("value")
                    if name is not None:
                        self.devices[serial].setdefault("properties", {})[name] = value
            for callback in self._event_callbacks:
                result = callback(event if isinstance(event, dict) else data)
                if asyncio.iscoroutine(result):
                    await result
