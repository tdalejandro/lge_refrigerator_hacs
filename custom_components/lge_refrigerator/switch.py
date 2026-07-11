"""Optional refrigerator feature switches."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    FEATURE_ECO_FRIENDLY,
    FEATURE_EXPRESS_FREEZER,
    FEATURE_EXPRESS_FRIDGE,
    FEATURE_ICE_PLUS,
)
from .coordinator import LGERefrigeratorCoordinator
from .entity import LGERefrigeratorEntity


@dataclass(frozen=True)
class RefrigeratorSwitchDescription:
    """A ThinQ feature that maps directly to an HA switch and HAP Switch."""

    key: str
    name: str
    icon: str


SWITCHES = (
    RefrigeratorSwitchDescription(FEATURE_ECO_FRIENDLY, "Eco friendly", "mdi:leaf"),
    RefrigeratorSwitchDescription(
        FEATURE_EXPRESS_FREEZER, "Express freezer", "mdi:snowflake"
    ),
    RefrigeratorSwitchDescription(
        FEATURE_EXPRESS_FRIDGE, "Express fridge", "mdi:coolant-temperature"
    ),
    RefrigeratorSwitchDescription(FEATURE_ICE_PLUS, "Ice plus", "mdi:ice-cream"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create only switches actually advertised by this refrigerator model."""
    coordinator: LGERefrigeratorCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        [
            LGERefrigeratorSwitch(coordinator, description)
            for description in SWITCHES
            if coordinator.supports(description.key)
        ]
    )


class LGERefrigeratorSwitch(LGERefrigeratorEntity, SwitchEntity):
    """Control one optional refrigerator capability through ThinQ."""

    def __init__(
        self,
        coordinator: LGERefrigeratorCoordinator,
        description: RefrigeratorSwitchDescription,
    ) -> None:
        """Initialize a feature switch."""
        super().__init__(coordinator, description.key)
        self.description = description
        self._attr_name = description.name
        self._attr_icon = description.icon

    @property
    def is_on(self) -> bool:
        """Treat only ThinQ's explicit on state as enabled."""
        return str(self.coordinator.features.get(self.description.key)).lower() == "on"

    @property
    def available(self) -> bool:
        """Disable controls while ThinQ reports eco mode or unavailable state."""
        if self.description.key == FEATURE_ECO_FRIENDLY:
            return super().available
        return super().available and self.coordinator.device.set_values_allowed

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable the LG feature."""
        await self.coordinator.async_set_feature(self.description.key, True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable the LG feature."""
        await self.coordinator.async_set_feature(self.description.key, False)
