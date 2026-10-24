# Development Plan

Eight-phase development plan for the Tatkal Agent Backend.

---

## Phase 1 — Backend Foundation ✅

**Status**: Complete

**Deliverables**:
- Project structure and directory layout
- FastAPI application with versioned API (`/api/v1`)
- Centralised configuration (pydantic-settings)
- Database foundation (SQLAlchemy 2.x + SQLite)
- Health-check endpoint with database connectivity verification
- Consistent API response and error handling conventions
- Integration contracts (typed Protocols) for all teammate modules
- Integration registry (dependency injection)
- Structured logging
- Automated tests (health, config, database, integrations)
- Documentation (README, Architecture, Integration Contracts, Development Plan)

---

## Phase 2 — Task & Execution State Infrastructure ✅

**Status**: Complete

**Deliverables**:
- Task ORM model with UUID ID, JSON configuration, lifecycle timestamps, optimistic concurrency version
- Formal task state machine with 10 states and centralised transition policy
- Task service layer (create, get, list, update, transition, cancel)
- Task repository (data-access layer with pagination and filtering)
- REST API endpoints: `POST /tasks`, `GET /tasks`, `GET /tasks/{id}`, `GET /tasks/{id}/status`, `POST /tasks/{id}/transition`, `POST /tasks/{id}/cancel`, `PATCH /tasks/{id}`
- Pydantic v2 request and response schemas with validation
- Typed exceptions (TaskNotFoundError, InvalidTaskTransitionError, TaskStateConflictError, TaskValidationError)
- Optimistic concurrency control via version column
- 83 new tests (114 total) covering CRUD, state transitions, cancellation, pagination, persistence, concurrency
- Updated documentation

**Intentionally deferred to later phases**:
- Execution Run model (Phase 3 — linked to agent orchestration)
- Action Log model (Phase 3 — individual steps within a run)
- Alembic migrations (will be introduced when schema stabilises)
- Agent execution — the task manager stores state but does not execute tasks


---

## Phase 3 — Agent Orchestration Core ✅

**Status**: Complete

**Deliverables**:
- Persistent `ExecutionRun` ORM model with `Task` relationship, step tracking, error details, execution metadata, and optimistic concurrency versioning
- Formal execution-run state machine with 8 distinct states (`CREATED`, `STARTING`, `RUNNING`, `PAUSED`, `CANCELLED`, `VERIFYING`, `COMPLETED`, `FAILED`) and centralised transition policy
- Independent task and run lifecycles with single-active-run constraint (prevents duplicate concurrent active runs on a task)
- Provider-agnostic LLM abstraction (`LLMClient`, `StructuredPlanner`, `FakePlanner`, `ModelConfig`, `PromptContext`, `Plan`, `PlanStep`, `ToolCallRequest`)
- Generic tool execution engine (`ToolExecutor`) with schema validation, adapter resolution via `IntegrationRegistry` (`AgentToolIntegration`), per-step timeouts, and error normalization
- Decoupled observation and verification interfaces (`Observer`, `DefaultObserver`, `Verifier`, `StepVerifier`, `RunVerifier`, `DeterministicVerifier`) ensuring verification cannot be bypassed
- Generic agent orchestrator (`AgentOrchestrator`) coordinating the loop: observe → plan → execute tool → observe outcome → verify, enforcing max-step limits, wall-clock timeouts, and checkpointed pause/resume/cancellation
- Run management service and repository (`RunService`, `RunRepository`)
- REST API endpoints:
  - `POST /api/v1/tasks/{task_id}/runs` — start or enqueue an execution run
  - `GET /api/v1/tasks/{task_id}/runs` — list runs for a task (paginated, filterable)
  - `GET /api/v1/runs/{run_id}` — get run details and current status
  - `POST /api/v1/runs/{run_id}/pause` — pause an active run at next checkpoint
  - `POST /api/v1/runs/{run_id}/resume` — resume a paused run
  - `POST /api/v1/runs/{run_id}/cancel` — cancel an active or paused run
- 87 new tests (201 total) covering state machine, API endpoints, tool execution, observer, verifier, and full orchestrator execution workflows
- Zero external LLM credential requirements for testing and development

**Intentionally deferred to later phases**:
- Concrete browser and desktop tool adapters (Phase 4)
- Skill loading and YAML workflow definitions (Phase 4)
- Teammate module implementations (Phase 5)
- Automated recovery and resilience policies (Phase 6)
- Audit evidence logging and screenshot storage (Phase 7)

---

## Phase 4 — Tool Adapters & Skill System ✅

**Status**: Complete

**Deliverables**:
- Consistent tool adapter architecture (`BaseToolAdapter`) implementing `AgentToolIntegration` with explicit capability declarations, input schemas, and granular status reporting
- Browser automation tool adapter (`BrowserToolAdapter`) supporting navigation, page inspection, text extraction, element click, text input, URL/title reading, and screenshot capture
- Pluggable driver layer (`BrowserDriver`) featuring high-fidelity in-memory `MockBrowserDriver` for hermetic testing and `PlaywrightBrowserDriver` for live environments
- Security barrier & CAPTCHA detection triggering structured `HUMAN_INTERVENTION_REQUIRED` results
- Desktop automation tool adapter (`DesktopToolAdapter`) with macOS permission guards, fail-safe availability reporting, and mouse/keyboard interaction schemas
- Artifact management service (`ArtifactManager`) providing collision-resistant naming, directory traversal protection, and file size bounding (5MB) for screenshots
- Declarative skill system loading validated YAML workflows from `app/skills/definitions/` (`SkillLoader`, `SkillDefinition`) with duplicate detection and zero arbitrary code execution
- Skill execution engine (`SkillExecutor`) coordinating multi-step workflows, variable interpolation (`{{ inputs.var }}`), tool availability verification, step-failure aborts, and cancellation
- Safe demonstration skill (`browser_inspection.yaml`) proving end-to-end multi-step tool orchestration without external network dependencies
- Tool discovery and health check API endpoints:
  - `GET /api/v1/tools` — list registered tools and capabilities
  - `GET /api/v1/tools/{tool_name}/health` — tool operational diagnostics
  - `GET /api/v1/skills` — list available declarative skills
  - `GET /api/v1/skills/{skill_name}` — retrieve skill definition and schema
- 58 new tests (259 total) covering registry, adapters, drivers, skills, artifacts, and end-to-end demonstration execution

**Intentionally deferred to later phases**:
- Teammate module implementations: Scheduler, Booking Assistance, Train Comparison, Security (Phase 5)
- Automated recovery, retry orchestration, and circuit breakers (Phase 6)
- Comprehensive audit logging, evidence indexing, and compliance reporting (Phase 7)
- End-to-end Tatkal booking demonstration and final hardening (Phase 8)

---

## Phase 5 — Teammate Module Integration, Backend Consolidation & Error Fixing

**Status**: Complete

**Deliverables**:
- Discovered and integrated teammate modules across the workspace (`Scheduler` and `ranking and security module`)
- Integrated Member 3's Tatkal booking scheduler logic into `TatkalSchedulerAdapter`:
  - AC opening (10:00 IST) and Non-AC opening (11:00 IST) calculations for the day prior to departure
  - Timezone handling (`Asia/Kolkata` IST and UTC)
  - Pre-alert reminder calculations with configurable lead times
  - Duplicate schedule prevention
  - Missed reminder recovery window (within 10 minutes past opening) and expiry handling
- Integrated Member 4's Train Ranking algorithm into `TrainComparisonAdapter`:
  - Route validation (`origin`, `destination`), `TATKAL` quota filtering, eligibility and verified availability enforcement
  - Multi-tier deterministic sorting: fare (cheapest first) → duration (shortest first) → alphanumeric train number tie-breaker
  - Rejection of invalid inputs, negative/unverified fares, and unverified availability
- Integrated Member 4's Security and Data Protection module into `SecurityAdapter` and `SecureCredentialStore`:
  - Recursive sensitive data redaction (`redact_sensitive_data`) matching Member 4 specifications
  - Protected credential store generating opaque reference tokens (`sec_ref_...`) in isolated memory
  - Authorization check blocking prohibited actions (`captcha_bypass`, `anti_bot_circumvention`, `auto_approve_payment`) and enforcing mandatory human intervention for payment approval
- Implemented `BookingAssistanceAdapter` enforcing strict safety boundaries:
  - Generates structured booking plans with human approval checkpoints for CAPTCHA and payment
  - Strictly disallows unattended live booking or automated payment execution
- Enhanced `IntegrationRegistry` with teammate integration discovery, metadata, and health checks
- Added versioned REST API endpoints under `/api/v1`:
  - `GET /api/v1/integrations` — list all registered integrations and metadata
  - `GET /api/v1/integrations/{name}/health` — check health of a registered integration
  - `POST /api/v1/trains/compare` — search and rank train options
  - `POST /api/v1/scheduler/calculate` — compute Tatkal opening dates and alert times
  - `POST /api/v1/scheduler/schedule` — schedule an execution run
  - `DELETE /api/v1/scheduler/{schedule_id}` — cancel a scheduled run
  - `POST /api/v1/security/check` — verify action authorization
  - `POST /api/v1/security/redact` — sanitize sensitive payload fields
  - `POST /api/v1/booking/plan` — create a validated booking plan
  - `POST /api/v1/booking/execute` — execute booking assistance with human handoff
- Automated tests: 49 new tests added (308 tests total, all passing)

**Intentionally deferred to later phases**:
- Automated recovery, retry orchestration, and circuit breakers (Phase 6)
- Comprehensive audit logging, evidence indexing, and compliance reporting (Phase 7)
- End-to-end Tatkal booking demonstration and final hardening (Phase 8)
- Frontend integration and final end-to-end testing (Phase 9)

---

## Phase 6 — Recovery & Resilience

**Status**: Complete

**Deliverables**:
- **Standardized Error Taxonomy**:
  - `TransientNetworkError`: Recoverable network drops, connection resets, DNS failures.
  - `OperationTimeoutError`: Deadline exceeded; differentiated between idempotent actions (retriable) and non-idempotent actions (unknown outcome).
  - `SessionExpiredError`: Authenticated session invalid or expired; controlled pause in `WAITING_FOR_HUMAN`.
  - `CaptchaChallengeError`: Anti-bot or CAPTCHA challenge detected; immediately pauses for human intervention (never automated bypass).
  - `RateLimitError`: 429 Too Many Requests; respects valid `Retry-After` header/message subject to execution deadlines.
  - `ServiceUnavailableRecoveryError`: 503 Service Unavailable / circuit breaker open state.
  - `ActionValidationError`: 422/400 invalid request/parameters; unrecoverable without changed input, never retried automatically.
  - `AuthenticationFailureError`: 401 invalid credentials; fails safely, never retried blindly.
  - `UnknownOutcomeError`: Ambiguous outcome on non-idempotent operations; repetition strictly prohibited, requires human verification.
  - `HumanInterventionRequiredError`: Explicit human checkpoint (payment authorization, CAPTCHA).
  - Safe diagnostic metadata: strict recursive sensitive-data redaction ensuring zero secrets or passwords in logs or error bodies.
- **Central Recovery Policy & Bounded Retries**:
  - Configurable parameters: `max_attempts` (default: 3), `initial_backoff` (default: 0.5s), `backoff_multiplier` (default: 2.0), `max_backoff` (default: 5.0s), `max_cumulative_retry_time` (default: 30.0s).
  - Deterministic evaluation emitting `RecoveryDecision` (`RETRY`, `PAUSE_FOR_HUMAN`, `FAIL_SAFELY`, `STOP_UNCERTAIN`).
  - Strict retry restrictions: zero retries for validation errors, invalid credentials, CAPTCHA challenges, cancellation, or uncertain outcomes.
  - Pluggable `Sleeper` protocol (`AsyncioSleeper` for production, `ZeroSleeper` for 0s deterministic test execution).
- **Idempotency & Unknown Outcomes**:
  - Action registry classifying actions into idempotent (`inspect`, `navigate`, `extract_text`, `find_trains`, `calculate_schedule`, `screenshot`) and non-idempotent (`click`, `type_text`, `execute_booking`, etc.).
  - Critical financial and booking actions marked as requiring human confirmation.
  - Ambiguous non-idempotent timeouts flagged with `requires_human=True`, preventing duplicate transactions.
- **Concurrency-Safe Circuit Breakers**:
  - 3 standard states: `CLOSED`, `OPEN`, `HALF_OPEN`.
  - Configurable settings: `failure_threshold` (default: 5), `cooldown_seconds` (default: 30.0s), `half_open_probe_limit` (default: 1), `failure_window_seconds` (default: 60.0s).
  - Exclusion of non-dependency errors: validation errors and CAPTCHAs do not increment failure counters.
  - Process-local thread/asyncio safety via `threading.RLock` and `asyncio.Lock`.
  - Named singleton management via `CircuitBreakerRegistry`.
- **Orchestrator and Integration Updates**:
  - Orchestrator pauses runs in `WAITING_FOR_HUMAN` when `tool_result.requires_human` is flagged (CAPTCHA, session expired, ambiguous timeout).
  - `ToolExecutor` guarded by process-local circuit breakers, failing fast with `ToolActionStatus.TOOL_UNAVAILABLE`.
  - `TrainComparisonAdapter` external data provider guarded by `"train_comparison"` circuit breaker; reports degraded health when breaker is OPEN.
  - REST API endpoint: `GET /api/v1/integrations/circuit-breakers` exposing real-time breaker health and metrics.
  - API exception handler for `BaseRecoveryError` preserving standard response envelope with safe structured recovery details.
- **Automated Tests**:
  - Added 43 comprehensive tests across `test_error_taxonomy.py`, `test_circuit_breaker.py`, `test_recovery_policy.py`, and `test_recovery_integration.py`.
  - Full suite: 351 passing tests (zero regressions, 0 failures).

**Intentionally deferred to later phases**:
- Comprehensive audit logging, evidence indexing, and compliance reporting (Phase 7)
- Backend hardening, demo readiness, and final performance optimization (Phase 8)
- Frontend integration and final end-to-end testing (Phase 9)

---

## Phase 7 — Audit, Evidence & Compliance ✅
*Status: Complete*

**Deliverables Implemented**:
- **Structured Persistent Audit Event Model**:
  - `AuditEvent` SQLAlchemy ORM model with UUID primary keys, UTC timestamps, `task_id`, `run_id`, `correlation_id`, `event_type`, `event_category`, `outcome`, `source`, `tool_or_skill_name`, `error_code`, `event_metadata` (sanitized JSON), and `evidence_references`.
  - Composite indexes on `(task_id, timestamp)`, `(run_id, timestamp)`, and `(event_type, timestamp)`.
- **Evidence Record Model & Cryptographic Tamper Detection**:
  - `EvidenceRecord` SQLAlchemy ORM model capturing artifact metadata, safe relative file paths, MIME content types, file sizes, SHA-256 checksums, and `integrity_status` (`VERIFIED`, `TAMPERED`, `MISSING`).
  - `EvidenceService` providing atomic file writes (temporary file swap), size bounding, strict path traversal rejection, and cryptographic SHA-256 verification against disk state.
- **Centralized Deep Secret Redaction**:
  - Deep recursive dictionary and list redaction covering standard and variant sensitive keys (passwords, OTPs, CVVs, card numbers, API keys, tokens, session IDs, private keys).
  - Regex pattern redactions for Bearer tokens, 16-digit credit card sequences, embedded URL credentials, and query parameter secrets.
  - HTTP header redaction (`Authorization`, `Cookie`, `X-Api-Key`).
  - Exception sanitization (`redact_exception()`) preventing sensitive data leakage through error logs or API responses.
- **Audit Service & Workflow Instrumentation**:
  - `AuditService` with safe transaction handling and zero crash guarantees on logging failure.
  - Instrumented Task lifecycle (`task.created`, `task.transitioned`, `task.metadata_updated`).
  - Instrumented Run lifecycle (`run.created`, `run.started`, `run.completed`, `run.failed`, `run.cancelled`, `run.paused`, `run.resumed`, `run.waiting_for_human`).
  - Instrumented Tool execution (`tool.execution.success`, `tool.execution.failure`) and Verification (`verification.failed`).
  - Instrumented Skill execution (`skill.execution.started`, `skill.execution.completed`, `skill.execution.failed`).
  - Instrumented Recovery & Resilience (`recovery.retry_scheduled`, `recovery.budget_exhausted`, `recovery.circuit_open`, `recovery.circuit_closed`).
  - Instrumented Human intervention gates (`human_intervention.required`).
- **Audit & Evidence REST APIs**:
  - `GET /api/v1/audit/events`: Paginated query with task, run, category, and date filtering.
  - `GET /api/v1/audit/events/{id}`: Audit event retrieval by ID.
  - `GET /api/v1/audit/tasks/{task_id}/events` & `GET /api/v1/audit/runs/{run_id}/events`.
  - `GET /api/v1/evidence`: Paginated evidence metadata listing.
  - `GET /api/v1/evidence/{id}`: Detailed evidence metadata retrieval.
  - `POST /api/v1/evidence/{id}/verify`: Real-time SHA-256 integrity verification.
  - `GET /api/v1/evidence/{id}/download`: Safe, controlled binary artifact download by ID (path traversal strictly blocked).
- **Automated Tests**:
  - 32 new comprehensive tests across `test_audit_event_model.py`, `test_secret_redaction_deep.py`, `test_evidence_service.py`, `test_audit_service.py`, `test_audit_api.py`, and `test_audit_lifecycle_integration.py`.
  - Full suite: **383 passed, 0 failed**.

**Intentionally deferred to later phases**:
- Backend hardening, demo readiness, and final performance optimization (Phase 8)
- Frontend integration and final end-to-end testing (Phase 9)


---

## Phase 8 — Final Backend Hardening, Integration Completion & Demo Readiness ✅
*Status: Complete*

**Deliverables Implemented**:
- **End-to-End Execution Flow Completion**:
  - `execute_run` method on `RunService` providing complete orchestrator loop execution with state synchronization, recovery bounds, evidence capture, and terminal immutability guards.
  - REST endpoint `POST /api/v1/runs/{run_id}/execute` to trigger the sense-plan-act-verify loop from start to completion.
  - REST endpoint `POST /api/v1/runs/{run_id}/transition` for explicit, validated run state transitions through the centralized state machine.
- **Task & Run Lifecycle Consistency**:
  - Cascaded task cancellation: cancelling a task automatically cascades to cancel any active execution run (`PENDING`, `RUNNING`, `PAUSED`, `WAITING_FOR_HUMAN`).
  - Terminal run immutability: completed or cancelled runs cannot be accidentally re-executed (enforces 409 Conflict).
- **Diagnostics & Observability Hardening**:
  - `GET /api/v1/health/liveness`: Process liveness probe returning HTTP 200 when backend is alive.
  - `GET /api/v1/health/readiness`: Subsystem readiness probe verifying database connectivity, storage directories, and tool registry readiness.
  - Graceful tool adapter shutdown in FastAPI `lifespan`: stops browser drivers and frees resources cleanly upon application exit.
- **Safety Boundary Enforcement**:
  - Live IRCTC booking submission remains strictly disabled.
  - Live payment execution remains strictly disabled.
  - Automated CAPTCHA solving / anti-bot bypass remains prohibited; challenges require human intervention (`WAITING_FOR_HUMAN`).
- **Manual Test Plan**:
  - `docs/MANUAL_TEST_PLAN.md`: Comprehensive 18-point manual testing matrix covering environment, lifecycle, tools, skills, recovery, audit, evidence, security, and safety.
- **Automated Tests**:
  - 7 new tests in `tests/test_backend_hardening.py` covering cascading cancellations, manual transitions, end-to-end execution, terminal immutability, liveness/readiness probes, and safety boundary enforcement.
  - Full test suite: **390 passed, 0 failed**.

---

## Phase 9 — Frontend Integration & Final E2E Validation ⏳
*Status: Deferred to Phase 9*

**Planned deliverables**:
- Integration with Team Member 1's frontend application.
- Real-time run streaming (WebSockets or Server-Sent Events).
- End-to-end rehearsal and live demo execution with human operator interaction.

---

## Phase Dependencies

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
                │                      │
                ▼                      ▼
             Phase 5 ◄──────────── Phase 5
                │
                ▼
             Phase 6 ──► Phase 7 ──► Phase 8 ──► Phase 9 (Frontend)
```

Phases 1–8 are complete. Phase 9 (frontend integration) will begin after manual backend verification.
