#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Generate RSA key pair for JWT signing.

This script generates development RSA keys for the auth service.
Keys are generated locally and NOT committed to version control.
"""

import sys
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_keys(output_dir: Path, key_size: int = 2048) -> None:
    """Generate RSA key pair.
    
    Args:
        output_dir: Directory to save keys
        key_size: RSA key size in bits
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    private_key_path = output_dir / "dev_jwt_private.pem"
    public_key_path = output_dir / "dev_jwt_public.pem"

    # Check if keys already exist
    if private_key_path.exists() and public_key_path.exists():
        print(f"Keys already exist in {output_dir}")
        print("  - dev_jwt_private.pem")
        print("  - dev_jwt_public.pem")
        return

    print(f"Generating {key_size}-bit RSA key pair...")

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )

    # Write private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    private_key_path.write_bytes(private_pem)
    print(f"  ✓ Private key saved to {private_key_path}")

    # Write public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    public_key_path.write_bytes(public_pem)
    print(f"  ✓ Public key saved to {public_key_path}")

    print("\nKeys generated successfully!")
    print("\n⚠️  WARNING: These keys are for development only.")
    print("    For production, use Azure Key Vault or another secure key management system.")


if __name__ == "__main__":
    # Get script directory
    script_dir = Path(__file__).parent

    # Default output directory is now the secrets folder
    output_dir = script_dir.parent / "secrets"

    # Allow custom output directory via command line
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])

    generate_keys(output_dir)
