"""Shared entity implementation for a single LGE refrigerator."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LGERefrigeratorCoordinator


class LGERefrigeratorEntity(CoordinatorEntity[LGERefrigeratorCoordinator]):
    """Base entity bound to the selected LG refrigerator coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LGERefrigeratorCoordinator, key: str) -> None:
        """Set stable LG identifiers and Home Assistant device metadata."""
        super().__init__(coordinator)
        info = coordinator.device.device_info
        self._attr_unique_id = f"{info.device_id}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.device_id)},
            name=info.name,
            manufacturer="LG Electronics",
            model=info.model_name,
            sw_version=info.firmware,
        )
