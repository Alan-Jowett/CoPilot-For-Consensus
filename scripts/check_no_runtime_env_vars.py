#!/usr/bin/env python3
"""
SPDX-License-Identifier: MIT
Copyright (c) 2025 Copilot-for-Consensus contributors

Check for direct OS environment variable access in service runtime code.

This script scans service code for disallowed patterns that read OS environment
variables directly (e.g., os.environ.get, os.getenv, os.environ[]) instead of
using schematized/typed configuration. Direct env var access bypasses validation,
documentation, and type safety.

Scope:
- Includes: Service runtime code (auth/, chunking/, embedding/, ingestion/,
  orchestrator/, parsing/, reporting/, summarization/)
- Excludes: **/tests/**, scripts/**, and explicitly allowlisted files

Exit codes:
- 0: No violations found
- 1: Violations found
"""

import argparse
import fnmatch
import re
import sys
from pathlib import Path
from typing import NamedTuple

# Default service directories to scan
DEFAULT_SERVICE_DIRS = [
    "auth",
    "chunking",
    "embedding",
    "ingestion",
    "orchestrator",
    "parsing",
    "reporting",
    "summarization",
]

# Default exclusion patterns (relative path components)
DEFAULT_EXCLUDES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".eggs",
    "*.egg-info",
    "tests",  # Exclude all test directories
}

# Patterns that indicate direct OS environment variable access
ENV_VAR_PATTERNS = [
    re.compile(r"\bos\.environ\.get\s*\("),
    re.compile(r"\bos\.getenv\s*\("),
    re.compile(r"\bos\.environ\s*\["),
]


class Violation(NamedTuple):
    """Represents a violation found in a file."""

    filepath: Path
    line_number: int
    line_content: str
    pattern: str


def should_check(path: Path, service_dirs: list[str], excludes: set[str]) -> bool:
    """
    Determine if a path should be checked for env var usage.

    Args:
        path: Path to check
        service_dirs: List of service directory names to include
        excludes: Set of exclusion patterns

    Returns:
        True if the path should be checked, False otherwise
    """
    # Must be a Python file
    if path.suffix.lower() != ".py":
        return False

    # Must be under one of the service directories
    parts = path.parts
    if not any(service_dir in parts for service_dir in service_dirs):
        return False

    # Check exclusions
    for exclude in excludes:
        if exclude.endswith(".egg-info"):
            if any(p.endswith(".egg-info") for p in parts):
                return False
        elif exclude in parts:
            return False

    return True


def load_allowlist(allowlist_path: Path) -> dict[str, list[re.Pattern]]:
    """
    Load the allowlist file containing file patterns and optional regex exceptions.

    Format:
        # Comments start with #
        path/to/file.py
        path/to/file.py:regex_pattern_to_allow

    Args:
        allowlist_path: Path to the allowlist file

    Returns:
        Dictionary mapping file paths to list of regex patterns (empty list if no patterns)
    """
    if not allowlist_path.exists():
        return {}

    allowlist = {}
    with allowlist_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Check if line contains a regex pattern
            if ":" in line:
                file_glob, pattern_str = line.split(":", 1)
                file_glob = file_glob.strip()
                pattern_str = pattern_str.strip()
                try:
                    pattern = re.compile(pattern_str)
                    allowlist.setdefault(file_glob, []).append(pattern)
                except re.error as e:
                    print(
                        f"Warning: Invalid regex pattern in allowlist: {pattern_str}: {e}",
                        file=sys.stderr,
                    )
            else:
                # No regex pattern, allow entire file
                allowlist[line] = []

    return allowlist


def is_allowlisted(filepath: Path, line_content: str, allowlist: dict[str, list[re.Pattern]], root: Path) -> bool:
    """
    Check if a violation is allowlisted.

    Args:
        filepath: Path to the file containing the violation
        line_content: Content of the line with the violation
        allowlist: Allowlist dictionary from load_allowlist()
        root: Root directory for relative path calculation

    Returns:
        True if the violation is allowlisted, False otherwise
    """
    try:
        rel_path = filepath.relative_to(root)
    except ValueError:
        rel_path = filepath

    for file_glob, patterns in allowlist.items():
        # Check if file matches glob pattern using fnmatch for more robust matching
        # Convert both to forward slashes for consistent matching across platforms
        normalized_rel_path = str(rel_path).replace("\\", "/")
        normalized_glob = file_glob.replace("\\", "/")

        if fnmatch.fnmatch(normalized_rel_path, normalized_glob):
            # If no specific patterns, entire file is allowlisted
            if not patterns:
                return True
            # Otherwise, check if line matches any of the patterns
            for pattern in patterns:
                if pattern.search(line_content):
                    return True

    return False


def check_file(filepath: Path) -> list[tuple[int, str, str]]:
    """
    Check a single file for disallowed environment variable access.

    Args:
        filepath: Path to the file to check

    Returns:
        List of tuples: (line_number, line_content, pattern_name)
    """
    try:
        with filepath.open("r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        # If file cannot be read, skip it
        return []

    violations = []
    for line_num, line in enumerate(lines, start=1):
        for pattern in ENV_VAR_PATTERNS:
            if pattern.search(line):
                pattern_name = pattern.pattern.replace(r"\b", "").replace(r"\s*\(", "(")
                violations.append((line_num, line.rstrip(), pattern_name))
                break  # Only report first match per line

    return violations


def scan_services(
    root: Path, service_dirs: list[str], excludes: set[str], allowlist: dict[str, list[re.Pattern]]
) -> list[Violation]:
    """
    Scan service directories for disallowed environment variable access.

    Args:
        root: Root directory to scan
        service_dirs: List of service directory names to include
        excludes: Set of exclusion patterns
        allowlist: Allowlist dictionary from load_allowlist()

    Returns:
        List of Violation objects
    """
    all_violations = []

    # Scan each service directory
    for service_dir in service_dirs:
        service_path = root / service_dir
        if not service_path.exists():
            continue

        for filepath in service_path.rglob("*.py"):
            if not should_check(filepath, service_dirs, excludes):
                continue

            file_violations = check_file(filepath)
            for line_num, line_content, pattern_name in file_violations:
                # Check if this violation is allowlisted
                if is_allowlisted(filepath, line_content, allowlist, root):
                    continue

                all_violations.append(
                    Violation(
                        filepath=filepath,
                        line_number=line_num,
                        line_content=line_content,
                        pattern=pattern_name,
                    )
                )

    return all_violations


def main() -> int:
    """Main entry point for the runtime env vars checker."""
    parser = argparse.ArgumentParser(
        description="Check for direct OS environment variable access in service runtime code"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--service-dirs",
        nargs="+",
        default=DEFAULT_SERVICE_DIRS,
        help=(
            "Service directories to scan (default: auth chunking embedding ingestion orchestrator parsing reporting "
            "summarization)"
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Additional patterns to exclude (can be specified multiple times)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path("scripts/env_var_allowlist.txt"),
        help="Path to allowlist file (default: scripts/env_var_allowlist.txt)",
    )

    args = parser.parse_args()

    # Build exclusion set
    excludes = DEFAULT_EXCLUDES.copy()
    if args.exclude:
        excludes.update(args.exclude)

    # Load allowlist
    allowlist_path = args.root / args.allowlist if not args.allowlist.is_absolute() else args.allowlist
    allowlist = load_allowlist(allowlist_path)

    # Scan for violations
    violations = scan_services(args.root, args.service_dirs, excludes, allowlist)

    if not violations:
        print("✓ No direct OS environment variable access found in service runtime code")
        return 0

    # Report violations
    print(f"✗ Found {len(violations)} direct OS environment variable access(es) in service runtime code:\n")

    for violation in sorted(violations, key=lambda v: (str(v.filepath), v.line_number)):
        try:
            rel_path = violation.filepath.relative_to(args.root)
        except ValueError:
            rel_path = violation.filepath

        print(f"  {rel_path}:{violation.line_number}")
        print(f"    Pattern: {violation.pattern}")
        print(f"    Line: {violation.line_content.strip()}")
        print()

    print("Direct OS environment variable access bypasses schematized configuration.")
    print("Use typed config objects instead of reading environment variables directly.")
    print("\nExample fix:")
    print("  # BAD")
    print("  retry_limit = int(os.environ.get('RETRY_LIMIT', '3'))")
    print()
    print("  # GOOD")
    print("  # In schema: define 'retry_limit' field")
    print("  # In code: use config.service_settings.retry_limit")
    print()
    print("If this is intentional (e.g., backward compatibility fallback),")
    print("add it to scripts/env_var_allowlist.txt with optional regex pattern.")

    return 1


if __name__ == "__main__":
    sys.exit(main())
