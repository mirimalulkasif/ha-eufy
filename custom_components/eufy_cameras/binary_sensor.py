"""Binary sensors for Eufy doorbell / indoor cameras."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EufyConfigEntry
from .entity import EufyCameraEntity

MOTION_DESC = BinarySensorEntityDescription(
    key="motion",
    name="Motion",
    device_class=BinarySensorDeviceClass.MOTION,
)

RING_DESC = BinarySensorEntityDescription(
    key="ring",
    name="Ring",
    device_class=BinarySensorDeviceClass.OCCUPANCY,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for serial, data in coordinator.data.items():
        entities.append(EufyMotionBinarySensor(coordinator, serial))
        if data.get("kind") == "doorbell":
            entities.append(EufyRingBinarySensor(coordinator, serial))
    async_add_entities(entities)


class EufyMotionBinarySensor(EufyCameraEntity, BinarySensorEntity):
    """Motion detected (from last push / property state)."""

    entity_description = MOTION_DESC

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"eufy_cameras_{serial}_motion"
        self._motion = False
        coordinator.client.on_event(self._handle_event)

    async def _handle_event(self, event: dict) -> None:
        serial = event.get("serialNumber") or event.get("device")
        if serial != self.serial:
            return
        name = str(event.get("eventName") or event.get("name") or "").lower()
        etype = event.get("eventType") or event.get("type")
        if "motion" in name or etype in (3101, 3102, 3106, 3108, 3109):
            self._motion = True
            self.async_write_ha_state()
            self.hass.loop.call_later(15, self._clear)

    def _clear(self) -> None:
        self._motion = False
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        prop = self._prop("motionDetected")
        if prop is not None:
            return bool(prop)
        return self._motion


class EufyRingBinarySensor(EufyCameraEntity, BinarySensorEntity):
    """Doorbell ring pulse."""

    entity_description = RING_DESC

    def __init__(self, coordinator, serial: str) -> None:
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"eufy_cameras_{serial}_ring"
        self._ringing = False
        coordinator.client.on_event(self._handle_event)

    async def _handle_event(self, event: dict) -> None:
        serial = event.get("serialNumber") or event.get("device")
        if serial != self.serial:
            return
        name = str(event.get("eventName") or event.get("name") or "").lower()
        etype = event.get("eventType") or event.get("type")
        if "ring" in name or "doorbell" in name or etype == 3103:
            self._ringing = True
            self.async_write_ha_state()
            self.hass.loop.call_later(10, self._clear)

    def _clear(self) -> None:
        self._ringing = False
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        return self._ringing
