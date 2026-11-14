"""Switches for Eufy cameras (Mega bridge writable bools)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EufyConfigEntry
from .entity import EufyCameraEntity
from .mega_client import EufyMegaError

SWITCH_DESCRIPTIONS: dict[str, SwitchEntityDescription] = {
    "enabled": SwitchEntityDescription(key="enabled", name="Enabled"),
    "statusLed": SwitchEntityDescription(key="statusLed", name="Status LED"),
    "light": SwitchEntityDescription(key="light", name="Light"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    for serial in coordinator.data:
        for key in coordinator.client.writable_switches(serial):
            desc = SWITCH_DESCRIPTIONS.get(key)
            if desc:
                entities.append(EufyBoolSwitch(coordinator, serial, desc))
    async_add_entities(entities)


class EufyBoolSwitch(EufyCameraEntity, SwitchEntity):
    """Toggle a Mega bridge bool property."""

    def __init__(
        self,
        coordinator,
        serial: str,
        description: SwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, serial)
        self.entity_description = description
        self._attr_unique_id = f"eufy_cameras_{serial}_{description.key}"

    @property
    def is_on(self) -> bool:
        key = self.entity_description.key
        if key == "enabled":
            props = self.device_data.get("properties") or {}
            if "enabled" in props:
                return bool(props["enabled"])
            if "privacy" in props:
                return not bool(props["privacy"])
            return True
        return bool(self._prop(key, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, value: bool) -> None:
        key = self.entity_description.key
        try:
            if key == "enabled":
                await self.coordinator.client.set_enabled(self.serial, value)
            else:
                await self.coordinator.client.set_property(self.serial, key, value)
        except EufyMegaError as err:
            raise HomeAssistantError(str(err)) from err
        props = self.device_data.setdefault("properties", {})
        if key == "enabled":
            if "privacy" in props and "enabled" not in props:
                props["privacy"] = not value
            else:
                props["enabled"] = value
        else:
            props[key] = value
        self.coordinator.async_set_updated_data(
            dict(self.coordinator.client.devices)
        )
