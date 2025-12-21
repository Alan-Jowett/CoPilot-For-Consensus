# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Grafana Dashboard Validation Script

This script performs comprehensive validation of Grafana dashboards:
1. Validates dashboard JSON schema and structure
2. Verifies Grafana API connectivity
3. Checks datasource availability and health
4. Validates dashboard provisioning and discoverability
5. Performs panel-level smoke testing (query execution)

Usage:
    python validate_grafana_dashboards.py [--grafana-url URL] [--dashboard-dir PATH]

Exit codes:
    0: All validations passed
    1: Validation failure detected
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


class GrafanaValidator:
    """Validates Grafana dashboards and their provisioning."""

    def __init__(
        self,
        grafana_url: str = "http://localhost:3000",
        username: str = "admin",
        password: str = "admin",
        dashboard_dir: str = "infra/grafana/dashboards",
        max_retries: int = 30,
        retry_delay: int = 5,
    ):
        self.grafana_url = grafana_url.rstrip("/")
        self.auth = (username, password)
        self.dashboard_dir = Path(dashboard_dir)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.auth = self.auth

    def wait_for_grafana(self) -> bool:
        """Wait for Grafana to be ready."""
        print(f"Waiting for Grafana at {self.grafana_url}...")
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    f"{self.grafana_url}/api/health", timeout=5
                )
                if response.status_code == 200:
                    health_data = response.json()
                    print(f"✓ Grafana is healthy: {health_data}")
                    return True
            except requests.exceptions.RequestException as e:
                print(
                    f"  Attempt {attempt}/{self.max_retries}: "
                    f"Grafana not ready yet ({e})"
                )

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)

        print(f"✗ Grafana failed to become ready after {self.max_retries} attempts")
        return False

    def wait_for_api_auth(self) -> bool:
        """Wait for Grafana API authentication to work.
        
        The admin user may take a few seconds to be fully provisioned after
        Grafana starts, so we retry datasource access to wait for auth.
        """
        print("Waiting for Grafana API authentication to be ready...")
        sys.stdout.flush()
        # Use up to 20 retries (or max_retries if smaller) for auth check
        max_auth_retries = min(self.max_retries, 20)
        response = None
        for attempt in range(1, max_auth_retries + 1):
            try:
                response = self.session.get(
                    f"{self.grafana_url}/api/datasources", timeout=5
                )
                print(
                    f"  Attempt {attempt}/{max_auth_retries}: "
                    f"Got status code {response.status_code}"
                )
                sys.stdout.flush()
                if response.status_code == 200:
                    print(f"✓ API authentication is working")
                    sys.stdout.flush()
                    return True
                elif response.status_code == 401:
                    # Try to get more details from the response
                    try:
                        error_body = response.json()
                        print(f"    Auth failed (401): {error_body}")
                    except json.JSONDecodeError:
                        print(f"    Authentication not ready yet (401), waiting...")
                    sys.stdout.flush()
                else:
                    print(f"    Unexpected status code, waiting...")
                    sys.stdout.flush()
            except requests.exceptions.RequestException as e:
                print(
                    f"  Attempt {attempt}/{max_auth_retries}: "
                    f"API not accessible yet ({e})"
                )
                sys.stdout.flush()

            if attempt < max_auth_retries:
                time.sleep(self.retry_delay)

        print(f"✗ API authentication failed after {max_auth_retries} attempts")
        if response is not None:
            print(f"  Last response status: {response.status_code}")
            try:
                print(f"  Response body: {response.text[:200]}")
            except Exception as e:
                print(f"  Response body could not be printed: {e}")
        sys.stdout.flush()
        return False

    def validate_dashboard_json(self, filepath: Path) -> Tuple[bool, Optional[str]]:
        """Validate dashboard JSON structure."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                dashboard = json.load(f)

            # Check required top-level fields
            required_fields = ["panels", "title"]
            missing_fields = [
                field for field in required_fields if field not in dashboard
            ]
            if missing_fields:
                return (
                    False,
                    f"Missing required fields: {', '.join(missing_fields)}",
                )

            # Validate panels structure
            if not isinstance(dashboard.get("panels"), list):
                return False, "'panels' must be a list"

            return True, None

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        except Exception as e:
            return False, f"Error reading file: {e}"

    def validate_all_dashboard_files(self) -> bool:
        """Validate all dashboard JSON files."""
        print("\n=== Validating Dashboard JSON Files ===")
        all_valid = True
        dashboard_files = list(self.dashboard_dir.glob("*.json"))

        if not dashboard_files:
            print(f"✗ No dashboard files found in {self.dashboard_dir}")
            return False

        for filepath in dashboard_files:
            is_valid, error_msg = self.validate_dashboard_json(filepath)
            if is_valid:
                print(f"✓ {filepath.name}: Valid JSON structure")
            else:
                print(f"✗ {filepath.name}: {error_msg}")
                all_valid = False

        return all_valid

    def get_datasources(self) -> Optional[List[Dict]]:
        """Get all configured datasources from Grafana."""
        try:
            response = self.session.get(
                f"{self.grafana_url}/api/datasources", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get datasources: {e}")
            return None

    def validate_datasource_health(self, datasource: Dict) -> Tuple[bool, str]:
        """Check if a datasource is healthy."""
        ds_id = datasource.get("uid")

        if not ds_id:
            return False, "Missing datasource UID"

        try:
            # Use the datasource health check endpoint
            response = self.session.get(
                f"{self.grafana_url}/api/datasources/uid/{ds_id}/health", timeout=10
            )
            response.raise_for_status()
            health_data = response.json()

            if health_data.get("status") == "OK":
                return True, "Healthy"
            else:
                return False, f"Unhealthy: {health_data.get('message', 'Unknown error')}"

        except requests.exceptions.RequestException as e:
            return False, f"Health check failed: {e}"

    def validate_datasources(self) -> bool:
        """Validate all datasources are available and healthy."""
        print("\n=== Validating Datasources ===")
        datasources = self.get_datasources()

        if not datasources:
            print("✗ No datasources found or failed to retrieve datasources")
            return False

        all_healthy = True
        required_datasources = {"Prometheus", "Loki"}
        found_datasources = set()

        for ds in datasources:
            ds_name = ds.get("name", "Unknown")
            found_datasources.add(ds_name)
            is_healthy, status_msg = self.validate_datasource_health(ds)

            if is_healthy:
                print(f"✓ Datasource '{ds_name}': {status_msg}")
            else:
                print(f"✗ Datasource '{ds_name}': {status_msg}")
                all_healthy = False

        # Check if all required datasources are present
        missing_datasources = required_datasources - found_datasources
        if missing_datasources:
            print(f"✗ Missing required datasources: {', '.join(missing_datasources)}")
            all_healthy = False

        return all_healthy

    def get_dashboards(self) -> Optional[List[Dict]]:
        """Get all dashboards from Grafana."""
        try:
            response = self.session.get(
                f"{self.grafana_url}/api/search?type=dash-db", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to get dashboards: {e}")
            return None

    def get_dashboard_by_uid(self, uid: str) -> Optional[Dict]:
        """Get a specific dashboard by UID."""
        try:
            response = self.session.get(
                f"{self.grafana_url}/api/dashboards/uid/{uid}", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Failed to get dashboard {uid}: {e}")
            return None

    def validate_dashboard_provisioning(self) -> bool:
        """Validate that dashboards are provisioned and discoverable."""
        print("\n=== Validating Dashboard Provisioning ===")

        # Get expected dashboards from filesystem
        dashboard_files = list(self.dashboard_dir.glob("*.json"))
        expected_dashboard_titles = set()

        for filepath in dashboard_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    dashboard = json.load(f)
                    title = dashboard.get("title", filepath.stem)
                    expected_dashboard_titles.add(title)
            except Exception as e:
                print(f"  Warning: Could not read {filepath.name}: {e}")

        # Get dashboards from Grafana
        grafana_dashboards = self.get_dashboards()
        if grafana_dashboards is None:
            return False

        found_titles = {db.get("title") for db in grafana_dashboards}

        # Check for missing dashboards
        all_provisioned = True
        for title in expected_dashboard_titles:
            if title in found_titles:
                print(f"✓ Dashboard '{title}': Provisioned and discoverable")
            else:
                print(f"✗ Dashboard '{title}': Not found in Grafana")
                all_provisioned = False

        if not grafana_dashboards:
            print("✗ No dashboards found in Grafana")
            return False

        return all_provisioned

    def execute_panel_query(
        self, panel: Dict, datasource_uid: str, dashboard_title: str
    ) -> Tuple[bool, str]:
        """Execute a panel query to check if it returns data.
        
        This performs actual query execution via Grafana's /api/ds/query endpoint
        to verify panels return data and don't have query errors.
        """
        # Check if panel has targets (queries)
        targets = panel.get("targets", [])
        if not targets:
            # Panel without queries (e.g., text panels, row headers) is valid
            return True, "No queries configured (non-query panel)"

        # Get datasource from panel
        datasource = panel.get("datasource")
        if not datasource:
            return True, "Panel has no datasource (may use dashboard default)"
        
        # Extract datasource UID and type
        # Datasource may be provided as a name (e.g., "Prometheus") or as a UID.
        # Attempt to resolve it via the Grafana API; fall back to assuming it is a UID
        # if resolution is not possible.
        if isinstance(datasource, dict):
            ds_uid = datasource.get("uid")
            ds_type = datasource.get("type")
        elif isinstance(datasource, str):
            # Try to resolve datasource name to UID
            ds_uid = None
            ds_type = None
            try:
                datasources = self.get_datasources()
                for ds in datasources:
                    name = ds.get("name")
                    uid = ds.get("uid")
                    dtype = ds.get("type")
                    if datasource == name or datasource == uid:
                        ds_uid = uid
                        ds_type = dtype
                        break
            except Exception:
                pass
            
            # If we could not resolve the reference, treat the string as a UID
            if ds_uid is None:
                ds_uid = datasource
        else:
            return True, "Could not determine datasource"
        
        if not ds_uid:
            return True, "Panel datasource has no UID"
        
        # Only validate Prometheus queries for now (most common)
        # Loki and other datasources have different query formats
        if ds_type and ds_type != "prometheus":
            return True, f"Skipping non-Prometheus datasource ({ds_type})"
        
        # Execute the first target query
        first_target = targets[0]
        query_expr = first_target.get("expr")
        
        if not query_expr:
            return True, "Panel has targets but no query expression"
        
        # Construct query payload for Grafana's query API
        # Use a simple time range (last 5 minutes)
        now = int(time.time())
        from_time = now - 300  # 5 minutes ago
        
        query_payload = {
            "queries": [
                {
                    "refId": first_target.get("refId", "A"),
                    "expr": query_expr,
                    "datasource": {"type": ds_type or "prometheus", "uid": ds_uid},
                    "intervalMs": 15000,
                    "maxDataPoints": 100,
                }
            ],
            "from": str(from_time * 1000),
            "to": str(now * 1000),
        }
        
        try:
            response = self.session.post(
                f"{self.grafana_url}/api/ds/query",
                json=query_payload,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            
            # Check for errors in the response
            if "results" in result:
                for query_result in result.get("results", {}).values():
                    if "error" in query_result:
                        return False, f"Query error: {query_result['error']}"
                    
                    # Check if query returned any data
                    frames = query_result.get("frames", [])
                    if not frames:
                        return False, "Query returned no data (empty frames)"
                    
                    # Check if frames have data points
                    has_data = False
                    for frame in frames:
                        if frame.get("data") and frame["data"].get("values"):
                            # Check if there are actual values
                            for value_array in frame["data"]["values"]:
                                if value_array and len(value_array) > 0:
                                    has_data = True
                                    break
                        if has_data:
                            break
                    
                    if not has_data:
                        return False, f"Query returned no data points (query: {query_expr[:50]}...)"
            
            return True, "Query executed successfully with data"
            
        except requests.exceptions.RequestException as e:
            return False, f"Query execution failed: {e}"

    def validate_panel_structure(self, panel: Dict) -> Tuple[bool, str]:
        """Validate basic panel structure and query configuration.
        
        Performs structural validation only - checks if panel has datasource and targets.
        Does not execute queries or validate query syntax.
        
        Note: This method is kept for backward compatibility but validate_panel_queries
        now uses execute_panel_query for actual query execution.
        """
        # Check if panel has targets (queries)
        targets = panel.get("targets", [])
        if not targets:
            # Panel without queries (e.g., text panels, row headers) is valid
            return True, "No queries configured (non-query panel)"

        # Get the first query expression
        first_target = targets[0]
        query_expr = first_target.get("expr")

        if not query_expr:
            # Query target exists but no expression - might be template variable
            return True, "Panel has targets but no query expression"

        # Validate the panel has the required basic structure
        return True, f"Basic structure valid (has query expr)"

    def validate_panel_queries(self) -> bool:
        """Execute and validate dashboard panel queries.

        This method performs live query execution for panels via
        :meth:`execute_panel_query` and verifies that queries return data.
        Structural-only checks are handled by :meth:`validate_panel_structure`,
        which is retained primarily for backward compatibility.
        """
        print("\n=== Validating Panel Queries (Executing Queries) ===")

        grafana_dashboards = self.get_dashboards()
        if not grafana_dashboards:
            print("✗ No dashboards to validate")
            return False

        all_valid = True
        total_panels = 0
        validated_panels = 0
        panels_with_data = 0
        panels_no_data = 0
        skipped_panels = 0

        for db in grafana_dashboards:
            db_uid = db.get("uid")
            db_title = db.get("title", "Unknown")

            if not db_uid:
                continue

            # Get full dashboard details
            dashboard_data = self.get_dashboard_by_uid(db_uid)
            if not dashboard_data:
                print(f"✗ Dashboard '{db_title}': Could not retrieve details")
                all_valid = False
                continue

            dashboard = dashboard_data.get("dashboard", {})
            panels = dashboard.get("panels", [])

            for panel in panels:
                total_panels += 1
                panel_title = panel.get("title", "Untitled")

                # Get datasource UID for the panel
                datasource = panel.get("datasource")
                ds_uid = ""
                if isinstance(datasource, dict):
                    ds_uid = datasource.get("uid", "")

                is_valid, status_msg = self.execute_panel_query(panel, ds_uid, db_title)

                if is_valid:
                    if "skip" in status_msg.lower() or "non-query" in status_msg.lower():
                        skipped_panels += 1
                        # Don't print skipped panels to reduce noise
                    else:
                        panels_with_data += 1
                        print(
                            f"✓ Dashboard '{db_title}' -> "
                            f"Panel '{panel_title}': {status_msg}"
                        )
                        sys.stdout.flush()
                    validated_panels += 1
                else:
                    # Query execution failed or returned no data
                    if "no data" in status_msg.lower():
                        panels_no_data += 1
                        print(
                            f"⚠ Dashboard '{db_title}' -> "
                            f"Panel '{panel_title}': {status_msg}"
                        )
                    else:
                        print(
                            f"✗ Dashboard '{db_title}' -> "
                            f"Panel '{panel_title}': {status_msg}"
                        )
                    sys.stdout.flush()
                    all_valid = False

        print(
            f"\nPanel validation summary: {total_panels} total, "
            f"{panels_with_data} with data, {panels_no_data} no data, "
            f"{skipped_panels} skipped, {total_panels - validated_panels} failed"
        )
        sys.stdout.flush()
        return all_valid

    def wait_for_dashboards(self) -> bool:
        """Wait for dashboards to be provisioned and available."""
        print("\nWaiting for dashboards to be provisioned...")
        for attempt in range(1, self.max_retries + 1):
            try:
                dashboards = self.get_dashboards()
                if dashboards is not None and len(dashboards) > 0:
                    print(f"✓ Found {len(dashboards)} dashboard(s) provisioned")
                    return True
            except Exception as e:
                print(f"  Attempt {attempt}/{self.max_retries}: Dashboards not ready yet ({e})")

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)

        print(f"✗ Dashboards failed to provision after {self.max_retries} attempts")
        return False

    def run_all_validations(self) -> bool:
        """Run all validation checks."""
        print("=" * 60)
        print("Grafana Dashboard Validation")
        print("=" * 60)

        # Step 1: Wait for Grafana to be ready
        if not self.wait_for_grafana():
            return False

        # Step 2: Wait for API authentication to work
        if not self.wait_for_api_auth():
            return False

        # Step 3: Validate dashboard JSON files
        if not self.validate_all_dashboard_files():
            return False

        # Step 4: Validate datasources
        if not self.validate_datasources():
            return False

        # Step 5: Wait for dashboards to be provisioned
        if not self.wait_for_dashboards():
            return False

        # Step 6: Validate dashboard provisioning
        if not self.validate_dashboard_provisioning():
            return False

        # Step 7: Validate panel structures
        if not self.validate_panel_queries():
            return False

        print("\n" + "=" * 60)
        print("✓ All Grafana dashboard validations passed!")
        print("=" * 60)
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Grafana dashboards and their provisioning"
    )
    parser.add_argument(
        "--grafana-url",
        default="http://localhost:3000",
        help="Grafana URL (default: http://localhost:3000)",
    )
    parser.add_argument(
        "--username", default="admin", help="Grafana username (default: admin)"
    )
    parser.add_argument(
        "--password", default="admin", help="Grafana password (default: admin)"
    )
    parser.add_argument(
        "--dashboard-dir",
        default="infra/grafana/dashboards",
        help="Dashboard directory (default: infra/grafana/dashboards)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=30,
        help="Max retries for Grafana readiness (default: 30)",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=5,
        help="Delay between retries in seconds (default: 5)",
    )

    args = parser.parse_args()

    validator = GrafanaValidator(
        grafana_url=args.grafana_url,
        username=args.username,
        password=args.password,
        dashboard_dir=args.dashboard_dir,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
    )

    success = validator.run_all_validations()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
