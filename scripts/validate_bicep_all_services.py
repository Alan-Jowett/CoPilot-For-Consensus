# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Validate all services in a Bicep Container Apps configuration.

Usage:
    python validate_bicep_all_services.py <bicep_file>
    python validate_bicep_all_services.py infra/azure/modules/containerapps.bicep

Note: 'ui' and 'gateway' are frontend/proxy services without adapter schemas and are skipped.
"""

import subprocess
import sys
import os
from pathlib import Path
import io

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)


# Microservices requiring schema validation (adapter-based)
VALIDATED_SERVICES = [
    "auth",
    "reporting",
    "ingestion",
    "parsing",
    "chunking",
    "embedding",
    "orchestrator",
    "summarization",
]

# Frontend/proxy services without schema validation
FRONTEND_SERVICES = [
    "ui",
    "gateway",
]

ALL_SERVICES = VALIDATED_SERVICES + FRONTEND_SERVICES


def validate_all_services(bicep_file: str, verbose: bool = False) -> int:
    """
    Validate all services in the Bicep file.
    Returns 0 if all pass, 1 if any fail.
    """
    script_path = Path(__file__).parent / "validate_bicep_config.py"
    
    print("=" * 70)
    print(f"Validating Bicep Container Apps Configuration")
    print(f"File: {bicep_file}")
    if verbose:
        print(f"Mode: VERBOSE")
    print("=" * 70)
    print()
    
    failed_services = []
    passed_services = []
    skipped_services = []
    
    for service in ALL_SERVICES:
        if service in FRONTEND_SERVICES:
            print(f"Validating '{service}'... [N/A] (frontend service)")
            skipped_services.append(service)
            continue
            
        print(f"Validating '{service}'...", end=" ", flush=True)
        
        args = [sys.executable, str(script_path), bicep_file, service]
        if verbose:
            args.append("--verbose")
        
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            env={**dict(os.environ), 'PYTHONIOENCODING': 'utf-8'}
        )
        
        if result.returncode == 0:
            print("[OK]")
            passed_services.append(service)
        else:
            print("[FAIL]")
            failed_services.append(service)
            # Print error details
            if result.stderr:
                for line in result.stderr.split("\n"):
                    if line.strip():
                        print(f"  {line}")
            if result.stdout:
                for line in result.stdout.split("\n"):
                    if line.strip() and ("❌" in line or "Invalid" in line or "Missing" in line or "Context" in line or "📊" in line):
                        print(f"  {line}")
    
    print()
    print("=" * 70)
    print(f"Results: {len(passed_services)} passed, {len(failed_services)} failed, {len(skipped_services)} skipped")
    print("=" * 70)
    
    if failed_services:
        print(f"\nFailed services:")
        for service in failed_services:
            print(f"  - {service}")
        if skipped_services:
            print(f"\nSkipped services (frontend/proxy):")
            for service in skipped_services:
                print(f"  - {service}")
        return 1
    else:
        print(f"\nAll {len(VALIDATED_SERVICES)} microservices validated successfully!")
        if skipped_services:
            print(f"\nSkipped services (frontend/proxy): {', '.join(skipped_services)}")
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_bicep_all_services.py <bicep_file> [--verbose]")
        print("Example: python validate_bicep_all_services.py infra/azure/modules/containerapps.bicep")
        print("         python validate_bicep_all_services.py infra/azure/modules/containerapps.bicep --verbose")
        sys.exit(1)
    
    bicep_file = sys.argv[1]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    sys.exit(validate_all_services(bicep_file, verbose))
