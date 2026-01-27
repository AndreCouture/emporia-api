#!/usr/bin/env python3

import argparse
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
from emporia_api import EmporiaAPI


def parse_relative_period(period: str) -> timedelta:
    """
    Supported:
      - 15M, 2H, 30S, 1D, 1W
      - 1h30m, 2h15m10s (case-insensitive)
      - PT15M, PT2H, PT30S (ISO-8601 subset)
    """
    if not period:
        raise ValueError("Empty period")

    p = period.strip().upper()

    # ISO-8601 subset: PT#H#M#S
    if p.startswith("PT"):
        hours = minutes = seconds = 0
        for value, unit in re.findall(r"(\d+)([HMS])", p[2:]):
            if unit == "H":
                hours += int(value)
            elif unit == "M":
                minutes += int(value)
            elif unit == "S":
                seconds += int(value)
        if hours == minutes == seconds == 0:
            raise ValueError(f"Invalid ISO-8601 period: {period}")
        return timedelta(hours=hours, minutes=minutes, seconds=seconds)

    # Combined short form: 1H30M10S / 2H15M / 15M etc.
    matches = re.findall(r"(\d+)([SMHDW])", p)
    if not matches:
        raise ValueError(f"Invalid period format: {period}")

    delta = timedelta()
    for value, unit in matches:
        v = int(value)
        if unit == "S":
            delta += timedelta(seconds=v)
        elif unit == "M":
            delta += timedelta(minutes=v)
        elif unit == "H":
            delta += timedelta(hours=v)
        elif unit == "D":
            delta += timedelta(days=v)
        elif unit == "W":
            delta += timedelta(weeks=v)
    return delta


def to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    required = [
        "emporia_username",
        "emporia_password",
        "user_pool_id",
        "client_id",
        "region",
    ]

    for k in required:
        if k not in cfg or not cfg[k]:
            raise SystemExit(f"Missing required key in config.json: {k}")

    return cfg


def main():
    parser = argparse.ArgumentParser("Emporia API local test")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--debug", action="store_true")

    # Actions
    parser.add_argument("--chart", action="store_true", help="Test chart-usage (historical usage list)")
    parser.add_argument("--peak", action="store_true", help="Test getCurrentMonthPeakDemand")
    parser.add_argument("--usages", action="store_true", help="Test c-api /v1/customers/devices/usages")

    # Common / chart parameters
    parser.add_argument("--device-gid", type=int, help="Device GID (required for --chart/--peak)")
    parser.add_argument("--channel", default="Mains", help="Chart channel (default: Mains)")
    parser.add_argument("--period", help="Relative period (e.g. 15M, 1h30m, PT2H)")
    parser.add_argument("--start", help="Start ISO timestamp (e.g. 2026-01-25T10:13:00.000Z)")
    parser.add_argument("--end", help="End ISO timestamp (e.g. 2026-01-25T13:33:00.000Z)")
    parser.add_argument("--scale", default="1MIN", help="Scale (e.g. 1S, 1MIN)")
    parser.add_argument("--energy-unit", default="AmpHours", help="Energy unit (e.g. AmpHours, KilowattHours, DOLLARS)")

    # Peak parameters
    parser.add_argument("--channels", default="1,2,3", help="Peak channels (default: 1,2,3)")

    # Usages parameters
    parser.add_argument(
        "--device-gids",
        help="Comma-separated device gids for --usages (e.g. 292237,280643,507958)",
    )
    parser.add_argument(
        "--instant",
        help='UTC instant for --usages (e.g. "2026-01-25T17:20:20.388Z"). Default: now',
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    config = load_config(args.config)
    api = EmporiaAPI(config)

    ran_any = False

    # --- Peak demand ---
    if args.peak:
        ran_any = True
        if not args.device_gid:
            raise SystemExit("--peak requires --device-gid")

        # Some endpoints expect KilowattHours; leaving user-selectable via --energy-unit
        data = api.get_current_month_peak_demand(
            device_gid=args.device_gid,
            channel=args.channels,
            energy_unit=args.energy_unit,
        )
        print(json.dumps(data, indent=2))

    # --- Historical chart usage ---
    if args.chart:
        ran_any = True
        if not args.device_gid:
            raise SystemExit("--chart requires --device-gid")

        start = args.start
        end = args.end

        if (not start or not end) and args.period:
            delta = parse_relative_period(args.period)
            now = datetime.now(timezone.utc)
            start = to_iso_z(now - delta)
            end = to_iso_z(now)

        if not start or not end:
            raise SystemExit("Provide --start/--end OR --period")

        data = api.get_chart_usage(
            device_gid=args.device_gid,
            channel=args.channel,
            start=start,
            end=end,
            scale=args.scale,
            energy_unit=args.energy_unit,
        )

        usage_list = data.get("usageList", []) or []
        print(f"firstUsageInstant: {data.get('firstUsageInstant')}")
        print(f"usageList length: {len(usage_list)}")
        print("preview:", usage_list[:10])

        if args.debug:
            print(json.dumps(data, indent=2))

    # --- Multi-device usages (c-api) ---
    if args.usages:
        ran_any = True
        if not args.device_gids:
            raise SystemExit("--usages requires --device-gids (e.g. 292237,280643,507958)")

        gids = [g.strip() for g in args.device_gids.split(",") if g.strip()]
        if not gids:
            raise SystemExit("No valid gids parsed from --device-gids")

        instant = args.instant
        if not instant:
            # include milliseconds like the API examples
            instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        # For this endpoint, the API uses energy_unit enums like DOLLARS.
        # You can pass --energy-unit DOLLARS.
        data = api.get_devices_usages(
            device_gids=gids,
            instant=instant,
            scale=args.scale,          # example: MONTH
            energy_unit=args.energy_unit,  # example: DOLLARS
        )
        print(json.dumps(data, indent=2))

    if not ran_any:
        parser.print_help()


if __name__ == "__main__":
    main()