# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-summarization package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="copilot-summarization",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="LLM summarization adapter library with support for multiple providers",
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
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.10",
    install_requires=[
        "copilot-config>=0.1.0",  # For DriverConfig
        "python-dotenv>=1.0.0",
        "requests>=2.32.4",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pylint>=3.0.0",
            "mypy>=1.0.0",
        ],
        "openai": [
            "openai>=1.0.0",
        ],
        # All optional backends
        "all": [
            "openai>=1.0.0",
        ],
        # Test extra includes all drivers for factory tests
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "openai>=1.0.0",
        ],
    },
)
