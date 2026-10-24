"""
Recovery and Resilience Package (Phase 6).
"""

from app.agent.recovery.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)
from app.agent.recovery.errors import (
    ActionValidationError,
    AuthenticationFailureError,
    BaseRecoveryError,
    CaptchaChallengeError,
    ClassifiedRecoveryError,
    ErrorCategory,
    HumanInterventionRequiredError,
    OperationTimeoutError,
    RateLimitError,
    ServiceUnavailableRecoveryError,
    SessionExpiredError,
    TransientNetworkError,
    UnknownOutcomeError,
    classify_exception,
)
from app.agent.recovery.idempotency import (
    CRITICAL_ACTIONS,
    IDEMPOTENT_ACTIONS,
    NON_IDEMPOTENT_ACTIONS,
    OperationOutcome,
    classify_outcome,
    is_action_critical,
    is_action_idempotent,
)
from app.agent.recovery.policy import (
    AsyncioSleeper,
    RecoveryAction,
    RecoveryDecision,
    RecoveryPolicy,
    Sleeper,
    ZeroSleeper,
)

__all__ = [
    # Errors & Taxonomy
    "ErrorCategory",
    "BaseRecoveryError",
    "ClassifiedRecoveryError",
    "TransientNetworkError",
    "OperationTimeoutError",
    "SessionExpiredError",
    "CaptchaChallengeError",
    "RateLimitError",
    "ServiceUnavailableRecoveryError",
    "ActionValidationError",
    "AuthenticationFailureError",
    "UnknownOutcomeError",
    "HumanInterventionRequiredError",
    "classify_exception",
    # Circuit Breaker
    "CircuitState",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitBreakerRegistry",
    "get_circuit_breaker_registry",
    # Idempotency
    "OperationOutcome",
    "IDEMPOTENT_ACTIONS",
    "NON_IDEMPOTENT_ACTIONS",
    "CRITICAL_ACTIONS",
    "is_action_idempotent",
    "is_action_critical",
    "classify_outcome",
    # Recovery Policy & Engine
    "Sleeper",
    "AsyncioSleeper",
    "ZeroSleeper",
    "RecoveryAction",
    "RecoveryDecision",
    "RecoveryPolicy",
]
