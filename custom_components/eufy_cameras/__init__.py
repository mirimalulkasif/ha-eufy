"""Eufy Cameras Home Assistant integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN, PLATFORMS
from .coordinator import EufyCamerasCoordinator
from .ws_client import EufyWsClient, EufyWsError

_LOGGER = logging.getLogger(__name__)

type EufyConfigEntry = ConfigEntry[EufyCamerasCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EufyConfigEntry) -> bool:
    """Set up Eufy Cameras from a config entry."""
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    port = int(entry.data.get(CONF_PORT, DEFAULT_PORT))
    session = async_get_clientsession(hass)
    client = EufyWsClient(host=host, port=port, session=session)

    try:
        await client.connect()
    except Exception as err:  # noqa: BLE001
        await client.disconnect()
        raise ConfigEntryNotReady(
            f"Cannot connect to eufy-security-ws at {host}:{port}"
        ) from err

    if not client.devices:
        _LOGGER.warning(
            "Connected to eufy-security-ws but no doorbell/indoor cameras were found"
        )

    coordinator = EufyCamerasCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _on_event(event: dict) -> None:
        serial = event.get("serialNumber") or event.get("device")
        if serial and serial in client.devices:
            coordinator.async_set_updated_data(dict(client.devices))

    client.on_event(_on_event)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EufyConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator = entry.runtime_data
    try:
        await coordinator.client.disconnect()
    except EufyWsError:
        pass
    return unload_ok
