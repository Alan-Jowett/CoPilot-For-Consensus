# SPDX-License-Identifier: MIT

import json
import subprocess
import sys
from typing import List


def install_editable(paths: List[str]) -> None:
    for path in paths:
        if not path:
            continue
        print(f"Installing extra editable dependency: {path}")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", path], check=True)


def install_packages(packages: List[str]) -> None:
    for pkg in packages:
        if not pkg:
            continue
        print(f"Installing extra package: {pkg}")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)


def main() -> int:
    try:
        extra_editable_json = sys.argv[1]
        extra_packages_json = sys.argv[2]
    except IndexError:
        print("Usage: install_extras.py <extra_editable_paths_json> <extra_pip_packages_json>")
        return 1

    editable_paths = json.loads(extra_editable_json)
    extra_packages = json.loads(extra_packages_json)

    install_editable(editable_paths)
    install_packages(extra_packages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())