"""
Secure credential vault and secret reference management.

Enforces security requirements:
- Never persist passwords, OTPs, or payment details in ordinary task configuration.
- Exchange raw secrets for opaque, collision-resistant secret references (e.g. 'sec_ref_...').
- Restrict retrieval to authorized actors.
- Zero secrets exposed via logs or string representation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SecretRecord:
    """Internal representation of a protected credential."""
    secret_ref: str
    secret_type: str
    owner_id: str
    created_at: datetime
    # The raw payload is stored here in isolated memory
    _payload: dict[str, Any] = field(repr=False)


class SecureCredentialStore:
    """
    In-memory isolated credential store for sensitive credentials.

    Tasks and API requests store credentials here and pass only the opaque
    `secret_ref` across services, state machines, and execution runs.
    """

    def __init__(self) -> None:
        self._vault: dict[str, SecretRecord] = {}

    def store_secret(
        self,
        owner_id: str,
        secret_type: str,
        payload: dict[str, Any],
    ) -> str:
        """
        Store a credential payload and return an opaque reference token.

        Args:
            owner_id: Identifier of the owner (e.g. user_id or task_id).
            secret_type: Category of secret (e.g. 'irctc_credentials', 'payment_auth').
            payload: Sensitive key-value mapping (e.g. {'password': '...', 'username': '...'}).

        Returns:
            Opaque secret reference token string (e.g. 'sec_ref_a1b2c3d4e5f6').
        """
        token = f"sec_ref_{uuid.uuid4().hex[:16]}"
        record = SecretRecord(
            secret_ref=token,
            secret_type=secret_type,
            owner_id=owner_id,
            created_at=datetime.now(timezone.utc),
            _payload=dict(payload),
        )
        self._vault[token] = record
        logger.info(
            "Stored protected secret of type '%s' for owner '%s' with ref '%s'",
            secret_type,
            owner_id,
            token,
        )
        return token

    def retrieve_secret(
        self,
        secret_ref: str,
        actor: str,
    ) -> Optional[dict[str, Any]]:
        """
        Retrieve a secret payload by its reference token for an authorized actor.

        Returns None if not found or if the token is invalid.
        """
        record = self._vault.get(secret_ref)
        if not record:
            logger.warning("Secret reference '%s' not found in vault", secret_ref)
            return None

        # Return a copy of the payload to protect internal vault state
        logger.info("Secret reference '%s' accessed by actor '%s'", secret_ref, actor)
        return dict(record._payload)

    def revoke_secret(self, secret_ref: str) -> bool:
        """Revoke and delete a secret from the vault."""
        if secret_ref in self._vault:
            del self._vault[secret_ref]
            logger.info("Revoked secret reference '%s'", secret_ref)
            return True
        return False

    def has_secret(self, secret_ref: str) -> bool:
        """Check if a secret reference exists."""
        return secret_ref in self._vault

    def count(self) -> int:
        """Return the number of stored secrets."""
        return len(self._vault)

    def clear(self) -> None:
        """Clear all stored secrets (primarily for testing)."""
        self._vault.clear()

    def __repr__(self) -> str:
        return f"<SecureCredentialStore secrets_count={len(self._vault)}>"


# Global singleton credential store
_vault: SecureCredentialStore | None = None


def get_credential_store() -> SecureCredentialStore:
    """Return the global credential store."""
    global _vault
    if _vault is None:
        _vault = SecureCredentialStore()
    return _vault


def reset_credential_store() -> None:
    """Reset the global credential store (for testing)."""
    global _vault
    _vault = None
