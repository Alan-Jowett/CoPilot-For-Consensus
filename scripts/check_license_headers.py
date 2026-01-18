"""
SPDX-License-Identifier: MIT
Copyright (c) 2025 Copilot-for-Consensus contributors
"""

import argparse
import os
import re
import sys
from pathlib import Path

SPDX_PATTERN = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9\-\.\+]+)")
COPYRIGHT_PATTERN = re.compile(r"Copyright\s*\(c\)\s*\d{4}(-\d{4})?")

DEFAULT_EXTENSIONS = {
    ".py",
    ".sh",
    ".ps1",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".proto",
    ".graphql",
    ".sql",
    ".css",
    ".scss",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
}

DEFAULT_FILENAMES = {"Dockerfile"}

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
    "htmlcov",
    ".gdn",
}


def should_check(path: Path, extensions: set[str], filenames: set[str], excludes: set[str]) -> bool:
    # Exclude by directory/file patterns
    parts = set(path.parts)
    for item in excludes:
        if item.endswith(".egg-info") and any(p.endswith(".egg-info") for p in parts):
            return False
        if item in parts:
            return False

    # Check by extension or filename
    if path.name in filenames:
        return True
    return path.suffix.lower() in extensions


def file_head(path: Path, head_lines: int = 30) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = []
            for i, line in enumerate(f):
                lines.append(line)
                if i + 1 >= head_lines:
                    break
            return "".join(lines)
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error reading file {path}: {e}", file=sys.stderr)
        return ""


def has_headers(text: str) -> tuple[bool, bool]:
    spdx = SPDX_PATTERN.search(text) is not None
    copyright = COPYRIGHT_PATTERN.search(text) is not None
    return spdx, copyright


def scan_repo(root: Path, extensions: set[str], filenames: set[str], excludes: set[str], head_lines: int) -> list[Path]:
    missing = []
    for dirpath, dirnames, filenames_list in os.walk(root):
        # Filter excluded directories in-place for os.walk performance
        dirnames[:] = [d for d in dirnames if d not in excludes and not d.endswith(".egg-info")]

        for fname in filenames_list:
            fpath = Path(dirpath) / fname
            if not should_check(fpath, extensions, filenames, excludes):
                continue
            head = file_head(fpath, head_lines=head_lines)
            spdx, copyright = has_headers(head)
            if not (spdx and copyright):
                missing.append(fpath)
    return missing


def load_ignore_file(root: Path, ignore_file: str | None) -> set[str]:
    patterns = set()
    if not ignore_file:
        return patterns
    path = root / ignore_file
    if not path.exists():
        return patterns
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.add(line)
    return patterns


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check SPDX and Copyright headers across the repository")
    p.add_argument(
        "--root", default=str(Path.cwd()), help="Root directory to scan (default: current working directory)"
    )
    p.add_argument(
        "--head-lines", type=int, default=30, help="Number of lines from start of file to search for headers"
    )
    p.add_argument(
        "--extensions", nargs="*", default=sorted(DEFAULT_EXTENSIONS), help="File extensions to check (space-separated)"
    )
    p.add_argument(
        "--filenames",
        nargs="*",
        default=sorted(DEFAULT_FILENAMES),
        help="Specific filenames to check (space-separated)",
    )
    p.add_argument(
        "--exclude",
        nargs="*",
        default=sorted(DEFAULT_EXCLUDES),
        help="Directories or patterns to exclude (space-separated)",
    )
    p.add_argument(
        "--ignore-file",
        default=".headercheckignore",
        help="Path relative to root of an ignore file with patterns (one per line)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()

    excludes = set(args.exclude)
    excludes |= load_ignore_file(root, args.ignore_file)

    missing = scan_repo(
        root=root,
        extensions=set(args.extensions),
        filenames=set(args.filenames),
        excludes=excludes,
        head_lines=args.head_lines,
    )

    if missing:
        print("Files missing required headers:")
        for p in sorted(missing):
            print(f" - {p.relative_to(root)}")
        print(f"\nTotal: {len(missing)} file(s) missing headers.")
        return 1
    else:
        print("All checked files contain SPDX and Copyright headers.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
