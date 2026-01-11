# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot-embedding package."""

from pathlib import Path

from setuptools import find_packages, setup

# Read the README file if it exists
this_directory = Path(__file__).parent
readme_path = this_directory / "README.md"
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")
else:
    long_description = "Shared embedding library for Copilot-for-Consensus microservices"

setup(
    name="copilot-embedding",
    version="0.1.0",
    author="Copilot-for-Consensus Contributors",
    description="Shared embedding provider library for Copilot-for-Consensus microservices",
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
        # Optional backend dependencies
        "sentencetransformers": [
            "sentence-transformers>=2.0.0",
        ],
        "openai": [
            "openai>=1.0.0",
        ],
        "huggingface": [
            "transformers>=4.0.0",
            "torch>=2.0.0",
        ],
        # All optional backends
        "all": [
            "sentence-transformers>=2.0.0",
            "openai>=1.0.0",
            "transformers>=4.0.0",
            "torch>=2.0.0",
        ],
    },
)
