# Emporia API

A Python API wrapper for Emporia Energy devices, providing authentication and device control functionality.

## Features

- AWS Cognito SRP authentication
- EV charger control and monitoring
- Real-time device status via SSE streaming
- Device usage and consumption queries
- Rate/tariff management
- Automatic token refresh

## Installation

### Local Development

```bash
pip install -e /path/to/emporia-api
```

### From Requirements

```bash
pip install -e ../emporia-api
```

## Usage

```python
from emporia_api import EmporiaAPI

config = {
    'user_pool_id': 'us-east-2_ghlOXVLi1',
    'client_id': '4qte47jbstod8apnfic0bunmrq',
    'region': 'us-east-2',
    'emporia_username': 'your_username',
    'emporia_password': 'your_password'
}

api = EmporiaAPI(config)
api.authenticate()

# Get EV chargers
chargers = api.get_ev_chargers()

# Control charger
api.set_ev_charger(True)  # Turn on

# Stream real-time status
def handle_event(event):
    print(event)

api.stream_device_status(handle_event)
```

## API Methods

### Authentication
- `authenticate()` - Authenticate with AWS Cognito
- `maybe_reauth()` - Check and refresh token if expired

### Device Status
- `devices()` - Get all devices
- `devices_status()` - Get device status (legacy API)
- `get_devices_status_c_api()` - Get device status (modern c-api)
- `stream_device_status(callback)` - Stream real-time updates via SSE

### EV Chargers
- `get_ev_chargers()` - Get all EV chargers
- `get_ev_charger(index)` - Get charger by index
- `get_ev_charger_by_id(device_gid)` - Get charger by device ID
- `set_ev_charger(on)` - Control first charger
- `set_ev_charger_by_id(device_gid, on)` - Control specific charger

### Usage/Consumption
- `get_current_charging_rate(energyUnit, device_gid)` - Legacy consumption query
- `get_instant_usage(device_gids, energy_unit)` - Efficient batched consumption (recommended)
- `get_chart_usage(device_gid, channel, start, end, scale, energy_unit)` - Historical usage
- `get_devices_usages(device_gids, instant, scale, energy_unit)` - Multi-device usage query

### Rate Management
- `get_devices_rate_properties()` - Get current rates
- `set_devices_rate_properties(new_rate)` - Update electricity rates

### Preferences
- `get_app_preferences()` - Get app preferences

## Development

### Running Tests

```bash
python test_emporia_api.py
```

## Dependencies

- `requests` - HTTP library
- `boto3` - AWS SDK for Cognito authentication
- `warrant` - AWS Cognito SRP authentication
- `python-jose[cryptography]` - JWT handling
- `cryptography` - Cryptographic operations

## License

MIT License
