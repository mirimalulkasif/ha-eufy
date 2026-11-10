"""Enable / disable switch for Eufy cameras."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EufyConfigEntry
from .entity import EufyCameraEntity
from .ws_client import EufyWsError

ENABLED_DESC = SwitchEntityDescription(
    key="enabled",
    name="Enabled",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        EufyEnabledSwitch(coordinator, serial) for serial in coordinator.data
    )


class EufyEnabledSwitch(EufyCameraEntity, SwitchEntity):
    """Toggle the Eufy device enabled (armed) flag."""

    entity_description = ENABLED_DESC

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"eufy_cameras_{serial}_enabled"

    @property
    def is_on(self) -> bool:
        return bool(self._prop("enabled", True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, enabled: bool) -> None:
        try:
            await self.coordinator.client.set_enabled(self.serial, enabled)
        except EufyWsError:
            raise
        props = self.device_data.setdefault("properties", {})
        props["enabled"] = enabled
        self.coordinator.async_set_updated_data(dict(self.coordinator.client.devices))
