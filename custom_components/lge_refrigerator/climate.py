"""Climate entities for the fresh-food and freezer compartments."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import LGERefrigeratorCoordinator
from .entity import LGERefrigeratorEntity
from .vendor.wideq.const import TemperatureUnit


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the two refrigerator compartments."""
    coordinator: LGERefrigeratorCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        [
            LGERefrigeratorClimate(coordinator, "fridge", "Fridge", "mdi:fridge-top"),
            LGERefrigeratorClimate(coordinator, "freezer", "Freezer", "mdi:fridge-bottom"),
        ]
    )


class LGERefrigeratorClimate(LGERefrigeratorEntity, ClimateEntity):
    """One target-temperature control exposed as a Home Assistant climate entity."""

    _attr_hvac_modes = [HVACMode.AUTO]
    _attr_hvac_mode = HVACMode.AUTO
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self,
        coordinator: LGERefrigeratorCoordinator,
        compartment: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize a fresh-food or freezer climate entity."""
        super().__init__(coordinator, compartment)
        self._compartment = compartment
        self._attr_name = name
        self._attr_icon = icon

    @property
    def temperature_unit(self) -> str:
        """Use the appliance's configured temperature scale."""
        if self.coordinator.data.temp_unit == TemperatureUnit.FAHRENHEIT:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self) -> float | None:
        """Return the target reported by the appliance."""
        value = (
            self.coordinator.data.temp_fridge
            if self._compartment == "fridge"
            else self.coordinator.data.temp_freezer
        )
        return float(value) if value is not None else None

    @property
    def current_temperature(self) -> float | None:
        """LG reports a compartment setting, so mirror it as its current value."""
        return self.target_temperature

    @property
    def min_temp(self) -> float:
        """Return the model-specific lower limit."""
        ranges = (
            self.coordinator.device.fridge_target_temp_range
            if self._compartment == "fridge"
            else self.coordinator.device.freezer_target_temp_range
        )
        return float(ranges[0])

    @property
    def max_temp(self) -> float:
        """Return the model-specific upper limit."""
        ranges = (
            self.coordinator.device.fridge_target_temp_range
            if self._compartment == "fridge"
            else self.coordinator.device.freezer_target_temp_range
        )
        return float(ranges[1])

    @property
    def target_temperature_step(self) -> float:
        """LG refrigerator target settings are integer degrees."""
        return float(self.coordinator.device.target_temperature_step)

    async def async_set_temperature(self, **kwargs: object) -> None:
        """Set the temperature directly through the one ThinQ coordinator."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set_temperature(
                self._compartment, float(temperature)
            )
