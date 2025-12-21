# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-archive-store package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="copilot-archive-store",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="Shared archive storage library for Copilot-for-Consensus microservices",
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
        # Core dependencies (none for base implementation)
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "pylint>=3.0.0",
            "mypy>=1.0.0",
        ],
        "mongodb": [
            "pymongo>=4.6.3",  # MongoDB client for GridFS support
            "motor>=3.3.0",     # Async MongoDB driver
        ],
        "azure": [
            "azure-storage-blob>=12.19.0",  # Azure Blob Storage SDK
        ],
        "s3": [
            "boto3>=1.28.0",  # AWS S3 (future)
        ],
    },
)
