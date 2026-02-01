# Task 12.4: Secrets Management (Vault Integration)

## Overview

Implement secure secrets management using HashiCorp Vault or cloud provider secrets managers for API keys, database credentials, and encryption keys with rotation support.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.8: Configuration Management
- Task 1.6: Encryption Service

## Implementation

```python
# src/elile/secrets/vault_client.py
import hvac

class VaultSecretsManager:
    """Manages secrets via HashiCorp Vault."""

    def __init__(self, vault_url: str, token: str):
        self.client = hvac.Client(url=vault_url, token=token)

    async def get_secret(self, path: str) -> dict:
        """Retrieve secret from Vault."""
        secret = self.client.secrets.kv.v2.read_secret_version(path=path)
        return secret['data']['data']

    async def get_database_credentials(self) -> dict:
        """Get database credentials."""
        return await self.get_secret("elile/database/postgres")

    async def get_provider_api_key(self, provider: str) -> str:
        """Get provider API key."""
        secrets = await self.get_secret(f"elile/providers/{provider}")
        return secrets['api_key']

    async def rotate_secret(self, path: str, new_value: dict) -> None:
        """Rotate secret."""
        self.client.secrets.kv.v2.create_or_update_secret(
            path=path,
            secret=new_value
        )

# Integration with settings
class Settings(BaseSettings):
    """Settings with Vault integration."""

    vault_url: str = "https://vault.example.com"
    vault_token: SecretStr

    @cached_property
    def secrets_manager(self) -> VaultSecretsManager:
        return VaultSecretsManager(
            self.vault_url,
            self.vault_token.get_secret_value()
        )

    async def get_database_url(self) -> str:
        """Get database URL from Vault."""
        creds = await self.secrets_manager.get_database_credentials()
        return f"postgresql://{creds['username']}:{creds['password']}@{creds['host']}/elile"

    async def get_anthropic_key(self) -> str:
        """Get Anthropic API key from Vault."""
        return await self.secrets_manager.get_secret("elile/ai/anthropic")['api_key']
```

```python
# Startup: Load secrets from Vault
@app.on_event("startup")
async def load_secrets():
    """Load secrets from Vault on startup."""
    settings = get_settings()

    # Load database credentials
    db_creds = await settings.secrets_manager.get_database_credentials()
    settings._database_url = f"postgresql://{db_creds['username']}:{db_creds['password']}@{db_creds['host']}/elile"

    # Load provider keys
    for provider in ["sterling", "checkr", "world_check"]:
        key = await settings.secrets_manager.get_provider_api_key(provider)
        settings._provider_keys[provider] = key
```

## Acceptance Criteria

- [ ] Vault client implemented
- [ ] Database credentials loaded from Vault
- [ ] Provider API keys stored in Vault
- [ ] AI model API keys secured
- [ ] Secret rotation supported
- [ ] No secrets in environment variables or code
- [ ] Vault policies configured

## Deliverables

- `src/elile/secrets/vault_client.py`
- Vault policies configuration
- Secret rotation procedure documentation

## References

- Architecture: [07-compliance.md](../../docs/architecture/07-compliance.md) - Secrets

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
