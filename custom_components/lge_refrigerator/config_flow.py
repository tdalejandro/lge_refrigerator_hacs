"""Configuration flow for the standalone LGE Refrigerator integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from .const import (
    CONF_CLIENT_ID,
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_HOMEKIT_NAME,
    CONF_HOMEKIT_PIN,
    CONF_HOMEKIT_PORT,
    CONF_LANGUAGE,
    CONF_OAUTH_URL,
    CONF_REFRESH_TOKEN,
    DEFAULT_COUNTRY,
    DEFAULT_HOMEKIT_PIN,
    DEFAULT_HOMEKIT_PORT,
    DEFAULT_LANGUAGE,
    DOMAIN,
)
from .vendor.wideq.core_async import ClientAsync
from .vendor.wideq.core_exceptions import AuthenticationError, InvalidCredentialError
from .vendor.wideq.device_info import DeviceType, NetworkType

_LOGGER = logging.getLogger(__name__)
CONF_USE_REDIRECT = "use_redirect"
CONF_CALLBACK_URL = "callback_url"
CONF_LOGIN_URL = "login_url"
PIN_PATTERN = re.compile(r"^\d{3}-\d{2}-\d{3}$")
LOCALE_PATTERN = re.compile(r"^[a-z]{2,3}(-[A-Z]{2,3})?$")
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2,3}$")


class LGERefrigeratorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one refrigerator while accepting only LG ThinQ credentials."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize temporary, non-persisted flow data."""
        self._country = DEFAULT_COUNTRY
        self._language = DEFAULT_LANGUAGE
        self._token: str | None = None
        self._oauth_url: str | None = None
        self._client_id: str | None = None
        self._login_url: str | None = None
        self._refrigerators: dict[str, str] = {}
        self._device_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authenticate directly with ThinQ or request LG's browser login URL."""
        if user_input is None:
            self._country = getattr(self.hass.config, "country", None) or DEFAULT_COUNTRY
            locale = getattr(self.hass.config, "language", None) or DEFAULT_LANGUAGE
            self._language = locale if LOCALE_PATTERN.match(locale) else DEFAULT_LANGUAGE
            return self._show_user_form()

        self._country = user_input[CONF_COUNTRY].upper().strip()
        language = user_input[CONF_LANGUAGE].strip()
        self._language = (
            f"{language.lower()}-{self._country}"
            if "-" not in language
            else language
        )
        if not COUNTRY_PATTERN.match(self._country):
            return self._show_user_form(errors={CONF_COUNTRY: "invalid_country"})
        if not LOCALE_PATTERN.match(self._language):
            return self._show_user_form(errors={CONF_LANGUAGE: "invalid_language"})

        try:
            if user_input[CONF_USE_REDIRECT]:
                self._login_url = await ClientAsync.get_login_url(
                    self._country,
                    self._language,
                    aiohttp_session=async_get_clientsession(self.hass),
                )
                return await self.async_step_callback()

            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "")
            if not username or not password:
                return self._show_user_form(errors={"base": "credentials_required"})
            oauth = await ClientAsync.oauth_info_from_user_login(
                username,
                password,
                self._country,
                self._language,
                aiohttp_session=async_get_clientsession(self.hass),
            )
            self._set_oauth(oauth)
        except (AuthenticationError, InvalidCredentialError):
            return self._show_user_form(errors={"base": "invalid_auth"})
        except Exception:  # LG provides no stable error contract for login failures.
            _LOGGER.exception("LG ThinQ login failed")
            return self._show_user_form(errors={"base": "cannot_connect"})
        return await self._async_find_refrigerators()

    async def async_step_callback(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept the LG ThinQ callback URL for accounts with social login."""
        if user_input is None:
            return self.async_show_form(
                step_id="callback",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_LOGIN_URL, default=self._login_url): str,
                        vol.Required(CONF_CALLBACK_URL): str,
                    }
                ),
            )
        try:
            oauth = await ClientAsync.oauth_info_from_url(
                user_input[CONF_CALLBACK_URL],
                self._country,
                self._language,
                aiohttp_session=async_get_clientsession(self.hass),
            )
            self._set_oauth(oauth)
        except (AuthenticationError, InvalidCredentialError):
            return self.async_show_form(
                step_id="callback", errors={"base": "invalid_auth"}
            )
        except Exception:
            _LOGGER.exception("LG ThinQ callback exchange failed")
            return self.async_show_form(
                step_id="callback", errors={"base": "cannot_connect"}
            )
        return await self._async_find_refrigerators()

    async def async_step_refrigerator(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one refrigerator; no other LG device types are accepted."""
        if user_input is not None:
            self._device_id = user_input[CONF_DEVICE_ID]
            await self.async_set_unique_id(self._device_id)
            self._abort_if_unique_id_configured()
            return await self.async_step_homekit()
        return self.async_show_form(
            step_id="refrigerator",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=device_id, label=name)
                                for device_id, name in self._refrigerators.items()
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_homekit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the independent single-accessory HomeKit endpoint."""
        selected_name = self._refrigerators[self._device_id]
        if user_input is None:
            return self._show_homekit_form(selected_name)

        port = user_input[CONF_HOMEKIT_PORT]
        pin = user_input[CONF_HOMEKIT_PIN].strip()
        if not 1024 <= port <= 65535:
            return self._show_homekit_form(selected_name, {CONF_HOMEKIT_PORT: "invalid_port"})
        if not PIN_PATTERN.match(pin):
            return self._show_homekit_form(selected_name, {CONF_HOMEKIT_PIN: "invalid_pin"})
        return self.async_create_entry(
            title=f"LGE Refrigerator: {user_input[CONF_HOMEKIT_NAME].strip()}",
            data={
                CONF_COUNTRY: self._country,
                CONF_LANGUAGE: self._language,
                CONF_REFRESH_TOKEN: self._token,
                CONF_OAUTH_URL: self._oauth_url,
                CONF_CLIENT_ID: self._client_id,
                CONF_DEVICE_ID: self._device_id,
                CONF_HOMEKIT_NAME: user_input[CONF_HOMEKIT_NAME].strip(),
                CONF_HOMEKIT_PORT: port,
                CONF_HOMEKIT_PIN: pin,
            },
        )

    def _set_oauth(self, oauth: dict[str, Any] | None) -> None:
        """Store only the refresh credential returned by LG, never the password."""
        if not oauth or not oauth.get("refresh_token"):
            raise AuthenticationError("LG did not return a refresh token")
        self._token = oauth["refresh_token"]
        self._oauth_url = oauth.get("oauth_url")

    async def _async_find_refrigerators(self) -> ConfigFlowResult:
        """Validate the token and enumerate Wi-Fi refrigerators only."""
        assert self._token is not None
        try:
            client = await ClientAsync.from_token(
                self._token,
                country=self._country,
                language=self._language,
                oauth_url=self._oauth_url,
                aiohttp_session=async_get_clientsession(self.hass),
            )
            self._client_id = client.client_id
            self._refrigerators = {
                info.device_id: info.name
                for info in client.devices or []
                if info.type is DeviceType.REFRIGERATOR
                and info.network_type is NetworkType.WIFI
            }
        except (AuthenticationError, InvalidCredentialError):
            return self.async_abort(reason="invalid_auth")
        except Exception:
            _LOGGER.exception("Unable to query LG ThinQ refrigerators")
            return self.async_abort(reason="cannot_connect")
        finally:
            if "client" in locals():
                await client.close()
        if not self._refrigerators:
            return self.async_abort(reason="no_refrigerators")
        if len(self._refrigerators) == 1:
            self._device_id = next(iter(self._refrigerators))
            await self.async_set_unique_id(self._device_id)
            self._abort_if_unique_id_configured()
            return await self.async_step_homekit()
        return await self.async_step_refrigerator()

    def _show_user_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show credentials without persisting them into the config entry."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COUNTRY, default=self._country): str,
                    vol.Required(CONF_LANGUAGE, default=self._language): str,
                    vol.Optional(CONF_USERNAME, default=""): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                    vol.Required(CONF_USE_REDIRECT, default=False): bool,
                }
            ),
            errors=errors,
        )

    def _show_homekit_form(
        self, name: str, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show HomeKit name, non-conflicting port, and pairing code."""
        return self.async_show_form(
            step_id="homekit",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOMEKIT_NAME, default=name): str,
                    vol.Required(CONF_HOMEKIT_PORT, default=DEFAULT_HOMEKIT_PORT): int,
                    vol.Required(CONF_HOMEKIT_PIN, default=DEFAULT_HOMEKIT_PIN): str,
                }
            ),
            errors=errors,
        )
