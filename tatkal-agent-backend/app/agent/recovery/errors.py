"""
Standardized Error Taxonomy for Recovery and Resilience (Phase 6).

Categorizes exceptions into structured error types with explicit flags for:
- recoverability (can this be retried?)
- requires_human (does a human need to intervene?)
- is_uncertain_outcome (could the operation have partially/fully completed?)
- safe diagnostic context (strictly sanitised, zero secrets)
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, Optional

from app.core.exceptions import AppException
from app.integrations.security.redaction import redact_sensitive_data

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Core categories of the standardized error taxonomy."""
    TRANSIENT_NETWORK = "transient_network"
    TIMEOUT = "timeout"
    SESSION_EXPIRED = "session_expired"
    CAPTCHA_CHALLENGE = "captcha_challenge"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    UNKNOWN_OUTCOME = "unknown_outcome"
    HUMAN_INTERVENTION_REQUIRED = "human_intervention_required"
    UNCLASSIFIED = "unclassified"


class ClassifiedRecoveryError(AppException):
    """
    Standardized base exception for recovery and resilience decisions.

    Carries rich metadata allowing the central recovery engine to make
    deterministic retry, pause, or abort decisions.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        code: str,
        *,
        recoverable: bool = False,
        requires_human: bool = False,
        is_uncertain_outcome: bool = False,
        retry_after_seconds: Optional[float] = None,
        retry_guidance: Optional[str] = None,
        safe_context: Optional[dict[str, Any]] = None,
        status_code: int = 500,
    ) -> None:
        # Strictly sanitize context to prevent credential leakage
        sanitized_context = redact_sensitive_data(safe_context or {})

        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=sanitized_context,
        )
        self.code = code
        self.error_code = code
        self.category = category
        self.recoverable = recoverable
        self.requires_human = requires_human
        self.is_uncertain_outcome = is_uncertain_outcome
        self.retry_after_seconds = retry_after_seconds
        self.retry_guidance = retry_guidance
        self.safe_context = sanitized_context

    def to_dict(self) -> dict[str, Any]:
        """Return safe, structured representation for logs and API responses."""
        return {
            "error_code": self.code,
            "category": self.category.value,
            "message": self.message,
            "recoverable": self.recoverable,
            "requires_human": self.requires_human,
            "is_uncertain_outcome": self.is_uncertain_outcome,
            "retry_after_seconds": self.retry_after_seconds,
            "retry_guidance": self.retry_guidance,
            "context": self.safe_context,
        }


# Alias for backward/forward naming compatibility
BaseRecoveryError = ClassifiedRecoveryError


# ── Concrete Error Classes ──────────────────────────────────────────

class TransientNetworkError(ClassifiedRecoveryError):
    """Temporary connection reset, socket error, or network drop."""

    def __init__(
        self,
        message: str = "A transient network error occurred",
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.TRANSIENT_NETWORK,
            code="TRANSIENT_NETWORK_ERROR",
            recoverable=True,
            requires_human=False,
            is_uncertain_outcome=False,
            retry_guidance="Retry with exponential backoff",
            safe_context=safe_context,
            status_code=503,
        )


class OperationTimeoutError(ClassifiedRecoveryError):
    """Operation exceeded its configured deadline."""

    def __init__(
        self,
        message: str = "Operation timed out",
        *,
        is_uncertain_outcome: bool = False,
        recoverable: bool = True,
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.TIMEOUT,
            code="TIMEOUT_ERROR",
            recoverable=recoverable and not is_uncertain_outcome,
            requires_human=is_uncertain_outcome,
            is_uncertain_outcome=is_uncertain_outcome,
            retry_guidance=(
                "Safe to retry for idempotent read operations"
                if not is_uncertain_outcome
                else "Do not repeat blindly; verify state or request human intervention"
            ),
            safe_context=safe_context,
            status_code=504,
        )


class SessionExpiredError(ClassifiedRecoveryError):
    """Authenticated session has expired or requires re-authentication."""

    def __init__(
        self,
        message: str = "Session expired or authentication renewal required",
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.SESSION_EXPIRED,
            code="SESSION_EXPIRED",
            recoverable=False,
            requires_human=True,
            is_uncertain_outcome=False,
            retry_guidance="Pause for human re-authentication or credentials refresh",
            safe_context=safe_context,
            status_code=401,
        )


class CaptchaChallengeError(ClassifiedRecoveryError):
    """CAPTCHA or anti-bot challenge detected. Never automatically bypassed."""

    def __init__(
        self,
        message: str = "CAPTCHA or security challenge detected",
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.CAPTCHA_CHALLENGE,
            code="CAPTCHA_CHALLENGE",
            recoverable=False,
            requires_human=True,
            is_uncertain_outcome=False,
            retry_guidance="Automated bypass prohibited; human operator must solve challenge",
            safe_context=safe_context,
            status_code=403,
        )


class RateLimitError(ClassifiedRecoveryError):
    """Caller exceeded allowed request rate."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after_seconds: Optional[float] = None,
        recoverable: bool = True,
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMIT,
            code="RATE_LIMIT_EXCEEDED",
            recoverable=recoverable,
            requires_human=False,
            is_uncertain_outcome=False,
            retry_after_seconds=retry_after_seconds,
            retry_guidance=f"Wait {retry_after_seconds:.1f}s before retrying" if retry_after_seconds else "Backoff before retrying",
            safe_context=safe_context,
            status_code=429,
        )


class ServiceUnavailableRecoveryError(ClassifiedRecoveryError):
    """External dependency is temporarily unavailable or circuit is open."""

    def __init__(
        self,
        service_name: str = "Service",
        message: Optional[str] = None,
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message or f"Dependency '{service_name}' is currently unavailable",
            category=ErrorCategory.SERVICE_UNAVAILABLE,
            code="SERVICE_UNAVAILABLE",
            recoverable=True,
            requires_human=False,
            is_uncertain_outcome=False,
            retry_guidance="Wait for service recovery or circuit breaker cooldown",
            safe_context=safe_context,
            status_code=503,
        )


class ActionValidationError(ClassifiedRecoveryError):
    """Request or action parameters are invalid. Automatic retry is not permitted."""

    def __init__(
        self,
        message: str = "Action parameters are invalid",
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION_ERROR,
            code="VALIDATION_ERROR",
            recoverable=False,
            requires_human=False,
            is_uncertain_outcome=False,
            retry_guidance="Do not retry without correcting input arguments",
            safe_context=safe_context,
            status_code=422,
        )


class AuthenticationFailureError(ClassifiedRecoveryError):
    """Invalid credentials. Never retry blindly."""

    def __init__(
        self,
        message: str = "Authentication failed: invalid credentials",
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION_ERROR,
            code="AUTHENTICATION_FAILED",
            recoverable=False,
            requires_human=False,
            is_uncertain_outcome=False,
            retry_guidance="Do not retry with same credentials; requires valid human input",
            safe_context=safe_context,
            status_code=401,
        )


class UnknownOutcomeError(ClassifiedRecoveryError):
    """Operation outcome is ambiguous; side-effect may have completed."""

    def __init__(
        self,
        message: str = "Operation outcome is unknown; side effects cannot be verified",
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.UNKNOWN_OUTCOME,
            code="UNKNOWN_OUTCOME",
            recoverable=False,
            requires_human=True,
            is_uncertain_outcome=True,
            retry_guidance="Blind repetition prohibited; re-observe state or require human verification",
            safe_context=safe_context,
            status_code=409,
        )


class HumanInterventionRequiredError(ClassifiedRecoveryError):
    """Action requires explicit human approval or presence."""

    def __init__(
        self,
        reason: str = "Action requires human presence or authorization",
        safe_context: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=reason,
            category=ErrorCategory.HUMAN_INTERVENTION_REQUIRED,
            code="HUMAN_INTERVENTION_REQUIRED",
            recoverable=False,
            requires_human=True,
            is_uncertain_outcome=False,
            retry_guidance="Execution paused for human takeover",
            safe_context=safe_context,
            status_code=403,
        )


# ── Error Classifier ────────────────────────────────────────────────

def classify_exception(
    exc: Exception,
    *,
    action_type: str = "",
    is_idempotent: bool = True,
    safe_context: Optional[dict[str, Any]] = None,
) -> ClassifiedRecoveryError:
    """
    Classify an arbitrary exception into the standardized error taxonomy.

    Inspects exception types, error strings, and idempotency status.
    Guarantees no raw secrets are retained in output.
    """
    if isinstance(exc, ClassifiedRecoveryError):
        return exc

    msg = str(exc).lower()
    ctx = redact_sensitive_data(safe_context or {})

    # 1. CAPTCHA & Anti-bot challenges
    if "captcha" in msg or "challenge" in msg or "bot" in msg or "human_intervention" in msg:
        return CaptchaChallengeError(message=f"Challenge screen detected: {exc}", safe_context=ctx)

    # 2. Session expiration / Re-auth
    if "session" in msg and ("expire" in msg or "timeout" in msg or "invalid" in msg):
        return SessionExpiredError(message=f"Session expired: {exc}", safe_context=ctx)

    # 3. Rate limiting
    if "rate limit" in msg or "429" in msg or "too many requests" in msg:
        retry_after = None
        match = re.search(r"retry-after[:\s=]+(\d+(?:\.\d+)?)", msg)
        if match:
            try:
                retry_after = float(match.group(1))
            except ValueError:
                pass
        return RateLimitError(
            message=f"Rate limit encountered: {exc}",
            retry_after_seconds=retry_after,
            safe_context=ctx,
        )

    # 4. Authentication errors
    if "unauthorized" in msg or "invalid password" in msg or "login failed" in msg:
        return AuthenticationFailureError(message=f"Authentication error: {exc}", safe_context=ctx)

    # 5. Timeouts
    if "timeout" in msg or isinstance(exc, TimeoutError):
        if not is_idempotent:
            return UnknownOutcomeError(
                message=f"Timeout occurred during non-idempotent action '{action_type}': {exc}",
                safe_context=ctx,
            )
        return OperationTimeoutError(message=f"Timeout during action '{action_type}': {exc}", safe_context=ctx)

    # 6. Transient network connection errors
    network_signatures = (
        "connection reset",
        "connection refused",
        "broken pipe",
        "network",
        "socket",
        "dns",
        "econnreset",
        "econnrefused",
        "disconnected",
    )
    if any(sig in msg for sig in network_signatures):
        if not is_idempotent:
            return UnknownOutcomeError(
                message=f"Connection dropped during non-idempotent action '{action_type}': {exc}",
                safe_context=ctx,
            )
        return TransientNetworkError(message=f"Transient network failure: {exc}", safe_context=ctx)

    # 7. Validation errors
    if "validation" in msg or "invalid argument" in msg or isinstance(exc, (ValueError, TypeError)):
        return ActionValidationError(message=f"Validation error: {exc}", safe_context=ctx)

    # 8. Service unavailable
    if "503" in msg or "service unavailable" in msg:
        return ServiceUnavailableRecoveryError(message=f"Service unavailable: {exc}", safe_context=ctx)

    # 9. Fallback unclassified
    return ClassifiedRecoveryError(
        message=f"Unclassified failure during '{action_type}': {exc}",
        category=ErrorCategory.UNCLASSIFIED,
        code="UNCLASSIFIED_ERROR",
        recoverable=False,
        requires_human=False,
        is_uncertain_outcome=not is_idempotent,
        safe_context=ctx,
        status_code=500,
    )
