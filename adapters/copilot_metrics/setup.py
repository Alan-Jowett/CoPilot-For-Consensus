# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-metrics package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="copilot-metrics",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="Metrics collection abstraction for Copilot-for-Consensus microservices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Alan-Jowett/CoPilot-For-Consensus",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "copilot-config>=0.1.0",  # For DriverConfig
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pylint>=3.0.0",
            "mypy>=1.0.0",
        ],
        "prometheus": [
            "prometheus-client>=0.19.0",  # Prometheus metrics client
        ],
        "azure": [
            # Pin to the current beta until a stable 1.x release is available
            # azure-monitor-opentelemetry-exporter==1.0.0b48 requires opentelemetry==1.39
            "azure-monitor-opentelemetry-exporter==1.0.0b48",
            "opentelemetry-api==1.39",
            "opentelemetry-sdk==1.39",
        ],
        # All optional backends
        "all": [
            "prometheus-client>=0.19.0",
            "azure-monitor-opentelemetry-exporter==1.0.0b48",
            "opentelemetry-api==1.39",
            "opentelemetry-sdk==1.39",
        ],
        # Test extra includes all drivers for factory tests
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "prometheus-client>=0.19.0",
            "azure-monitor-opentelemetry-exporter==1.0.0b48",
            "opentelemetry-api==1.39",
            "opentelemetry-sdk==1.39",
        ],
    },
)
