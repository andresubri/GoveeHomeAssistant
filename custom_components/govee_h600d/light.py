"""Light platform for Govee H600D integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    API_BRIGHTNESS_MAX,
    API_BRIGHTNESS_MIN,
    CMD_BRIGHTNESS,
    CMD_COLOR,
    CMD_COLOR_TEM,
    CMD_TURN,
    CONF_FILTER_ALL_LIGHTS,
    CONF_MODEL_FILTER,
    DEFAULT_FILTER_ALL_LIGHTS,
    DEFAULT_MAX_COLOR_TEMP_KELVIN,
    DEFAULT_MIN_COLOR_TEMP_KELVIN,
    DEFAULT_MODEL_FILTER,
    DEVICE_ATTR_CONTROLLABLE,
    DEVICE_ATTR_DEVICE,
    DEVICE_ATTR_DEVICE_NAME,
    DEVICE_ATTR_MODEL,
    DEVICE_ATTR_PROPERTIES,
    DEVICE_ATTR_SUPPORT_CMDS,
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
    """Set up Govee H600D light entities from a config entry.

    Args:
        hass: Home Assistant instance.
        config_entry: Config entry.
        async_add_entities: Callback to add entities.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    api_client = hass.data[DOMAIN][config_entry.entry_id]["api_client"]

    # Get filter settings from options
    model_filter = config_entry.options.get(CONF_MODEL_FILTER, DEFAULT_MODEL_FILTER)
    filter_all_lights = config_entry.options.get(
        CONF_FILTER_ALL_LIGHTS, DEFAULT_FILTER_ALL_LIGHTS
    )

    entities = []
    for device in coordinator.data:
        # Skip non-controllable devices
        if not device.get(DEVICE_ATTR_CONTROLLABLE, False):
            continue

        # Apply model filter unless "all lights" is enabled
        if not filter_all_lights:
            device_model = device.get(DEVICE_ATTR_MODEL, "")
            if model_filter and model_filter.upper() not in device_model.upper():
                _LOGGER.debug(
                    "Skipping device %s with model %s (filter: %s)",
                    device.get(DEVICE_ATTR_DEVICE),
                    device_model,
                    model_filter,
                )
                continue

        # Check if device supports turn command (basic light functionality)
        support_cmds = device.get(DEVICE_ATTR_SUPPORT_CMDS, [])
        if CMD_TURN not in support_cmds:
            _LOGGER.debug(
                "Skipping device %s - does not support turn command",
                device.get(DEVICE_ATTR_DEVICE),
            )
            continue

        entities.append(
            GoveeH600DLight(
                coordinator=coordinator,
                api_client=api_client,
                device_data=device,
                config_entry=config_entry,
            )
        )

    _LOGGER.info("Adding %d Govee light entities", len(entities))
    async_add_entities(entities)


def _ha_to_api_brightness(ha_brightness: int) -> int:
    """Convert Home Assistant brightness (1-255) to API brightness (0-100).

    Args:
        ha_brightness: Brightness value from Home Assistant (1-255).

    Returns:
        Brightness value for API (0-100).
    """
    # Scale from 1-255 to 0-100
    return round(
        (ha_brightness - HA_BRIGHTNESS_MIN)
        * (API_BRIGHTNESS_MAX - API_BRIGHTNESS_MIN)
        / (HA_BRIGHTNESS_MAX - HA_BRIGHTNESS_MIN)
        + API_BRIGHTNESS_MIN
    )


def _api_to_ha_brightness(api_brightness: int) -> int:
    """Convert API brightness (0-100) to Home Assistant brightness (1-255).

    Args:
        api_brightness: Brightness value from API (0-100).

    Returns:
        Brightness value for Home Assistant (1-255).
    """
    # Scale from 0-100 to 1-255
    return round(
        (api_brightness - API_BRIGHTNESS_MIN)
        * (HA_BRIGHTNESS_MAX - HA_BRIGHTNESS_MIN)
        / (API_BRIGHTNESS_MAX - API_BRIGHTNESS_MIN)
        + HA_BRIGHTNESS_MIN
    )


class GoveeH600DLight(CoordinatorEntity, LightEntity):
    """Representation of a Govee H600D light."""

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
        self._device_mac = device_data.get(DEVICE_ATTR_DEVICE, "")
        self._device_model = device_data.get(DEVICE_ATTR_MODEL, "")
        self._device_name = device_data.get(DEVICE_ATTR_DEVICE_NAME, "Govee Light")
        self._support_cmds = device_data.get(DEVICE_ATTR_SUPPORT_CMDS, [])
        self._properties = device_data.get(DEVICE_ATTR_PROPERTIES, {})

        # Unique ID based on device MAC
        self._attr_unique_id = f"{DOMAIN}_{self._device_mac.replace(':', '_')}"

        # Set entity name (will be combined with device name)
        self._attr_name = None  # Use device name only

        # Determine supported color modes
        self._attr_supported_color_modes = self._determine_color_modes()
        self._attr_color_mode = self._get_default_color_mode()

        # Set color temperature range
        self._attr_min_color_temp_kelvin = self._get_min_color_temp()
        self._attr_max_color_temp_kelvin = self._get_max_color_temp()

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_mac)},
            name=self._device_name,
            manufacturer="Govee",
            model=self._device_model,
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

        if CMD_COLOR in self._support_cmds:
            modes.add(ColorMode.RGB)

        if CMD_COLOR_TEM in self._support_cmds:
            modes.add(ColorMode.COLOR_TEMP)

        # If brightness is supported but no color modes, use brightness mode
        if CMD_BRIGHTNESS in self._support_cmds and not modes:
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
        # Try to get from device properties
        if isinstance(self._properties, dict):
            color_tem = self._properties.get("colorTem", {})
            if isinstance(color_tem, dict):
                range_info = color_tem.get("range", {})
                if isinstance(range_info, dict) and "min" in range_info:
                    return range_info["min"]

        return DEFAULT_MIN_COLOR_TEMP_KELVIN

    def _get_max_color_temp(self) -> int:
        """Get maximum color temperature in Kelvin.

        Returns:
            Maximum color temperature.
        """
        # Try to get from device properties
        if isinstance(self._properties, dict):
            color_tem = self._properties.get("colorTem", {})
            if isinstance(color_tem, dict):
                range_info = color_tem.get("range", {})
                if isinstance(range_info, dict) and "max" in range_info:
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

        # Try to get from coordinator data
        device_data = self._get_device_data()
        if device_data:
            properties = device_data.get(DEVICE_ATTR_PROPERTIES, {})
            if isinstance(properties, dict):
                power_state = properties.get("powerState")
                if power_state is not None:
                    return power_state == "on"

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

        # Try to get from coordinator data
        device_data = self._get_device_data()
        if device_data:
            properties = device_data.get(DEVICE_ATTR_PROPERTIES, {})
            if isinstance(properties, dict):
                api_brightness = properties.get("brightness")
                if api_brightness is not None:
                    return _api_to_ha_brightness(api_brightness)

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

        # Try to get from coordinator data
        device_data = self._get_device_data()
        if device_data:
            properties = device_data.get(DEVICE_ATTR_PROPERTIES, {})
            if isinstance(properties, dict):
                color = properties.get("color")
                if isinstance(color, dict):
                    r = color.get("r", 0)
                    g = color.get("g", 0)
                    b = color.get("b", 0)
                    return (r, g, b)

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

        # Try to get from coordinator data
        device_data = self._get_device_data()
        if device_data:
            properties = device_data.get(DEVICE_ATTR_PROPERTIES, {})
            if isinstance(properties, dict):
                color_tem = properties.get("colorTemInKelvin")
                if color_tem is not None:
                    return color_tem

        return None

    def _get_device_data(self) -> dict[str, Any] | None:
        """Get the current device data from coordinator.

        Returns:
            Device data dictionary or None.
        """
        if self.coordinator.data:
            for device in self.coordinator.data:
                if device.get(DEVICE_ATTR_DEVICE) == self._device_mac:
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
                self._device_mac,
                self._device_model,
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
                self._device_mac,
                self._device_model,
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
                self._device_mac,
                self._device_model,
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
                self._device_mac,
                self._device_model,
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
            self._device_mac,
            self._device_model,
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
