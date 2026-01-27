#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

import unittest
from unittest.mock import patch, MagicMock
from emporia_api import EmporiaAPI

class TestEmporiaAPI(unittest.TestCase):
    
    def setUp(self):
        """Set up a mock configuration and authenticate once."""
        self.mock_config = {
            "user_pool_id": "test_pool",
            "client_id": "test_client",
            "region": "us-east-1",
            "emporia_username": "test_user",
            "emporia_password": "test_password"
        }
        self.api = EmporiaAPI(self.mock_config)
        
        # ✅ Patch both boto3 and AWSSRP globally for this test class
        with patch('emporia_api.boto3.client') as mock_boto, \
             patch('emporia_api.AWSSRP') as mock_awssrp:
                
            # Mock Cognito Client and Token Generation
            mock_client = MagicMock()
            mock_client.initiate_auth.return_value = {
                'AuthenticationResult': {
                    'IdToken': 'mock_id_token',
                    'RefreshToken': 'mock_refresh_token',
                    'ExpiresIn': 3600
                }
            }
            mock_boto.return_value = mock_client
        
            # Mock AWSSRP
            mock_awssrp_instance = MagicMock()
            mock_awssrp_instance.authenticate_user.return_value = {
                'AuthenticationResult': {
                    'IdToken': 'mock_id_token',
                    'RefreshToken': 'mock_refresh_token',
                    'ExpiresIn': 3600
                }
            }
            mock_awssrp.return_value = mock_awssrp_instance
        
            # Authenticate Once for All Tests
            self.api.authenticate()
        
    # ✅ No re-authentication needed
    def test_authenticated_headers_set(self):
        """Test if headers are correctly set after authentication."""
        self.assertIsNotNone(self.api.emporia_headers)
        self.assertIn('authToken', self.api.emporia_headers)
        
    # ✅ Test successful device retrieval without re-authenticating
    @patch('emporia_api.requests.get')
    def test_devices_successful(self, mock_requests_get):
        """Test the successful retrieval of devices."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"devices": [{"deviceGid": "12345"}]}
        mock_requests_get.return_value = mock_response
        
        devices = self.api.devices()
        self.assertEqual(len(devices['devices']), 1)
        self.assertEqual(devices['devices'][0]['deviceGid'], "12345")
        
    # ✅ Test device status without re-authenticating
    @patch('emporia_api.requests.get')
    def test_devices_status_successful(self, mock_requests_get):
        """Test getting device status successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "online"}
        mock_requests_get.return_value = mock_response
        
        result = self.api.devices_status()
        self.assertEqual(result["status"], "online")
        
    # ✅ Force a re-authentication scenario
    @patch('emporia_api.requests.get')
    def test_devices_status_unauthorized(self, mock_requests_get):
        """Test if the API re-authenticates on 401 error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_requests_get.return_value = mock_response
        
        with patch.object(self.api, "authenticate") as mock_auth:
            self.api.devices_status()
            mock_auth.assert_called_once()  # Ensure it attempted re-authentication
            
    # ✅ Test setting the EV charger state with proper handling
    @patch('emporia_api.requests.put')
    def test_set_ev_charger_successful(self, mock_requests_put):
        """Test setting EV charger state."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_requests_put.return_value = mock_response
        
        self.api.get_ev_charger = MagicMock(return_value={"chargerOn": False})
        result = self.api.set_ev_charger({"chargerOn": True})
        self.assertEqual(result, {})
        
    # ✅ Ensure charging rate calculation works (legacy endpoint)
    @patch('emporia_api.requests.get')
    def test_get_current_charging_rate(self, mock_requests_get):
        """Test getting the current charging rate (legacy AppAPI endpoint)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usageList": [0.001, 0.002, 0.003]
        }
        mock_requests_get.return_value = mock_response
        self.api.get_ev_charger = MagicMock(return_value={"deviceGid": "12345"})

        rate = self.api.get_current_charging_rate()
        self.assertEqual(rate, max([0.001, 0.002, 0.003]) * 3600000)

    # ✅ Test get_chart_usage (c-api)
    @patch('emporia_api.requests.get')
    def test_get_chart_usage(self, mock_requests_get):
        """Test the c-api chart usage endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "firstUsageInstant": "2026-01-27T12:00:00Z",
            "usageList": [1.5, 2.0, 1.8]
        }
        mock_requests_get.return_value = mock_response

        result = self.api.get_chart_usage(
            device_gid=12345,
            channel="1,2,3",
            start="2026-01-27T11:00:00Z",
            end="2026-01-27T12:00:00Z",
            scale="1H",
            energy_unit="KILOWATT_HOURS"
        )
        self.assertIn("usageList", result)
        self.assertEqual(len(result["usageList"]), 3)

    # ✅ Test get_devices_usages (c-api)
    @patch('emporia_api.requests.get')
    def test_get_devices_usages(self, mock_requests_get):
        """Test the c-api devices usages endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "instant": "2026-01-27T12:00:00Z",
            "scale": "HOUR",
            "energy_unit": "KILOWATT_HOURS",
            "device_usages": [
                {
                    "device_gid": 12345,
                    "channel_usages": [
                        {"channel_id": "Mains", "usage": 1.5}
                    ]
                }
            ]
        }
        mock_requests_get.return_value = mock_response

        result = self.api.get_devices_usages(
            device_gids=[12345],
            instant="2026-01-27T12:00:00Z",
            scale="HOUR",
            energy_unit="KILOWATT_HOURS"
        )
        self.assertIn("device_usages", result)
        self.assertEqual(result["device_usages"][0]["device_gid"], 12345)

    # ✅ Test get_instant_usage (c-api wrapper)
    @patch('emporia_api.requests.get')
    def test_get_instant_usage(self, mock_requests_get):
        """Test the new get_instant_usage method (c-api)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "instant": "2026-01-27T12:00:00Z",
            "scale": "HOUR",
            "energy_unit": "KILOWATT_HOURS",
            "device_usages": [
                {
                    "device_gid": 12345,
                    "channel_usages": [
                        {"channel_id": "Mains", "usage": 1.5}
                    ]
                },
                {
                    "device_gid": 67890,
                    "channel_usages": [
                        {"channel_id": "Mains", "usage": 2.3}
                    ]
                }
            ]
        }
        mock_requests_get.return_value = mock_response

        result = self.api.get_instant_usage([12345, 67890], energy_unit="KILOWATT_HOURS")

        # Should return dict mapping device_gid to watts
        self.assertIsInstance(result, dict)
        self.assertIn(12345, result)
        self.assertIn(67890, result)
        # Usage is converted from kW to W (multiply by 1000)
        self.assertEqual(result[12345], 1.5 * 1000)
        self.assertEqual(result[67890], 2.3 * 1000)

    # ✅ Test get_app_preferences (c-api with base64 decoding)
    @patch('emporia_api.requests.get')
    def test_get_app_preferences(self, mock_requests_get):
        """Test the c-api app preferences endpoint with base64 decoding."""
        import base64
        import json

        # Simulate base64-encoded JSON response
        prefs_data = {"theme": "dark", "units": "metric"}
        encoded_prefs = base64.b64encode(json.dumps(prefs_data).encode('utf-8')).decode('utf-8')

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"preferences": encoded_prefs}
        mock_requests_get.return_value = mock_response

        result = self.api.get_app_preferences()
        self.assertEqual(result["theme"], "dark")
        self.assertEqual(result["units"], "metric")

    # ✅ Test get_devices_status_c_api
    @patch('emporia_api.requests.get')
    def test_get_devices_status_c_api(self, mock_requests_get):
        """Test the c-api devices status endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "devices_connected": [
                {"device_gid": 12345, "connected": True, "offline_since": None}
            ],
            "evses": [
                {"device_gid": 12345, "charger_status": "CHARGING"}
            ],
            "batteries": [],
            "outlets": []
        }
        mock_requests_get.return_value = mock_response

        result = self.api.get_devices_status_c_api()
        self.assertIn("devices_connected", result)
        self.assertIn("evses", result)
        self.assertEqual(result["evses"][0]["charger_status"], "CHARGING")

    # ✅ Test 401 re-authentication for c-api endpoints
    @patch('emporia_api.requests.get')
    def test_c_api_unauthorized_reauth(self, mock_requests_get):
        """Test that c-api endpoints re-authenticate on 401."""
        # First call returns 401, second succeeds
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"devices_connected": []}

        mock_requests_get.side_effect = [mock_response_401, mock_response_200]

        with patch.object(self.api, "authenticate") as mock_auth:
            result = self.api.get_devices_status_c_api()
            mock_auth.assert_called_once()
            self.assertIn("devices_connected", result)

    # ✅ Test get_current_month_peak_demand
    @patch('emporia_api.requests.get')
    def test_get_current_month_peak_demand(self, mock_requests_get):
        """Test the peak demand endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "peakDemand": {
                "Timestamp": {"epochSecond": 1768450500, "nano": 0},
                "Value": 9.298,
                "value": 9.298
            },
            "peakType": "15 minute peak"
        }
        mock_requests_get.return_value = mock_response

        result = self.api.get_current_month_peak_demand(
            device_gid=12345,
            channel="1,2,3",
            energy_unit="KilowattHours"
        )
        self.assertIn("peakDemand", result)
        self.assertEqual(result["peakType"], "15 minute peak")

if __name__ == "__main__":
    unittest.main()