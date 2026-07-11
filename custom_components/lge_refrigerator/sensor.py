"""Temperature and optional filter-life sensors for the LG refrigerator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    FEATURE_FRESH_AIR_FILTER,
    FEATURE_WATER_FILTER,
)
from .coordinator import LGERefrigeratorCoordinator
from .entity import LGERefrigeratorEntity
from .vendor.wideq.const import TemperatureUnit


@dataclass(frozen=True)
class RefrigeratorSensorDescription:
    """A scalar refrigerator value."""

    key: str
    name: str
    icon: str
    value: Callable[[LGERefrigeratorCoordinator], float | int | None]
    unit: str | Callable[[LGERefrigeratorCoordinator], str] | None = None
    device_class: SensorDeviceClass | None = None


def _temperature_unit(coordinator: LGERefrigeratorCoordinator) -> str:
    return (
        UnitOfTemperature.FAHRENHEIT
        if coordinator.data.temp_unit == TemperatureUnit.FAHRENHEIT
        else UnitOfTemperature.CELSIUS
    )


SENSORS = (
    RefrigeratorSensorDescription(
        "fridge_temperature",
        "Fridge temperature",
        "mdi:thermometer",
        lambda coordinator: coordinator.data.temp_fridge,
        _temperature_unit,
        SensorDeviceClass.TEMPERATURE,
    ),
    RefrigeratorSensorDescription(
        "freezer_temperature",
        "Freezer temperature",
        "mdi:thermometer-chevron-down",
        lambda coordinator: coordinator.data.temp_freezer,
        _temperature_unit,
        SensorDeviceClass.TEMPERATURE,
    ),
    RefrigeratorSensorDescription(
        FEATURE_FRESH_AIR_FILTER,
        "Fresh air filter remaining",
        "mdi:air-filter",
        lambda coordinator: coordinator.features.get(FEATURE_FRESH_AIR_FILTER),
        PERCENTAGE,
    ),
    RefrigeratorSensorDescription(
        FEATURE_WATER_FILTER,
        "Water filter remaining",
        "mdi:waves",
        lambda coordinator: coordinator.features.get(FEATURE_WATER_FILTER),
        PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add temperature sensors and only model-supported filter sensors."""
    coordinator: LGERefrigeratorCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        [
            LGERefrigeratorSensor(coordinator, description)
            for description in SENSORS
            if description.key.endswith("temperature") or coordinator.supports(description.key)
        ]
    )


class LGERefrigeratorSensor(LGERefrigeratorEntity, SensorEntity):
    """Expose a one-value ThinQ refrigerator reading."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: LGERefrigeratorCoordinator,
        description: RefrigeratorSensorDescription,
    ) -> None:
        """Initialize the scalar sensor."""
        super().__init__(coordinator, description.key)
        self.description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_device_class = description.device_class

    @property
    def native_value(self) -> float | int | None:
        """Return the last ThinQ reading."""
        return self.description.value(self.coordinator)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return either the appliance scale or percentage."""
        if callable(self.description.unit):
            return self.description.unit(self.coordinator)
        return self.description.unit
