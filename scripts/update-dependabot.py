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


def find_dockerfiles(root_dir: Path) -> list[str]:
    """
    Find all directories containing Dockerfiles or docker-compose files.

    Returns:
        List of directory paths (formatted as /path/to/dir)
    """
    dockerfile_dirs = set()

    # Always include root directory for docker-compose files
    dockerfile_dirs.add('/')

    # Exclude directories we don't want to scan
    # Note: This differs from find_python_packages() - we intentionally include 'infra'
    # because it contains Dockerfiles (mongodb-exporter, nginx) but no Python packages
    exclude_dirs = {'.git', '.github', '__pycache__', 'node_modules', '.pytest_cache', '.venv', 'venv', 'env', 'documents'}

    # Walk through the directory tree
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter out excluded directories
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        # Check if this directory has a Dockerfile
        has_dockerfile = any(f.startswith('Dockerfile') for f in filenames)

        if has_dockerfile:
            rel_path = os.path.relpath(dirpath, root_dir)
            # Convert '.' (root) to '/', else prepend '/' and convert to Unix-style
            if rel_path == '.':
                rel_path = '/'
            else:
                rel_path = '/' + rel_path.replace('\\', '/')

            dockerfile_dirs.add(rel_path)

    return sorted(dockerfile_dirs)


def generate_dependabot_config(packages: list[tuple[str, str]], dockerfile_dirs: list[str]) -> str:
    """Generate the dependabot.yml content with separate entries for each directory."""
    content = HEADER

    # Monitor Python dependencies across all services and adapters
    # Create separate update entries for each directory (required by Dependabot)
    content += "  # Monitor Python dependencies across all services and adapters\n"
    content += "  # Each directory requires its own update entry\n"
    
    for directory, description in packages:
        content += f"  - package-ecosystem: \"pip\"\n"
        content += f"    directory: \"{directory}\"\n"
        content += "    schedule:\n"
        content += "      interval: \"weekly\"\n"
        content += "    open-pull-requests-limit: 10\n"
        content += "    labels:\n"
        content += "      - \"dependencies\"\n"
        content += "      - \"python\"\n"
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

    # Add Docker image monitoring for docker-compose and Dockerfiles
    content += "  # Monitor Docker image updates in docker-compose and Dockerfiles\n"
    content += "  - package-ecosystem: \"docker\"\n"
    content += "    directories:\n"
    for directory in dockerfile_dirs:
        content += f"      - \"{directory}\"\n"
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

    # Find all directories with Dockerfiles
    dockerfile_dirs = find_dockerfiles(repo_root)

    print(f"\nFound {len(dockerfile_dirs)} directories with Dockerfiles:")
    for directory in dockerfile_dirs:
        print(f"  - {directory}")

    # Generate the config
    config_content = generate_dependabot_config(packages, dockerfile_dirs)

    # Determine output path
    if output_path_arg:
        output_path = Path(output_path_arg)
    else:
        output_path = repo_root / '.github' / 'dependabot.yml'

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(config_content)

    print(f"\n✅ Successfully generated {output_path}")
    print(f"   Total update entries: {len(packages) + 3} ({len(packages)} pip + 1 npm + 1 docker + 1 github-actions)")
    print(f"   Python directories monitored: {len(packages)}")
    print(f"   Docker directories monitored: {len(dockerfile_dirs)}")


if __name__ == '__main__':
    import sys
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(output_path)
