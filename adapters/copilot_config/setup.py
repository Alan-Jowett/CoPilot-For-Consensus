# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-config package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="copilot-config",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="Shared configuration management library for Copilot-for-Consensus microservices",
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
        # No external dependencies - uses stdlib only
    ],
    extras_require={
        "secrets": [
            "copilot-secrets>=0.1.0",
        ],
        "storage": [
            "copilot-storage>=0.1.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pylint>=3.0.0",
            "mypy>=1.0.0",
        ],
    },
)
