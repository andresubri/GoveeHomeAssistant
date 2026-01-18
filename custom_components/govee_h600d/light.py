"""Light platform for Govee integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    API_BRIGHTNESS_MAX,
    API_BRIGHTNESS_MIN,
    CAP_COLOR_SETTING,
    CAP_INSTANCE_BRIGHTNESS,
    CAP_INSTANCE_COLOR_RGB,
    CAP_INSTANCE_COLOR_TEMP,
    CAP_INSTANCE_POWER,
    CAP_ON_OFF,
    CAP_RANGE,
    DEFAULT_MAX_COLOR_TEMP_KELVIN,
    DEFAULT_MIN_COLOR_TEMP_KELVIN,
    DEVICE_ATTR_CAPABILITIES,
    DEVICE_ATTR_DEVICE,
    DEVICE_ATTR_DEVICE_NAME,
    DEVICE_ATTR_SKU,
    DEVICE_ATTR_TYPE,
    DEVICE_TYPE_LIGHT,
    DOMAIN,
    HA_BRIGHTNESS_MAX,
    HA_BRIGHTNESS_MIN,
)

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Govee light entities from a config entry.

    Args:
        hass: Home Assistant instance.
        config_entry: Config entry.
        async_add_entities: Callback to add entities.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    api_client = hass.data[DOMAIN][config_entry.entry_id]["api_client"]

    entities = []
    for device in coordinator.data:
        device_type = device.get(DEVICE_ATTR_TYPE, "")

        # Only add light devices
        if device_type != DEVICE_TYPE_LIGHT:
            _LOGGER.debug(
                "Skipping device %s with type %s (not a light)",
                device.get(DEVICE_ATTR_DEVICE),
                device_type,
            )
            continue

        # Check if device has on/off capability (basic light functionality)
        capabilities = device.get(DEVICE_ATTR_CAPABILITIES, [])
        has_power_control = any(
            cap.get("type") == CAP_ON_OFF and cap.get("instance") == CAP_INSTANCE_POWER
            for cap in capabilities
        )

        if not has_power_control:
            _LOGGER.debug(
                "Skipping device %s - does not support power control",
                device.get(DEVICE_ATTR_DEVICE),
            )
            continue

        entities.append(
            GoveeLight(
                coordinator=coordinator,
                api_client=api_client,
                device_data=device,
                config_entry=config_entry,
            )
        )

    _LOGGER.info("Adding %d Govee light entities", len(entities))
    async_add_entities(entities)


def _ha_to_api_brightness(ha_brightness: int) -> int:
    """Convert Home Assistant brightness (1-255) to API brightness (1-100).

    Args:
        ha_brightness: Brightness value from Home Assistant (1-255).

    Returns:
        Brightness value for API (1-100).
    """
    # Scale from 1-255 to 1-100
    return round(
        (ha_brightness - HA_BRIGHTNESS_MIN)
        * (API_BRIGHTNESS_MAX - API_BRIGHTNESS_MIN)
        / (HA_BRIGHTNESS_MAX - HA_BRIGHTNESS_MIN)
        + API_BRIGHTNESS_MIN
    )


def _api_to_ha_brightness(api_brightness: int) -> int:
    """Convert API brightness (1-100) to Home Assistant brightness (1-255).

    Args:
        api_brightness: Brightness value from API (1-100).

    Returns:
        Brightness value for Home Assistant (1-255).
    """
    # Scale from 1-100 to 1-255
    return round(
        (api_brightness - API_BRIGHTNESS_MIN)
        * (HA_BRIGHTNESS_MAX - HA_BRIGHTNESS_MIN)
        / (API_BRIGHTNESS_MAX - API_BRIGHTNESS_MIN)
        + HA_BRIGHTNESS_MIN
    )


def _get_capability(capabilities: list[dict], cap_type: str, instance: str) -> dict | None:
    """Get a specific capability from the capabilities list.

    Args:
        capabilities: List of capability dictionaries.
        cap_type: Capability type to find.
        instance: Capability instance to find.

    Returns:
        Capability dictionary or None if not found.
    """
    for cap in capabilities:
        if cap.get("type") == cap_type and cap.get("instance") == instance:
            return cap
    return None


class GoveeLight(CoordinatorEntity, LightEntity):
    """Representation of a Govee light."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        api_client,
        device_data: dict[str, Any],
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the light entity.

        Args:
            coordinator: Data update coordinator.
            api_client: Govee API client.
            device_data: Device data from API.
            config_entry: Config entry.
        """
        super().__init__(coordinator)

        self._api_client = api_client
        self._device_id = device_data.get(DEVICE_ATTR_DEVICE, "")
        self._device_sku = device_data.get(DEVICE_ATTR_SKU, "")
        self._device_name = device_data.get(DEVICE_ATTR_DEVICE_NAME, "Govee Light")
        self._capabilities = device_data.get(DEVICE_ATTR_CAPABILITIES, [])

        # Unique ID based on device ID
        self._attr_unique_id = f"{DOMAIN}_{self._device_id.replace(':', '_')}"

        # Set entity name (will be combined with device name)
        self._attr_name = None  # Use device name only

        # Determine supported color modes
        self._attr_supported_color_modes = self._determine_color_modes()
        self._attr_color_mode = self._get_default_color_mode()

        # Set color temperature range from capabilities
        self._attr_min_color_temp_kelvin = self._get_min_color_temp()
        self._attr_max_color_temp_kelvin = self._get_max_color_temp()

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="Govee",
            model=self._device_sku,
            via_device=(DOMAIN, config_entry.entry_id),
        )

        # Optimistic state tracking
        self._optimistic_state: dict[str, Any] = {
            "is_on": None,
            "brightness": None,
            "rgb_color": None,
            "color_temp_kelvin": None,
        }

    def _determine_color_modes(self) -> set[ColorMode]:
        """Determine supported color modes based on device capabilities.

        Returns:
            Set of supported ColorModes.
        """
        modes: set[ColorMode] = set()

        # Check for RGB color support
        if _get_capability(self._capabilities, CAP_COLOR_SETTING, CAP_INSTANCE_COLOR_RGB):
            modes.add(ColorMode.RGB)

        # Check for color temperature support
        if _get_capability(self._capabilities, CAP_COLOR_SETTING, CAP_INSTANCE_COLOR_TEMP):
            modes.add(ColorMode.COLOR_TEMP)

        # Check for brightness support (if no color modes)
        if _get_capability(self._capabilities, CAP_RANGE, CAP_INSTANCE_BRIGHTNESS) and not modes:
            modes.add(ColorMode.BRIGHTNESS)

        # If only on/off, use ONOFF mode
        if not modes:
            modes.add(ColorMode.ONOFF)

        return modes

    def _get_default_color_mode(self) -> ColorMode:
        """Get the default color mode.

        Returns:
            Default ColorMode for this device.
        """
        if ColorMode.RGB in self._attr_supported_color_modes:
            return ColorMode.RGB
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    def _get_min_color_temp(self) -> int:
        """Get minimum color temperature in Kelvin.

        Returns:
            Minimum color temperature.
        """
        cap = _get_capability(self._capabilities, CAP_COLOR_SETTING, CAP_INSTANCE_COLOR_TEMP)
        if cap:
            params = cap.get("parameters", {})
            range_info = params.get("range", {})
            if "min" in range_info:
                return range_info["min"]

        return DEFAULT_MIN_COLOR_TEMP_KELVIN

    def _get_max_color_temp(self) -> int:
        """Get maximum color temperature in Kelvin.

        Returns:
            Maximum color temperature.
        """
        cap = _get_capability(self._capabilities, CAP_COLOR_SETTING, CAP_INSTANCE_COLOR_TEMP)
        if cap:
            params = cap.get("parameters", {})
            range_info = params.get("range", {})
            if "max" in range_info:
                return range_info["max"]

        return DEFAULT_MAX_COLOR_TEMP_KELVIN

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on.

        Returns:
            True if the light is on, False otherwise, None if unknown.
        """
        # Use optimistic state if available
        if self._optimistic_state["is_on"] is not None:
            return self._optimistic_state["is_on"]

        # State is not retrievable from this API without device state endpoint
        return None

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light.

        Returns:
            Brightness value (1-255) or None if unknown.
        """
        # Use optimistic state if available
        if self._optimistic_state["brightness"] is not None:
            return self._optimistic_state["brightness"]

        return None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color of the light.

        Returns:
            RGB tuple or None if unknown.
        """
        # Use optimistic state if available
        if self._optimistic_state["rgb_color"] is not None:
            return self._optimistic_state["rgb_color"]

        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin.

        Returns:
            Color temperature or None if unknown.
        """
        # Use optimistic state if available
        if self._optimistic_state["color_temp_kelvin"] is not None:
            return self._optimistic_state["color_temp_kelvin"]

        return None

    def _get_device_data(self) -> dict[str, Any] | None:
        """Get the current device data from coordinator.

        Returns:
            Device data dictionary or None.
        """
        if self.coordinator.data:
            for device in self.coordinator.data:
                if device.get(DEVICE_ATTR_DEVICE) == self._device_id:
                    return device
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on.

        Args:
            **kwargs: Additional arguments (brightness, rgb_color, color_temp_kelvin).
        """
        _LOGGER.debug(
            "Turning on %s with kwargs: %s",
            self._device_name,
            kwargs,
        )

        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs:
            ha_brightness = kwargs[ATTR_BRIGHTNESS]
            api_brightness = _ha_to_api_brightness(ha_brightness)
            await self._api_client.async_set_brightness(
                self._device_id,
                self._device_sku,
                api_brightness,
            )
            self._optimistic_state["brightness"] = ha_brightness
            self._optimistic_state["is_on"] = True
            # Update color mode if needed
            if self._attr_color_mode not in (ColorMode.RGB, ColorMode.COLOR_TEMP):
                self._attr_color_mode = ColorMode.BRIGHTNESS

        # Handle RGB color
        elif ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            await self._api_client.async_set_color(
                self._device_id,
                self._device_sku,
                r,
                g,
                b,
            )
            self._optimistic_state["rgb_color"] = (r, g, b)
            self._optimistic_state["is_on"] = True
            self._attr_color_mode = ColorMode.RGB
            # Clear color temp when setting RGB
            self._optimistic_state["color_temp_kelvin"] = None

        # Handle color temperature
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            # Clamp to device-supported range
            kelvin = max(
                self._attr_min_color_temp_kelvin,
                min(self._attr_max_color_temp_kelvin, kelvin),
            )
            await self._api_client.async_set_color_temperature(
                self._device_id,
                self._device_sku,
                kelvin,
            )
            self._optimistic_state["color_temp_kelvin"] = kelvin
            self._optimistic_state["is_on"] = True
            self._attr_color_mode = ColorMode.COLOR_TEMP
            # Clear RGB when setting color temp
            self._optimistic_state["rgb_color"] = None

        # Just turn on (no specific attribute)
        else:
            await self._api_client.async_turn_on(
                self._device_id,
                self._device_sku,
            )
            self._optimistic_state["is_on"] = True

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off.

        Args:
            **kwargs: Additional arguments (unused).
        """
        _LOGGER.debug("Turning off %s", self._device_name)

        await self._api_client.async_turn_off(
            self._device_id,
            self._device_sku,
        )

        self._optimistic_state["is_on"] = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        This clears optimistic state when real data is received.
        """
        # Clear optimistic state on coordinator update
        # to allow real values to take precedence
        self._optimistic_state = {
            "is_on": None,
            "brightness": None,
            "rgb_color": None,
            "color_temp_kelvin": None,
        }
        super()._handle_coordinator_update()
