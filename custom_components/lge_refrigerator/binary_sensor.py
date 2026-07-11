"""Door state for the selected LG refrigerator."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import LGERefrigeratorCoordinator
from .entity import LGERefrigeratorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the refrigerator door contact sensor."""
    coordinator: LGERefrigeratorCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities([LGERefrigeratorDoor(coordinator)])


class LGERefrigeratorDoor(LGERefrigeratorEntity, BinarySensorEntity):
    """Expose the appliance's door-open state."""

    _attr_name = "Door open"
    _attr_icon = "mdi:fridge-alert-outline"
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator: LGERefrigeratorCoordinator) -> None:
        """Initialize the door sensor."""
        super().__init__(coordinator, "door_open")

    @property
    def is_on(self) -> bool:
        """Return true only when ThinQ explicitly reports an open door."""
        return str(self.coordinator.data.door_opened_state).lower() == "on"
