# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot_service_base package."""

from setuptools import setup, find_packages

setup(
    name="copilot_service_base",
    version="0.1.0",
    description="Shared utilities and base classes for Copilot microservices",
    author="Copilot-for-Consensus contributors",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        # Core dependencies from other adapters
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
