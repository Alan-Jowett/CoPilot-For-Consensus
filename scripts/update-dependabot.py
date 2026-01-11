#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Generate or update .github/dependabot.yml based on workspace structure.

This script scans the workspace for all directories containing requirements.txt
or setup.py files and generates a complete dependabot.yml configuration.
"""

import os
from pathlib import Path

HEADER = """# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Dependabot configuration for tracking and updating dependencies
# Documentation: https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file
#
# THIS FILE IS AUTO-GENERATED - DO NOT EDIT MANUALLY
# Run `python scripts/update-dependabot.py` to regenerate

version: 2
updates:
"""


def find_python_packages(root_dir: Path) -> list[tuple[str, str]]:
    """
    Find all directories with Python package metadata.

    Returns:
        List of (directory_path, description) tuples
    """
    packages = []

    # Exclude directories we don't want to scan
    exclude_dirs = {
        '.git', '.github', '__pycache__', 'node_modules',
        '.pytest_cache', '.venv', 'venv', 'env',
        'documents', 'infra', 'schemas'
    }

    # Walk through the directory tree
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter out excluded directories
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        # Check if this directory has Python package files
        has_requirements = 'requirements.txt' in filenames or 'requirements.in' in filenames
        has_setup = 'setup.py' in filenames

        if has_requirements or has_setup:
            rel_path = os.path.relpath(dirpath, root_dir)
            # Convert '.' (root) to '/', else prepend '/' and convert to Unix-style
            if rel_path == '.':
                rel_path = '/'
            else:
                rel_path = '/' + rel_path.replace('\\', '/')

            # Generate a description
            dir_name = os.path.basename(dirpath)
            parent_dir = os.path.basename(os.path.dirname(dirpath))

            if parent_dir == 'adapters':
                description = f"{dir_name} adapter"
            elif rel_path.count('/') == 1:  # Top-level service
                description = f"{dir_name} service"
            else:
                description = dir_name

            packages.append((rel_path, description))

    # Sort packages: services first, then adapters alphabetically
    def sort_key(item):
        path, _ = item
        is_adapter = '/adapters/' in path
        return (is_adapter, path)

    return sorted(packages, key=sort_key)


def generate_dependabot_config(packages: list[tuple[str, str]]) -> str:
    """Generate the dependabot.yml content using multi-directory configuration."""
    content = HEADER

    # Extract all directories for Python packages
    python_directories = [directory for directory, _ in packages]

    # Split directories into groups to avoid Dependabot timeout
    # See: https://github.com/orgs/community/discussions/179358
    # Separate services from adapters, and split adapters into smaller groups
    services = [d for d in python_directories if '/adapters/' not in d]
    adapters = [d for d in python_directories if '/adapters/' in d]
    
    # Split adapters into two groups of roughly equal size
    adapters_mid = len(adapters) // 2
    adapters_group1 = adapters[:adapters_mid]
    adapters_group2 = adapters[adapters_mid:]

    # Group 1: Core Services
    content += "  # Monitor Python dependencies - Core Services\n"
    content += "  # Split into multiple entries to prevent Dependabot timeout\n"
    content += "  # See: https://github.com/orgs/community/discussions/179358\n"
    content += "  - package-ecosystem: \"pip\"\n"
    content += "    directories:\n"
    for directory in services:
        content += f"      - \"{directory}\"\n"
    content += "    schedule:\n"
    content += "      interval: \"weekly\"\n"
    content += "    open-pull-requests-limit: 10\n"
    content += "    labels:\n"
    content += "      - \"dependencies\"\n"
    content += "      - \"python\"\n"
    content += "      - \"services\"\n"
    content += "    groups:\n"
    content += "      pip-minor-patch:\n"
    content += "        patterns:\n"
    content += "          - \"*\"\n"
    content += "        update-types:\n"
    content += "          - \"minor\"\n"
    content += "          - \"patch\"\n\n"

    # Group 2: Adapters Group 1
    content += "  # Monitor Python dependencies - Adapters Group 1\n"
    content += "  - package-ecosystem: \"pip\"\n"
    content += "    directories:\n"
    for directory in adapters_group1:
        content += f"      - \"{directory}\"\n"
    content += "    schedule:\n"
    content += "      interval: \"weekly\"\n"
    content += "    open-pull-requests-limit: 10\n"
    content += "    labels:\n"
    content += "      - \"dependencies\"\n"
    content += "      - \"python\"\n"
    content += "      - \"adapters\"\n"
    content += "    groups:\n"
    content += "      pip-minor-patch:\n"
    content += "        patterns:\n"
    content += "          - \"*\"\n"
    content += "        update-types:\n"
    content += "          - \"minor\"\n"
    content += "          - \"patch\"\n\n"

    # Group 3: Adapters Group 2
    content += "  # Monitor Python dependencies - Adapters Group 2\n"
    content += "  - package-ecosystem: \"pip\"\n"
    content += "    directories:\n"
    for directory in adapters_group2:
        content += f"      - \"{directory}\"\n"
    content += "    schedule:\n"
    content += "      interval: \"weekly\"\n"
    content += "    open-pull-requests-limit: 10\n"
    content += "    labels:\n"
    content += "      - \"dependencies\"\n"
    content += "      - \"python\"\n"
    content += "      - \"adapters\"\n"
    content += "    groups:\n"
    content += "      pip-minor-patch:\n"
    content += "        patterns:\n"
    content += "          - \"*\"\n"
    content += "        update-types:\n"
    content += "          - \"minor\"\n"
    content += "          - \"patch\"\n\n"

    # Add npm monitoring for the React UI
    content += "  # Monitor npm dependencies in React UI\n"
    content += "  - package-ecosystem: \"npm\"\n"
    content += "    directory: \"/ui\"\n"
    content += "    schedule:\n"
    content += "      interval: \"weekly\"\n"
    content += "    open-pull-requests-limit: 5\n"
    content += "    labels:\n"
    content += "      - \"dependencies\"\n"
    content += "      - \"javascript\"\n"
    content += "    groups:\n"
    content += "      npm-minor-patch:\n"
    content += "        patterns:\n"
    content += "          - \"*\"\n"
    content += "        update-types:\n"
    content += "          - \"minor\"\n"
    content += "          - \"patch\"\n\n"

    # Add Docker image monitoring for docker-compose
    content += "  # Monitor Docker image updates in docker-compose\n"
    content += "  - package-ecosystem: \"docker\"\n"
    content += "    directory: \"/\"\n"
    content += "    schedule:\n"
    content += "      interval: \"weekly\"\n"
    content += "    open-pull-requests-limit: 5\n"
    content += "    labels:\n"
    content += "      - \"dependencies\"\n"
    content += "      - \"docker\"\n"
    content += "    groups:\n"
    content += "      docker-minor-patch:\n"
    content += "        patterns:\n"
    content += "          - \"*\"\n"
    content += "        update-types:\n"
    content += "          - \"minor\"\n"
    content += "          - \"patch\"\n\n"

    # Add GitHub Actions monitoring
    content += "  # Monitor GitHub Actions\n"
    content += "  - package-ecosystem: \"github-actions\"\n"
    content += "    directory: \"/\"\n"
    content += "    schedule:\n"
    content += "      interval: \"weekly\"\n"
    content += "    open-pull-requests-limit: 5\n"
    content += "    labels:\n"
    content += "      - \"dependencies\"\n"
    content += "      - \"github-actions\"\n"
    content += "    groups:\n"
    content += "      github-actions-minor-patch:\n"
    content += "        patterns:\n"
    content += "          - \"*\"\n"
    content += "        update-types:\n"
    content += "          - \"minor\"\n"
    content += "          - \"patch\"\n"

    return content


def main(output_path_arg=None):
    """Main entry point.

    Args:
        output_path_arg: Optional output path for dependabot.yml. Defaults to .github/dependabot.yml
    """
    # Get the repository root (parent of scripts directory)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    print(f"Scanning repository: {repo_root}")

    # Find all Python packages
    packages = find_python_packages(repo_root)

    print(f"Found {len(packages)} Python packages:")
    for directory, description in packages:
        print(f"  - {directory} ({description})")

    # Generate the config
    config_content = generate_dependabot_config(packages)

    # Determine output path
    if output_path_arg:
        output_path = Path(output_path_arg)
    else:
        output_path = repo_root / '.github' / 'dependabot.yml'

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(config_content)

    print(f"\n✅ Successfully generated {output_path}")
    print(f"   Total update entries: 6 (3 pip groups + 1 npm + 1 docker + 1 github-actions)")
    print(f"   Python directories monitored: {len(packages)}")
    print(f"\n💡 Using split multi-directory configuration to avoid Dependabot timeouts")
    print(f"   Services and adapters are processed in separate groups to stay within time limits")


if __name__ == '__main__':
    import sys
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(output_path)
