"""Config flow for Eufy Cameras (Mega SDK bridge / add-on)."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from .mega_client import EufyMegaClient, EufyMegaError


def _host_port_schema(host: str, port: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): int,
        }
    )


STEP_USER_DATA_SCHEMA = _host_port_schema(DEFAULT_HOST, DEFAULT_PORT)


class EufyCamerasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy Cameras."""

    VERSION = 2

    def __init__(self) -> None:
        self._host: str = DEFAULT_HOST
        self._port: int = DEFAULT_PORT
        self._client: EufyMegaClient | None = None
        self._bridge_id: str | None = None
        self._captcha_image: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EufyCamerasOptionsFlow:
        """Return the options flow (Configure button)."""
        return EufyCamerasOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual host/port — used after the bridge is running."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = str(user_input[CONF_HOST]).strip()
            self._port = int(user_input[CONF_PORT])
            try:
                return await self._async_try_connect()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Change host/port from the integration ⋮ → Reconfigure menu."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        current_host = str(entry.data.get(CONF_HOST, DEFAULT_HOST))
        current_port = int(entry.data.get(CONF_PORT, DEFAULT_PORT))

        if user_input is not None:
            self._host = str(user_input[CONF_HOST]).strip()
            self._port = int(user_input[CONF_PORT])
            session = async_get_clientsession(self.hass)
            client = EufyMegaClient(
                host=self._host, port=self._port, session=session
            )
            try:
                await client.connect(require_auth_ok=True)
            except (EufyMegaError, aiohttp.ClientError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await client.disconnect()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                    },
                )
            finally:
                if not errors:
                    pass
                else:
                    await client.disconnect()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_host_port_schema(current_host, current_port),
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: Any) -> FlowResult:
        """Discovered by the Eufy Cameras Bridge add-on."""
        config = getattr(discovery_info, "config", None) or discovery_info
        if not isinstance(config, dict):
            return self.async_abort(reason="unknown")
        self._host = str(config.get("host") or DEFAULT_HOST)
        self._port = int(config.get("port") or DEFAULT_PORT)
        await self.async_set_unique_id(
            f"hassio-{self._host}:{self._port}"
        )
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Supervisor discovery."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._async_try_connect()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={
                "host": self._host,
                "port": str(self._port),
            },
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Submit Eufy 2FA code to the bridge."""
        errors: dict[str, str] = {}
        if user_input is not None and self._client:
            code = str(user_input.get("mfa_code") or "").strip()
            try:
                auth = await self._client.auth_submit(code=code)
            except EufyMegaError:
                errors["base"] = "invalid_auth"
            else:
                state = auth.get("state")
                if state == "ok":
                    return await self._async_create_from_client()
                if state == "require_captcha":
                    self._captcha_image = auth.get("image")
                    return await self.async_step_captcha()
                if state == "require_2fa":
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="mfa",
            data_schema=vol.Schema({vol.Required("mfa_code"): str}),
            errors=errors,
        )

    async def async_step_captcha(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Submit captcha answer to the bridge."""
        errors: dict[str, str] = {}
        if user_input is not None and self._client:
            answer = str(user_input.get("captcha_code") or "").strip()
            try:
                auth = await self._client.auth_submit(captcha=answer)
            except EufyMegaError:
                errors["base"] = "invalid_auth"
            else:
                state = auth.get("state")
                if state == "ok":
                    return await self._async_create_from_client()
                if state == "require_2fa":
                    return await self.async_step_mfa()
                if state == "require_captcha":
                    self._captcha_image = auth.get("image")
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="captcha",
            data_schema=vol.Schema({vol.Required("captcha_code"): str}),
            description_placeholders={
                "image_note": (
                    "Open the bridge add-on log or health UI if the captcha "
                    "image is not shown here; then enter the characters."
                ),
            },
            errors=errors,
        )

    async def _async_try_connect(self) -> FlowResult:
        session = async_get_clientsession(self.hass)
        client = EufyMegaClient(
            host=self._host, port=self._port, session=session
        )
        try:
            await client.connect(require_auth_ok=False)
        except (EufyMegaError, aiohttp.ClientError, OSError, TimeoutError) as err:
            await client.disconnect()
            raise CannotConnect from err

        self._client = client
        self._bridge_id = client.bridge_id or f"{self._host}:{self._port}"
        state = client.auth_state

        if state == "ok":
            return await self._async_create_from_client()
        if state == "require_2fa":
            return await self.async_step_mfa()
        if state == "require_captcha":
            self._captcha_image = (client.auth_extra or {}).get("image")
            return await self.async_step_captcha()

        await client.disconnect()
        self._client = None
        raise CannotConnect(f"auth state {state!r}")

    async def _async_create_from_client(self) -> FlowResult:
        assert self._client is not None
        bridge_id = self._client.bridge_id or self._bridge_id or (
            f"{self._host}:{self._port}"
        )
        await self.async_set_unique_id(bridge_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )
        title = f"Eufy Cameras ({bridge_id[:8]})"
        await self._client.disconnect()
        self._client = None
        return self.async_create_entry(
            title=title,
            data={CONF_HOST: self._host, CONF_PORT: self._port},
        )


class EufyCamerasOptionsFlow(config_entries.OptionsFlow):
    """Configure button — change bridge host/port."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        current_host = str(self._config_entry.data.get(CONF_HOST, DEFAULT_HOST))
        current_port = int(self._config_entry.data.get(CONF_PORT, DEFAULT_PORT))

        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            port = int(user_input[CONF_PORT])
            session = async_get_clientsession(self.hass)
            client = EufyMegaClient(host=host, port=port, session=session)
            try:
                await client.connect(require_auth_ok=True)
            except (EufyMegaError, aiohttp.ClientError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await client.disconnect()
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={CONF_HOST: host, CONF_PORT: port},
                )
                await self.hass.config_entries.async_reload(
                    self._config_entry.entry_id
                )
                return self.async_create_entry(title="", data={})
            await client.disconnect()

        return self.async_show_form(
            step_id="init",
            data_schema=_host_port_schema(current_host, current_port),
            errors=errors,
        )


class CannotConnect(Exception):
    """Bridge unreachable or not ready."""
