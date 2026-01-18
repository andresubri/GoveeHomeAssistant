"""Govee API client for H600D integration."""

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
    CMD_BRIGHTNESS,
    CMD_COLOR,
    CMD_COLOR_TEM,
    CMD_TURN,
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
    """Client to interact with Govee Developer API."""

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

        devices = response.get("data", {}).get("devices", [])
        _LOGGER.debug("Found %d devices", len(devices))

        return devices

    async def async_control_device(
        self,
        device: str,
        model: str,
        cmd_name: str,
        cmd_value: Any,
    ) -> bool:
        """Send a control command to a device.

        Args:
            device: Device MAC address.
            model: Device model.
            cmd_name: Command name (turn, brightness, color, colorTem).
            cmd_value: Command value.

        Returns:
            True if command was successful.

        Raises:
            GoveeApiError: If the request fails.
        """
        _LOGGER.debug(
            "Sending command to device %s: %s=%s",
            device,
            cmd_name,
            cmd_value,
        )

        payload = {
            "device": device,
            "model": model,
            "cmd": {
                "name": cmd_name,
                "value": cmd_value,
            },
        }

        await self._request("PUT", API_CONTROL_ENDPOINT, json_data=payload)
        return True

    async def async_turn_on(self, device: str, model: str) -> bool:
        """Turn on a device.

        Args:
            device: Device MAC address.
            model: Device model.

        Returns:
            True if successful.
        """
        return await self.async_control_device(device, model, CMD_TURN, "on")

    async def async_turn_off(self, device: str, model: str) -> bool:
        """Turn off a device.

        Args:
            device: Device MAC address.
            model: Device model.

        Returns:
            True if successful.
        """
        return await self.async_control_device(device, model, CMD_TURN, "off")

    async def async_set_brightness(
        self,
        device: str,
        model: str,
        brightness: int,
    ) -> bool:
        """Set device brightness.

        Args:
            device: Device MAC address.
            model: Device model.
            brightness: Brightness level (0-100).

        Returns:
            True if successful.
        """
        brightness = max(0, min(100, brightness))
        return await self.async_control_device(
            device, model, CMD_BRIGHTNESS, brightness
        )

    async def async_set_color(
        self,
        device: str,
        model: str,
        r: int,
        g: int,
        b: int,
    ) -> bool:
        """Set device color.

        Args:
            device: Device MAC address.
            model: Device model.
            r: Red component (0-255).
            g: Green component (0-255).
            b: Blue component (0-255).

        Returns:
            True if successful.
        """
        color_value = {
            "r": max(0, min(255, r)),
            "g": max(0, min(255, g)),
            "b": max(0, min(255, b)),
        }
        return await self.async_control_device(device, model, CMD_COLOR, color_value)

    async def async_set_color_temperature(
        self,
        device: str,
        model: str,
        kelvin: int,
    ) -> bool:
        """Set device color temperature.

        Args:
            device: Device MAC address.
            model: Device model.
            kelvin: Color temperature in Kelvin.

        Returns:
            True if successful.
        """
        return await self.async_control_device(device, model, CMD_COLOR_TEM, kelvin)

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
