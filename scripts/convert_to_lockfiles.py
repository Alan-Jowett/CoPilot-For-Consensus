#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Convert existing requirements.txt files to requirements.in format and compile lockfiles.

This script helps migrate services to the pip-tools lockfile workflow:
1. Converts pinned dependencies (==) to ranged dependencies (>=) in .in files
2. Runs pip-compile to generate new lockfiles with full transitive dependencies
"""

import os
import re
import subprocess
import sys
from pathlib import Path


HEADER_IN = """# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# {service} Service Dependencies
# This file lists direct external dependencies with version ranges.
# Run `pip-compile requirements.in` to generate requirements.txt with pinned versions.
#
# Note: Local adapters (copilot-*) are installed separately in the Dockerfile
# via scripts/install_adapters.py and are not included in this lockfile.

"""

HEADER_TXT = """# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# {service} Service Dependencies - LOCKFILE
# This file is generated from requirements.in using pip-compile.
# DO NOT EDIT MANUALLY - run `pip-compile requirements.in` to update.
#
# Note: Local adapters (copilot-*) are installed separately in the Dockerfile
# via scripts/install_adapters.py and are not included in this lockfile.

"""


def convert_to_in_file(requirements_txt: Path, service_name: str) -> list[str]:
    """Convert requirements.txt to requirements.in format."""
    lines = []
    
    with open(requirements_txt, 'r') as f:
        content = f.read()
    
    # Skip existing headers and license
    in_header = True
    for line in content.split('\n'):
        line = line.strip()
        
        # Skip SPDX, copyright, and empty lines at the start
        if in_header:
            if not line or line.startswith('#') or line.startswith('SPDX'):
                continue
            else:
                in_header = False
        
        # Skip comment-only lines (but keep inline comments)
        if line.startswith('#'):
            # Keep section headers like "# Core dependencies"
            if any(keyword in line.lower() for keyword in ['dependencies', 'framework', 'monitoring', 'authentication', 'client', 'configuration']):
                lines.append(line)
            continue
        
        # Skip empty lines
        if not line:
            continue
        
        # Skip adapter note
        if 'NOTE:' in line or 'Adapters' in line:
            continue
        
        # Convert pinned versions (==) to ranged versions (>=)
        if '==' in line:
            # Extract package name and version
            match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)==(.+)$', line)
            if match:
                package, version = match.groups()
                lines.append(f"{package}>={version}")
            else:
                # Keep as-is if we can't parse it
                lines.append(line)
        else:
            # Keep as-is (already uses >= or other operators)
            lines.append(line)
    
    return lines


def create_in_file(service_path: Path):
    """Create requirements.in from requirements.txt."""
    requirements_txt = service_path / 'requirements.txt'
    requirements_in = service_path / 'requirements.in'
    
    if not requirements_txt.exists():
        print(f"⚠️  No requirements.txt found in {service_path}")
        return False
    
    if requirements_in.exists():
        print(f"ℹ️  requirements.in already exists in {service_path}, skipping")
        return False
    
    service_name = service_path.name.title()
    
    # Convert dependencies
    deps = convert_to_in_file(requirements_txt, service_name)
    
    # Write .in file
    with open(requirements_in, 'w') as f:
        f.write(HEADER_IN.format(service=service_name))
        f.write('\n'.join(deps))
        f.write('\n')
    
    print(f"✅ Created {requirements_in}")
    return True


def compile_lockfile(service_path: Path):
    """Compile requirements.txt from requirements.in using pip-compile."""
    requirements_in = service_path / 'requirements.in'
    
    if not requirements_in.exists():
        print(f"⚠️  No requirements.in found in {service_path}")
        return False
    
    print(f"🔄 Compiling lockfile for {service_path.name}...")
    
    try:
        # Run pip-compile
        result = subprocess.run(
            ['pip-compile', 'requirements.in', '--output-file', 'requirements.txt.new', 
             '--allow-unsafe', '--strip-extras'],
            cwd=service_path,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Read the compiled file
        compiled_txt = service_path / 'requirements.txt.new'
        with open(compiled_txt, 'r') as f:
            compiled_content = f.read()
        
        # Write with custom header
        requirements_txt = service_path / 'requirements.txt'
        service_name = service_path.name.title()
        with open(requirements_txt, 'w') as f:
            f.write(HEADER_TXT.format(service=service_name))
            f.write(compiled_content)
        
        # Clean up temp file
        compiled_txt.unlink()
        
        print(f"✅ Compiled lockfile for {service_path.name}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to compile lockfile for {service_path.name}")
        print(f"Error: {e.stderr}")
        return False


def main():
    """Main entry point."""
    # Get repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    # Services to convert
    services = [
        'auth',
        'chunking',
        'embedding',
        'ingestion',
        'orchestrator',
        'parsing',
        'reporting',
        'summarization'
    ]
    
    if len(sys.argv) > 1:
        # Allow specifying specific services
        services = sys.argv[1:]
    
    print(f"Converting {len(services)} services to pip-tools lockfile workflow...\n")
    
    success_count = 0
    for service_name in services:
        service_path = repo_root / service_name
        
        if not service_path.exists():
            print(f"⚠️  Service directory {service_path} not found, skipping")
            continue
        
        print(f"\n📦 Processing {service_name}...")
        
        # Create .in file
        created = create_in_file(service_path)
        
        # Compile lockfile
        if created or (service_path / 'requirements.in').exists():
            if compile_lockfile(service_path):
                success_count += 1
    
    print(f"\n✅ Successfully converted {success_count}/{len(services)} services")


if __name__ == '__main__':
    main()
