"""Encryption utilities for PII protection.

Provides AES-256-GCM encryption for sensitive data fields like canonical_identifiers
and raw_response in cached data sources.

Usage:
    from elile.core.encryption import encrypt, decrypt, get_encryptor

    # Simple encryption/decryption
    ciphertext = encrypt(b"sensitive data")
    plaintext = decrypt(ciphertext)

    # Using Encryptor instance
    encryptor = get_encryptor()
    ciphertext = encryptor.encrypt(b"sensitive data")
    plaintext = encryptor.decrypt(ciphertext)

    # JSON field encryption
    encrypted = encrypt_json({"ssn": "123-45-6789"})
    decrypted = decrypt_json(encrypted)
"""

import base64
import hashlib
import json
import os
import secrets
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from elile.utils.exceptions import ElileError


class EncryptionError(ElileError):
    """Raised when encryption or decryption fails."""

    pass


class EncryptionKeyError(EncryptionError):
    """Raised when encryption key is missing or invalid."""

    pass


class DecryptionError(EncryptionError):
    """Raised when decryption fails (wrong key, corrupted data, etc.)."""

    pass


# Constants
NONCE_SIZE = 12  # 96 bits recommended for AES-GCM
KEY_SIZE = 32  # 256 bits for AES-256


class Encryptor:
    """AES-256-GCM encryptor for sensitive data.

    Uses authenticated encryption to provide both confidentiality and integrity.

    Attributes:
        _key: The 256-bit encryption key
        _aesgcm: The AESGCM cipher instance
    """

    def __init__(self, key: bytes):
        """Initialize encryptor with a key.

        Args:
            key: 32-byte (256-bit) encryption key

        Raises:
            EncryptionKeyError: If key is not 32 bytes
        """
        if len(key) != KEY_SIZE:
            raise EncryptionKeyError(
                f"Encryption key must be {KEY_SIZE} bytes, got {len(key)}"
            )
        self._key = key
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: bytes, associated_data: bytes | None = None) -> bytes:
        """Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt
            associated_data: Optional additional authenticated data (AAD)
                            This data is authenticated but not encrypted.

        Returns:
            Encrypted data in format: nonce (12 bytes) || ciphertext || tag (16 bytes)

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            nonce = secrets.token_bytes(NONCE_SIZE)
            ciphertext = self._aesgcm.encrypt(nonce, plaintext, associated_data)
            return nonce + ciphertext
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, ciphertext: bytes, associated_data: bytes | None = None) -> bytes:
        """Decrypt data encrypted with AES-256-GCM.

        Args:
            ciphertext: Data in format: nonce (12 bytes) || ciphertext || tag
            associated_data: Optional AAD that was used during encryption

        Returns:
            Decrypted plaintext

        Raises:
            DecryptionError: If decryption fails (wrong key, tampered data, etc.)
        """
        if len(ciphertext) < NONCE_SIZE + 16:  # nonce + minimum tag
            raise DecryptionError("Ciphertext too short")

        try:
            nonce = ciphertext[:NONCE_SIZE]
            actual_ciphertext = ciphertext[NONCE_SIZE:]
            return self._aesgcm.decrypt(nonce, actual_ciphertext, associated_data)
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}") from e

    def encrypt_string(self, plaintext: str, associated_data: bytes | None = None) -> str:
        """Encrypt a string and return base64-encoded result.

        Args:
            plaintext: String to encrypt
            associated_data: Optional AAD

        Returns:
            Base64-encoded encrypted string
        """
        encrypted = self.encrypt(plaintext.encode("utf-8"), associated_data)
        return base64.b64encode(encrypted).decode("ascii")

    def decrypt_string(self, ciphertext: str, associated_data: bytes | None = None) -> str:
        """Decrypt a base64-encoded string.

        Args:
            ciphertext: Base64-encoded encrypted string
            associated_data: Optional AAD

        Returns:
            Decrypted string
        """
        encrypted = base64.b64decode(ciphertext)
        decrypted = self.decrypt(encrypted, associated_data)
        return decrypted.decode("utf-8")

    def encrypt_json(self, data: Any, associated_data: bytes | None = None) -> str:
        """Encrypt JSON-serializable data.

        Args:
            data: JSON-serializable Python object
            associated_data: Optional AAD

        Returns:
            Base64-encoded encrypted JSON
        """
        json_str = json.dumps(data, separators=(",", ":"), sort_keys=True)
        return self.encrypt_string(json_str, associated_data)

    def decrypt_json(self, ciphertext: str, associated_data: bytes | None = None) -> Any:
        """Decrypt to JSON-serializable data.

        Args:
            ciphertext: Base64-encoded encrypted JSON
            associated_data: Optional AAD

        Returns:
            Decrypted Python object
        """
        json_str = self.decrypt_string(ciphertext, associated_data)
        return json.loads(json_str)


def derive_key_from_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Derive an encryption key from a password using PBKDF2.

    Args:
        password: Password to derive key from
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (key, salt) where key is 32 bytes
    """
    if salt is None:
        salt = secrets.token_bytes(16)

    # Use PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP 2023 recommendation)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=600_000,
        dklen=KEY_SIZE,
    )
    return key, salt


def generate_key() -> bytes:
    """Generate a new random 256-bit encryption key.

    Returns:
        32-byte random key suitable for AES-256
    """
    return secrets.token_bytes(KEY_SIZE)


def key_to_string(key: bytes) -> str:
    """Convert key to base64 string for storage.

    Args:
        key: 32-byte encryption key

    Returns:
        Base64-encoded key string
    """
    return base64.b64encode(key).decode("ascii")


def key_from_string(key_string: str) -> bytes:
    """Convert base64 string back to key bytes.

    Args:
        key_string: Base64-encoded key

    Returns:
        32-byte encryption key

    Raises:
        EncryptionKeyError: If key string is invalid
    """
    try:
        key = base64.b64decode(key_string)
        if len(key) != KEY_SIZE:
            raise EncryptionKeyError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")
        return key
    except Exception as e:
        raise EncryptionKeyError(f"Invalid key string: {e}") from e


# Global encryptor instance (lazy-loaded)
_encryptor: Encryptor | None = None


def get_encryptor() -> Encryptor:
    """Get the global encryptor instance.

    Loads the encryption key from settings on first call.

    Returns:
        Configured Encryptor instance

    Raises:
        EncryptionKeyError: If ENCRYPTION_KEY is not configured
    """
    global _encryptor

    if _encryptor is None:
        from elile.config.settings import get_settings

        settings = get_settings()
        if settings.ENCRYPTION_KEY is None:
            raise EncryptionKeyError(
                "ENCRYPTION_KEY is not configured. Set it in environment variables."
            )

        key = key_from_string(settings.ENCRYPTION_KEY.get_secret_value())
        _encryptor = Encryptor(key)

    return _encryptor


def reset_encryptor() -> None:
    """Reset the global encryptor (for testing)."""
    global _encryptor
    _encryptor = None


# Convenience functions using global encryptor


def encrypt(plaintext: bytes, associated_data: bytes | None = None) -> bytes:
    """Encrypt data using the global encryptor.

    Args:
        plaintext: Data to encrypt
        associated_data: Optional AAD

    Returns:
        Encrypted bytes
    """
    return get_encryptor().encrypt(plaintext, associated_data)


def decrypt(ciphertext: bytes, associated_data: bytes | None = None) -> bytes:
    """Decrypt data using the global encryptor.

    Args:
        ciphertext: Encrypted data
        associated_data: Optional AAD

    Returns:
        Decrypted bytes
    """
    return get_encryptor().decrypt(ciphertext, associated_data)


def encrypt_string(plaintext: str, associated_data: bytes | None = None) -> str:
    """Encrypt string using the global encryptor.

    Args:
        plaintext: String to encrypt
        associated_data: Optional AAD

    Returns:
        Base64-encoded encrypted string
    """
    return get_encryptor().encrypt_string(plaintext, associated_data)


def decrypt_string(ciphertext: str, associated_data: bytes | None = None) -> str:
    """Decrypt string using the global encryptor.

    Args:
        ciphertext: Base64-encoded encrypted string
        associated_data: Optional AAD

    Returns:
        Decrypted string
    """
    return get_encryptor().decrypt_string(ciphertext, associated_data)


def encrypt_json(data: Any, associated_data: bytes | None = None) -> str:
    """Encrypt JSON data using the global encryptor.

    Args:
        data: JSON-serializable Python object
        associated_data: Optional AAD

    Returns:
        Base64-encoded encrypted JSON
    """
    return get_encryptor().encrypt_json(data, associated_data)


def decrypt_json(ciphertext: str, associated_data: bytes | None = None) -> Any:
    """Decrypt JSON data using the global encryptor.

    Args:
        ciphertext: Base64-encoded encrypted JSON
        associated_data: Optional AAD

    Returns:
        Decrypted Python object
    """
    return get_encryptor().decrypt_json(ciphertext, associated_data)
