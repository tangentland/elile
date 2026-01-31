"""Unit tests for encryption utilities."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from elile.core.encryption import (
    KEY_SIZE,
    NONCE_SIZE,
    DecryptionError,
    Encryptor,
    EncryptionError,
    EncryptionKeyError,
    derive_key_from_password,
    generate_key,
    get_encryptor,
    key_from_string,
    key_to_string,
    reset_encryptor,
)


class TestEncryptor:
    """Tests for Encryptor class."""

    @pytest.fixture
    def key(self) -> bytes:
        """Generate a test encryption key."""
        return generate_key()

    @pytest.fixture
    def encryptor(self, key: bytes) -> Encryptor:
        """Create an Encryptor instance."""
        return Encryptor(key)

    def test_init_with_valid_key(self, key: bytes):
        """Test encryptor initialization with valid 32-byte key."""
        encryptor = Encryptor(key)
        assert encryptor is not None

    def test_init_with_invalid_key_length(self):
        """Test encryptor rejects invalid key lengths."""
        with pytest.raises(EncryptionKeyError, match="must be 32 bytes"):
            Encryptor(b"short_key")

        with pytest.raises(EncryptionKeyError, match="must be 32 bytes"):
            Encryptor(b"x" * 64)

    def test_encrypt_decrypt_roundtrip(self, encryptor: Encryptor):
        """Test basic encryption/decryption roundtrip."""
        plaintext = b"Hello, World!"
        ciphertext = encryptor.encrypt(plaintext)

        assert ciphertext != plaintext
        assert len(ciphertext) >= NONCE_SIZE + len(plaintext) + 16  # nonce + data + tag

        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext(self, encryptor: Encryptor):
        """Test that encrypting same data twice produces different ciphertext (random nonce)."""
        plaintext = b"Same data"
        ciphertext1 = encryptor.encrypt(plaintext)
        ciphertext2 = encryptor.encrypt(plaintext)

        assert ciphertext1 != ciphertext2

    def test_decrypt_with_wrong_key_fails(self, key: bytes):
        """Test decryption with wrong key fails."""
        encryptor1 = Encryptor(key)
        encryptor2 = Encryptor(generate_key())

        ciphertext = encryptor1.encrypt(b"Secret data")

        with pytest.raises(DecryptionError):
            encryptor2.decrypt(ciphertext)

    def test_decrypt_with_tampered_data_fails(self, encryptor: Encryptor):
        """Test decryption fails if ciphertext is tampered."""
        ciphertext = encryptor.encrypt(b"Secret data")

        # Tamper with the ciphertext
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF
        tampered = bytes(tampered)

        with pytest.raises(DecryptionError):
            encryptor.decrypt(tampered)

    def test_decrypt_short_ciphertext_fails(self, encryptor: Encryptor):
        """Test decryption fails with too-short ciphertext."""
        with pytest.raises(DecryptionError, match="too short"):
            encryptor.decrypt(b"short")

    def test_encrypt_with_associated_data(self, encryptor: Encryptor):
        """Test encryption with additional authenticated data."""
        plaintext = b"Secret data"
        aad = b"context_info"

        ciphertext = encryptor.encrypt(plaintext, aad)
        decrypted = encryptor.decrypt(ciphertext, aad)

        assert decrypted == plaintext

    def test_decrypt_with_wrong_aad_fails(self, encryptor: Encryptor):
        """Test decryption fails with wrong AAD."""
        plaintext = b"Secret data"
        aad = b"correct_context"

        ciphertext = encryptor.encrypt(plaintext, aad)

        with pytest.raises(DecryptionError):
            encryptor.decrypt(ciphertext, b"wrong_context")

    def test_encrypt_empty_data(self, encryptor: Encryptor):
        """Test encrypting empty data."""
        ciphertext = encryptor.encrypt(b"")
        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == b""

    def test_encrypt_large_data(self, encryptor: Encryptor):
        """Test encrypting large data."""
        plaintext = b"x" * 1_000_000  # 1MB
        ciphertext = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext


class TestEncryptorStrings:
    """Tests for string encryption methods."""

    @pytest.fixture
    def encryptor(self) -> Encryptor:
        """Create an Encryptor instance."""
        return Encryptor(generate_key())

    def test_encrypt_string_roundtrip(self, encryptor: Encryptor):
        """Test string encryption roundtrip."""
        plaintext = "Hello, World! 🌍"
        ciphertext = encryptor.encrypt_string(plaintext)

        # Ciphertext should be base64 encoded
        assert isinstance(ciphertext, str)
        base64.b64decode(ciphertext)  # Should not raise

        decrypted = encryptor.decrypt_string(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_string_unicode(self, encryptor: Encryptor):
        """Test string encryption handles unicode."""
        plaintext = "日本語テスト 🎌"
        ciphertext = encryptor.encrypt_string(plaintext)
        decrypted = encryptor.decrypt_string(ciphertext)
        assert decrypted == plaintext


class TestEncryptorJSON:
    """Tests for JSON encryption methods."""

    @pytest.fixture
    def encryptor(self) -> Encryptor:
        """Create an Encryptor instance."""
        return Encryptor(generate_key())

    def test_encrypt_json_dict(self, encryptor: Encryptor):
        """Test JSON dict encryption."""
        data = {"name": "John", "ssn": "123-45-6789", "age": 30}
        ciphertext = encryptor.encrypt_json(data)
        decrypted = encryptor.decrypt_json(ciphertext)
        assert decrypted == data

    def test_encrypt_json_list(self, encryptor: Encryptor):
        """Test JSON list encryption."""
        data = [1, 2, 3, "four", {"five": 5}]
        ciphertext = encryptor.encrypt_json(data)
        decrypted = encryptor.decrypt_json(ciphertext)
        assert decrypted == data

    def test_encrypt_json_nested(self, encryptor: Encryptor):
        """Test nested JSON encryption."""
        data = {
            "level1": {
                "level2": {
                    "level3": [1, 2, {"deep": True}]
                }
            }
        }
        ciphertext = encryptor.encrypt_json(data)
        decrypted = encryptor.decrypt_json(ciphertext)
        assert decrypted == data

    def test_encrypt_json_null(self, encryptor: Encryptor):
        """Test JSON null value encryption."""
        data = None
        ciphertext = encryptor.encrypt_json(data)
        decrypted = encryptor.decrypt_json(ciphertext)
        assert decrypted is None


class TestKeyDerivation:
    """Tests for key derivation functions."""

    def test_derive_key_produces_correct_length(self):
        """Test derived key has correct length."""
        key, salt = derive_key_from_password("my_password")
        assert len(key) == KEY_SIZE
        assert len(salt) == 16

    def test_derive_key_same_password_same_salt(self):
        """Test same password and salt produce same key."""
        password = "test_password"
        key1, salt = derive_key_from_password(password)
        key2, _ = derive_key_from_password(password, salt)
        assert key1 == key2

    def test_derive_key_different_passwords(self):
        """Test different passwords produce different keys."""
        salt = b"x" * 16
        key1, _ = derive_key_from_password("password1", salt)
        key2, _ = derive_key_from_password("password2", salt)
        assert key1 != key2

    def test_derive_key_different_salts(self):
        """Test different salts produce different keys."""
        password = "same_password"
        key1, _ = derive_key_from_password(password, b"salt1" + b"\x00" * 11)
        key2, _ = derive_key_from_password(password, b"salt2" + b"\x00" * 11)
        assert key1 != key2


class TestKeyManagement:
    """Tests for key management functions."""

    def test_generate_key_length(self):
        """Test generated key has correct length."""
        key = generate_key()
        assert len(key) == KEY_SIZE

    def test_generate_key_randomness(self):
        """Test generated keys are random."""
        key1 = generate_key()
        key2 = generate_key()
        assert key1 != key2

    def test_key_to_string_roundtrip(self):
        """Test key serialization roundtrip."""
        key = generate_key()
        key_str = key_to_string(key)

        assert isinstance(key_str, str)
        assert len(key_str) == 44  # base64 of 32 bytes

        recovered_key = key_from_string(key_str)
        assert recovered_key == key

    def test_key_from_invalid_string(self):
        """Test key_from_string rejects invalid input."""
        with pytest.raises(EncryptionKeyError, match="Invalid key string"):
            key_from_string("not_valid_base64!!!")

    def test_key_from_wrong_length_string(self):
        """Test key_from_string rejects wrong-length key."""
        short_key = base64.b64encode(b"short").decode()
        with pytest.raises(EncryptionKeyError, match="must be 32 bytes"):
            key_from_string(short_key)


class TestGlobalEncryptor:
    """Tests for global encryptor functions."""

    def setup_method(self):
        """Reset global encryptor before each test."""
        reset_encryptor()

    def teardown_method(self):
        """Reset global encryptor after each test."""
        reset_encryptor()

    def test_get_encryptor_without_key_raises(self):
        """Test get_encryptor raises when key not configured."""
        with patch("elile.config.settings.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(ENCRYPTION_KEY=None)

            with pytest.raises(EncryptionKeyError, match="not configured"):
                get_encryptor()

    def test_get_encryptor_caches_instance(self):
        """Test get_encryptor returns same instance."""
        key = generate_key()
        key_str = key_to_string(key)

        with patch("elile.config.settings.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ENCRYPTION_KEY=MagicMock(get_secret_value=lambda: key_str)
            )

            encryptor1 = get_encryptor()
            encryptor2 = get_encryptor()

            assert encryptor1 is encryptor2

    def test_reset_encryptor_clears_cache(self):
        """Test reset_encryptor clears the cached instance."""
        key = generate_key()
        key_str = key_to_string(key)

        with patch("elile.config.settings.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ENCRYPTION_KEY=MagicMock(get_secret_value=lambda: key_str)
            )

            encryptor1 = get_encryptor()
            reset_encryptor()
            encryptor2 = get_encryptor()

            assert encryptor1 is not encryptor2
