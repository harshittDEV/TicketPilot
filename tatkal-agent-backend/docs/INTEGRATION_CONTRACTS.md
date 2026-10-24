# Integration Contracts

This document defines the integration boundaries between the core backend and the modules developed by each team member. Each contract is a typed Python Protocol defined in `app/integrations/contracts.py`.

**Rule**: The core backend never imports teammate code directly. All integration happens through Protocol-based adapters registered in the `IntegrationRegistry`.

---

## API Base Path & Response Conventions

All API endpoints are served under:

```
/api/v1/
```

### Success Response Format

```json
{
  "success": true,
  "data": { },
  "message": "Operation completed"
}
```

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found"
  }
}
```

### Error Codes

| Code                        | HTTP Status | Description                              |
|-----------------------------|-------------|------------------------------------------|
| `VALIDATION_ERROR`          | 422         | Request body or query parameter invalid  |
| `RESOURCE_NOT_FOUND`        | 404         | Requested entity does not exist          |
| `RESOURCE_CONFLICT`         | 409         | Duplicate or conflicting operation       |
| `SERVICE_UNAVAILABLE`       | 503         | A required backend service is down       |
| `INTEGRATION_NOT_REGISTERED`| 501         | A required integration adapter is missing|
| `INTERNAL_ERROR`            | 500         | Unexpected server error                  |

---

## A. Scheduler Integration (Team Member 2)

**Registry name**: `"scheduler"`

**Protocol**: `SchedulerIntegration`

### Methods

| Method          | Input              | Output           | Description                            |
|-----------------|--------------------|------------------|----------------------------------------|
| `schedule_run`  | `ScheduleRequest`  | `ScheduleResult` | Request a task to run at a future time |
| `cancel_run`    | `schedule_id: str` | `ScheduleResult` | Cancel a previously scheduled run      |

### Data Models

**ScheduleRequest**:
```python
{
    "task_id": str,       # Unique task identifier
    "execute_at": datetime, # UTC execution time
    "metadata": dict      # Optional context
}
```

**ScheduleResult**:
```python
{
    "schedule_id": str,   # Assigned schedule identifier
    "status": str,        # "scheduled" | "cancelled" | "failed"
    "message": str        # Human-readable status message
}
```

### How to Implement

1. Create a class that satisfies the `SchedulerIntegration` protocol.
2. Register it: `registry.register("scheduler", MySchedulerAdapter())`.
3. The core backend will retrieve it via `registry.get("scheduler")`.

---

## B. Booking Assistance Integration (Team Member 2)

**Registry name**: `"booking_assistance"`

**Protocol**: `BookingAssistanceIntegration`

### Methods

| Method            | Input            | Output          | Description                           |
|-------------------|------------------|-----------------|---------------------------------------|
| `execute_booking` | `BookingContext`  | `BookingResult` | Execute booking with validated context|

### Data Models

**BookingContext**:
```python
{
    "task_id": str,
    "passenger_count": int,       # >= 1
    "journey_details": dict       # Route, class, quota, etc.
}
```

**BookingResult**:
```python
{
    "task_id": str,
    "success": bool,
    "booking_reference": str | None,
    "message": str,
    "evidence": dict              # Screenshots, logs, etc.
}
```

---

## C. Train Comparison Integration (Team Member 3)

**Registry name**: `"train_comparison"`

**Protocol**: `TrainComparisonIntegration`

### Methods

| Method        | Input        | Output                  | Description                         |
|---------------|--------------|-------------------------|-------------------------------------|
| `find_trains` | `TrainQuery` | `TrainComparisonResult` | Find eligible trains for a journey  |

### Data Models

**TrainQuery**:
```python
{
    "source_station": str,
    "destination_station": str,
    "travel_date": str,           # ISO 8601
    "travel_class": str | None,
    "quota": str                  # Default: "TATKAL"
}
```

**TrainCandidate**:
```python
{
    "train_number": str,
    "train_name": str,
    "departure_time": str,
    "arrival_time": str,
    "available_classes": list[str],
    "availability_status": str,
    "fare": float | None,
    "metadata": dict
}
```

**TrainComparisonResult**:
```python
{
    "query": TrainQuery,
    "candidates": list[TrainCandidate],
    "message": str
}
```

---

## D. Security Integration (Team Member 3)

**Registry name**: `"security"`

**Protocol**: `SecurityIntegration`

### Methods

| Method                | Input                  | Output               | Description                        |
|-----------------------|------------------------|-----------------------|------------------------------------|
| `check_authorization` | `SecurityCheckRequest` | `SecurityCheckResult` | Validate if an action is allowed   |

### Data Models

**SecurityCheckRequest**:
```python
{
    "action": str,        # The sensitive action being requested
    "actor": str,         # Who is performing it
    "resource": str | None,
    "context": dict
}
```

**SecurityCheckResult**:
```python
{
    "allowed": bool,
    "reason": str
}
```

---

## E. Agent Tool Integration (Core — Phase 4)

**Registry name**: `"tool:<tool_name>"` or bare name `"<tool_name>"` (e.g. `"browser"`, `"desktop"`)

**Protocol**: `AgentToolIntegration`

### Methods

| Method         | Input        | Output                | Description                     |
|----------------|--------------|------------------------|---------------------------------|
| `execute`      | `ToolAction` | `ToolExecutionResult`  | Execute a validated tool action |
| `health_check` | —            | `bool`                 | Check if the tool is operational|
| `get_metadata` | —            | `ToolMetadata`         | Retrieve capabilities and schema|

### Data Models

**ToolAction**:
```python
{
    "action_type": str,        # "click", "type_text", "screenshot", "navigate", etc.
    "parameters": dict,
    "timeout_seconds": float   # Default: 30.0
}
```

**ToolExecutionResult**:
```python
{
    "status": (
        "success" | "failure" | "timeout" | "skipped" |
        "invalid_arguments" | "unknown_tool" | "tool_unavailable" |
        "recoverable_failure" | "non_recoverable_failure" |
        "human_intervention_required"
    ),
    "output": Any,
    "error_message": str | None,
    "duration_seconds": float | None,
    "metadata": dict
}
```

**ToolMetadata**:
```python
{
    "name": str,
    "description": str,
    "version": str,
    "capabilities": list[str],
    "input_schema": dict,
    "is_available": bool,
    "health_status": dict
}
```

---

## F. Frontend Integration (Team Member 1)

The frontend consumes the REST API over HTTP.

### Key Information

| Item                | Value                                  |
|---------------------|----------------------------------------|
| Base URL            | `http://localhost:8000/api/v1`         |
| API Docs            | `http://localhost:8000/docs` (Swagger) |
| Response format     | JSON (see envelope conventions above)  |
| CORS allowed origins| Configurable via `ALLOWED_ORIGINS`     |

### Implemented Endpoints (Phases 1–5)

| Method | Path                              | Description                      | Status Code |
|--------|-----------------------------------|----------------------------------|-------------|
| GET    | `/api/v1/health`                  | Health check                     | 200 / 503   |
| POST   | `/api/v1/tasks`                   | Create a new task                | 201         |
| GET    | `/api/v1/tasks`                   | List tasks (paginated, filtered) | 200         |
| GET    | `/api/v1/tasks/{id}`              | Get task details                 | 200 / 404   |
| GET    | `/api/v1/tasks/{id}/status`       | Get task status + timestamps     | 200 / 404   |
| POST   | `/api/v1/tasks/{id}/transition`   | Transition task state (internal) | 200 / 409   |
| POST   | `/api/v1/tasks/{id}/cancel`       | Cancel a task                    | 200 / 409   |
| PATCH  | `/api/v1/tasks/{id}`              | Update task metadata             | 200 / 409   |
| POST   | `/api/v1/tasks/{id}/runs`         | Create execution run for task    | 201 / 409   |
| GET    | `/api/v1/tasks/{id}/runs`         | List runs for a task             | 200         |
| GET    | `/api/v1/runs/{id}`               | Get execution run details        | 200 / 404   |
| POST   | `/api/v1/runs/{id}/pause`         | Pause execution run              | 200 / 409   |
| POST   | `/api/v1/runs/{id}/resume`        | Resume execution run             | 200 / 409   |
| POST   | `/api/v1/runs/{id}/cancel`        | Cancel execution run             | 200 / 409   |
| GET    | `/api/v1/tools`                   | List registered tools & status   | 200         |
| GET    | `/api/v1/tools/{tool_name}/health`| Tool operational diagnostics     | 200 / 404   |
| GET    | `/api/v1/skills`                  | List available declarative skills| 200         |
| GET    | `/api/v1/skills/{skill_name}`     | Retrieve skill schema & metadata | 200 / 404   |
| GET    | `/api/v1/integrations`            | List all registered integrations | 200         |
| GET    | `/api/v1/integrations/{name}/health`| Integration health diagnostics | 200 / 404   |
| POST   | `/api/v1/trains/compare`          | Compare and rank trains (Member 4)| 200 / 400  |
| POST   | `/api/v1/scheduler/calculate`     | Tatkal opening calculation (M3)  | 200 / 400   |
| POST   | `/api/v1/scheduler/schedule`      | Schedule task execution run (M3) | 200 / 400   |
| DELETE | `/api/v1/scheduler/{schedule_id}` | Cancel scheduled task run (M3)   | 200 / 404   |
| POST   | `/api/v1/security/check`          | Check security authorization (M4)| 200         |
| POST   | `/api/v1/security/redact`         | Redact sensitive keys from JSON  | 200         |
| POST   | `/api/v1/booking/plan`            | Generate validated booking plan  | 200 / 400   |
| POST   | `/api/v1/booking/execute`         | Execute booking with human handoff| 200         |

### Task Creation Request

```json
{
  "name": "Tatkal booking task",
  "task_type": "train_booking",
  "description": "Book an authorized train journey",
  "configuration": {
    "source": "Roorkee",
    "destination": "Haridwar",
    "passenger_count": 1
  }
}
```

### Task Listing Query Parameters

| Parameter   | Type   | Default | Description                 |
|-------------|--------|---------|-----------------------------|
| `page`      | int    | 1       | Page number (≥ 1)           |
| `page_size` | int    | 20      | Items per page (1–100)      |
| `status`    | string | —       | Filter by task status       |
| `task_type` | string | —       | Filter by task type         |

### State Transitions

The transition endpoint is an **internal orchestration interface**. It must be restricted before production deployment. State transitions are validated by the centralised state machine — the backend owns all lifecycle state changes.

### Scheduler Integration with Tasks

The future scheduler (Team Member 2) should:
1. Query tasks in `CREATED` status via `GET /api/v1/tasks?status=CREATED`.
2. Transition eligible tasks to `READY` via `POST /api/v1/tasks/{id}/transition`.
3. The task service validates the transition — the scheduler cannot bypass the state machine.

### Orchestrator Integration with Tasks

The future orchestrator (Phase 3) will:
1. Read task state and configuration via `TaskService.get_task()`.
2. Request transitions (READY→RUNNING, RUNNING→VERIFYING, etc.) via `TaskService.transition_task()`.
3. Store execution runs and action logs linked to the task ID.

---

## Integration Registry Usage

```python
from app.integrations.registry import get_registry

registry = get_registry()

# Register an adapter (at startup or during initialisation)
registry.register("scheduler", MySchedulerAdapter())

# Retrieve an adapter (in a service or dependency)
scheduler = registry.get("scheduler")
await scheduler.schedule_run(request)

# Check availability before use
if registry.is_registered("train_comparison"):
    comparison = registry.get("train_comparison")
    result = await comparison.find_trains(query)
```

---

## Rules for Implementers

1. **Implement the Protocol**: Your adapter class must satisfy the corresponding `Protocol` from `contracts.py`.
2. **Register at startup**: Use the `IntegrationRegistry` to register your adapter.
3. **Do not import core internals**: Use only the public interfaces.
4. **Return structured results**: Always return the Pydantic model specified by the contract.
5. **Handle errors gracefully**: Raise `AppException` or `ClassifiedRecoveryError` subclasses for expected errors.
6. **Do not log secrets**: Never log API keys, passwords, payment details, or PII.

---

## F. Recovery & Resilience Contracts (Phase 6)

### Standardized Error Metadata

Integrations raising recoverable or unrecoverable exceptions must map to `ClassifiedRecoveryError`:

```python
{
    "code": str,                         # Stable identifier e.g. "SERVICE_UNAVAILABLE"
    "category": str,                     # "transient_network", "timeout", "captcha_challenge", etc.
    "message": str,                      # Human-readable sanitized description
    "recoverable": bool,                 # Whether automated retry is permitted
    "requires_human": bool,              # Whether execution must pause for human intervention
    "is_uncertain_outcome": bool,        # Whether side effects may have already executed
    "retry_after_seconds": float | None, # Optional rate limit cooldown period
    "retry_guidance": str | None,        # Human or agent guidance
    "context": dict                      # Strictly sanitized diagnostic metadata (zero secrets)
}
```

### Action Idempotency Contract

| Action Category | Action Types | Repetition on Ambiguous Timeout |
|---|---|---|
| **Idempotent** | `inspect`, `navigate`, `extract_text`, `get_url_and_title`, `screenshot`, `find_trains`, `calculate_schedule`, `validate_plan` | **Permitted** (within retry budget) |
| **Non-Idempotent** | `click`, `type_text`, `press_key`, `execute_booking`, `confirm_payment` | **PROHIBITED** (triggers `UNKNOWN_OUTCOME` & pauses for human) |

### Circuit Breaker Contract

Integrations prone to repeated external failures (e.g. `train_comparison`, remote scrapers) expose circuit breaker metrics:

```python
{
    "name": str,
    "state": str,                       # "closed" | "open" | "half_open"
    "failure_count": int,               # Failures recorded in active sliding window
    "failure_threshold": int,           # Configured trip threshold
    "cooldown_remaining_seconds": float,# Seconds remaining before HALF_OPEN probe
    "half_open_probes_active": int,     # Number of test probes currently permitted
    "total_calls": int,
    "total_failures": int
}
```

When circuit breaker is `OPEN`, adapter calls fast-fail immediately with `CircuitBreakerOpenError` without initiating network I/O.

---

## G. Audit & Evidence Contracts (Phase 7)

### Audit Event Contract

All workflow and integration events recorded by subsystems conform to `AuditEventResponse`:

```python
{
    "id": str,                          # UUID4 identifier
    "task_id": str | None,              # Correlated task identifier
    "run_id": str | None,               # Correlated execution run identifier
    "correlation_id": str | None,       # Request/flow correlation ID
    "event_type": str,                  # e.g. "task.created", "tool.execution.success"
    "event_category": str,              # "TASK" | "RUN" | "TOOL" | "SKILL" | "RECOVERY" | "SECURITY" | "EVIDENCE"
    "timestamp": str,                   # ISO 8601 UTC timestamp
    "outcome": str,                     # "SUCCESS" | "FAILURE" | "WARNING" | "PENDING"
    "source": str,                      # Subsystem name (e.g. "task_service", "orchestrator")
    "tool_or_skill_name": str | None,   # Associated tool or skill name
    "error_code": str | None,           # Standardized error code
    "event_metadata": dict | None,      # Sanitized metadata (passwords, tokens, cards redacted)
    "evidence_references": list[str] | None, # Associated evidence UUIDs
    "schema_version": int               # Schema version (1)
}
```

### Evidence Artifact Contract

Stored artifacts and evidence metadata conform to `EvidenceResponse`:

```python
{
    "id": str,                          # Evidence record UUID
    "task_id": str | None,
    "run_id": str | None,
    "audit_event_id": str | None,
    "evidence_type": str,               # "SCREENSHOT" | "DOM_SNAPSHOT" | "EXECUTION_SUMMARY" | "ERROR_SNAPSHOT"
    "timestamp": str,                   # ISO 8601 UTC timestamp
    "file_path": str,                   # Safe relative path within artifact_dir
    "content_type": str,                # MIME type (e.g. "image/png", "application/json")
    "file_size_bytes": int,
    "sha256_checksum": str,             # 64-character hex cryptographic hash
    "capture_source": str,              # Originating adapter or tool
    "metadata_payload": dict | None,    # Sanitized descriptive metadata
    "integrity_status": str             # "VERIFIED" | "TAMPERED" | "MISSING"
}
```

### Evidence Verification Protocol

Clients can verify stored evidence against filesystem state via `POST /api/v1/evidence/{evidence_id}/verify`:
- Recalculates SHA-256 hash of the artifact on disk.
- Compares calculated checksum against stored `sha256_checksum`.
- Updates and returns `integrity_status` (`VERIFIED`, `TAMPERED`, or `MISSING`).

