"""Data update coordinator for Eufy Cameras."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .ws_client import EufyWsClient, EufyWsError

_LOGGER = logging.getLogger(__name__)


class EufyCamerasCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll eufy-security-ws for doorbell / indoor cameras."""

    def __init__(self, hass: HomeAssistant, client: EufyWsClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            await self.client.refresh()
        except EufyWsError as err:
            raise UpdateFailed(str(err)) from err
        return dict(self.client.devices)
