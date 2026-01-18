"""Constants for the Govee H600D integration."""

from typing import Final

# Integration domain
DOMAIN: Final = "govee_h600d"

# Configuration keys
CONF_API_KEY: Final = "api_key"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_MODEL_FILTER: Final = "model_filter"
CONF_FILTER_ALL_LIGHTS: Final = "filter_all_lights"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
DEFAULT_MODEL_FILTER: Final = "H600D"
DEFAULT_FILTER_ALL_LIGHTS: Final = False

# API endpoints
API_BASE_URL: Final = "https://developer-api.govee.com"
API_DEVICES_ENDPOINT: Final = "/v1/devices"
API_CONTROL_ENDPOINT: Final = "/v1/devices/control"

# API headers
API_KEY_HEADER: Final = "Govee-API-Key"

# API commands
CMD_TURN: Final = "turn"
CMD_BRIGHTNESS: Final = "brightness"
CMD_COLOR: Final = "color"
CMD_COLOR_TEM: Final = "colorTem"

# API command values
VALUE_ON: Final = "on"
VALUE_OFF: Final = "off"

# Brightness conversion
HA_BRIGHTNESS_MIN: Final = 1
HA_BRIGHTNESS_MAX: Final = 255
API_BRIGHTNESS_MIN: Final = 0
API_BRIGHTNESS_MAX: Final = 100

# Color temperature defaults (Kelvin)
DEFAULT_MIN_COLOR_TEMP_KELVIN: Final = 2000
DEFAULT_MAX_COLOR_TEMP_KELVIN: Final = 9000

# Rate limiting
MIN_TIME_BETWEEN_UPDATES: Final = 1  # seconds
API_TIMEOUT: Final = 10  # seconds

# Device properties
DEVICE_ATTR_DEVICE: Final = "device"
DEVICE_ATTR_MODEL: Final = "model"
DEVICE_ATTR_DEVICE_NAME: Final = "deviceName"
DEVICE_ATTR_CONTROLLABLE: Final = "controllable"
DEVICE_ATTR_RETRIEVABLE: Final = "retrievable"
DEVICE_ATTR_SUPPORT_CMDS: Final = "supportCmds"
DEVICE_ATTR_PROPERTIES: Final = "properties"

# Logging
LOGGER_NAME: Final = DOMAIN
