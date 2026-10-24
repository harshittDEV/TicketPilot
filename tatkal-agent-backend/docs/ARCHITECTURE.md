# Architecture

## Overview

The Tatkal Agent Backend follows a **modular monolith** architecture — a single deployable application with clearly separated internal modules that communicate through well-defined interfaces.

This approach was chosen because:

1. **Simplicity**: No inter-service networking, no distributed tracing needed, no deployment orchestration.
2. **Speed**: A hackathon demands fast iteration. A monolith is faster to develop, test, and debug.
3. **Extractability**: Clean internal boundaries mean modules can be extracted into services later if needed.

---

## Architecture Layers

```
┌──────────────────────────────────────────────────────┐
│                    API Layer                         │
│         FastAPI routers under /api/v1                │
├──────────────────────────────────────────────────────┤
│                  Service Layer                       │
│       Business logic and orchestration               │
├──────────────────────────────────────────────────────┤
│               Integration Layer                      │
│    Contracts (Protocols) + Registry (DI)             │
├──────────────────────────────────────────────────────┤
│                 Database Layer                        │
│        SQLAlchemy 2.x + SQLite                       │
├──────────────────────────────────────────────────────┤
│                   Core Layer                         │
│    Config, Logging, Exceptions                       │
└──────────────────────────────────────────────────────┘
```

### API Layer (`app/api/`)

- FastAPI routers mounted under `/api/v1`.
- Thin handlers — validate input, delegate to services, return responses.
- No business logic in route handlers.
- Consistent response envelopes via `ApiResponse` / `ApiErrorResponse`.

### Service Layer (`app/services/`)

- Business logic lives here (future phases).
- Services consume database sessions and integration adapters.
- Services are injected via FastAPI's `Depends()`.

### Integration Layer (`app/integrations/`)

- **Contracts** (`contracts.py`): Python `Protocol` classes defining typed interfaces for each teammate's module.
- **Registry** (`registry.py`): A simple dependency-injection container where adapters are registered by name and retrieved by consumers.
- External implementations wrap around these protocols — the core backend never imports teammate code directly.

### Database Layer (`app/database/`)

- **Engine**: Singleton `create_engine()` with connection pooling.
- **Session Factory**: `sessionmaker` bound to the engine.
- **Dependency**: `get_db()` generator ensures one session per request, always closed.
- **Base**: `DeclarativeBase` from which all ORM models inherit.
- **Init**: `create_all()` for development; Alembic migrations planned for later.

### Core Layer (`app/core/`)

- **Config**: `pydantic-settings` with environment variable binding, validation, and development defaults.
- **Logging**: Structured formatter with timestamps, levels, and logger names.
- **Exceptions**: Hierarchy of typed exceptions mapped to HTTP status codes via centralised handlers.

---

## Dependency Injection

FastAPI's built-in `Depends()` is the primary DI mechanism:

- `get_db()` → database sessions
- `get_settings()` → configuration
- `get_registry()` → integration adapters

The `IntegrationRegistry` adds a second layer specifically for teammate modules, which are registered at startup and retrieved by name.

---

## Agent Orchestration Architecture (Phase 3)

The generic agent orchestration core (`app/agent/`) coordinates task execution using a provider-agnostic, structured loop:

```
┌────────────────────────────────────────────────────────┐
│                   AgentOrchestrator                    │
│                                                        │
│   ┌───────────┐     ┌───────────────┐     ┌─────────┐  │
│   │  Observer │ ──► │ LLM / Planner │ ──► │  Tools  │  │
│   └───────────┘     └───────────────┘     └─────────┘  │
│         ▲                                       │      │
│         │          ┌───────────────┐            │      │
│         └───────── │   Verifier    │ ◄──────────┘      │
│                    └───────────────┘                   │
└────────────────────────────────────────────────────────┘
```

1. **Observer** (`app/agent/observer.py`): Captures initial state, context, and post-action outcome observations.
2. **Planner / LLM** (`app/agent/llm/base.py`): Receives context and produces structured plans (`Plan`, `PlanStep`, `ToolCallRequest`).
3. **Tool Executor** (`app/agent/tool_executor.py`): Validates tool call schema and resolves tools through `IntegrationRegistry` (`AgentToolIntegration`).
4. **Verifier** (`app/agent/verifier.py`): Explicit verification layer evaluating outcomes. Failed verification prevents false successes.
5. **Run State Machine** (`app/services/run_state_machine.py`): Manages execution run lifecycle independently from tasks.

---

## How the System Evolves Without a Rewrite

| Change                          | Impact                                                |
|---------------------------------|-------------------------------------------------------|
| Add new API endpoints           | New router file, include in `api_v1_router`           |
| Add database models             | New model file, import in `init_db.py`                |
| Integrate a teammate module     | Implement Protocol, register adapter in registry      |
| Add agent orchestration         | New service module, consumes existing interfaces      |
| Switch database                 | Change `DATABASE_URL` env var                         |
| Add authentication              | New middleware + dependency, no core changes          |
| Extract a microservice          | Move module behind HTTP/gRPC, replace adapter         |

---

## Schema Migration Strategy

**Phase 1**: `Base.metadata.create_all()` — sufficient for development.

**Phase 2+**: Introduce Alembic when the schema stabilises. The migration path:

1. `pip install alembic`
2. `alembic init alembic`
3. Configure `alembic.ini` to use `DATABASE_URL` from settings.
4. Generate initial migration from existing models.
5. Replace `create_all()` with `alembic upgrade head` in `init_db.py`.

---

## Task Management (Phase 2)

### Task Model (`app/models/task.py`)

The `Task` ORM model stores generic task state:

| Column          | Type              | Purpose                                      |
|-----------------|-------------------|----------------------------------------------|
| `id`            | String(36) PK     | UUID4 identifier                             |
| `task_type`     | String(100)       | Generic category (e.g. `train_booking`)      |
| `status`        | String(50)        | Current lifecycle state (managed by SM)       |
| `configuration` | JSON              | Task-specific parameters                     |
| `version`       | Integer           | Optimistic concurrency control               |
| `created_at`    | DateTime(tz)      | Creation timestamp (UTC)                     |
| `started_at`    | DateTime(tz)      | When execution began (nullable)              |
| `completed_at`  | DateTime(tz)      | Terminal success timestamp (nullable)        |
| `cancelled_at`  | DateTime(tz)      | Cancellation timestamp (nullable)            |

### Task State Machine (`app/services/task_state_machine.py`)

All state transitions are validated centrally. The transition policy:

```
CREATED → READY, CANCELLED, FAILED
READY → RUNNING, CANCELLED, FAILED
RUNNING → RECOVERING, AWAITING_HUMAN, AWAITING_PAYMENT_APPROVAL, VERIFYING, COMPLETED, FAILED, CANCELLED
RECOVERING → RUNNING, AWAITING_HUMAN, FAILED, CANCELLED
AWAITING_HUMAN → RUNNING, FAILED, CANCELLED
AWAITING_PAYMENT_APPROVAL → RUNNING, FAILED, CANCELLED
VERIFYING → COMPLETED, RECOVERING, AWAITING_HUMAN, FAILED
COMPLETED → (terminal)
FAILED → (terminal)
CANCELLED → (terminal)
```

### Service & Repository Layers

- **TaskRepository** (`app/services/task_repository.py`): Pure data access — queries, pagination, transaction helpers.
- **TaskService** (`app/services/task_service.py`): Business rules — creation, transition validation, optimistic locking, cancellation.
- **API handlers** (`app/api/tasks.py`): Thin — validate input, delegate to service, return response.

### Database Transaction Boundaries

- Each API request gets one database session via `get_db()`.
- The service calls `flush()` for in-transaction visibility and `commit()` on success.
- On exception, the session is rolled back by the `finally` block in `get_db()`.
- Optimistic locking: the `version` column is checked before state transitions; stale updates raise `TaskStateConflictError`.

---

## Execution Run Management (Phase 3)

### ExecutionRun Model (`app/models/execution_run.py`)

The `ExecutionRun` ORM model tracks individual attempts to execute a task:

| Column         | Type          | Purpose                                        |
|----------------|---------------|------------------------------------------------|
| `id`           | String(36) PK | UUID4 identifier                               |
| `task_id`      | String(36) FK | References `tasks.id` (foreign key)            |
| `status`       | String(50)    | Current lifecycle state (`RunStatus`)          |
| `step_count`   | Integer       | Completed step counter                         |
| `max_steps`    | Integer       | Configured ceiling for loop steps              |
| `error_detail` | String(1000)  | Failure summary (nullable)                     |
| `version`      | Integer       | Optimistic concurrency control                 |
| `created_at`   | DateTime(tz)  | Enqueue/creation timestamp (UTC)               |
| `started_at`   | DateTime(tz)  | Execution start timestamp                      |
| `completed_at` | DateTime(tz)  | Terminal success timestamp                     |
| `failed_at`    | DateTime(tz)  | Terminal failure timestamp                     |
| `cancelled_at` | DateTime(tz)  | Cancellation timestamp                         |

### Run State Machine (`app/services/run_state_machine.py`)

Run transitions are strictly validated and separated from Task transitions:

```
CREATED → STARTING, CANCELLED
STARTING → RUNNING, FAILED, CANCELLED
RUNNING → PAUSED, VERIFYING, COMPLETED, FAILED, CANCELLED
PAUSED → RUNNING, CANCELLED
VERIFYING → COMPLETED, FAILED, CANCELLED
COMPLETED → (terminal)
FAILED → (terminal)
CANCELLED → (terminal)
```

### Single Active Run Policy

To prevent race conditions, the system enforces that a Task cannot have multiple concurrent active runs (`STARTING`, `RUNNING`, `PAUSED`, `VERIFYING`). Attempting to start a new run while another is active raises `DuplicateActiveRunError`.

### Orchestrator Integration

1. The orchestrator receives an initialized `ExecutionRun`.
2. It advances run status to `RUNNING` via `RunStateMachine`.
3. In each loop iteration, it:
   - Checks checkpoint flags (`paused`, `cancelled`).
   - Gathers observations through `Observer`.
   - Obtains next plan steps through `StructuredPlanner`.
   - Validates and runs tools through `ToolExecutor`.
   - Verifies intermediate and final outcomes via `Verifier`.
5. On terminal exit, it updates the run to `COMPLETED`, `FAILED`, or `CANCELLED`.

---

## Tool Adapters & Skill System (Phase 4)

Phase 4 introduces modular computer-use tool adapters and declarative skill definitions.

### Tool Adapter Architecture

Tool adapters implement the `AgentToolIntegration` protocol via the common base class `BaseToolAdapter`:

```
┌──────────────────────────────────────────────────────────────────┐
│                       IntegrationRegistry                        │
│   (register_tool, get_tool, list_tools, check_tool_health)       │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
┌─────────────────────────────┐             ┌─────────────────────┐
│     BrowserToolAdapter      │             │ DesktopToolAdapter  │
│  (navigate, click, type...) │             │ (screenshot, click) │
└──────────────┬──────────────┘             └──────────┬──────────┘
               │                                       │
        BrowserDriver                            DesktopDriver
    ┌──────────┴──────────┐                 ┌──────────┴──────────┐
    ▼                     ▼                 ▼                     ▼
MockBrowserDriver  PlaywrightDriver   MockDesktopDriver    MacDesktopDriver
 (in-memory test)  (live headless)     (in-memory test)    (OS-level Aqua)
```

1. **Decoupled Drivers**: Concrete adapters separate action dispatch from the driver implementation. `MockBrowserDriver` and `MockDesktopDriver` allow 100% of the test suite to execute without launching browsers or windowing sessions.
2. **Standardized Status Reporting**: Outcomes map directly to `ToolActionStatus`: `SUCCESS`, `INVALID_ARGUMENTS`, `UNKNOWN_TOOL`, `TOOL_UNAVAILABLE`, `TIMEOUT`, `RECOVERABLE_FAILURE`, `NON_RECOVERABLE_FAILURE`, `HUMAN_INTERVENTION_REQUIRED`.
3. **Security Barrier & Challenge Detection**: When the browser encounters authentication barriers, CAPTCHAs, or Cloudflare challenges, it returns `HUMAN_INTERVENTION_REQUIRED`, prompting the agent or task to pause for human takeover rather than attempting evasion.

### Desktop Automation Prerequisites (macOS)

The desktop adapter (`app/tools/desktop/`) is disabled by default for safety (`ENABLE_DESKTOP_ADAPTER=false`). When enabled, it enforces macOS platform prerequisites:
- Active Aqua / WindowServer GUI session (non-headless).
- **Accessibility Permissions** granted under *System Settings → Privacy & Security → Accessibility*.
- **Screen Recording Permissions** granted under *System Settings → Privacy & Security → Screen Recording*.
If unverified or denied, it returns `TOOL_UNAVAILABLE` or `HUMAN_INTERVENTION_REQUIRED` instead of crashing.

### Artifact Management (`app/tools/artifacts.py`)

- **Storage**: Binary screenshots are persisted under `artifacts/screenshots/` with collision-resistant UUID and timestamp naming (`screen_<run_id>_<timestamp>_<uuid>.png`).
- **Path Traversal Protection**: All reference resolution (`artifact://screenshots/...`) is verified to reside strictly within `ARTIFACT_DIR`.
- **Bounding**: Single screenshots are capped at 5 MB (`MAX_ARTIFACT_SIZE_BYTES`).
- **Redaction Limitation**: Automated visual pixel blurring/redaction is **not** implemented in Phase 4. Screenshots reflect raw rendered states. Sensitive financial credentials (CVVs, passwords) must not be entered during capture.

### Declarative Skill System (`app/skills/`)

Skills allow the agent to execute predefined multi-step workflows loaded from YAML files under `app/skills/definitions/`:

```yaml
name: browser_inspection
version: 1.0.0
description: "Safe demonstration skill that inspects title and text, capturing a screenshot"
required_inputs:
  - name: test_url
    type: string
    default: "https://example.com"
allowed_tools:
  - browser
steps:
  - step_id: step_1_navigate
    tool_name: browser
    action_type: navigate
    parameters:
      url: "{{ inputs.test_url }}"
  - step_id: step_2_screenshot
    tool_name: browser
    action_type: screenshot
```

- **Validation**: Schema validated via `SkillDefinition` (Pydantic v2).
- **Security**: No arbitrary Python code is permitted in skill files; steps may only invoke declared, registered tools.
- **Execution**: `SkillExecutor` executes steps sequentially, performs template parameter substitution (`{{ inputs.var }}`), stops upon step failure or human intervention checkpoint, and returns a structured `SkillExecutionResult`.

---

## Phase 5: Teammate Module Integration Architecture

In Phase 5, existing implementations provided by teammates were adapted and integrated into the backend behind standardized integration protocols:

```
                            ┌────────────────────────┐
                            │    User / REST API     │
                            └───────────┬────────────┘
                                        │
                                        ▼
                            ┌────────────────────────┐
                            │  IntegrationRegistry   │
                            └───────────┬────────────┘
         ┌──────────────────┬───────────┴───────────┬──────────────────┐
         ▼                  ▼                       ▼                  ▼
┌──────────────────┐┌─────────────────┐   ┌──────────────────┐┌──────────────────┐
│ TatkalScheduler  ││ TrainComparison │   │ SecurityAdapter  ││BookingAssistance │
│     Adapter      ││     Adapter     │   │ & CredentialVault││     Adapter      │
└────────┬─────────┘└────────┬────────┘   └────────┬─────────┘└────────┬─────────┘
         │                   │                     │                   │
         ▼                   ▼                     ▼                   ▼
  Member 3 Logic      Member 4 Logic        Member 4 Logic      Safe Verification
  - 10:00/11:00 IST   - Roorkee->Haridwar   - Redaction engine    Checkpoints
  - Day prior calc    - Fare sorting        - Prohibited policies - Human CAPTCHA/
  - Pre-alert window  - Duration sorting    - Opaque vault refs     payment handoff
  - 10m recovery      - Verified avail only
```

### Module Responsibilities:

1. **Scheduler (`app/integrations/scheduler/`)**:
   - Implements `SchedulerIntegration` protocol.
   - Embeds Member 3's Tatkal opening rules (`CLASS_TIMES` for AC at 10:00 IST and non-AC at 11:00 IST).
   - Explicit timezone calculations (`Asia/Kolkata` IST converted accurately to UTC).
   - Duplicate schedule prevention via deduplication keys.
   - Recovery window: preserves and executes missed alerts if within 10 minutes past opening; marks older missed alerts expired without replaying.

2. **Train Comparison (`app/integrations/train_comparison/`)**:
   - Implements `TrainComparisonIntegration` protocol.
   - Embeds Member 4's `trainRanker.js` ranking algorithm.
   - Route and quota verification (`origin`, `destination`, `quota="TATKAL"`).
   - Verifies `eligible=True` and `availabilityVerified=True`.
   - Deterministic sorting: 1) `totalFare` asc, 2) `durationMinutes` asc, 3) `trainNumber` alphanumeric asc.

3. **Security and Credential Storage (`app/integrations/security/`)**:
   - Implements `SecurityIntegration` protocol.
   - Sensitive data redaction (`redact_sensitive_data`): recursively sanitizes passwords, OTPs, CVVs, card numbers, and passenger names with `[REDACTED]`.
   - `SecureCredentialStore`: in-memory isolated vault that exchanges raw credentials for opaque references (`sec_ref_...`), ensuring secrets never enter SQLite configuration or unredacted API logs.
   - Policy gate: blocks `captcha_bypass`, `anti_bot_circumvention`, and `auto_approve_payment`. Mandatory human presence required for `payment_approval`.

4. **Booking Assistance (`app/integrations/booking/`)**:
   - Implements `BookingAssistanceIntegration` protocol.
   - Generates validated booking plans from `BookingContext` (`task_id`, `passenger_count`, `journey_details`).
   - Strictly enforces Phase 5 safety: unattended booking and automated payment execution are disabled, returning `AWAITING_HUMAN_INTERVENTION` with structured checkpoints.

---

## Recovery & Resilience Engine (Phase 6)

Phase 6 implements a centralized, deterministic recovery engine (`app/agent/recovery/`) ensuring bounded retries, circuit breaking, idempotency guardrails, and graceful human handoff.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Agent Orchestrator Loop                         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ executes step
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                             ToolExecutor                               │
│  ┌───────────────────────┐                 ┌────────────────────────┐  │
│  │   Circuit Breaker     │                 │     Recovery Policy    │  │
│  │ (CLOSED/OPEN/HALF_OPEN)│                │   (bounded backoff)    │  │
│  └───────────┬───────────┘                 └───────────┬────────────┘  │
│              │ check health                            │ eval decision │
│              ▼                                         ▼               │
│  ┌───────────────────────┐                 ┌────────────────────────┐  │
│  │  External Adapter /   │──── timeout ───►│   Idempotency Filter   │  │
│  │     Integration       │    or error     │(idempotent vs uncertain)│ │
│  └───────────────────────┘                 └───────────┬────────────┘  │
└────────────────────────────────────────────────────────┼───────────────┘
                                                         │
             ┌───────────────────────────────────────────┴───────────────────────────────────────────┐
             ▼                                           ▼                                           ▼
   ┌───────────────────┐                       ┌───────────────────┐                       ┌───────────────────┐
   │       RETRY       │                       │  PAUSE_FOR_HUMAN  │                       │    FAIL_SAFELY    │
   │ bounded backoff   │                       │  CAPTCHA, session,│                       │  validation error,│
   │ within deadline   │                       │  uncertain outcome│                       │ budget exhaustion │
   └───────────────────┘                       └───────────────────┘                       └───────────────────┘
```

### 1. Standardized Error Taxonomy (`app/agent/recovery/errors.py`)

All exceptions are categorized through `classify_exception()` into structured classes inheriting from `ClassifiedRecoveryError`:
- `TransientNetworkError`: Recoverable connection drop, reset, or socket error. Retried with exponential backoff.
- `OperationTimeoutError`: Deadline exceeded. Idempotent actions are retriable; non-idempotent actions become `UnknownOutcomeError`.
- `SessionExpiredError`: Session cookie expired or re-authentication challenge. Prompts controlled pause in `WAITING_FOR_HUMAN`.
- `CaptchaChallengeError`: CAPTCHA, Cloudflare, or anti-bot challenge detected. Never triggers automated bypass; pauses immediately for human intervention.
- `RateLimitError`: 429 Too Many Requests. Honors `Retry-After` if within the remaining execution deadline. If wait exceeds deadline, fails safely rather than retrying prematurely.
- `ServiceUnavailableRecoveryError`: 503 or open circuit breaker state.
- `ActionValidationError`: Invalid input parameters. Unrecoverable without input change; never retried automatically.
- `AuthenticationFailureError`: Bad credentials. Unrecoverable; fails safely without repeated retries.
- `UnknownOutcomeError`: Ambiguous outcome where side effect may have occurred. Blind repetition strictly prohibited; pauses for human verification.
- `HumanInterventionRequiredError`: Explicit checkpoint (payment authorization, CAPTCHA).

### 2. Central Recovery Policy & Retry Budgets (`app/agent/recovery/policy.py`)

- **Exponential Backoff**: Computes `min(initial_backoff * (multiplier ^ (attempt - 1)), max_backoff)`.
- **Default Parameters**:
  - `max_attempts`: 3 attempts.
  - `initial_backoff`: 0.5 seconds.
  - `backoff_multiplier`: 2.0.
  - `max_backoff`: 5.0 seconds.
  - `max_cumulative_retry_time`: 30.0 seconds.
- **Strict Retry Restrictions**:
  - Zero retries for validation errors, invalid credentials, CAPTCHAs, or cancelled contexts.
  - Bounded retry budget; exhausted attempts transition to `FAIL_SAFELY`.
  - Pluggable `Sleeper` protocol (`AsyncioSleeper` for production, `ZeroSleeper` for 0s deterministic test execution).

### 3. Idempotency & Unknown Outcomes (`app/agent/recovery/idempotency.py`)

- Actions classified into:
  - **Idempotent**: `inspect`, `navigate`, `extract_text`, `get_url_and_title`, `screenshot`, `find_trains`, `calculate_schedule`, `validate_plan`. Safe to repeat after confirmed transient failures.
  - **Non-Idempotent**: `click`, `type_text`, `press_key`, `execute_booking`, `confirm_payment`.
- **Ambiguous Timeout Safety**: If a non-idempotent action times out, the outcome is classified as `UNKNOWN_OUTCOME`. Repetition is strictly prohibited to prevent duplicate bookings or form submissions. The tool result sets `requires_human=True`, prompting the orchestrator to pause in `WAITING_FOR_HUMAN`.

### 4. Circuit Breakers (`app/agent/recovery/circuit_breaker.py`)

- **States**: `CLOSED` (normal operation), `OPEN` (fast-fail without calling dependency), `HALF_OPEN` (limited probes to test recovery).
- **Default Parameters**:
  - `failure_threshold`: 5 failures.
  - `failure_window_seconds`: 60.0s rolling window.
  - `cooldown_seconds`: 30.0s cooldown before `HALF_OPEN`.
  - `half_open_probe_limit`: 1 probe permitted.
- **Non-transient Filtering**: Validation errors, CAPTCHAs, and client bad requests do not count toward dependency failure thresholds.
- **Concurrency & Process-Local Scope**:
  - Thread-safe and asyncio-safe using `threading.RLock` and `asyncio.Lock`.
  - **Known Architectural Limitation**: Circuit breaker state is process-local and in-memory. State is not shared across multi-process clusters (e.g. multi-worker Uvicorn without distributed coordination).

### 5. Recovery Observability & REST API

- Structured logging with task ID, run ID, attempt number, backoff duration, and circuit state.
- Strictly sanitized context metadata via `redact_sensitive_data` (zero passwords, OTPs, CVVs, or tokens in logs or responses).
- REST API endpoint: `GET /api/v1/integrations/circuit-breakers` reports real-time state and diagnostics.

---

## Phase 7: Evidence, Audit, and Compliance Architecture

Phase 7 establishes a production-grade, privacy-conscious audit trail and cryptographic evidence verification pipeline for the Tatkal Agent Backend.

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 Application Workflow                    │
                  │   (Task, Run, Orchestrator, Skills, Recovery Engine)    │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                               ▼
                              ┌──────────────────────────────────┐
                              │     Central Redaction Filter     │
                              │ (Passwords, OTPs, CVVs, Bearer,  │
                              │  Cards, URL creds, Secrets)      │
                              └────────────────┬─────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
        ┌─────────────────────────────┐                 ┌─────────────────────────────┐
        │        Audit Service        │                 │      Evidence Service       │
        │  Structured AuditEvent      │                 │  Atomic File Storage        │
        │  Lifecycle, Tool, Recovery  │                 │  SHA-256 Checksum Calc      │
        │  Safe Metadata JSON         │                 │  Tamper / Missing Detection │
        └──────────────┬──────────────┘                 └──────────────┬──────────────┘
                       │                                               │
                       ▼                                               ▼
        ┌─────────────────────────────┐                 ┌─────────────────────────────┐
        │        audit_events         │                 │      evidence_records       │
        │      (SQLAlchemy DB)        │                 │  (DB Metadata + File Path)  │
        └─────────────────────────────┘                 └─────────────────────────────┘
                       │                                               │
                       └───────────────────────┬───────────────────────┘
                                               ▼
                               ┌───────────────────────────────┐
                               │     REST Query & Verify API   │
                               │  GET /api/v1/audit/events     │
                               │  GET /api/v1/evidence         │
                               │  POST /api/v1/evidence/verify │
                               │  GET /api/v1/evidence/download│
                               └───────────────────────────────┘
```

### 1. Audit Event Architecture (`app/models/audit.py`, `app/services/audit_service.py`)

- **Persistent Model**: `AuditEvent` table stores immutable lifecycle records:
  - `id`: UUID4 primary key.
  - `task_id`, `run_id`, `correlation_id`: Context correlation identifiers.
  - `event_type`: Specific action string (e.g., `task.created`, `run.started`, `tool.execution.success`).
  - `event_category`: Category partition (`TASK`, `RUN`, `TOOL`, `SKILL`, `RECOVERY`, `SECURITY`, `EVIDENCE`).
  - `timestamp`: UTC datetime (indexed).
  - `outcome`: `SUCCESS`, `FAILURE`, `WARNING`, `PENDING`.
  - `source`: Subsystem identifier (`task_service`, `run_service`, `tool_executor`, `skill_executor`, `recovery_policy`, `circuit_breaker`).
  - `event_metadata`: Sanitized JSON payload with deep secret redaction applied.
  - `evidence_references`: Linked evidence artifact UUIDs.
- **Fail-Safe Persistence Guarantee**: Audit logging failures never crash core agent execution or trigger uncontrolled retry loops.

### 2. Evidence Pipeline & Cryptographic Verification (`app/services/evidence_service.py`)

- **Artifact Storage**:
  - Saved under controlled paths within `settings.artifact_dir` using collision-resistant UUIDs (`type_timestamp_uuid.ext`).
  - **Strict Path Traversal Protection**: Relative paths are checked against directory escapes (`..`, `/`, absolute paths) raising `EvidencePathTraversalError`.
  - **Atomic File Writes**: Payloads are written to a `.tmp` file, synced to disk, and atomically renamed to destination.
  - **Size Limit Enforcement**: Bounded by `settings.max_artifact_size_bytes` (5 MB default).
- **Cryptographic Verification**:
  - SHA-256 checksum is calculated during capture and stored in `EvidenceRecord`.
  - `verify_integrity(evidence_id)` recalculates the SHA-256 hash from the disk file and compares it to stored checksum:
    - Matches: `integrity_status = "VERIFIED"` (`valid=True`).
    - Mismatch: `integrity_status = "TAMPERED"` (`valid=False`).
    - File missing: `integrity_status = "MISSING"` (`valid=False`).

### 3. Centralized Deep Secret Redaction (`app/integrations/security/redaction.py`)

- **Recursive Key Redaction**: Recursively strips sensitive keys from dictionaries, lists, and Pydantic models:
  - `password`, `otp`, `totp`, `cvv`, `cvc`, `cardnumber`, `creditcard`, `upiid`, `token`, `bearer`, `authorization`, `cookie`, `sessionid`, `apikey`, `secret`, `privatekey`, `pin`, `dob`, `passport`, `aadhar`.
- **Regex Pattern Matching**:
  - Bearer tokens: `Bearer eyJ...` -> `Bearer [REDACTED]`
  - Credit card numbers: 16-digit sequences -> `[REDACTED]`
  - URL credentials: `https://user:password@host` -> `https://user:[REDACTED]@host`
  - URL secret query parameters: `?token=xyz&api_key=123` -> `?token=[REDACTED]&api_key=[REDACTED]`
- **Header & Exception Redaction**:
  - `redact_http_headers()`: Replaces sensitive HTTP headers (`Authorization`, `Cookie`, `X-Api-Key`).
  - `redact_exception()`: Strips embedded credentials from error messages before logging or API serialization.

### 4. Event Coverage Matrix

| Lifecycle Point | Event Type | Category | Outcome | Context Captured |
|---|---|---|---|---|
| Task Creation | `task.created` | `TASK` | `SUCCESS` | `task_type`, `name` |
| Task Transition | `task.<status>` | `TASK` | `SUCCESS`/`FAILURE` | `from_status`, `to_status`, `version`, `error_code` |
| Task Metadata Updated | `task.metadata_updated` | `TASK` | `SUCCESS` | `task_id`, `version` |
| Run Creation | `run.created` | `RUN` | `SUCCESS` | `run_id`, `task_id`, initial `status` |
| Run Transition | `run.<status>` | `RUN` | `SUCCESS`/`FAILURE`/`PENDING` | `from_status`, `to_status`, `current_step`, `steps_completed` |
| Tool Execution Started | `tool.execution.started` | `TOOL` | `PENDING` | `tool_name`, `action_type`, sanitized `parameters` |
| Tool Execution Completed | `tool.execution.success` | `TOOL` | `SUCCESS` | `tool_name`, duration, evidence reference |
| Tool Execution Failed | `tool.execution.failure` | `TOOL` | `FAILURE` | `tool_name`, duration, `error_code` |
| Skill Execution Started | `skill.execution.started` | `SKILL` | `PENDING` | `skill_name`, sanitized `inputs`, step count |
| Skill Execution Completed | `skill.execution.success` | `SKILL` | `SUCCESS` | `skill_name`, steps completed |
| Skill Execution Failed | `skill.execution.failure` | `SKILL` | `FAILURE` | `skill_name`, error summary |
| Recovery Retry Scheduled | `recovery.retry_scheduled` | `RECOVERY` | `SUCCESS` | `error_category`, `error_code`, backoff duration, attempt |
| Retry Budget Exhausted | `recovery.budget_exhausted` | `RECOVERY` | `FAILURE` | `error_category`, total attempts |
| Circuit Breaker Open | `recovery.circuit_open` | `RECOVERY` | `WARNING` | `breaker_name`, failure count, threshold |
| Circuit Breaker Closed | `recovery.circuit_closed` | `RECOVERY` | `SUCCESS` | `breaker_name`, successful probe |
| Human Intervention Required | `human_intervention.required`| `RUN` | `PENDING` | `reason` (e.g. CAPTCHA, ambiguous timeout), step |
| Verification Failed | `verification.failed` | `RUN` | `FAILURE` | `step`, verifier explanation |
| Evidence Captured | `evidence.captured` | `EVIDENCE` | `SUCCESS` | `evidence_id`, `evidence_type`, checksum prefix, size |

### 5. Audit & Evidence Query REST API

- `GET /api/v1/audit/events`: Paginated audit events with filters for `task_id`, `run_id`, `event_type`, `event_category`, `start_time`, `end_time`.
- `GET /api/v1/audit/events/{id}`: Single event detail.
- `GET /api/v1/audit/tasks/{task_id}/events`: Events for a given task.
- `GET /api/v1/audit/runs/{run_id}/events`: Events for a given run.
- `GET /api/v1/evidence`: Paginated evidence metadata listing.
- `GET /api/v1/evidence/{id}`: Evidence record metadata.
- `POST /api/v1/evidence/{id}/verify`: Real-time SHA-256 integrity verification against disk artifact.
- `GET /api/v1/evidence/{id}/download`: Safe binary download of stored evidence artifact (path traversal strictly rejected).

### 6. Safety Boundaries & Known Limitations

- **Mandatory Safety Boundaries Confirmed**:
  - Live IRCTC booking execution remains strictly disabled.
  - Live payment execution remains strictly disabled (no unattended authorization or credit card entry).
  - Anti-bot / CAPTCHA bypass remains strictly prohibited. Challenges emit `human_intervention.required` and pause runs in `WAITING_FOR_HUMAN`.
- **Access Control Limitation**: The current backend implements API versioning and response envelopes, but tenant user ownership boundaries and JWT client authentication belong to later phases. Audit endpoints reflect public backend visibility suitable for local development and hackathon evaluation.
- **Cryptographic Guarantees**: SHA-256 checksums verify file integrity and detect local file corruption or tampering; they do not represent asymmetric digital signatures or append-only ledger immutability.

---

## Phase 8 — Final Backend Hardening, Execution Flow & Readiness

### 1. End-to-End Execution Flow

The backend orchestrates the complete execution loop from task creation to truthful completion:

```
[Client]
   │  POST /api/v1/tasks (Creates Task in CREATED state)
   ▼
[TaskService] ──► [TaskRepository] (Persists Task)
   │  POST /api/v1/tasks/{id}/runs (Creates ExecutionRun in PENDING state)
   ▼
[RunService] ──► [RunRepository] (Persists Run)
   │  POST /api/v1/runs/{id}/execute
   ▼
[RunService.execute_run]
   │
   ├─► Transitions Task: CREATED -> READY -> RUNNING
   ├─► Transitions Run: PENDING -> RUNNING
   │
   ▼
[Agent Orchestrator]
   │
   ├── Sense: [DefaultObserver] captures normalized environment state
   ├── Plan:  [LLM / FakePlanner] proposes next action
   ├── Act:   [ToolExecutor] resolves tool, validates bounds, checks circuit breaker
   └── Verify: [DeterministicVerifier] verifies execution outcome
   │
   ▼
[Synchronization & Completion]
   ├─► Synchronizes Run to COMPLETED, WAITING_FOR_HUMAN, or FAILED
   ├─► Synchronizes Task to matching status
   ├─► Captures EXECUTION_SUMMARY in EvidenceRecord with SHA-256 digest
   └─► Emits structured audit events across all transition points
```

### 2. Cascading Task Cancellation & Immutability Guards

- **Cascaded Cancellation**: Invoking `POST /api/v1/tasks/{id}/cancel` automatically resolves any active execution run (`PENDING`, `RUNNING`, `PAUSED`, `WAITING_FOR_HUMAN`) and transitions it to `CANCELLED`, ensuring orphan background loops never continue running indefinitely.
- **Terminal Immutability**: Any attempt to re-execute a completed, failed, or cancelled run (`POST /api/v1/runs/{id}/execute`) is rejected immediately with HTTP 409 Conflict.

### 3. Diagnostics: Liveness vs Readiness

- **`GET /api/v1/health/liveness`**: Ultra-lightweight endpoint returning HTTP 200 `status: "alive"` as long as the FastAPI process is responsive.
- **`GET /api/v1/health/readiness`**: Comprehensive subsystem probe returning HTTP 200 `status: "ready"` only if:
  1. Database engine connects and executes `SELECT 1`.
  2. Data (`data/`) and artifact (`artifacts/`) directories are present and writable.
  3. Default tool adapters (`browser`) are initialized in the `IntegrationRegistry`.
- **`GET /api/v1/health`**: Legacy endpoint maintained for full backward compatibility across all phases.

### 4. Graceful Shutdown & Resource Management

In `app/main.py`, the application `lifespan` handler captures shutdown signals and iterates all registered tool adapters:
- For `BrowserToolAdapter`, calls `adapter.close()`, which cleanly halts running browser drivers and headless processes.
- Prevents leaked child processes, unclosed file descriptors, or dangling SQLite write-ahead log locks during server reloads.


