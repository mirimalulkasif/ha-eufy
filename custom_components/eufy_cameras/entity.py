"""Shared entity base for Eufy Cameras."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_KIND, ATTR_MODEL, ATTR_SERIAL, DOMAIN
from .coordinator import EufyCamerasCoordinator


class EufyCameraEntity(CoordinatorEntity[EufyCamerasCoordinator]):
    """Base entity tied to one Eufy doorbell or indoor camera."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EufyCamerasCoordinator,
        serial: str,
    ) -> None:
        super().__init__(coordinator)
        self.serial = serial

    @property
    def device_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self.serial, {})

    @property
    def available(self) -> bool:
        return self.serial in self.coordinator.data and super().available

    @property
    def device_info(self) -> DeviceInfo:
        data = self.device_data
        kind = data.get("kind", "camera")
        model_name = data.get("model_name")
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=data.get("name") or self.serial,
            manufacturer="Eufy",
            model=str(model_name or data.get("model") or kind),
            serial_number=self.serial,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.device_data
        return {
            ATTR_SERIAL: self.serial,
            ATTR_KIND: data.get("kind"),
            ATTR_MODEL: data.get("model"),
        }

    def _prop(self, name: str, default: Any = None) -> Any:
        props = self.device_data.get("properties") or {}
        return props.get(name, default)
