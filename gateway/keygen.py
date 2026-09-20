#!/usr/bin/env python3
"""Generate Ed25519 signing keypair for the Flood Alert Gateway.

This creates the cryptographic identity used to sign flood alerts.
The public key is hardcoded into the modified Android app so phones
can distinguish official flood warnings from normal chat messages.

Usage:
    python keygen.py [--output-dir ./keys] [--name flood_authority]
"""

import argparse
import hashlib
import os
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

def compute_sender_id(public_key_bytes: bytes) -> bytes:
    """Compute 8-byte sender ID matching BitChat derivation."""
    return hashlib.sha256(public_key_bytes).digest()[:8]

def main():
    parser = argparse.ArgumentParser(description="Generate Ed25519 keypair for Flood Alert Gateway")
    parser.add_argument("--output-dir", default="./keys", help="Directory to save keys")
    parser.add_argument("--name", default="flood_authority", help="Base name for key files")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    priv_path = os.path.join(args.output_dir, f"{args.name}.key")
    pub_hex_path = os.path.join(args.output_dir, f"{args.name}.pub")
    pub_pem_path = os.path.join(args.output_dir, f"{args.name}.pub.pem")

    if not args.force and (os.path.exists(priv_path) or os.path.exists(pub_hex_path) or os.path.exists(pub_pem_path)):
        print(f"Error: Key files already exist in {args.output_dir}. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    print("Generating Ed25519 keypair...")
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Get raw 32 bytes public key
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    # PEM format for private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # PEM format for public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    with open(priv_path, "wb") as f:
        f.write(private_pem)

    with open(pub_hex_path, "w") as f:
        f.write(public_key_bytes.hex())

    with open(pub_pem_path, "wb") as f:
        f.write(public_pem)

    sender_id = compute_sender_id(public_key_bytes)

    print(f"Key generation successful!")
    print(f"Public Key (hex): {public_key_bytes.hex()}")
    print(f"Sender ID (hex):  {sender_id.hex()}")
    print(f"Private Key saved to: {priv_path}")
    print(f"Public Key (hex) saved to: {pub_hex_path}")
    print(f"Public Key (PEM) saved to: {pub_pem_path}")
    print("\nRemember to update config.yaml with the Public Key and Sender ID hex strings!")

if __name__ == "__main__":
    main()
