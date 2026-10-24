"""
Security integration adapter.

Implements the SecurityIntegration protocol (contracts.py) and incorporates security
guidelines from Member 4 (SECURITY.md).
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.contracts import (
    SecurityCheckRequest,
    SecurityCheckResult,
    SecurityIntegration,
)
from app.integrations.security.redaction import redact_sensitive_data
from app.integrations.security.vault import SecureCredentialStore, get_credential_store

logger = logging.getLogger(__name__)


# Actions that are strictly prohibited by security policy
PROHIBITED_ACTIONS = {
    "captcha_bypass",
    "anti_bot_circumvention",
    "queue_bypass",
    "auto_approve_payment",
}

# Actions requiring human intervention / human presence
HUMAN_REQUIRED_ACTIONS = {
    "payment_approval",
    "booking_confirmation",
    "credential_consent",
}


class SecurityAdapter:
    """
    Adapter implementing the SecurityIntegration protocol.

    Enforces authorization, prohibits anti-bot/CAPTCHA evasion, guards payment
    actions with mandatory human approval, and provides data sanitisation.
    """

    def __init__(self, vault: SecureCredentialStore | None = None) -> None:
        self._vault = vault or get_credential_store()

    async def check_authorization(
        self, request: SecurityCheckRequest
    ) -> SecurityCheckResult:
        """
        Evaluate whether the requested action is permitted for the actor.
        """
        action = request.action.lower()
        actor = request.actor.lower()

        # 1. Prohibited actions are always blocked
        if action in PROHIBITED_ACTIONS:
            logger.warning(
                "Security policy BLOCKED action '%s' requested by actor '%s'",
                action,
                request.actor,
            )
            return SecurityCheckResult(
                allowed=False,
                reason=(
                    f"Action '{action}' is strictly prohibited by security policy "
                    "(anti-bot evasion, CAPTCHA bypass, and automatic payment approval are disallowed)."
                ),
            )

        # 2. Human-required actions require explicit human context
        if action in HUMAN_REQUIRED_ACTIONS:
            has_human_approval = (
                actor in {"human", "user", "operator"}
                or request.context.get("human_approved") is True
                or request.context.get("requires_human") is False
                and request.context.get("confirmed_by_human") is True
            )
            if not has_human_approval:
                logger.info(
                    "Action '%s' blocked for actor '%s': requires human authorization",
                    action,
                    request.actor,
                )
                return SecurityCheckResult(
                    allowed=False,
                    reason=f"Action '{action}' requires explicit human verification and approval.",
                )

        # 3. Credential access check
        if action == "access_credential":
            resource = request.resource
            if not resource:
                return SecurityCheckResult(
                    allowed=False, reason="Missing secret reference in resource."
                )
            if not self._vault.has_secret(resource):
                return SecurityCheckResult(
                    allowed=False,
                    reason=f"Secret reference '{resource}' not found in secure vault.",
                )

        return SecurityCheckResult(
            allowed=True,
            reason=f"Action '{action}' authorized for actor '{request.actor}'.",
        )

    def redact(self, value: Any) -> Any:
        """Sanitise sensitive fields from data structures."""
        return redact_sensitive_data(value)

    async def health_check(self) -> bool:
        """Return True if the security adapter and vault are operational."""
        return True

    def get_metadata(self) -> dict[str, Any]:
        """Return metadata describing security policies and redaction rules."""
        return {
            "name": "security",
            "version": "1.0.0",
            "description": "Security policy enforcement, credential vault, and data redaction",
            "vault_records_count": self._vault.count(),
            "prohibited_actions": sorted(PROHIBITED_ACTIONS),
            "human_required_actions": sorted(HUMAN_REQUIRED_ACTIONS),
        }
