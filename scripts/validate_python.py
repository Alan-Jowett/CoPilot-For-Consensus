#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Validation script to run all static analysis and import tests locally.

This script runs the same validation checks as CI to help developers
catch issues before pushing code.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str, check: bool = False) -> tuple[int, str]:
    """
    Run a command and return the result.

    Args:
        cmd: Command and arguments to run
        description: Human-readable description of what's being run
        check: If True, raise exception on non-zero exit code

    Returns:
        Tuple of (exit_code, output)
    """
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return result.returncode, result.stdout + result.stderr

    except subprocess.CalledProcessError as e:
        print(f"Error running {description}: {e}", file=sys.stderr)
        return e.returncode, str(e)


def get_repo_root() -> Path:
    """Get the repository root directory."""
    # Try git to find repo root
    try:
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        # Fallback to script location (scripts/ -> repo root)
        return Path(__file__).parent.parent


def validate_ruff(repo_root: Path, fix: bool = False) -> int:
    """Run ruff linting."""
    cmd = ["ruff", "check", str(repo_root)]
    if fix:
        cmd.append("--fix")

    return run_command(cmd, "Ruff - Fast Python Linter")[0]


def validate_mypy(repo_root: Path, target: str = None) -> int:
    """Run mypy type checking."""
    if target:
        targets = [str(repo_root / target)]
    else:
        # Check adapters
        targets = [
            str(d / d.name)
            for d in (repo_root / "adapters").glob("copilot_*")
            if d.is_dir() and (d / d.name / "__init__.py").exists()
        ]

    exit_codes = []
    for target_path in targets:
        exit_code, _ = run_command(
            ["mypy", target_path, "--no-error-summary"], f"MyPy Type Checker - {Path(target_path).name}"
        )
        exit_codes.append(exit_code)

    return max(exit_codes) if exit_codes else 0


def validate_pyright(repo_root: Path, target: str = None) -> int:
    """Run pyright type checking."""
    # Check if pyright is available
    try:
        subprocess.run(["pyright", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n⚠️  Pyright not found. Install with: npm install -g pyright")
        return 0

    if target:
        targets = [str(repo_root / target)]
    else:
        # Check adapters
        targets = [
            str(d / d.name)
            for d in (repo_root / "adapters").glob("copilot_*")
            if d.is_dir() and (d / d.name / "__init__.py").exists()
        ]

    exit_codes = []
    for target_path in targets:
        exit_code, _ = run_command(
            ["pyright", target_path, "--level", "error"], f"Pyright Type Checker - {Path(target_path).name}"
        )
        exit_codes.append(exit_code)

    return max(exit_codes) if exit_codes else 0


def validate_pylint(repo_root: Path, target: str = None) -> int:
    """Run pylint attribute checking."""
    if target:
        targets = [str(repo_root / target)]
    else:
        # Check adapters
        targets = [
            str(d / d.name)
            for d in (repo_root / "adapters").glob("copilot_*")
            if d.is_dir() and (d / d.name / "__init__.py").exists()
        ]

    exit_codes = []
    for target_path in targets:
        exit_code, _ = run_command(
            [
                "pylint",
                target_path,
                "--disable=all",
                "--enable=E1101,E0611,E1102,E1120,E1121",
                "--output-format=colorized",
            ],
            f"Pylint Attribute Checker - {Path(target_path).name}",
        )
        exit_codes.append(exit_code)

    return max(exit_codes) if exit_codes else 0


def run_import_tests(repo_root: Path) -> int:
    """Run import smoke tests."""
    test_file = repo_root / "tests" / "test_imports.py"
    if not test_file.exists():
        print(f"⚠️  Import test file not found: {test_file}")
        return 0

    return run_command(["pytest", str(test_file), "-v", "--tb=short"], "Import Smoke Tests")[0]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Python validation checks locally")
    parser.add_argument(
        "--tool",
        choices=["ruff", "mypy", "pyright", "pylint", "import-tests", "all"],
        default="all",
        help="Which validation tool to run (default: all)",
    )
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues where possible (only for ruff)")
    parser.add_argument("--target", help="Specific target directory to check (relative to repo root)")

    args = parser.parse_args()
    repo_root = get_repo_root()

    print(f"\n🔍 Running Python validation checks in: {repo_root}\n")

    # Track results
    results = {}

    # Run selected tools
    if args.tool in ("ruff", "all"):
        results["ruff"] = validate_ruff(repo_root, fix=args.fix)

    if args.tool in ("mypy", "all"):
        results["mypy"] = validate_mypy(repo_root, args.target)

    if args.tool in ("pyright", "all"):
        results["pyright"] = validate_pyright(repo_root, args.target)

    if args.tool in ("pylint", "all"):
        results["pylint"] = validate_pylint(repo_root, args.target)

    if args.tool in ("import-tests", "all"):
        results["import-tests"] = run_import_tests(repo_root)

    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for tool, exit_code in results.items():
        status = "✅ PASSED" if exit_code == 0 else "❌ FAILED"
        print(f"{tool:20s}: {status}")
        if exit_code != 0:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✅ All validation checks passed!")
        return 0
    else:
        print("\n❌ Some validation checks failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
