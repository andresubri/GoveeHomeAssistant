"""Constants for the Govee integration."""

from typing import Final

# Integration domain
DOMAIN: Final = "govee_h600d"

# Configuration keys
CONF_API_KEY: Final = "api_key"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds

# API endpoints (Govee OpenAPI)
API_BASE_URL: Final = "https://openapi.api.govee.com"
API_DEVICES_ENDPOINT: Final = "/router/api/v1/user/devices"
API_CONTROL_ENDPOINT: Final = "/router/api/v1/device/control"

# API headers
API_KEY_HEADER: Final = "Govee-API-Key"

# Capability types
CAP_ON_OFF: Final = "devices.capabilities.on_off"
CAP_RANGE: Final = "devices.capabilities.range"
CAP_COLOR_SETTING: Final = "devices.capabilities.color_setting"

# Capability instances
CAP_INSTANCE_POWER: Final = "powerSwitch"
CAP_INSTANCE_BRIGHTNESS: Final = "brightness"
CAP_INSTANCE_COLOR_RGB: Final = "colorRgb"
CAP_INSTANCE_COLOR_TEMP: Final = "colorTemperatureK"

# Device types
DEVICE_TYPE_LIGHT: Final = "devices.types.light"

# Brightness conversion
HA_BRIGHTNESS_MIN: Final = 1
HA_BRIGHTNESS_MAX: Final = 255
API_BRIGHTNESS_MIN: Final = 1
API_BRIGHTNESS_MAX: Final = 100

# Color temperature defaults (Kelvin)
DEFAULT_MIN_COLOR_TEMP_KELVIN: Final = 2000
DEFAULT_MAX_COLOR_TEMP_KELVIN: Final = 9000

# Rate limiting
MIN_TIME_BETWEEN_UPDATES: Final = 1  # seconds
API_TIMEOUT: Final = 10  # seconds

# Device properties
DEVICE_ATTR_DEVICE: Final = "device"
DEVICE_ATTR_SKU: Final = "sku"
DEVICE_ATTR_DEVICE_NAME: Final = "deviceName"
DEVICE_ATTR_TYPE: Final = "type"
DEVICE_ATTR_CAPABILITIES: Final = "capabilities"

# Logging
LOGGER_NAME: Final = DOMAIN
