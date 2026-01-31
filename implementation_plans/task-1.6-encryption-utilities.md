# Task 1.6: Encryption Utilities

## Overview

Implement AES-256-GCM encryption for protecting sensitive PII data stored in the database, such as canonical_identifiers and raw_response fields in cached data sources.

**Priority**: P0 (Critical)
**Dependencies**: None (can be done in parallel)

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/core/encryption.py` | Core encryption utilities |
| `src/elile/db/types/__init__.py` | SQLAlchemy types package |
| `src/elile/db/types/encrypted.py` | SQLAlchemy type decorators for encrypted fields |
| `tests/unit/test_encryption.py` | 29 unit tests |

## Component Design

### 1. Encryption Module (`src/elile/core/encryption.py`)

**Encryptor Class**:
```python
class Encryptor:
    def encrypt(self, plaintext: bytes, associated_data: bytes | None = None) -> bytes
    def decrypt(self, ciphertext: bytes, associated_data: bytes | None = None) -> bytes
    def encrypt_string(self, plaintext: str, associated_data: bytes | None = None) -> str
    def decrypt_string(self, ciphertext: str, associated_data: bytes | None = None) -> str
    def encrypt_json(self, data: Any, associated_data: bytes | None = None) -> str
    def decrypt_json(self, ciphertext: str, associated_data: bytes | None = None) -> Any
```

**Key Management Functions**:
```python
def generate_key() -> bytes  # Generate 256-bit random key
def key_to_string(key: bytes) -> str  # Base64 encode for storage
def key_from_string(key_string: str) -> bytes  # Decode from storage
def derive_key_from_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]
```

**Global Encryptor**:
```python
def get_encryptor() -> Encryptor  # Uses ENCRYPTION_KEY from settings
def reset_encryptor() -> None  # For testing
```

**Convenience Functions**:
```python
encrypt(), decrypt()
encrypt_string(), decrypt_string()
encrypt_json(), decrypt_json()
```

### 2. SQLAlchemy Type Decorators (`src/elile/db/types/encrypted.py`)

**EncryptedString**:
- Transparently encrypts/decrypts string columns
- Stores as base64-encoded text
- Graceful fallback for missing keys in development

**EncryptedJSON**:
- Transparently encrypts/decrypts JSON columns
- Preserves full JSON structure
- Graceful fallback for unencrypted data

### 3. Custom Exceptions

```python
class EncryptionError(ElileError):
    """Base encryption error."""

class EncryptionKeyError(EncryptionError):
    """Key missing or invalid."""

class DecryptionError(EncryptionError):
    """Decryption failed (wrong key, tampered data)."""
```

## Security Features

1. **AES-256-GCM**: Authenticated encryption providing confidentiality and integrity
2. **Random Nonces**: 96-bit random nonce per encryption (prevents replay attacks)
3. **Associated Data (AAD)**: Optional additional authenticated data for context binding
4. **PBKDF2 Key Derivation**: 600,000 iterations (OWASP 2023 recommendation)
5. **Secure Key Generation**: Uses Python's `secrets` module

## Ciphertext Format

```
[nonce: 12 bytes][ciphertext][auth tag: 16 bytes]
```

For string/JSON operations, the binary ciphertext is base64-encoded.

## Configuration

Uses existing `ENCRYPTION_KEY` setting from `Settings`:

```python
# In settings.py
ENCRYPTION_KEY: SecretStr | None = None
```

Generate a key with:
```python
from elile.core.encryption import generate_key, key_to_string
key = key_to_string(generate_key())
# Set as ENCRYPTION_KEY environment variable
```

## Usage Examples

### Direct Encryption

```python
from elile.core.encryption import encrypt_json, decrypt_json

# Encrypt sensitive data
encrypted = encrypt_json({"ssn": "123-45-6789"})

# Decrypt when needed
data = decrypt_json(encrypted)
```

### SQLAlchemy Models

```python
from elile.db.types import EncryptedString, EncryptedJSON

class SensitiveData(Base):
    __tablename__ = "sensitive"

    ssn = Column(EncryptedString())  # Automatically encrypted
    pii_data = Column(EncryptedJSON())  # JSON with encryption
```

## Test Summary

| Test Class | Tests | Description |
|------------|-------|-------------|
| TestEncryptor | 11 | Basic encrypt/decrypt operations |
| TestEncryptorStrings | 2 | String encryption with Unicode |
| TestEncryptorJSON | 4 | JSON structure preservation |
| TestKeyDerivation | 4 | Password-based key derivation |
| TestKeyManagement | 4 | Key generation and serialization |
| TestGlobalEncryptor | 3 | Global instance management |
| **Total** | **29** | |

## Verification

```bash
# Run tests
.venv/bin/pytest tests/unit/test_encryption.py -v

# Generate a key
python -c "from elile.core.encryption import generate_key, key_to_string; print(key_to_string(generate_key()))"
```

## Notes

- Encryption is optional in development (warns if key not set)
- Graceful handling of unencrypted data during key rotation
- Base64 encoding adds ~33% overhead to ciphertext size
- Thread-safe global encryptor with lazy initialization
