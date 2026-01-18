"""Govee API client for the integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError, ClientTimeout

from .const import (
    API_BASE_URL,
    API_CONTROL_ENDPOINT,
    API_DEVICES_ENDPOINT,
    API_KEY_HEADER,
    API_TIMEOUT,
    CAP_INSTANCE_BRIGHTNESS,
    CAP_INSTANCE_COLOR_RGB,
    CAP_INSTANCE_COLOR_TEMP,
    CAP_INSTANCE_POWER,
    CAP_ON_OFF,
    CAP_RANGE,
    CAP_COLOR_SETTING,
    DOMAIN,
)

_LOGGER = logging.getLogger(DOMAIN)


class GoveeApiError(Exception):
    """Base exception for Govee API errors."""


class GoveeAuthenticationError(GoveeApiError):
    """Authentication error with Govee API."""


class GoveeConnectionError(GoveeApiError):
    """Connection error with Govee API."""


class GoveeRateLimitError(GoveeApiError):
    """Rate limit exceeded error."""


class GoveeApiClient:
    """Client to interact with Govee OpenAPI."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client.

        Args:
            api_key: Govee Developer API key.
            session: aiohttp ClientSession for making requests.
        """
        self._api_key = api_key
        self._session = session
        self._timeout = ClientTimeout(total=API_TIMEOUT)

    @property
    def _headers(self) -> dict[str, str]:
        """Return headers for API requests."""
        return {
            API_KEY_HEADER: self._api_key,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request.

        Args:
            method: HTTP method (GET, PUT, POST).
            endpoint: API endpoint.
            json_data: Optional JSON body data.

        Returns:
            API response as dictionary.

        Raises:
            GoveeAuthenticationError: If authentication fails.
            GoveeConnectionError: If connection fails.
            GoveeRateLimitError: If rate limit is exceeded.
            GoveeApiError: For other API errors.
        """
        url = f"{API_BASE_URL}{endpoint}"

        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                json=json_data,
                timeout=self._timeout,
            ) as response:
                if response.status == 401:
                    _LOGGER.error("Authentication failed with Govee API")
                    raise GoveeAuthenticationError("Invalid API key")

                if response.status == 429:
                    _LOGGER.warning("Rate limit exceeded for Govee API")
                    raise GoveeRateLimitError("Rate limit exceeded")

                if response.status >= 400:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Govee API error: status=%s, response=%s",
                        response.status,
                        error_text,
                    )
                    raise GoveeApiError(
                        f"API request failed with status {response.status}"
                    )

                return await response.json()

        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout connecting to Govee API")
            raise GoveeConnectionError("Connection timeout") from err
        except ClientResponseError as err:
            _LOGGER.error("HTTP error from Govee API: %s", err)
            raise GoveeApiError(f"HTTP error: {err}") from err
        except ClientError as err:
            _LOGGER.error("Connection error to Govee API: %s", err)
            raise GoveeConnectionError(f"Connection error: {err}") from err

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Fetch all devices from Govee API.

        Returns:
            List of device dictionaries.

        Raises:
            GoveeApiError: If the request fails.
        """
        _LOGGER.debug("Fetching devices from Govee API")

        response = await self._request("GET", API_DEVICES_ENDPOINT)

        # New API returns devices directly in data array
        devices = response.get("data", [])
        _LOGGER.debug("Found %d devices", len(devices))

        return devices

    async def async_control_device(
        self,
        device: str,
        sku: str,
        capability_type: str,
        instance: str,
        value: Any,
    ) -> bool:
        """Send a control command to a device.

        Args:
            device: Device ID/MAC address.
            sku: Device SKU/model.
            capability_type: Capability type (e.g., devices.capabilities.on_off).
            instance: Capability instance (e.g., powerSwitch).
            value: Command value.

        Returns:
            True if command was successful.

        Raises:
            GoveeApiError: If the request fails.
        """
        _LOGGER.debug(
            "Sending command to device %s: %s.%s=%s",
            device,
            capability_type,
            instance,
            value,
        )

        payload = {
            "requestId": "uuid",
            "payload": {
                "sku": sku,
                "device": device,
                "capability": {
                    "type": capability_type,
                    "instance": instance,
                    "value": value,
                },
            },
        }

        await self._request("POST", API_CONTROL_ENDPOINT, json_data=payload)
        return True

    async def async_turn_on(self, device: str, sku: str) -> bool:
        """Turn on a device.

        Args:
            device: Device ID/MAC address.
            sku: Device SKU/model.

        Returns:
            True if successful.
        """
        return await self.async_control_device(
            device, sku, CAP_ON_OFF, CAP_INSTANCE_POWER, 1
        )

    async def async_turn_off(self, device: str, sku: str) -> bool:
        """Turn off a device.

        Args:
            device: Device ID/MAC address.
            sku: Device SKU/model.

        Returns:
            True if successful.
        """
        return await self.async_control_device(
            device, sku, CAP_ON_OFF, CAP_INSTANCE_POWER, 0
        )

    async def async_set_brightness(
        self,
        device: str,
        sku: str,
        brightness: int,
    ) -> bool:
        """Set device brightness.

        Args:
            device: Device ID/MAC address.
            sku: Device SKU/model.
            brightness: Brightness level (1-100).

        Returns:
            True if successful.
        """
        brightness = max(1, min(100, brightness))
        return await self.async_control_device(
            device, sku, CAP_RANGE, CAP_INSTANCE_BRIGHTNESS, brightness
        )

    async def async_set_color(
        self,
        device: str,
        sku: str,
        r: int,
        g: int,
        b: int,
    ) -> bool:
        """Set device color.

        Args:
            device: Device ID/MAC address.
            sku: Device SKU/model.
            r: Red component (0-255).
            g: Green component (0-255).
            b: Blue component (0-255).

        Returns:
            True if successful.
        """
        # Convert RGB to integer value (RGB packed into single int)
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        color_value = (r << 16) + (g << 8) + b
        return await self.async_control_device(
            device, sku, CAP_COLOR_SETTING, CAP_INSTANCE_COLOR_RGB, color_value
        )

    async def async_set_color_temperature(
        self,
        device: str,
        sku: str,
        kelvin: int,
    ) -> bool:
        """Set device color temperature.

        Args:
            device: Device ID/MAC address.
            sku: Device SKU/model.
            kelvin: Color temperature in Kelvin.

        Returns:
            True if successful.
        """
        return await self.async_control_device(
            device, sku, CAP_COLOR_SETTING, CAP_INSTANCE_COLOR_TEMP, kelvin
        )

    async def async_validate_api_key(self) -> bool:
        """Validate the API key by making a test request.

        Returns:
            True if the API key is valid.

        Raises:
            GoveeAuthenticationError: If the API key is invalid.
            GoveeConnectionError: If the connection fails.
        """
        await self.async_get_devices()
        return True
