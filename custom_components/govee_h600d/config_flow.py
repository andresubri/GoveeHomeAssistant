"""Config flow for Govee integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    GoveeApiClient,
    GoveeAuthenticationError,
    GoveeConnectionError,
    GoveeApiError,
)
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(DOMAIN)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=DEFAULT_SCAN_INTERVAL,
        ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
    }
)


class GoveeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step.

        This is called when the user initiates adding the integration.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the API key
            try:
                await self._validate_api_key(user_input[CONF_API_KEY])
            except GoveeAuthenticationError:
                errors["base"] = "invalid_auth"
            except GoveeConnectionError:
                errors["base"] = "cannot_connect"
            except GoveeApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception during config validation")
                errors["base"] = "unknown"
            else:
                # Check if already configured
                await self.async_set_unique_id(
                    f"govee_{user_input[CONF_API_KEY][:8]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Govee",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _validate_api_key(self, api_key: str) -> bool:
        """Validate the API key by making a test request.

        Args:
            api_key: Govee API key to validate.

        Returns:
            True if the API key is valid.

        Raises:
            GoveeAuthenticationError: If the API key is invalid.
            GoveeConnectionError: If the connection fails.
        """
        session = async_get_clientsession(self.hass)
        client = GoveeApiClient(api_key, session)
        return await client.async_validate_api_key()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GoveeOptionsFlow:
        """Get the options flow for this handler."""
        return GoveeOptionsFlow(config_entry)


class GoveeOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Govee."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options.

        This is called when the user clicks Configure on an existing integration.
        """
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_options = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                }
            ),
        )
