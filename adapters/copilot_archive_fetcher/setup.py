# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-archive-fetcher package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="copilot-archive-fetcher",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="Archive fetcher adapter for multiple sources (rsync, HTTP, local, IMAP) for Copilot-for-Consensus",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Alan-Jowett/CoPilot-For-Consensus",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=[
        # imapclient is optional, imported conditionally
    ],
    extras_require={
        "imap": [
            "imapclient>=2.3.0",
        ],
        "http": [
            "requests>=2.28.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
            "pylint>=3.0.0",
            "mypy>=1.0.0",
            "imapclient>=2.3.0",
            "requests>=2.28.0",
        ],
    },
)
