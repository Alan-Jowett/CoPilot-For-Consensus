# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-events package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read the README file if it exists
this_directory = Path(__file__).parent
readme_path = this_directory / "README.md"
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")
else:
    long_description = "Shared event publishing library for Copilot-for-Consensus microservices"

setup(
    name="copilot-events",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="Shared event publishing and models library for Copilot-for-Consensus microservices",
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
        "pika>=1.3.0",  # RabbitMQ client
        "copilot-schema-validation>=0.1.0",  # Event models and validation
        "azure-servicebus>=7.11.0",  # Azure Service Bus client
        "azure-identity>=1.16.1",  # Azure authentication for managed identity
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pylint>=3.0.0",
            "mypy>=1.0.0",
        ],
    },
)
