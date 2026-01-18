"""The Govee integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GoveeApiClient,
    GoveeApiError,
    GoveeAuthenticationError,
    GoveeConnectionError,
)
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(DOMAIN)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry.

    Returns:
        True if setup was successful.
    """
    _LOGGER.debug("Setting up Govee integration")

    # Get API key from entry data
    api_key = entry.data[CONF_API_KEY]

    # Create API client using shared aiohttp session
    session = async_get_clientsession(hass)
    api_client = GoveeApiClient(api_key, session)

    # Get scan interval from options
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # Create data update coordinator
    coordinator = GoveeDataUpdateCoordinator(
        hass,
        api_client=api_client,
        scan_interval=scan_interval,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator and API client for platform setup
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Govee integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry.

    Returns:
        True if unload was successful.
    """
    _LOGGER.debug("Unloading Govee integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        # Clean up domain data if no more entries
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.

    Args:
        hass: Home Assistant instance.
        entry: Config entry.
    """
    _LOGGER.debug("Options updated, reloading Govee integration")
    await hass.config_entries.async_reload(entry.entry_id)


class GoveeDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator to manage data updates from Govee API.

    This coordinator polls the Govee API for device information
    and provides shared state updates for all entities.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: GoveeApiClient,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            api_client: Govee API client.
            scan_interval: Update interval in seconds.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._api_client = api_client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from Govee API.

        Returns:
            List of device data dictionaries.

        Raises:
            UpdateFailed: If the update fails.
        """
        try:
            _LOGGER.debug("Fetching device data from Govee API")
            devices = await self._api_client.async_get_devices()
            _LOGGER.debug("Received data for %d devices", len(devices))
            return devices

        except GoveeAuthenticationError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise UpdateFailed(f"Authentication failed: {err}") from err

        except GoveeConnectionError as err:
            _LOGGER.warning("Connection error: %s", err)
            raise UpdateFailed(f"Connection error: {err}") from err

        except GoveeApiError as err:
            _LOGGER.error("API error: %s", err)
            raise UpdateFailed(f"API error: {err}") from err

        except Exception as err:
            _LOGGER.exception("Unexpected error during data update")
            raise UpdateFailed(f"Unexpected error: {err}") from err
