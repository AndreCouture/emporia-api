# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Added timeout parameter (30s) to all HTTP requests for security compliance (CWE-400)
- SSE stream connection intentionally uses no timeout (documented with nosec)

### Changed
- Enhanced SSE stream documentation with example event structure

### Added
- CI/CD pipeline with GitHub Actions
- Multi-Python version testing (3.9-3.13)
- Security scanning (Bandit, Safety, pip-audit)
- Code quality checks (flake8, pylint, black, isort)
- Comprehensive documentation
- Semantic versioning

## [1.0.0] - 2026-01-28

### Added
- Initial public release
- AWS Cognito SRP authentication
- EV charger control and monitoring
- Real-time device status via SSE streaming
- Device usage and consumption queries
- Historical usage data (chart usage)
- Multi-device batched consumption queries
- Rate/tariff management
- App preferences API
- Automatic token refresh
- Support for Python 3.9+

### API Methods
- `authenticate()` - AWS Cognito authentication
- `maybe_reauth()` - Token refresh check
- `devices()` - Get all devices
- `devices_status()` - Legacy device status
- `get_devices_status_c_api()` - Modern C-API device status
- `stream_device_status()` - SSE real-time streaming
- `get_ev_chargers()` - Get EV charger list
- `get_ev_charger()` - Get charger by index
- `get_ev_charger_by_id()` - Get charger by device ID
- `set_ev_charger()` - Control first charger
- `set_ev_charger_by_id()` - Control specific charger
- `get_current_charging_rate()` - Legacy consumption query
- `get_instant_usage()` - Efficient batched consumption
- `get_chart_usage()` - Historical usage data
- `get_devices_usages()` - Multi-device usage query
- `get_current_month_peak_demand()` - Peak demand data
- `get_devices_rate_properties()` - Get electricity rates
- `set_devices_rate_properties()` - Update electricity rates
- `get_app_preferences()` - Get app preferences

[Unreleased]: https://github.com/AndreCouture/emporia-api/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/AndreCouture/emporia-api/releases/tag/v1.0.0
