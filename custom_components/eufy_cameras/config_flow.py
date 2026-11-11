"""Config flow for Eufy Cameras (Mega SDK bridge / add-on)."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
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


class EufyCamerasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy Cameras."""

    VERSION = 2

    def __init__(self) -> None:
        self._host: str = DEFAULT_HOST
        self._port: int = DEFAULT_PORT
        self._client: EufyMegaClient | None = None
        self._bridge_id: str | None = None
        self._captcha_image: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual host/port — used after the add-on is running."""
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
            description_placeholders={
                "hint": (
                    "Install & start the Eufy Cameras Bridge add-on from this "
                    "same repository first. On Supervised/HA OS use your HA "
                    "host IP (not 127.0.0.1) and port 3000."
                ),
            },
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


class CannotConnect(Exception):
    """Bridge unreachable or not ready."""
