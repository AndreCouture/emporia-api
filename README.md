# Emporia API

![CI Status](https://github.com/AndreCouture/emporia-api/actions/workflows/ci.yml/badge.svg)
![Python Versions](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A Python API wrapper for Emporia Energy devices, enabling seamless integration with Emporia EV chargers and energy monitors. Provides intuitive access to device control, real-time monitoring, consumption tracking, and more.

> **Note:** This is an unofficial API wrapper. Use this repository to report issues, request features, or provide feedback.

## Features

- AWS Cognito SRP authentication
- EV charger control and monitoring
- Real-time device status via SSE streaming
- Device usage and consumption queries
- Rate/tariff management
- Automatic token refresh

## Installation

### From GitHub (Recommended)

```bash
# Install latest stable version
pip install git+https://github.com/AndreCouture/emporia-api.git@main

# Install specific version
pip install git+https://github.com/AndreCouture/emporia-api.git@v1.0.0

# Install development version
pip install git+https://github.com/AndreCouture/emporia-api.git@dev
```

### From Requirements File

```txt
# requirements.txt
# Latest stable
git+https://github.com/AndreCouture/emporia-api.git@main#egg=emporia-api

# Specific version (recommended for production)
git+https://github.com/AndreCouture/emporia-api.git@v1.0.0#egg=emporia-api
```

### Local Development

```bash
git clone https://github.com/AndreCouture/emporia-api.git
cd emporia-api
pip install -e .
```

## Quick Start

```python
from emporia_api import EmporiaAPI

# Configure with your Emporia account credentials
config = {
    'user_pool_id': 'us-east-2_ghlOXVLi1',
    'client_id': '4qte47jbstod8apnfic0bunmrq',
    'region': 'us-east-2',
    'emporia_username': 'your_username@example.com',
    'emporia_password': 'your_password'
}

# Initialize and authenticate
api = EmporiaAPI(config)
api.authenticate()

# Get all EV chargers
chargers = api.get_ev_chargers()
print(f"Found {len(chargers)} EV charger(s)")

# Control a charger
api.set_ev_charger(True)  # Turn ON
api.set_ev_charger(False)  # Turn OFF

# Get real-time consumption
usage = api.get_instant_usage(device_gids=[12345], energy_unit="KILOWATT_HOURS")
print(f"Current usage: {usage[12345]} kW")
```

## Advanced Usage

### Real-Time Device Monitoring (SSE Stream)

```python
import threading

def handle_status_event(event):
    """Called when device status changes"""
    if event.get("event_type") == "DEVICE_STATUS":
        evses = event.get("data", {}).get("evses", [])
        for evse in evses:
            print(f"Charger {evse['device_gid']}: {evse['charger_status']}")

# Start SSE stream in background thread
stop_event = threading.Event()
stream_thread = threading.Thread(
    target=api.stream_device_status,
    args=(handle_status_event, stop_event)
)
stream_thread.start()

# ... do other work ...

# Stop streaming when done
stop_event.set()
stream_thread.join()
```

**Example SSE Event Data:**

```json
{
  "event_type": "DEVICE_STATUS",
  "data": {
    "devices_connected": [],
    "batteries": [],
    "evses": [
      {
        "device_id": "REDACTED",
        "device_gid": 123456,
        "load_gid": 789012,
        "charger_status": "CHARGING"
      }
    ],
    "outlets": []
  }
}
```

The `charger_status` field can be: `IDLE`, `CHARGING`, `READY`, `DISCONNECTED`, etc.

### Multi-Device Consumption Tracking

```python
from datetime import datetime, timezone

# Get instant usage for multiple devices at once
device_ids = [12345, 67890]
usage_data = api.get_instant_usage(
    device_gids=device_ids,
    energy_unit="KILOWATT_HOURS"
)

for device_id, watts in usage_data.items():
    print(f"Device {device_id}: {watts}W")
```

### Historical Usage Data

```python
from datetime import datetime, timedelta, timezone

# Get last hour of usage data
end = datetime.now(timezone.utc)
start = end - timedelta(hours=1)

usage = api.get_chart_usage(
    device_gid=12345,
    channel="1,2,3",
    start=start.isoformat(),
    end=end.isoformat(),
    scale="1S",  # 1-second resolution
    energy_unit="KilowattHours"
)

print(f"First reading: {usage['firstUsageInstant']}")
print(f"Data points: {len(usage['usageList'])}")
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

## Versioning

This library follows [Semantic Versioning](https://semver.org/). Version numbers use the format `MAJOR.MINOR.PATCH`:

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backwards-compatible)
- **PATCH**: Bug fixes (backwards-compatible)

### Checking Version

```python
import emporia_api
print(emporia_api.__version__)  # e.g., "1.0.0"
print(emporia_api.__version_info__)  # e.g., (1, 0, 0)
```

### Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

### Pinning Versions

For production use, pin to a specific version tag:

```bash
pip install git+https://github.com/AndreCouture/emporia-api.git@v1.0.0
```

Or in `requirements.txt`:
```txt
git+https://github.com/AndreCouture/emporia-api.git@v1.0.0#egg=emporia-api
```

## Configuration

The API requires AWS Cognito credentials for authentication. These values are specific to Emporia's infrastructure:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `user_pool_id` | `us-east-2_ghlOXVLi1` | AWS Cognito User Pool ID (not secret) |
| `client_id` | `4qte47jbstod8apnfic0bunmrq` | AWS Cognito Client ID (not secret) |
| `region` | `us-east-2` | AWS Region (not secret) |
| `emporia_username` | Your email | Your Emporia account email (secret) |
| `emporia_password` | Your password | Your Emporia account password (secret) |

> **Note**: The `user_pool_id`, `client_id`, and `region` parameters are publicly visible identifiers used by Emporia's web application and mobile apps. They are not sensitive credentials. Only your username and password should be kept secret.

## Supported Devices

- **EV Chargers**: Emporia EV chargers with real-time control and monitoring
- **Energy Monitors**: Emporia Vue and Vue 2 energy monitors
- **Smart Outlets**: Emporia smart plugs (experimental)

## API Endpoints

This library uses both legacy and modern Emporia API endpoints:

- **Legacy API**: `api.emporiaenergy.com/AppAPI` (being phased out)
- **Modern C-API**: `c-api.emporiaenergy.com/v1/` (recommended)
- **SSE Stream**: `c-api.emporiaenergy.com/v1/customers/stream` (real-time events)

## Contributing

Contributions are welcome! Please feel free to:

- Report bugs via [GitHub Issues](https://github.com/AndreCouture/emporia-api/issues)
- Request features or enhancements
- Submit pull requests with improvements

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/AndreCouture/emporia-api.git
cd emporia-api

# Install development dependencies
pip install -r requirements-dev.txt

# Or install with optional dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests with pytest
pytest

# Run with coverage report
pytest --cov=emporia_api --cov-report=html

# Run specific test file
pytest test_emporia_api.py -v

# Run with unittest (legacy)
python test_emporia_api.py
```

### Security Scanning

```bash
# Run Bandit (security linter)
bandit -r emporia_api/

# Check for dependency vulnerabilities
safety check

# Audit dependencies
pip-audit
```

### Code Quality

```bash
# Format code with Black
black emporia_api/

# Sort imports
isort emporia_api/

# Lint with flake8
flake8 emporia_api/

# Lint with pylint
pylint emporia_api/
```

### CI/CD

The project uses GitHub Actions for automated testing and security checks:

- **Tests**: Runs on Python 3.9, 3.10, 3.11, 3.12, and 3.13
- **Security**: Bandit, Safety, and pip-audit scans
- **Code Quality**: flake8, pylint, black, and isort checks
- **Build**: Package build verification

### Code Structure

```
emporia_api/
├── __init__.py       # Package exports
└── api.py            # Main EmporiaAPI class
```

## Troubleshooting

### Authentication Errors

If you receive authentication errors when logging in, Emporia may have updated their AWS Cognito configuration. Common error messages include:

- `ClientError: An error occurred (ResourceNotFoundException) when calling the InitiateAuth operation: User pool client does not exist.`
- `ClientError: An error occurred (NotAuthorizedException) when calling the InitiateAuth operation`
- HTTP 400/401 errors during authentication

#### Extracting Updated Cognito Credentials

If you encounter these errors, you can extract the current `user_pool_id` and `client_id` from Emporia's web application:

1. **Open Emporia Web App** in your browser:
   - Navigate to https://web.emporiaenergy.com/
   - Open your browser's Developer Tools (F12 or right-click → Inspect)

2. **Go to Network Tab**:
   - Switch to the "Network" tab in Developer Tools
   - Check "Preserve log" to keep requests visible

3. **Log in to Emporia**:
   - Enter your email and password
   - Click "Sign In"

4. **Find Cognito Request**:
   - Look for a request to `cognito-idp.us-east-2.amazonaws.com`
   - Click on the request to view details

5. **Extract Values from Request Headers**:
   - In the "Headers" tab, find `X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth`
   - In the "Payload" or "Request" tab, you'll see JSON like:
   ```json
   {
     "AuthParameters": {
       "USERNAME": "your-email@example.com",
       "SRP_A": "..."
     },
     "AuthFlow": "USER_SRP_AUTH",
     "ClientId": "4qte47jbstod8apnfic0bunmrq"
   }
   ```
   - Note the `ClientId` value

6. **Extract User Pool ID**:
   - In the same request or nearby Cognito requests, look for:
   ```json
   {
     "UserPoolId": "us-east-2_ghlOXVLi1",
     ...
   }
   ```
   - Or check the request URL which may contain the region (e.g., `cognito-idp.us-east-2.amazonaws.com`)

7. **Update Your Configuration**:
   ```python
   api = EmporiaAPI(
       emporia_username="your-email@example.com",
       emporia_password="your-password",
       user_pool_id="us-east-2_ghlOXVLi1",  # Updated value
       client_id="4qte47jbstod8apnfic0bunmrq",  # Updated value
       region="us-east-2"  # Extracted from URL
   )
   ```

### Other Common Issues

- **Rate Limiting**: If you see HTTP 429 errors, reduce polling frequency
- **SSE Stream Disconnects**: The library automatically reconnects, but check your network stability
- **Token Expiration**: Tokens are automatically refreshed; if issues persist, delete token cache and re-authenticate

If problems continue, please [open an issue](https://github.com/AndreCouture/emporia-api/issues) with error details.

## Dependencies

- `requests` - HTTP client library
- `boto3` - AWS SDK for Cognito authentication
- `warrant` - AWS Cognito SRP authentication
- `python-jose[cryptography]` - JWT token handling
- `cryptography` - Cryptographic operations
- `python-dateutil` - Date/time utilities

## Related Projects

- [emporia-mqtt-service](https://github.com/AndreCouture/emporia-mqtt-service) - MQTT bridge for home automation
- [PyEmVue](https://github.com/magico13/PyEmVue) - Alternative Emporia API wrapper

## Disclaimer

This is an unofficial API wrapper and is not affiliated with, endorsed by, or connected to Emporia Energy. Use at your own risk.

## License

MIT License - See [LICENSE](LICENSE) file for details
