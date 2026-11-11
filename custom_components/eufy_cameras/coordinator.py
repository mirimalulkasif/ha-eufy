"""Data update coordinator for Eufy Cameras."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .mega_client import EufyMegaClient, EufyMegaError

_LOGGER = logging.getLogger(__name__)


class EufyCamerasCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll the Mega SDK bridge for doorbell / indoor cameras."""

    def __init__(self, hass: HomeAssistant, client: EufyMegaClient) -> None:
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
        except EufyMegaError as err:
            raise UpdateFailed(str(err)) from err
        return dict(self.client.devices)
