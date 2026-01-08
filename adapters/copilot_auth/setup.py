# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-auth package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="copilot-auth",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="Identity and authentication abstraction layer for Copilot-for-Consensus microservices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Alan-Jowett/CoPilot-For-Consensus",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
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
        "fastapi>=0.109.0",  # For HTTP exception handling and request/response types
        "httpx>=0.27.0",  # For OIDC HTTP requests and middleware JWKS fetching
        "PyJWT>=2.8.0",  # For JWT token minting and validation
        "cryptography>=44.0.1",  # For JWT key management
        "pydantic>=2.4.0",  # For configuration and validation
        "starlette>=0.49.1",  # For middleware base classes
        "copilot-logging>=0.1.0",  # For logging utilities
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pylint>=3.0.0",
            "mypy>=1.0.0",
            "flask>=2.0.0",  # For examples
        ],
    },
)
