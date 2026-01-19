# Govee Home Assistant Integration

A custom Home Assistant integration for controlling Govee Smart LED Bulbs using the Govee Developer API.

## Features

- **Device Discovery**: Automatically discovers Govee devices via the cloud API
- **Light Controls**:
  - On/Off toggle
  - Brightness control (0-100%)
  - RGB color support
  - Color temperature (Kelvin)
- **UI Configuration**: Setup via Home Assistant's Integrations UI (no YAML required)
- **Options Flow**: Configure scan interval and device filtering after setup
- **Optimistic Updates**: Immediate UI feedback while cloud commands are processed

## Requirements

- Home Assistant Core 2023.1 or later
- Govee Developer API key (free from Govee Home app)

## Installation

### HACS (Recommended)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance

2. Add this repository as a custom repository in HACS:
   - Open HACS in Home Assistant
   - Click on **Integrations**
   - Click the three dots menu in the top right
   - Select **Custom repositories**
   - Add `https://github.com/andresubri/GoveeHomeAssistant` as the repository URL
   - Select **Integration** as the category
   - Click **Add**

3. Search for "Govee H600D" in HACS and install it

4. Restart Home Assistant

5. Go to **Settings** > **Devices & Services** > **Add Integration**

6. Search for "Govee H600D" and follow the setup wizard

### Manual Installation

1. Copy the `custom_components/govee_h600d` folder to your Home Assistant's `custom_components` directory:
   ```
   <config>/custom_components/govee_h600d/
   ```

2. Restart Home Assistant

3. Go to **Settings** > **Devices & Services** > **Add Integration**

4. Search for "Govee H600D" and click to add

5. Enter your Govee API key and configure options

### Getting a Govee API Key

1. Open the **Govee Home** app on your mobile device
2. Go to **Settings** (gear icon)
3. Tap **About Us**
4. Tap **Apply for API Key**
5. Follow the instructions to receive your API key via email

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| API Key | (required) | Your Govee Developer API key |
| Scan Interval | 30 seconds | How often to poll the API for updates (10-300 seconds) |
| Model Filter | H600D | Only discover devices matching this model |
| Include All Lights | false | If enabled, discovers all controllable lights regardless of model |

## Supported Commands

The integration detects device capabilities and enables features accordingly:

- **turn**: On/Off control
- **brightness**: Brightness level (converted between HA 1-255 and API 0-100)
- **color**: RGB color control
- **colorTem**: Color temperature in Kelvin

## Architecture

```
custom_components/govee_h600d/
├── __init__.py          # Integration setup and coordinator
├── api.py               # Govee API client
├── config_flow.py       # UI configuration flow
├── const.py             # Constants and configuration
├── light.py             # Light entity implementation
├── manifest.json        # Integration manifest
├── strings.json         # Translation strings
└── translations/
    └── en.json          # English translations
```

## API Rate Limiting

The Govee API has rate limits. This integration:
- Uses a `DataUpdateCoordinator` for efficient polling
- Caches device state between updates
- Applies optimistic updates after commands
- Defaults to 30-second polling interval (configurable)

## Troubleshooting

### "Invalid API key" error
- Verify your API key is correct
- Ensure you applied for a **Developer** API key, not just user account access
- Check that the API key hasn't expired

### Devices not discovered
- Ensure devices are set up in the Govee Home app
- Check the model filter matches your device model
- Try enabling "Include All Controllable Lights" option

### Slow response times
- Cloud API latency is normal (1-3 seconds)
- Increase the scan interval if hitting rate limits
- Optimistic updates provide immediate UI feedback

### Debug Logging

Enable debug logging by adding to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.govee_h600d: debug
```

## Known Limitations

- Cloud API only (no local control)
- Rate limits may affect heavy usage scenarios
- Some device states may not be retrievable (optimistic updates used)
- Device capability detection depends on API response accuracy

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or supported by Govee. Use at your own risk.
