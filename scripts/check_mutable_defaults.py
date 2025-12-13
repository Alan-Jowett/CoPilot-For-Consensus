#!/usr/bin/env python3
"""
SPDX-License-Identifier: MIT
Copyright (c) 2025 Copilot-for-Consensus contributors

Check for mutable default arguments in Python function definitions.

This script scans Python files for functions that use mutable default arguments
(lists, dictionaries, or sets), which can lead to unexpected behavior due to
shared state across function invocations.
"""
import argparse
import ast
import sys
from pathlib import Path


DEFAULT_EXCLUDES = {
    ".git", "node_modules", "venv", ".venv", "env", ".env",
    "__pycache__", "build", "dist", ".pytest_cache", ".mypy_cache",
    ".tox", ".eggs", "*.egg-info"
}


def should_check(path: Path, excludes: set[str]) -> bool:
    """Determine if a path should be checked for mutable defaults."""
    parts = set(path.parts)
    for item in excludes:
        if item.endswith(".egg-info") and any(p.endswith(".egg-info") for p in parts):
            return False
        if item in parts:
            return False
    return path.suffix.lower() == ".py"


def is_mutable_default(node: ast.AST) -> tuple[bool, str]:
    """
    Check if an AST node represents a mutable default argument.
    
    Returns (is_mutable, type_name) where type_name is 'list', 'dict', or 'set'.
    """
    # Direct literals: [] (list), {} (dict), or {1, 2} (set with elements)
    if isinstance(node, ast.List):
        return True, "list"
    elif isinstance(node, ast.Dict):
        return True, "dict"
    elif isinstance(node, ast.Set):
        return True, "set"
    # Constructor calls: list(), dict(), set() with any arguments
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in ('list', 'dict', 'set'):
            return True, node.func.id
    return False, ""


def find_mutable_defaults(filepath: Path) -> list[tuple[int, str, str, str]]:
    """
    Find mutable default arguments in a Python file.
    
    Returns a list of tuples: (line_number, function_name, param_name, default_type)
    """
    try:
        with filepath.open('r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            tree = ast.parse(content, str(filepath))
    except Exception:
        # If file cannot be parsed, skip it
        return []
    
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check regular positional/keyword defaults
            for i, default in enumerate(node.args.defaults):
                is_mutable, default_type = is_mutable_default(default)
                if is_mutable:
                    param_idx = len(node.args.args) - len(node.args.defaults) + i
                    param_name = node.args.args[param_idx].arg
                    issues.append((node.lineno, node.name, param_name, default_type))
            
            # Check keyword-only defaults
            for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if default:
                    is_mutable, default_type = is_mutable_default(default)
                    if is_mutable:
                        param_name = arg.arg
                        issues.append((node.lineno, node.name, param_name, default_type))
    
    return issues


def scan_directory(root: Path, excludes: set[str]) -> list[tuple[Path, int, str, str, str]]:
    """
    Scan a directory for Python files with mutable default arguments.
    
    Returns a list of tuples: (filepath, line_number, function_name, param_name, default_type)
    """
    all_issues = []
    
    for filepath in root.rglob("*.py"):
        if not should_check(filepath, excludes):
            continue
        
        issues = find_mutable_defaults(filepath)
        for line, func_name, param_name, default_type in issues:
            all_issues.append((filepath, line, func_name, param_name, default_type))
    
    return all_issues


def load_ignore_file(root: Path, ignore_file: str | None) -> set[str]:
    """Load additional exclusions from an ignore file."""
    if not ignore_file:
        return set()
    
    ignore_path = root / ignore_file
    if not ignore_path.exists():
        return set()
    
    excludes = set()
    with ignore_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                excludes.add(line)
    
    return excludes


def main() -> int:
    """Main entry point for the mutable defaults checker."""
    parser = argparse.ArgumentParser(
        description="Check for mutable default arguments in Python functions"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root directory to scan (default: current directory)"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Additional patterns to exclude (can be specified multiple times)"
    )
    parser.add_argument(
        "--ignore-file",
        help="File containing additional exclusion patterns (one per line)"
    )
    
    args = parser.parse_args()
    
    # Build exclusion set
    excludes = DEFAULT_EXCLUDES.copy()
    if args.exclude:
        excludes.update(args.exclude)
    
    ignore_file_excludes = load_ignore_file(args.root, args.ignore_file)
    excludes.update(ignore_file_excludes)
    
    # Scan for issues
    issues = scan_directory(args.root, excludes)
    
    if not issues:
        print("✓ No mutable default arguments found")
        return 0
    
    # Report issues
    print(f"✗ Found {len(issues)} mutable default argument(s):\n")
    
    for filepath, line, func_name, param_name, default_type in sorted(issues):
        rel_path = filepath.relative_to(args.root)
        print(f"  {rel_path}:{line}")
        print(f"    Function: {func_name}()")
        print(f"    Parameter: {param_name}={{{default_type}}} (mutable default)")
        print(f"    Recommendation: Use {param_name}=None and initialize inside the function")
        print()
    
    print("Mutable default arguments can cause unexpected behavior due to shared state.")
    print("Use None as the default and initialize mutable objects inside the function.")
    print("\nExample fix:")
    print("  # BAD")
    print("  def func(items=[]):")
    print("      items.append(1)")
    print()
    print("  # GOOD")
    print("  def func(items=None):")
    print("      if items is None:")
    print("          items = []")
    print("      items.append(1)")
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
