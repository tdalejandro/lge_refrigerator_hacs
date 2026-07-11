"""One native HAP accessory with all services of an LG refrigerator."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from homeassistant.components import persistent_notification, zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback

from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver

from .const import (
    CONF_HOMEKIT_NAME,
    CONF_HOMEKIT_PIN,
    CONF_HOMEKIT_PORT,
    DOMAIN,
    FEATURE_ECO_FRIENDLY,
    FEATURE_EXPRESS_FREEZER,
    FEATURE_EXPRESS_FRIDGE,
    FEATURE_ICE_PLUS,
    FEATURE_WATER_FILTER,
    STORAGE_FILE_PREFIX,
)
from .coordinator import LGERefrigeratorCoordinator
from .vendor.wideq.const import TemperatureUnit

COOL = 2
CONTACT_CLOSED = 0
CONTACT_OPEN = 1
CELSIUS = 0
FILTER_OK = 0
CHANGE_FILTER = 1

_FEATURE_NAMES = {
    FEATURE_ECO_FRIENDLY: "Eco Friendly",
    FEATURE_EXPRESS_FREEZER: "Express Freezer",
    FEATURE_EXPRESS_FRIDGE: "Express Fridge",
    FEATURE_ICE_PLUS: "Ice Plus",
}


class LGERefrigeratorAccessory(Accessory):
    """One multi-service HomeKit accessory, not one accessory per HA entity."""

    def __init__(
        self,
        driver: AccessoryDriver,
        display_name: str,
        hass: HomeAssistant,
        coordinator: LGERefrigeratorCoordinator,
    ) -> None:
        """Create only services supported by the selected refrigerator."""
        super().__init__(driver, display_name)
        self.hass = hass
        self.coordinator = coordinator
        info = coordinator.device.device_info
        accessory_info = self.get_service("AccessoryInformation")
        accessory_info.configure_char("Manufacturer", value="LG Electronics")
        accessory_info.configure_char("Model", value=info.model_name)
        accessory_info.configure_char("SerialNumber", value=info.device_id)

        self._fridge_current, self._fridge_target = self._add_thermostat(
            "Fridge", "fridge", "fridge", -5, 15
        )
        self._freezer_current, self._freezer_target = self._add_thermostat(
            "Freezer", "freezer", "freezer", -35, 10
        )

        self._door_state = None
        if str(coordinator.data.door_opened_state) != "-":
            door = self.add_preload_service(
                "ContactSensor", chars=["Name"], unique_id="door"
            )
            door.configure_char("Name", value="Refrigerator Door")
            self._door_state = door.configure_char("ContactSensorState")

        self._feature_states: dict[str, Any] = {}
        for feature, name in _FEATURE_NAMES.items():
            if coordinator.supports(feature):
                service = self.add_preload_service("Switch", chars=["Name"], unique_id=feature)
                service.configure_char("Name", value=name)
                self._feature_states[feature] = service.configure_char(
                    "On", setter_callback=lambda value, key=feature: self._set_feature(key, value)
                )

        self._filter_life = None
        self._filter_indication = None
        if coordinator.supports(FEATURE_WATER_FILTER):
            service = self.add_preload_service(
                "FilterMaintenance",
                chars=["Name", "FilterLifeLevel", "FilterChangeIndication"],
                unique_id="water-filter",
            )
            service.configure_char("Name", value="Water Filter")
            self._filter_life = service.configure_char("FilterLifeLevel")
            self._filter_indication = service.configure_char("FilterChangeIndication")

    def _add_thermostat(
        self,
        name: str,
        unique_id: str,
        compartment: str,
        minimum: int,
        maximum: int,
    ) -> tuple[Any, Any]:
        """Create a cool-only thermostat; HomeKit characteristic values are Celsius."""
        service = self.add_preload_service("Thermostat", chars=["Name"], unique_id=unique_id)
        service.configure_char("Name", value=name)
        service.configure_char("CurrentHeatingCoolingState", value=COOL)
        target_mode = service.configure_char("TargetHeatingCoolingState", value=COOL)
        target_mode.override_properties(valid_values={"cool": COOL})
        service.configure_char("TemperatureDisplayUnits", value=CELSIUS)
        current = service.configure_char(
            "CurrentTemperature",
            properties={"minValue": -40, "maxValue": 100, "minStep": 0.1},
        )
        target = service.configure_char(
            "TargetTemperature",
            properties={"minValue": minimum, "maxValue": maximum, "minStep": 0.1},
            setter_callback=lambda value: self._set_temperature(compartment, value),
        )
        return current, target

    def _set_temperature(self, compartment: str, value: float) -> None:
        """Translate Celsius HAP input to the scale configured in the refrigerator."""
        self.hass.async_create_task(
            self.coordinator.async_set_temperature(
                compartment, self._from_homekit_celsius(float(value))
            )
        )

    def _set_feature(self, feature: str, value: bool) -> None:
        """Set an optional LG feature from its HomeKit Switch service."""
        self.hass.async_create_task(self.coordinator.async_set_feature(feature, bool(value)))

    def update_from_coordinator(self) -> None:
        """Push a single cloud update to all HomeKit services immediately."""
        data = self.coordinator.data
        self._update_thermostat(data.temp_fridge, self._fridge_current, self._fridge_target)
        self._update_thermostat(data.temp_freezer, self._freezer_current, self._freezer_target)
        if self._door_state is not None:
            self._door_state.set_value(
                CONTACT_OPEN
                if str(data.door_opened_state).lower() == "on"
                else CONTACT_CLOSED
            )
        for feature, characteristic in self._feature_states.items():
            characteristic.set_value(str(self.coordinator.features.get(feature)).lower() == "on")
        if self._filter_life is not None:
            life = self._as_float(self.coordinator.features.get(FEATURE_WATER_FILTER))
            if life is not None:
                self._filter_life.set_value(max(0, min(100, life)))
                self._filter_indication.set_value(
                    CHANGE_FILTER if life < 5 else FILTER_OK
                )

    def _update_thermostat(self, value: Any, current: Any, target: Any) -> None:
        """Update the two HAP temperature characteristics from a ThinQ setting."""
        raw_value = self._as_float(value)
        if raw_value is None:
            return
        value_celsius = self._to_homekit_celsius(raw_value)
        current.set_value(value_celsius)
        target.set_value(value_celsius)

    def _to_homekit_celsius(self, value: float) -> float:
        if self.coordinator.data.temp_unit == TemperatureUnit.FAHRENHEIT:
            return round((value - 32) * 5 / 9, 1)
        return value

    def _from_homekit_celsius(self, value: float) -> float:
        if self.coordinator.data.temp_unit == TemperatureUnit.FAHRENHEIT:
            return round(value * 9 / 5 + 32)
        return round(value)

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class LGERefrigeratorHomeKitBridge:
    """Run the HAP driver without creating a second ThinQ client or poller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LGERefrigeratorCoordinator,
        shared_zeroconf: "_SharedZeroconfProxy",
    ) -> None:
        """Synchronously construct HAP state, persistence, and one accessory."""
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        persist_file = Path(
            hass.config.path(".storage", f"{STORAGE_FILE_PREFIX}{entry.entry_id}.state")
        )
        self.driver = AccessoryDriver(
            address="0.0.0.0",
            port=entry.data[CONF_HOMEKIT_PORT],
            persist_file=str(persist_file),
            pincode=entry.data[CONF_HOMEKIT_PIN].encode(),
            loop=hass.loop,
            async_zeroconf_instance=shared_zeroconf,
        )
        if isinstance(self.driver.state.pincode, str):
            self.driver.state.pincode = self.driver.state.pincode.encode()
        self.accessory = LGERefrigeratorAccessory(
            self.driver,
            entry.data[CONF_HOMEKIT_NAME],
            hass,
            coordinator,
        )
        self.driver.add_accessory(self.accessory)
        self._remove_listener: Callable[[], None] | None = None
        self._remove_stop_listener: Callable[[], None] | None = None
        self._driver_started = False

    @classmethod
    async def async_create(
        cls,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LGERefrigeratorCoordinator,
    ) -> "LGERefrigeratorHomeKitBridge":
        """Build HAP objects off the Home Assistant event loop."""
        shared_zeroconf = await zeroconf.async_get_instance(hass)
        return await hass.async_add_executor_job(
            cls, hass, entry, coordinator, _SharedZeroconfProxy(shared_zeroconf)
        )

    async def async_start(self) -> None:
        """Start HTTP/mDNS only after status and all HAP services are complete."""
        self.accessory.update_from_coordinator()
        try:
            await self.driver.async_start()
        except Exception:
            if self.driver.mdns_service_info is not None:
                await self.driver.async_stop()
            raise
        self._driver_started = True
        self._remove_listener = self.coordinator.async_add_listener(
            self.accessory.update_from_coordinator
        )
        self._remove_stop_listener = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_hass_stop
        )
        if not self.driver.state.paired:
            persistent_notification.async_create(
                self.hass,
                (
                    "En Casa: Añadir accesorio > Más opciones > "
                    f"{self.entry.data[CONF_HOMEKIT_NAME]}. Código HomeKit: "
                    f"{self.entry.data[CONF_HOMEKIT_PIN]}"
                ),
                title="LGE Refrigerator listo para emparejar",
                notification_id=f"{DOMAIN}_{self.entry.entry_id}",
            )

    async def async_stop(self) -> None:
        """Withdraw mDNS and close HAP cleanly, freeing the configured port."""
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
        if self._remove_stop_listener:
            self._remove_stop_listener()
            self._remove_stop_listener = None
        if self._driver_started:
            await self.driver.async_stop()
            self._driver_started = False

    @callback
    def _async_hass_stop(self, event: Event) -> None:
        """Stop HAP during HA shutdown even if config unloading is skipped."""
        self.hass.async_create_task(self.async_stop())


class _SharedZeroconfProxy:
    """Prevent pyhap from closing Home Assistant's process-wide mDNS instance."""

    def __init__(self, instance: Any) -> None:
        self._instance = instance

    async def async_register_service(self, *args: Any, **kwargs: Any) -> Any:
        """Register only the refrigerator service."""
        return await self._instance.async_register_service(*args, **kwargs)

    async def async_unregister_service(self, *args: Any, **kwargs: Any) -> Any:
        """Unregister only the refrigerator service."""
        return await self._instance.async_unregister_service(*args, **kwargs)

    async def async_close(self) -> None:
        """Leave Home Assistant's shared mDNS instance alive."""
