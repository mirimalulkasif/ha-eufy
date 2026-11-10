"""Sensors for Eufy doorbell / indoor cameras."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EufyConfigEntry
from .entity import EufyCameraEntity

BATTERY_DESC = SensorEntityDescription(
    key="battery",
    name="Battery",
    device_class=SensorDeviceClass.BATTERY,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
    entity_category=EntityCategory.DIAGNOSTIC,
)

KIND_DESC = SensorEntityDescription(
    key="kind",
    name="Device kind",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for serial, data in coordinator.data.items():
        entities.append(EufyKindSensor(coordinator, serial))
        props = data.get("properties") or {}
        if "battery" in props or "batteryLevel" in props:
            entities.append(EufyBatterySensor(coordinator, serial))
    async_add_entities(entities)


class EufyBatterySensor(EufyCameraEntity, SensorEntity):
    """Battery level when the device reports one."""

    entity_description = BATTERY_DESC

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"eufy_cameras_{serial}_battery"

    @property
    def native_value(self) -> int | None:
        value = self._prop("battery")
        if value is None:
            value = self._prop("batteryLevel")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class EufyKindSensor(EufyCameraEntity, SensorEntity):
    """doorbell | indoor."""

    entity_description = KIND_DESC

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"eufy_cameras_{serial}_kind"

    @property
    def native_value(self) -> str | None:
        return self.device_data.get("kind")
