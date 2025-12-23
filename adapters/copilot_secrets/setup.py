# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot_secrets adapter."""

from setuptools import setup, find_packages

setup(
    name="copilot-secrets",
    version="0.1.0",
    description="Secret management adapter for Copilot-for-Consensus",
    author="Copilot-for-Consensus contributors",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "copilot-logging>=0.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
        "azure": [
            "azure-keyvault-secrets>=4.7.0",
            "azure-identity>=1.12.0",
        ],
        # Future cloud provider extras:
        # "aws": ["boto3>=1.26.0"],
        # "gcp": ["google-cloud-secret-manager>=2.16.0"],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
    ],
)
