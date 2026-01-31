"""SQLAlchemy type decorators for encrypted fields.

Provides transparent encryption/decryption for database columns storing
sensitive PII data.

Usage:
    from elile.db.types.encrypted import EncryptedString, EncryptedJSON

    class SensitiveModel(Base):
        __tablename__ = "sensitive"

        ssn = Column(EncryptedString())  # Encrypted string
        pii_data = Column(EncryptedJSON())  # Encrypted JSON
"""

from typing import Any

from sqlalchemy import Text, TypeDecorator

from elile.core.encryption import (
    DecryptionError,
    EncryptionKeyError,
    decrypt_json,
    decrypt_string,
    encrypt_json,
    encrypt_string,
)


class EncryptedString(TypeDecorator):
    """SQLAlchemy type that transparently encrypts/decrypts string values.

    Stores encrypted data as base64-encoded text in the database.
    Automatically encrypts on write and decrypts on read.

    Example:
        class User(Base):
            ssn = Column(EncryptedString())

        user = User(ssn="123-45-6789")  # Stored encrypted
        print(user.ssn)  # Returns "123-45-6789" (decrypted)
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        """Encrypt value before storing in database."""
        if value is None:
            return None
        try:
            return encrypt_string(value)
        except EncryptionKeyError:
            # If encryption is not configured, store as plaintext in development
            # This should be caught during startup in production
            import logging

            logging.warning(
                "ENCRYPTION_KEY not configured. Storing sensitive data unencrypted."
            )
            return value

    def process_result_value(self, value: str | None, dialect) -> str | None:
        """Decrypt value when reading from database."""
        if value is None:
            return None
        try:
            return decrypt_string(value)
        except (DecryptionError, EncryptionKeyError):
            # If decryption fails, assume data was stored unencrypted
            # (development mode or key rotation scenario)
            return value


class EncryptedJSON(TypeDecorator):
    """SQLAlchemy type that transparently encrypts/decrypts JSON values.

    Stores encrypted JSON as base64-encoded text in the database.
    Automatically encrypts on write and decrypts on read.

    Example:
        class DataSource(Base):
            raw_response = Column(EncryptedJSON())

        source = DataSource(raw_response={"data": "sensitive"})  # Stored encrypted
        print(source.raw_response)  # Returns {"data": "sensitive"} (decrypted)
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect) -> str | None:
        """Encrypt JSON value before storing in database."""
        if value is None:
            return None
        try:
            return encrypt_json(value)
        except EncryptionKeyError:
            # If encryption is not configured, store as plaintext JSON
            import json
            import logging

            logging.warning(
                "ENCRYPTION_KEY not configured. Storing sensitive JSON unencrypted."
            )
            return json.dumps(value)

    def process_result_value(self, value: str | None, dialect) -> Any | None:
        """Decrypt JSON value when reading from database."""
        if value is None:
            return None
        try:
            return decrypt_json(value)
        except (DecryptionError, EncryptionKeyError):
            # If decryption fails, try parsing as plain JSON
            import json

            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
