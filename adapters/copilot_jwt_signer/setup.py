# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Setup configuration for copilot_jwt_signer adapter."""

from setuptools import find_packages, setup

setup(
    name="copilot-jwt-signer",
    version="0.1.0",
    description="JWT signing adapter for Copilot-for-Consensus",
    author="Copilot-for-Consensus contributors",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "copilot-logging>=0.1.0",
        "cryptography>=46.0.3",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
        ],
        "azure": [
            "azure-keyvault-keys>=4.9.0",
            "azure-identity>=1.16.1",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
