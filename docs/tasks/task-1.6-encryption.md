# Task 1.6: Encryption Utilities

## Overview

Implement AES-256-GCM encryption for PII data at rest (SSN, DOB, addresses) with key rotation support. Provides field-level encryption for sensitive identifiers stored in database JSON fields.

**Priority**: P0 | **Effort**: 1-2 days | **Status**: Not Started

## Dependencies

- External: `cryptography` library 41+
- Future: Task 12.2 (Vault integration for key management)

## Implementation Checklist

- [ ] Create encryption service with AES-256-GCM
- [ ] Implement key derivation from master key
- [ ] Build encrypt/decrypt functions with versioning
- [ ] Add SQLAlchemy custom type for encrypted fields
- [ ] Support key rotation (versioned keys)
- [ ] Write encryption/decryption tests
- [ ] Security audit for key handling

## Key Implementation

```python
# src/elile/core/encryption.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
import os

class EncryptionService:
    """AES-256-GCM encryption for PII data."""

    def __init__(self, master_key: bytes, key_version: int = 1):
        self.key_version = key_version
        self.cipher = AESGCM(master_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt string and return base64-encoded ciphertext with version."""
        if not plaintext:
            return plaintext

        nonce = os.urandom(12)
        ciphertext = self.cipher.encrypt(
            nonce,
            plaintext.encode('utf-8'),
            None
        )

        # Format: version:nonce:ciphertext (all base64)
        encrypted = f"{self.key_version}:{base64.b64encode(nonce).decode()}:{base64.b64encode(ciphertext).decode()}"
        return encrypted

    def decrypt(self, encrypted: str) -> str:
        """Decrypt base64-encoded ciphertext."""
        if not encrypted or ':' not in encrypted:
            return encrypted

        version, nonce_b64, ciphertext_b64 = encrypted.split(':', 2)
        nonce = base64.b64decode(nonce_b64)
        ciphertext = base64.b64decode(ciphertext_b64)

        plaintext = self.cipher.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')

# src/elile/models/types.py
from sqlalchemy.types import TypeDecorator, String

class EncryptedString(TypeDecorator):
    """SQLAlchemy type for encrypted string fields."""
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encrypt before storing."""
        if value is not None:
            return encryption_service.encrypt(value)
        return value

    def process_result_value(self, value, dialect):
        """Decrypt after loading."""
        if value is not None:
            return encryption_service.decrypt(value)
        return value

# Usage in models
class Entity(Base):
    ssn: Mapped[str] = mapped_column(EncryptedString(255), nullable=True)
```

## Testing Requirements

### Unit Tests
- Encrypt/decrypt roundtrip preserves data
- Empty/null values handled correctly
- Key versioning in encrypted output
- Different keys produce different ciphertext

### Security Tests
- Same plaintext produces different ciphertext (nonce randomization)
- Wrong key fails decryption
- Tampered ciphertext fails decryption
- Performance: encrypt/decrypt 1000 items <100ms

**Coverage Target**: 95%+ (security critical)

## Acceptance Criteria

- [ ] AES-256-GCM encryption implemented
- [ ] Encryption includes random nonce per operation
- [ ] Encrypted format includes key version
- [ ] SQLAlchemy EncryptedString type works transparently
- [ ] Key loaded from environment variable
- [ ] Encryption roundtrip tests pass
- [ ] Performance acceptable (<1ms per operation)

## Deliverables

- `src/elile/core/encryption.py`
- `src/elile/models/types.py` (EncryptedString)
- `tests/unit/test_encryption.py`
- `tests/security/test_encryption_security.py`
- `.env.example` (ENCRYPTION_KEY documentation)

## References

- Architecture: [07-compliance.md](../architecture/07-compliance.md) - Data security
- Future: Task 12.2 (Vault key management)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
