# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-storage package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="copilot-storage",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="Shared document storage library for Copilot-for-Consensus microservices",
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
        "pymongo>=4.6.3",  # MongoDB client
        "azure-cosmos>=4.5.0",  # Azure Cosmos DB client
        "azure-identity>=1.16.1",  # Azure managed identity support
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pylint>=3.0.0",
            "mypy>=1.0.0",
        ],
        "validation": [
            "copilot-schema-validation>=0.1.0",  # Optional: for ValidatingDocumentStore
        ],
        # Test extra includes validation for factory tests
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "copilot-schema-validation>=0.1.0",
        ],
    },
)
