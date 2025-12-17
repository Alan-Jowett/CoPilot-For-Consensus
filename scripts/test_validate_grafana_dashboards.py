# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Unit tests for validate_grafana_dashboards.py
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent))

from validate_grafana_dashboards import GrafanaValidator


class TestGrafanaValidator(unittest.TestCase):
    """Test cases for GrafanaValidator."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = GrafanaValidator(
            grafana_url="http://localhost:3000",
            username="admin",
            password="admin",
            max_retries=3,
            retry_delay=1,
        )

    def test_validate_dashboard_json_valid(self):
        """Test validating a valid dashboard JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            dashboard = {
                "title": "Test Dashboard",
                "panels": [
                    {
                        "title": "Test Panel",
                        "targets": [{"expr": "up"}]
                    }
                ]
            }
            json.dump(dashboard, f)
            temp_path = Path(f.name)

        try:
            is_valid, error_msg = self.validator.validate_dashboard_json(temp_path)
            self.assertTrue(is_valid)
            self.assertIsNone(error_msg)
        finally:
            temp_path.unlink()

    def test_validate_dashboard_json_missing_title(self):
        """Test validating a dashboard JSON without title."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            dashboard = {
                "panels": []
            }
            json.dump(dashboard, f)
            temp_path = Path(f.name)

        try:
            is_valid, error_msg = self.validator.validate_dashboard_json(temp_path)
            self.assertFalse(is_valid)
            self.assertIn("title", error_msg.lower())
        finally:
            temp_path.unlink()

    def test_validate_dashboard_json_missing_panels(self):
        """Test validating a dashboard JSON without panels."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            dashboard = {
                "title": "Test Dashboard"
            }
            json.dump(dashboard, f)
            temp_path = Path(f.name)

        try:
            is_valid, error_msg = self.validator.validate_dashboard_json(temp_path)
            self.assertFalse(is_valid)
            self.assertIn("panels", error_msg.lower())
        finally:
            temp_path.unlink()

    def test_validate_dashboard_json_invalid_json(self):
        """Test validating an invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json")
            temp_path = Path(f.name)

        try:
            is_valid, error_msg = self.validator.validate_dashboard_json(temp_path)
            self.assertFalse(is_valid)
            self.assertIn("Invalid JSON", error_msg)
        finally:
            temp_path.unlink()

    @patch('validate_grafana_dashboards.requests.Session')
    def test_wait_for_grafana_success(self, mock_session_class):
        """Test waiting for Grafana when it becomes ready."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"database": "ok"}
        mock_session.get.return_value = mock_response

        validator = GrafanaValidator(max_retries=3, retry_delay=1)
        validator.session = mock_session
        
        result = validator.wait_for_grafana()
        self.assertTrue(result)

    @patch('validate_grafana_dashboards.requests.Session')
    def test_wait_for_grafana_timeout(self, mock_session_class):
        """Test waiting for Grafana when it times out."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Simulate connection failure
        import requests
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        validator = GrafanaValidator(max_retries=2, retry_delay=0.1)
        validator.session = mock_session
        
        result = validator.wait_for_grafana()
        self.assertFalse(result)

    def test_validate_datasource_health_healthy(self):
        """Test validating a healthy datasource."""
        datasource = {
            "name": "Prometheus",
            "uid": "test-uid"
        }
        
        mock_response = Mock()
        mock_response.json.return_value = {"status": "OK"}
        self.validator.session.get = Mock(return_value=mock_response)
        
        is_healthy, status_msg = self.validator.validate_datasource_health(datasource)
        self.assertTrue(is_healthy)
        self.assertEqual(status_msg, "Healthy")

    def test_validate_datasource_health_unhealthy(self):
        """Test validating an unhealthy datasource."""
        datasource = {
            "name": "Prometheus",
            "uid": "test-uid"
        }
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ERROR",
            "message": "Connection refused"
        }
        self.validator.session.get = Mock(return_value=mock_response)
        
        is_healthy, status_msg = self.validator.validate_datasource_health(datasource)
        self.assertFalse(is_healthy)
        self.assertIn("Connection refused", status_msg)

    def test_execute_panel_query_no_targets(self):
        """Test panel query validation with no targets."""
        panel = {
            "title": "Test Panel",
            "targets": []
        }
        
        is_valid, status_msg = self.validator.execute_panel_query(panel, "ds-uid", "db-uid")
        self.assertTrue(is_valid)
        self.assertEqual(status_msg, "No queries to test")

    def test_execute_panel_query_with_expression(self):
        """Test panel query validation with query expression."""
        panel = {
            "title": "Test Panel",
            "targets": [
                {
                    "expr": "up{job='prometheus'}"
                }
            ]
        }
        
        is_valid, status_msg = self.validator.execute_panel_query(panel, "ds-uid", "db-uid")
        self.assertTrue(is_valid)
        self.assertIn("Panel structure valid", status_msg)


if __name__ == '__main__':
    unittest.main()
