# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup script for copilot_startup adapter."""

from setuptools import find_packages, setup

setup(
    name="copilot_startup",
    version="0.1.0",
    description="Startup utilities for Copilot services",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        # Core dependencies - installed from parent project
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "copilot-schema-validation",  # For schema validation tests
        ],
    },
)
