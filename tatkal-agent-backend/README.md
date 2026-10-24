# Tatkal Agent Backend

Core backend infrastructure for the Tatkal Booking Agent — a general-purpose computer-use AI agent built for a hackathon. The agent's primary task is to book Tatkal train tickets, but the architecture is designed to be reusable for any computer-based automation task.

## Project Status

- **Phase 1 — Backend Foundation** ✅
- **Phase 2 — Task Management & State Machine** ✅
- **Phase 3 — Generic Agent Orchestration Core** ✅
- **Phase 4 — Tool Adapters & Skill System** ✅
- **Phase 5 — Teammate Module Integration, Backend Consolidation & Error Fixing** ✅
- **Phase 6 — Recovery and Resilience Engine** ✅
- **Phase 7 — Evidence, Audit, and Compliance** ✅
- **Phase 8 — Final Backend Hardening, Integration Completion, and Demo Readiness** ✅
- **Phase 9 — Full Frontend Integration, Real Railway Data Providers & Zero-Mock Architecture** ✅

The core backend infrastructure, persistent task & execution-run state machines, generic orchestrator loop, browser and desktop tool adapters, declarative skill system, teammate modules (Scheduler, Train Comparison, Security & Vault, Booking Assistance), centralized recovery engine, cryptographic evidence verification, and real Railway Data Providers (official open datasets, RapidAPI adapter, transparent caching, zero-mock production flows, and station directory) are fully implemented and verified with 417 passing automated tests.

---

## Technology Stack

| Component          | Technology                  |
|--------------------|-----------------------------|
| Language           | Python 3.12+                |
| Web Framework      | FastAPI                     |
| ASGI Server        | Uvicorn                     |
| Validation         | Pydantic v2                 |
| Configuration      | pydantic-settings           |
| Database           | SQLAlchemy 2.x + SQLite     |
| Testing            | pytest + httpx              |

## Prerequisites

- Python 3.12 or compatible (3.10+ should work)
- macOS (developed and tested on Mac)
- pip (included with Python)

## Setup

### 1. Clone and Navigate

```bash
cd tatkal-agent-backend
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed — defaults work for local development
```

### 5. Start the Server

```bash
uvicorn app.main:app --reload
```

The server starts at [http://127.0.0.1:8000](http://127.0.0.1:8000).

The database is initialised automatically on first startup.

### 6. API Documentation

| Interface  | URL                                      |
|------------|------------------------------------------|
| Swagger UI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)   |
| ReDoc      | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |

### 7. Run Tests

```bash
pytest -v
```

Tests use isolated temporary databases — no external services required.

---

## API Endpoints

### Health Check

```
GET /api/v1/health
```

**Response (healthy):**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "api_version": "v1",
    "database": "connected"
  },
  "message": "All systems operational"
}
```

**Response (degraded — HTTP 503):**
```json
{
  "success": false,
  "data": {
    "status": "degraded",
    "api_version": "v1",
    "database": "disconnected"
  },
  "message": "Database connectivity issue"
}
```

### Create a Task

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tatkal booking",
    "task_type": "train_booking",
    "description": "Book a Tatkal ticket",
    "configuration": {"source": "Delhi", "destination": "Mumbai", "passenger_count": 2}
  }'
```

### List Tasks

```bash
# All tasks (paginated)
curl http://127.0.0.1:8000/api/v1/tasks?page=1&page_size=10

# Filter by status
curl http://127.0.0.1:8000/api/v1/tasks?status=CREATED

# Filter by task type
curl http://127.0.0.1:8000/api/v1/tasks?task_type=train_booking
```

### Get a Task

```bash
curl http://127.0.0.1:8000/api/v1/tasks/{task_id}
```

### Get Task Status

```bash
curl http://127.0.0.1:8000/api/v1/tasks/{task_id}/status
```

### Transition a Task (Internal)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/{task_id}/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "READY"}'
```

### Cancel a Task

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/{task_id}/cancel
```

### Update Task Metadata

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/tasks/{task_id} \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated name", "configuration": {"key": "value"}}'
```

### Create an Execution Run

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/{task_id}/runs
```

### List Execution Runs for a Task

```bash
curl "http://127.0.0.1:8000/api/v1/tasks/{task_id}/runs?page=1&page_size=20"
```

### Get Execution Run Details

```bash
curl http://127.0.0.1:8000/api/v1/runs/{run_id}
```

### Pause an Execution Run

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runs/{run_id}/pause
```

### Resume an Execution Run

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runs/{run_id}/resume
```

### Cancel an Execution Run

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runs/{run_id}/cancel
```

### Transition an Execution Run (State Machine)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runs/{run_id}/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "RUNNING"}'
```

### Execute Run (Orchestrator Loop)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runs/{run_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"max_steps": 20, "timeout_seconds": 60.0}'
```

### List Registered Tools

```bash
curl http://127.0.0.1:8000/api/v1/tools
```

### Check Tool Health

```bash
curl http://127.0.0.1:8000/api/v1/tools/browser/health
```

### List Available Skills

```bash
curl http://127.0.0.1:8000/api/v1/skills
```

### Get Skill Definition

```bash
curl http://127.0.0.1:8000/api/v1/skills/browser_inspection
```

### List Registered Teammate Integrations

```bash
curl http://127.0.0.1:8000/api/v1/integrations
```

### Check Integration Circuit Breakers

```bash
curl http://127.0.0.1:8000/api/v1/integrations/circuit-breakers
```

### Compare & Rank Trains (Member 4)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/trains/compare \
  -H "Content-Type: application/json" \
  -d '{
    "source_station": "Roorkee",
    "destination_station": "Haridwar",
    "travel_date": "2026-11-20",
    "quota": "TATKAL"
  }'
```

### Calculate Tatkal Schedule Opening (Member 3)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/scheduler/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "journey_date": "2026-11-20",
    "travel_class": "3A",
    "reminder_minutes_before": 5
  }'
```

### Redact Sensitive Keys (Member 4)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/security/redact \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "username": "user1",
      "password": "mySecretPassword123",
      "passengerName": "Alice"
    }
  }'
```

### List Audit Events
```bash
curl "http://127.0.0.1:8000/api/v1/audit/events?page=1&page_size=20"
```

### List Audit Events for a Task or Run
```bash
curl "http://127.0.0.1:8000/api/v1/audit/tasks/{task_id}/events"
curl "http://127.0.0.1:8000/api/v1/audit/runs/{run_id}/events"
```

### List Evidence Artifacts
```bash
curl "http://127.0.0.1:8000/api/v1/evidence?page=1&page_size=20"
```

### Verify Cryptographic Integrity of Evidence
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/evidence/{evidence_id}/verify"
```

### Download Safe Evidence Artifact
```bash
curl "http://127.0.0.1:8000/api/v1/evidence/{evidence_id}/download" -O
```

---

## Railway Data Provider Endpoints (Phase 9)

### 1. Provider Status & Capability Reporting
```bash
curl http://127.0.0.1:8000/api/v1/railway/providers/status
```

### 2. Search Railway Stations
```bash
# Prefix, name, city, or state search
curl "http://127.0.0.1:8000/api/v1/railway/stations?q=NDLS&limit=5"
curl "http://127.0.0.1:8000/api/v1/railway/stations?q=Mumbai&limit=10"
```

### 3. Get Station Details
```bash
curl http://127.0.0.1:8000/api/v1/railway/stations/BCT
```

### 4. Query Authentic Trains Between Stations
```bash
curl "http://127.0.0.1:8000/api/v1/railway/trains/between?from_station=NDLS&to_station=MMCT&date=2026-11-01&travel_class=3A"
```

### 5. Stop-by-Stop Train Timetable
```bash
curl http://127.0.0.1:8000/api/v1/railway/trains/12952/schedule
```

### 6. Live Running Status Observation
```bash
# Returns truthful live telemetry if API key configured; otherwise truthful unavailable status
curl "http://127.0.0.1:8000/api/v1/railway/trains/12952/live?date=2026-11-01"
```

### 7. PNR Status Query (Strict Privacy Redaction)
```bash
curl http://127.0.0.1:8000/api/v1/railway/pnr/2849182371
```

---

## Railway Data Provider Capability Matrix

| Feature | Official IR Open Data | RapidAPI IRCTC Provider | Caching Policy |
| :--- | :--- | :--- | :--- |
| **Station Directory** | ✅ Supported (80+ hubs) | ✅ Supported | 7 Days TTL |
| **Train Timetables** | ✅ Supported (major sectors) | ✅ Supported | 24 Hours TTL |
| **Trains Between Stations** | ✅ Supported | ✅ Supported | 24 Hours TTL |
| **Official Passenger Fares** | ✅ Supported (IR rules) | ⚠️ Tier Dependent | 24 Hours TTL |
| **Live Running GPS Telemetry**| ❌ Unavailable | 🔑 Requires API Key | 2 Minutes TTL |
| **Seat Allocation Estimates** | ⚠️ Quota Estimates Only | 🔑 Requires API Key | 5 Minutes TTL |
| **PNR Inquiries** | ❌ Unavailable | 🔑 Requires API Key | 5 Minutes TTL |
| **Automated Booking Submission**| ⛔ Strictly Disabled | ⛔ Strictly Disabled | N/A |
| **Automated Live Payments** | ⛔ Strictly Disabled | ⛔ Strictly Disabled | N/A |

---

## Project Structure

```
tatkal-agent-backend/
├── app/
│   ├── main.py                  # FastAPI application entry point
│   ├── agent/                   # Generic agent orchestration core
│   │   ├── errors.py            # Typed agent & orchestrator errors
│   │   ├── llm/                 # Provider-agnostic LLM abstraction
│   │   │   └── base.py          # LLMClient, StructuredPlanner, FakePlanner
│   │   ├── models.py            # Plan, Step, Action, Observation, StepResult
│   │   ├── observer.py          # Observation interface & DefaultObserver
│   │   ├── orchestrator.py      # Core agent loop (Plan → Tool → Observe → Verify)
│   │   ├── recovery/            # Phase 6 Recovery and Resilience Engine
│   │   │   ├── circuit_breaker.py # Tri-state process-local circuit breaker & registry
│   │   │   ├── errors.py        # Standardized error taxonomy & exception classifier
│   │   │   ├── idempotency.py   # Operation idempotency registry & unknown-outcome tracker
│   │   │   └── policy.py        # Central recovery policy & bounded exponential backoff
│   │   ├── tool_executor.py     # Tool execution engine with registry lookup & retries
│   │   └── verifier.py          # Verifier interface & DeterministicVerifier
│   ├── api/                     # API routes
│   │   ├── router.py            # Versioned router (/api/v1)
│   │   ├── health.py            # Health-check endpoint
│   │   ├── tasks.py             # Task management endpoints
│   │   ├── runs.py              # Execution run endpoints
│   │   ├── tools.py             # Tool discovery & health endpoints
│   │   ├── skills.py            # Skill listing & inspection endpoints
│   │   ├── integrations.py      # Teammate integration & circuit-breaker endpoints
│   │   ├── audit.py             # Phase 7 Audit event query endpoints
│   │   └── evidence.py          # Phase 7 Evidence query, verify & download endpoints
│   ├── core/                    # Core infrastructure
│   │   ├── config.py            # Centralised configuration (Phase 1-7 settings)
│   │   ├── exceptions.py        # Exception hierarchy, BaseRecoveryError & Evidence error handlers
│   │   └── logging.py           # Structured logging setup
│   ├── database/                # Database layer
│   │   ├── base.py              # Declarative base
│   │   ├── session.py           # Engine, sessions, dependencies, and get_session context manager
│   │   └── init_db.py           # Table initialisation
│   ├── integrations/            # Integration contracts & registry
│   │   ├── contracts.py         # Typed protocols for teammates, tools, audit & evidence
│   │   ├── registry.py          # Adapter & tool DI registry
│   │   ├── booking/             # BookingAssistanceAdapter & safe plan generator
│   │   ├── scheduler/           # TatkalSchedulerAdapter & opening time calculator
│   │   ├── security/            # SecurityAdapter, deep recursive redaction, & SecureCredentialStore
│   │   └── train_comparison/    # TrainComparisonAdapter guarded by circuit breaker
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── task.py              # Task entity
│   │   ├── execution_run.py     # ExecutionRun entity
│   │   └── audit.py             # Phase 7 AuditEvent & EvidenceRecord entities
│   ├── schemas/                 # Pydantic response/request models
│   │   ├── common.py            # ApiResponse, HealthResponse
│   │   ├── task.py              # Task schemas
│   │   ├── run.py               # Run schemas
│   │   ├── audit.py             # Phase 7 Audit response schemas
│   │   └── evidence.py          # Phase 7 Evidence response & verify schemas
│   ├── services/                # Business logic & state machines
│   │   ├── task_service.py      # Task lifecycle service
│   │   ├── task_repository.py   # Task data access
│   │   ├── task_state_machine.py# Task state machine
│   │   ├── run_service.py       # Run lifecycle service
│   │   ├── run_repository.py    # Run data access
│   │   ├── run_state_machine.py # Run state machine
│   │   ├── audit_service.py     # Phase 7 Centralized audit recording & query service
│   │   └── evidence_service.py  # Phase 7 Atomic SHA-256 evidence storage & integrity verifier
│   ├── skills/                  # Skill definitions & execution engine
│   │   ├── definitions/         # Declarative YAML workflow definitions
│   │   ├── executor.py          # Skill execution engine
│   │   ├── loader.py            # YAML loader & schema validator
│   │   └── models.py            # SkillDefinition, SkillStep, SkillInput
│   ├── tools/                   # Tool adapters & artifact manager
│   │   ├── artifacts.py         # ArtifactManager (UUID screenshot storage)
│   │   ├── base.py              # BaseToolAdapter with schema validation
│   │   ├── browser/             # Browser automation adapter & drivers
│   │   └── desktop/             # Desktop automation adapter & drivers
│   ├── dependencies/            # FastAPI dependencies
│   └── utils/                   # Shared utilities
├── tests/                       # 390 automated tests (all phases 1–8 passing)
├── docs/                        # Architecture, integration, and manual testing plan
├── data/                        # Local SQLite database storage
├── artifacts/                   # Agent artefact & evidence storage
├── .env.example                 # Environment template
├── .gitignore                   # Git exclusions
├── requirements.txt             # Python dependencies
└── pytest.ini                   # Test configuration
```

---

## Phase 8 Pre-Frontend Limitations & Guarantees

The following are **explicit guarantees, verified capabilities, and intentional boundaries**:

- **End-to-End Backend Verification**: All backend components from task creation, run scheduling, orchestrator execution, tool dispatch, recovery handling, audit logging, to evidence verification are complete and verified with 390 automated tests and a documented [Manual Test Plan](docs/MANUAL_TEST_PLAN.md).
- **Liveness & Readiness Probes**: Separate probes are provided via `GET /api/v1/health/liveness` and `GET /api/v1/health/readiness` for container and process orchestrators.
- **Cascading Cancellations & Terminal Guards**: Cancelling a task cascades to cancel all active execution runs. Completed or cancelled runs cannot be re-executed.
- **Frontend Integration (Phase 9 Deferred)**: Web UI dashboards, task creation web interfaces, and WebSocket/SSE real-time streaming are reserved for Phase 9. Frontend files in the workspace remain completely untouched.
- **Anti-bot/CAPTCHA Evasion**: By design, automated CAPTCHA solving is strictly prohibited; detection pauses the run for human intervention (`WAITING_FOR_HUMAN`).
- **Payment Gateway Automation**: Live payment execution is strictly prohibited without explicit human authorization. No automated payment flows exist.
- **Train Catalog Source**: Train comparison uses static sample catalog data for demonstration; it does not connect to live IRCTC production servers.

See [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) and [docs/MANUAL_TEST_PLAN.md](docs/MANUAL_TEST_PLAN.md).

## Team

| Member | Responsibility                                  |
|--------|--------------------------------------------------|
| 1      | Frontend (UI, dashboards, task creation)         |
| 2      | Scheduler + Booking Assistance                   |
| 3      | Train Comparison + Security + Testing            |
| 4 (Me) | Core Backend + Integration + Orchestration       |

See [docs/INTEGRATION_CONTRACTS.md](docs/INTEGRATION_CONTRACTS.md) for API contracts between modules.
