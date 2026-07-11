"""LG ThinQ refrigerator state and command coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CLIENT_ID,
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_LANGUAGE,
    CONF_OAUTH_URL,
    CONF_REFRESH_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .vendor.wideq.const import RefrigeratorFeatures
from .vendor.wideq.core_async import ClientAsync
from .vendor.wideq.core_exceptions import InvalidCredentialError
from .vendor.wideq.device_info import DeviceType, NetworkType
from .vendor.wideq.devices.refrigerator import RefrigeratorDevice, RefrigeratorStatus

_LOGGER = logging.getLogger(__name__)


class LGERefrigeratorCoordinator(DataUpdateCoordinator[RefrigeratorStatus]):
    """Own the sole ThinQ client and rate-limited refrigerator polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ClientAsync,
        device: RefrigeratorDevice,
    ) -> None:
        """Initialize the coordinator after model metadata has been loaded."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{device.name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.entry = entry
        self.client = client
        self.device = device

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, entry: ConfigEntry
    ) -> "LGERefrigeratorCoordinator":
        """Authenticate once, select exactly the configured refrigerator, and poll it."""
        def _update_client_id(client_id: str) -> None:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_CLIENT_ID: client_id}
            )

        client = await ClientAsync.from_token(
            entry.data[CONF_REFRESH_TOKEN],
            country=entry.data[CONF_COUNTRY],
            language=entry.data[CONF_LANGUAGE],
            oauth_url=entry.data.get(CONF_OAUTH_URL),
            client_id=entry.data.get(CONF_CLIENT_ID),
            aiohttp_session=async_get_clientsession(hass),
            update_clientid_callback=_update_client_id,
        )
        device_info = next(
            (
                info
                for info in client.devices or []
                if info.device_id == entry.data[CONF_DEVICE_ID]
                and info.type is DeviceType.REFRIGERATOR
                and info.network_type is NetworkType.WIFI
            ),
            None,
        )
        if device_info is None:
            await client.close()
            raise ValueError(entry.data[CONF_DEVICE_ID])

        device = RefrigeratorDevice(client, device_info)
        if not await device.init_device_info():
            await client.close()
            raise ValueError("model information unavailable")

        coordinator = cls(hass, entry, client, device)
        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception:
            await client.close()
            raise
        return coordinator

    async def _async_update_data(self) -> RefrigeratorStatus:
        """Read refrigerator state; the 300-second cadence avoids LG blocking."""
        try:
            state = await self.device.poll()
        except InvalidCredentialError as err:
            raise ConfigEntryAuthFailed("LG ThinQ credentials need reauthentication") from err
        except Exception as err:
            raise UpdateFailed(f"LG ThinQ refrigerator update failed: {err}") from err
        if state is None:
            raise UpdateFailed("LG ThinQ did not return refrigerator state")
        return state

    @property
    def features(self) -> dict[str, Any]:
        """Return model-supported refrigerator features for entity and HAP selection."""
        return self.data.device_features if self.data is not None else {}

    def supports(self, feature: str) -> bool:
        """Return whether the selected refrigerator exposed a given feature."""
        return feature in self.features

    async def async_set_temperature(self, compartment: str, value: float) -> None:
        """Set a target temperature and publish the optimistic ThinQ status."""
        if compartment == "fridge":
            minimum, maximum = self.device.fridge_target_temp_range
            await self.device.set_fridge_target_temp(min(max(value, minimum), maximum))
        elif compartment == "freezer":
            minimum, maximum = self.device.freezer_target_temp_range
            await self.device.set_freezer_target_temp(min(max(value, minimum), maximum))
        else:
            raise ValueError(f"Unsupported refrigerator compartment: {compartment}")
        self.async_set_updated_data(self.device.status)

    async def async_set_feature(self, feature: str, enabled: bool) -> None:
        """Set a supported optional feature and publish its optimistic state."""
        commands = {
            RefrigeratorFeatures.ECOFRIENDLY: self.device.set_eco_friendly,
            RefrigeratorFeatures.EXPRESSMODE: self.device.set_express_mode,
            RefrigeratorFeatures.EXPRESSFRIDGE: self.device.set_express_fridge,
            RefrigeratorFeatures.ICEPLUS: self.device.set_ice_plus,
        }
        try:
            command = commands[RefrigeratorFeatures(feature)]
        except (KeyError, ValueError) as err:
            raise ValueError(f"Unsupported refrigerator feature: {feature}") from err
        await command(enabled)
        self.async_set_updated_data(self.device.status)

    async def async_close(self) -> None:
        """Release the ThinQ client without closing Home Assistant's shared session."""
        await self.client.close()
