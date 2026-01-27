# Emporia API Implementation
import json
import time
import logging
from datetime import datetime, timezone, timedelta
import requests
import boto3
from warrant.aws_srp import AWSSRP


API_URL = "https://api.emporiaenergy.com"
EMPORIA_CHANGE_RATE = API_URL + "/devices/{}/locationProperties"
CUSTOMERS_DEVICES = API_URL + "/customers/devices"
DEVICES_STATUS = API_URL + "/customers/devices/status"
EVCHARGER = API_URL + "/devices/evcharger"
GET_CHARGING_RATE = (
    API_URL +
      "/AppAPI?apiMethod=getChartUsage&deviceGid={deviceGid}&channel=1%2C2%2C3"
      "&start={period_start}&end={period_end}&scale=1S&energyUnit={energyUnit}"
)
GET_CURRENT_MONTH_PEAK_DEMAND = (
    API_URL
    + "/AppAPI?apiMethod=getCurrentMonthPeakDemand&deviceGid={deviceGid}"
    + "&channel={channel}&energyUnit={energyUnit}"
)


class EmporiaAPI:
    """
    A class that encapsulates Emporia authentication, device queries,
    rate updates, and EV charger interactions.
    """

    def __init__(self, config):
        """
        :param config: Dictionary with the necessary configuration keys:
            - user_pool_id
            - client_id
            - region
            - emporia_username
            - emporia_password
            - hydro_rate_low (optional)
            - hydro_rate_high (optional)
            - hydro_rate_generac (optional)
        """
        self.config = config
        self.emporia_headers = None
        self.refresh_token = None
        self.expiration_timestamp = None
        self.refresh_token_interval = None

        # Optional convenience rates if you want them
        self.hydro_rate_low = config.get("hydro_rate_low")
        self.hydro_rate_high = config.get("hydro_rate_high")
        self.hydro_rate_generac = config.get("hydro_rate_generac")

        # Track "previous rate" if desired
        self.previous_rate = "LOW"

    def get_ev_chargers(self):
        """
        Return the EV chargers list from the devices status data.
        Always returns a list (possibly empty) for consistency.
        """
        status_data = self.devices_status()
        chargers = status_data.get("evChargers") or []
        logging.debug(f"Status data evChargers: {chargers}")
        # Backward-compatibility note:
        # Older code may have assumed a list with a single empty dict when no chargers.
        # We standardize to an empty list here. Callers that used index 0 safely
        # should continue to work via get_ev_charger(index) which guards empties.
        return chargers

    def get_ev_chargers_ids(self):
        """
        Return the list of EV charger deviceGid values from the devices status data.
        """
        chargers = self.get_ev_chargers()
        ids = [c.get("deviceGid") for c in chargers if isinstance(c, dict) and c.get("deviceGid") is not None]
        return ids

    def get_ev_charger(self, index=0):
        """
        Return the EV charger at the given index (default 0).
        Returns {} if the index is invalid or no chargers are present.
        """
        chargers = self.get_ev_chargers()
        if not chargers:
            return {}
        if index < 0:
            logging.warning(f"Negative EV charger index {index} is not allowed.")
            return {}
        try:
            return chargers[index]
        except (IndexError, TypeError):
            logging.warning(f"Requested EV charger index {index} but only {len(chargers)} charger(s) found.")
            return {}

    def get_ev_charger_by_id(self, device_gid):
        """
        Return the EV charger dict for a specific deviceGid.
        Returns {} if not found or device_gid is invalid.
        """
        if device_gid is None:
            return {}

        try:
            device_gid = int(device_gid)
        except (TypeError, ValueError):
            logging.warning(f"Invalid device_gid for EV charger: {device_gid}")
            return {}

        chargers = self.get_ev_chargers()
        for c in chargers:
            if isinstance(c, dict) and c.get("deviceGid") == device_gid:
                return c

        logging.warning(f"EV charger with deviceGid={device_gid} not found.")
        return {}

    def authenticate(self):
        """
        Authenticate against AWS Cognito using either an existing refresh token
        or a username/password SRP flow. Then set self.emporia_headers.
        """
        start_time = time.time()
        try:
            client = boto3.client('cognito-idp', region_name=self.config['region'])

            if self.refresh_token:
                # If refresh_token is known, try to refresh
                tokens = client.initiate_auth(
                    ClientId=self.config['client_id'],
                    AuthFlow='REFRESH_TOKEN_AUTH',
                    AuthParameters={'REFRESH_TOKEN': self.refresh_token}
                )
                id_token = tokens['AuthenticationResult']['IdToken']
                logging.info(f"Token refreshed successfully in {time.time() - start_time:.2f} seconds")

            else:
                # Otherwise, do SRP flow
                aws = AWSSRP(
                    username=self.config['emporia_username'],
                    password=self.config['emporia_password'],
                    pool_id=self.config['user_pool_id'],
                    client_id=self.config['client_id'],
                    client=client
                )
                tokens = aws.authenticate_user()
                id_token = tokens['AuthenticationResult']['IdToken']
                self.refresh_token = tokens['AuthenticationResult']['RefreshToken']
                logging.info(f"Emporia Authentication via SRP flow successful in {time.time() - start_time:.2f} seconds")

            self.emporia_headers = {
                'authToken': id_token,
                'Content-Type': 'application/json; charset=utf-8'
            }
            self.refresh_token_interval = int(tokens['AuthenticationResult']['ExpiresIn'])
            self.expiration_timestamp = int(time.time()) + self.refresh_token_interval - 30

            self._format_timestamp(self.expiration_timestamp)

        except Exception as e:
            logging.error(f"Emporia Authentication failed: {e}")
            self.emporia_headers = None

    def _format_timestamp(self, timestamp):
        """
        Utility to format and log an expiration timestamp.
        """
        expiration_datetime = datetime.fromtimestamp(timestamp)
        formatted_expiration = expiration_datetime.strftime("%Y-%m-%d %H:%M:%S")
        current_time_str = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        logging.info(
            f"Current Time: {current_time_str} | "
            f"Token Expiration Time (Human-Readable): {formatted_expiration}"
        )

    def devices(self):
        """
        Return list of user's devices from Emporia.
        """
        if not self.emporia_headers:
            self.authenticate()

        try:
            response = requests.get(CUSTOMERS_DEVICES, headers=self.emporia_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error retrieving devices: {e}")
            return {}

    def devices_status(self):
        """
        Return status of user's devices from Emporia.
        """
        if not self.emporia_headers:
            self.authenticate()

        try:
            response = requests.get(DEVICES_STATUS, headers=self.emporia_headers)
            if response.status_code == 401:
                # Possibly expired token; re-auth and try again
                logging.warning("401 Unauthorized - re-authenticating...")
                self.authenticate()
                response = requests.get(DEVICES_STATUS, headers=self.emporia_headers)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error retrieving device status: {e}")
            return {}

    def set_ev_charger(self, on):
        """
        Backward-compatible setter to turn the FIRST EV charger ON/OFF.
        - on: bool
        Returns the API response JSON or {} on error.
        """
        if not self.emporia_headers:
            self.authenticate()

        current_state = self.get_current_charger_state()
        if current_state == on:
            return {}
        try:
            ev_charger_data = self.get_ev_charger()
            if not ev_charger_data:
                logging.warning("No EV charger available to set state.")
                return {}
            ev_charger_data["chargerOn"] = bool(on)
            response = requests.put(EVCHARGER, json=ev_charger_data, headers=self.emporia_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error updating EV charger: {e}")
            return {}

    def set_ev_charger_by_id(self, device_gid, on):
        """
        New helper: set a specific EV charger by its deviceGid ON/OFF.
        Keeps backward compatibility by not changing existing set_ev_charger signature.
        """
        if not self.emporia_headers:
            self.authenticate()

        try:
            device_gid = int(device_gid)
        except (TypeError, ValueError):
            logging.warning(f"Invalid device_gid for set_ev_charger_by_id: {device_gid}")
            return {}

        ev_charger_data = self.get_ev_charger_by_id(device_gid)
        if not ev_charger_data:
            logging.warning(f"EV charger {device_gid} not found to set state.")
            return {}

        # Only send if it actually changes
        if ev_charger_data.get("chargerOn") == bool(on):
            return {}

        try:
            ev_charger_data["chargerOn"] = bool(on)
            response = requests.put(EVCHARGER, json=ev_charger_data, headers=self.emporia_headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error updating EV charger by id: {e}")
            return {}

    def get_current_charger_state(self):
        """
        Returns the current 'chargerOn' boolean state.
        (True if ON, False if OFF, None if cannot retrieve.)
        """
        ev_charger = self.get_ev_charger()
        if not ev_charger:
            return None
        return ev_charger.get("chargerOn")

    def get_current_charging_rate(self, energyUnit="KilowattHours", device_gid=None):
        """
        Retrieve the current watt usage for the EV charger over the last 5 seconds.
        possilble values for energyUnit:
        "KilowattHours"
        "AmpHours"
        "Dollars"
        """
        if not self.emporia_headers:
            self.authenticate()

        now = datetime.now(timezone.utc) - timedelta(seconds=1)
        start_dt = now - timedelta(seconds=5)

        def to_encoded_iso(dt):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            iso_str = dt.isoformat(timespec="milliseconds")
            iso_str = iso_str.replace("+00:00", "Z")
            iso_str = iso_str.replace(":", "%3A")
            return iso_str

        period_start = to_encoded_iso(start_dt)
        period_end = to_encoded_iso(now)

        ev_charger = (
            self.get_ev_charger_by_id(device_gid) if device_gid is not None else self.get_ev_charger()
        )
        if not ev_charger or not ev_charger.get("deviceGid"):
            logging.warning("No valid EV charger found to get charging rate.")
            return 0.0

        url = GET_CHARGING_RATE.format(
            deviceGid=ev_charger["deviceGid"],
            period_start=period_start,
            period_end=period_end,
            energyUnit=energyUnit
        )

        try:
            response = requests.get(url, headers=self.emporia_headers)
            response.raise_for_status()
            data = response.json()
            usage_list = data.get("usageList") or []
            filtered_list = [u for u in usage_list if u is not None]
            if not filtered_list:
                return 0.0
            # Each usage is in kWh over 1 second, multiply by 3600000 to get watts
            max_usage = max(filtered_list) * 3600000
            return max_usage
        except Exception as e:
            logging.error(f"Error retrieving current charging rate: {e}")
            return 0.0

    def get_devices_location_properties(self):
        """
        Fetches all devices and their current rate properties.
        """
        if not self.emporia_headers:
            self.authenticate()

        devices_data = self.devices()
        my_devices = devices_data.get('devices', [])
        if not my_devices:
            logging.warning("No devices found.")
            return []
        location_props = []
        for device in my_devices:
            location_props.append(device.get('locationProperties', {}))

        return location_props

    def get_devices_rate_properties(self):
        """
        Fetches all devices and their current rate properties.
        """
        location_props = self.get_devices_location_properties()
        device_rates = []
        for device in location_props:
            device_gid = device.get('deviceGid')
            current_rate = device.get('usageCentPerKwHour')

            if device_gid:
                device_rates.append({"deviceGid": device_gid, "usageCentPerKwHour": current_rate})
                logging.debug(f"Device {device_gid} has rate: {current_rate} cents/kWh.")

        return device_rates

    def set_devices_rate_properties(self, new_rate):
        """
        Updates the 'usageCentPerKwHour' property for all devices,
        only if the rate actually changed.
        """
        # 1) Check if new_rate is different from the previously applied rate
        if new_rate == self.previous_rate:
            logging.debug(f"Rate is already set to {new_rate} cents/kWh. Skipping update.")
            return

        # Fetch devices and their rates
        devices_data = self.get_devices_rate_properties()
        if not devices_data:
            logging.warning("No devices available to update rates.")
            return
        logging.debug(devices_data)
        # 2) Apply rate update only if different from the current rate
        location_props = self.get_devices_location_properties()

        for device in location_props:
            device_gid = device.get('deviceGid')
            if not device_gid:
                logging.warning("Device GID not found. Skipping device.")
                continue

            logging.debug(device)
            device_gid = device.get('deviceGid')
            current_rate = device.get('usageCentPerKwHour')

            if current_rate == new_rate:
                logging.debug(f"Device {device_gid} already set to {new_rate} cents/kWh. Skipping.")
                continue

            # Prepare data for the PATCH request
            device["usageCentPerKwHour"] = new_rate

            # 3) Perform API call to update the rate
            try:
                endpoint = EMPORIA_CHANGE_RATE.format(device_gid)
                resp = requests.patch(endpoint, json=device, headers=self.emporia_headers)
                if resp.status_code == 200:
                    logging.info(f"Successfully updated rate for device {device_gid}.")
                else:
                    logging.error(f"Failed to update rate for device {device_gid}: {resp.status_code} - {resp.text}")
                    logging.error(f"updated_properties: {device}")
            except Exception as e:
                logging.error(f"Error updating rate for device {device_gid}: {e}")

        # 4) Update the cached rate
        self.previous_rate = new_rate
        logging.info(f"Rate updated to {new_rate} cents/kWh for all devices.")

    def get_chart_usage(
            self,
            device_gid,
            channel,
            start,
            end,
            scale="1S",
            energy_unit="AmpHours",
            timeout=30,
    ):
        """
        Calls:
          GET https://c-api.emporiaenergy.com/v1/migrated/app-api/chart-usage
        Returns:
          dict with firstUsageInstant + usageList
        """
        # Ensure token exists and is fresh
        if not self.emporia_headers:
            self.authenticate()
        else:
            # refresh if near/after expiry
            self.maybe_reauth()

        url = "https://c-api.emporiaenergy.com/v1/migrated/app-api/chart-usage"
        params = {
            "deviceGid": str(device_gid),
            "channel": channel,
            "start": start,
            "end": end,
            "scale": scale,
            "energyUnit": energy_unit,
        }

        # Start from the known-working header style
        headers = dict(self.emporia_headers or {})
        headers.setdefault("Accept", "application/json")

        # Add Authorization bearer as compatibility (some Emporia endpoints accept it)
        id_token = headers.get("authToken")
        if id_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {id_token}"

        resp = requests.get(url, params=params, headers=headers, timeout=timeout)

        # If token expired, re-auth and retry once (same pattern as devices_status)
        if resp.status_code == 401:
            logging.warning("401 Unauthorized on chart-usage - re-authenticating and retrying...")
            self.authenticate()
            headers = dict(self.emporia_headers or {})
            headers.setdefault("Accept", "application/json")
            id_token = headers.get("authToken")
            if id_token:
                headers["Authorization"] = f"Bearer {id_token}"
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)

        resp.raise_for_status()
        return resp.json()

    def maybe_reauth(self):
        """
        Simple token-expiration check that re-authenticates synchronously.
        This replaces an older async-based approach that referenced an undefined executor.
        """
        current_time = int(time.time())
        if self.expiration_timestamp and self.expiration_timestamp < current_time:
            logging.info("Token expired -> re-authenticating...")
            self.authenticate()
            
    def get_current_month_peak_demand(
        self,
        device_gid,
        channel="1,2,3",
        energy_unit="KilowattHours",
        timeout=30,
    ):
        """
        Calls:
          GET https://api.emporiaenergy.com/AppAPI?apiMethod=getCurrentMonthPeakDemand&deviceGid=...&channel=...&energyUnit=...

        Returns:
          dict (API response JSON)
        """
        if not self.emporia_headers:
            self.authenticate()

        url = API_URL + "/AppAPI"
        params = {
            "apiMethod": "getCurrentMonthPeakDemand",
            "deviceGid": str(device_gid),
            "channel": channel,            # e.g. "1,2,3"
            "energyUnit": energy_unit,     # e.g. "KilowattHours"
        }

        try:
            resp = requests.get(url, params=params, headers=self.emporia_headers, timeout=timeout)

            # Retry once on 401 (same pattern as devices_status / chart_usage)
            if resp.status_code == 401:
                logging.warning("401 Unauthorized on getCurrentMonthPeakDemand - re-authenticating and retrying...")
                self.authenticate()
                resp = requests.get(url, params=params, headers=self.emporia_headers, timeout=timeout)

            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error(f"Error retrieving current month peak demand: {e}")
            return {}

    def get_devices_usages(
        self,
        device_gids,
        instant,
        scale="MONTH",
        energy_unit="DOLLARS",
        timeout=30,
    ):
        """
        Calls:
          GET https://c-api.emporiaenergy.com/v1/customers/devices/usages
            ?device_gids=...&instant=...&scale=...&energy_unit=...

        Args:
          device_gids: list[int] | list[str] | str
            - list -> joined as "292237,280643,507958"
            - str  -> can be "292237,280643,507958" (commas ok)
          instant: str
            - ISO8601 with Z, e.g. "2026-01-25T17:20:20.388Z"
          scale: str
            - e.g. "MONTH" (as per your example)
          energy_unit: str
            - e.g. "DOLLARS" (as per your example)

        Returns:
          dict (JSON response)
        """
        # Ensure token exists and is fresh
        if not self.emporia_headers:
            self.authenticate()
        else:
            self.maybe_reauth()

        url = "https://c-api.emporiaenergy.com/v1/customers/devices/usages"

        # Normalize gids
        if isinstance(device_gids, (list, tuple)):
            gids_str = ",".join(str(x) for x in device_gids)
        else:
            gids_str = str(device_gids)

        params = {
            "device_gids": gids_str,     # requests will URL-encode commas as needed
            "instant": instant,          # expects ...Z (UTC)
            "scale": scale,
            "energy_unit": energy_unit,
        }

        # Start from the known-working header style
        headers = dict(self.emporia_headers or {})
        headers.setdefault("Accept", "application/json")

        # Add Authorization bearer as compatibility
        id_token = headers.get("authToken")
        if id_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {id_token}"

        resp = requests.get(url, params=params, headers=headers, timeout=timeout)

        # Retry once on 401
        if resp.status_code == 401:
            logging.warning("401 Unauthorized on devices/usages - re-authenticating and retrying...")
            self.authenticate()
            headers = dict(self.emporia_headers or {})
            headers.setdefault("Accept", "application/json")
            id_token = headers.get("authToken")
            if id_token:
                headers["Authorization"] = f"Bearer {id_token}"
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)

        resp.raise_for_status()
        return resp.json()
    def get_app_preferences(self, timeout=20):
        """
        Retrieve app preferences from c-api endpoint.
        Returns decoded JSON from base64-encoded response.

        Example:
          GET https://c-api.emporiaenergy.com/v1/customers/app-preferences

        Response is a base64-encoded JSON string that gets automatically decoded.
        """
        import base64

        if not self.emporia_headers:
            self.authenticate()
        else:
            self.maybe_reauth()

        url = "https://c-api.emporiaenergy.com/v1/customers/app-preferences"

        headers = dict(self.emporia_headers or {})
        headers.setdefault("Accept", "application/json")

        id_token = headers.get("authToken")
        if id_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {id_token}"

        resp = requests.get(url, headers=headers, timeout=timeout)

        # Retry once on 401
        if resp.status_code == 401:
            logging.warning("401 Unauthorized on app-preferences - re-authenticating and retrying...")
            self.authenticate()
            headers = dict(self.emporia_headers or {})
            headers.setdefault("Accept", "application/json")
            id_token = headers.get("authToken")
            if id_token:
                headers["Authorization"] = f"Bearer {id_token}"
            resp = requests.get(url, headers=headers, timeout=timeout)

        resp.raise_for_status()

        # Response is base64-encoded JSON
        try:
            response_data = resp.json()

            # Handle different response formats
            if isinstance(response_data, dict) and "preferences" in response_data:
                # If response has a preferences field that's base64
                encoded_prefs = response_data.get("preferences", "")
                if encoded_prefs:
                    decoded_bytes = base64.b64decode(encoded_prefs)
                    return json.loads(decoded_bytes.decode('utf-8'))
                return response_data
            elif isinstance(response_data, str):
                # If entire response is base64-encoded JSON string
                decoded_bytes = base64.b64decode(response_data)
                return json.loads(decoded_bytes.decode('utf-8'))
            else:
                # If already decoded JSON, return as-is
                return response_data
        except Exception as e:
            logging.error(f"Error decoding app preferences: {e}")
            # Return raw response if decoding fails
            return resp.json()

    def get_devices_status_c_api(self, timeout=20):
        """
        Retrieve comprehensive device status from c-api endpoint.
        Returns detailed status including connection state, EVSEs, batteries, outlets.

        Example:
          GET https://c-api.emporiaenergy.com/v1/customers/devices/status

        Response includes:
        - devices_connected: List of all devices with connection status
        - evses: EV charger status (CHARGING, DISCONNECTED_ON, etc.)
        - batteries: Battery device status
        - outlets: Smart outlet status
        """
        if not self.emporia_headers:
            self.authenticate()
        else:
            self.maybe_reauth()

        url = "https://c-api.emporiaenergy.com/v1/customers/devices/status"

        headers = dict(self.emporia_headers or {})
        headers.setdefault("Accept", "application/json")

        id_token = headers.get("authToken")
        if id_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {id_token}"

        resp = requests.get(url, headers=headers, timeout=timeout)

        # Retry once on 401
        if resp.status_code == 401:
            logging.warning("401 Unauthorized on devices/status - re-authenticating and retrying...")
            self.authenticate()
            headers = dict(self.emporia_headers or {})
            headers.setdefault("Accept", "application/json")
            id_token = headers.get("authToken")
            if id_token:
                headers["Authorization"] = f"Bearer {id_token}"
            resp = requests.get(url, headers=headers, timeout=timeout)

        resp.raise_for_status()
        return resp.json()

    def stream_device_status(self, event_callback, stop_event=None):
        """
        Stream device status updates via Server-Sent Events (SSE).

        This establishes a persistent connection to receive real-time device status updates
        instead of polling. The stream emits DEVICE_STATUS events with the same data structure
        as get_devices_status_c_api().

        Args:
            event_callback: Function called with parsed event data dict when events arrive
            stop_event: Optional threading.Event to signal stream shutdown

        Example event:
            {
                "event_type": "DEVICE_STATUS",
                "data": {
                    "devices_connected": [...],
                    "evses": [...],
                    "batteries": [],
                    "outlets": []
                }
            }

        The stream will automatically reconnect on connection loss unless stop_event is set.
        """
        import threading

        if stop_event is None:
            stop_event = threading.Event()

        reconnect_delay = 5  # seconds

        while not stop_event.is_set():
            try:
                if not self.emporia_headers:
                    self.authenticate()
                else:
                    self.maybe_reauth()

                url = "https://c-api.emporiaenergy.com/v1/customers/stream?event_types=DEVICE_STATUS"

                headers = dict(self.emporia_headers or {})
                headers.setdefault("Accept", "text/event-stream")

                id_token = headers.get("authToken")
                if id_token and "Authorization" not in headers:
                    headers["Authorization"] = f"Bearer {id_token}"

                logging.info("Connecting to device status SSE stream...")
                resp = requests.get(url, headers=headers, stream=True, timeout=None)

                if resp.status_code == 401:
                    logging.warning("401 Unauthorized on SSE stream - re-authenticating...")
                    self.authenticate()
                    continue

                resp.raise_for_status()
                logging.info("Connected to device status SSE stream")

                # Parse SSE stream
                buffer = ""
                for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
                    if stop_event.is_set():
                        break

                    if chunk:
                        buffer += chunk

                        # Process complete lines
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()

                            if not line:
                                continue

                            # SSE format: "data: {json}"
                            if line.startswith("data:"):
                                try:
                                    json_str = line[5:].strip()
                                    event_data = json.loads(json_str)

                                    # Call the callback with parsed event
                                    if event_data.get("event_type") == "DEVICE_STATUS":
                                        logging.debug("SSE event received: DEVICE_STATUS")
                                        event_callback(event_data)

                                except json.JSONDecodeError as e:
                                    logging.warning(f"Failed to parse SSE event: {e}")
                                except Exception as e:
                                    logging.error(f"Error processing SSE event: {e}")

            except requests.exceptions.RequestException as e:
                if not stop_event.is_set():
                    logging.warning(f"SSE stream disconnected: {e}. Reconnecting in {reconnect_delay}s...")
                    stop_event.wait(reconnect_delay)
            except Exception as e:
                if not stop_event.is_set():
                    logging.error(f"Unexpected error in SSE stream: {e}. Reconnecting in {reconnect_delay}s...")
                    stop_event.wait(reconnect_delay)

        logging.info("Device status SSE stream stopped")

    def get_instant_usage(self, device_gids, energy_unit="KILOWATT_HOURS", timeout=20):
        """
        Get instantaneous power usage using c-api devices/usages endpoint with scale=HOUR.
        
        This is a more efficient alternative to get_current_charging_rate() because:
        - Single API call returns data for all requested devices
        - Returns usage in the requested unit directly (no conversion needed)
        - Uses newer c-api endpoint
        
        Args:
            device_gids: int, str, or list of device GIDs
            energy_unit: "KILOWATT_HOURS", "AMP_HOURS", or "DOLLARS"
            timeout: Request timeout in seconds
            
        Returns:
            dict: {
                device_gid: usage_value,
                ...
            }
            
        Example:
            >>> api.get_instant_usage([280643, 507958], "KILOWATT_HOURS")
            {280643: 0.0, 507958: 1.243}
        """
        from datetime import datetime, timezone
        
        # Get current instant
        instant = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        
        # Call existing get_devices_usages with HOUR scale for instantaneous data
        result = self.get_devices_usages(
            device_gids=device_gids,
            instant=instant,
            scale="HOUR",
            energy_unit=energy_unit.upper(),
            timeout=timeout
        )
        
        # Parse response to extract usage per device
        usage_map = {}
        device_usages = result.get("device_usages", [])
        
        for device_usage in device_usages:
            device_gid = device_usage.get("device_gid")
            if not device_gid:
                continue
                
            # Get the Mains channel usage (primary consumption)
            channel_usages = device_usage.get("channel_usages", [])
            for channel in channel_usages:
                if channel.get("channel_id") == "Mains":
                    usage = channel.get("usage", 0.0)
                    # Convert from kWh/hour to watts (multiply by 1000)
                    if energy_unit.upper() == "KILOWATT_HOURS":
                        usage = usage * 1000  # Convert kW to W
                    usage_map[device_gid] = usage
                    break
            
            # If Mains not found, use first channel or 0
            if device_gid not in usage_map:
                if channel_usages:
                    usage_map[device_gid] = channel_usages[0].get("usage", 0.0)
                else:
                    usage_map[device_gid] = 0.0
        
        return usage_map
