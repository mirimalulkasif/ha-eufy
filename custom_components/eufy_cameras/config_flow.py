"""Config flow for Eufy Cameras (Mega SDK bridge)."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from .mega_client import EufyMegaClient, EufyMegaError

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def _validate(
    hass: HomeAssistant, host: str, port: int
) -> dict[str, str]:
    session = async_get_clientsession(hass)
    client = EufyMegaClient(host=host, port=port, session=session)
    try:
        await client.connect()
    except (EufyMegaError, aiohttp.ClientError, OSError, TimeoutError) as err:
        raise ConnectionError(str(err)) from err
    finally:
        await client.disconnect()
    title = f"Eufy Cameras ({host}:{port})"
    if client.bridge_id:
        title = f"Eufy Cameras ({client.bridge_id[:8]})"
    return {
        "title": title,
        "bridge_id": client.bridge_id or f"{host}:{port}",
    }


class EufyCamerasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy Cameras."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Point at a running ha-eufy-sdk-bridge (Mega)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])
            try:
                info = await _validate(self.hass, host, port)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["bridge_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
