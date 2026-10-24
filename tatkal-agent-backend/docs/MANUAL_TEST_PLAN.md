# Manual Test Plan & Pre-Frontend Verification Guide

**Project:** Tatkal Agent Backend  
**Phase:** Phase 8 — Final Backend Hardening, Integration Completion, and Demo Readiness  
**Target Audience:** Developer / QA Engineer conducting manual backend verification before Phase 9 frontend integration.

---

> [!IMPORTANT]
> **Safety Notice:**
> - Live unattended IRCTC booking submission is **strictly disabled**.
> - Live payment execution is **strictly disabled**.
> - Automated CAPTCHA solving / bypass is **strictly prohibited**.
> - Tests must use mock fixtures or safe sandbox inputs. Do not submit real IRCTC bookings or payment authorizations.

---

## Overview

This document specifies the complete manual verification procedure for the Tatkal Agent Backend. All steps must be executed against a running instance before proceeding to Phase 9 frontend integration.

---

## A. Environment Checks

### A.1 Python Environment & Dependencies
1. Verify Python version is 3.10+ (tested on Python 3.12 / 3.15):
   ```bash
   ./venv/bin/python --version
   ```
   *Expected:* Output indicates Python 3.10+.
2. Verify all dependencies are installed:
   ```bash
   ./venv/bin/pip check
   ```
   *Expected:* "No broken requirements found."

### A.2 Configuration & Storage Directories
1. Verify `.env` exists and contains development defaults:
   ```bash
   ls -la .env
   ```
   *Expected:* `.env` exists and contains local port, host, and database URL.
2. Verify storage directories exist:
   ```bash
   ls -d data artifacts artifacts/evidence
   ```
   *Expected:* All directories exist.

### A.3 Server Startup & Swagger UI
1. Start the server (if not already running):
   ```bash
   ./venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   *Expected:* Server starts without import errors and logs "Application startup complete".
2. Open Swagger UI in browser:
   * URL: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   *Expected:* OpenAPI documentation loads, displaying endpoints under `Health`, `Tasks`, `Runs`, `Tools`, `Skills`, `Integrations`, `Audit`, and `Evidence`.

### A.4 Health, Liveness, and Readiness
1. Check standard health endpoint:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/health | jq .
   ```
   *Expected:* `status: "ok"`, `database: "connected"`, HTTP 200.
2. Check process liveness probe:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/health/liveness | jq .
   ```
   *Expected:* `status: "alive"`, HTTP 200.
3. Check subsystem readiness probe:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/health/readiness | jq .
   ```
   *Expected:* `status: "ready"`, `database: "connected"`, `storage: "ready"`, `tool_registry: "ready"`, HTTP 200.

---

## B. Task and Execution Run Lifecycle

### B.1 Valid Task Creation & Retrieval
1. Create a task:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/tasks \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Delhi to Mumbai Tatkal",
       "task_type": "train_booking",
       "description": "Book 3A ticket for 2 passengers",
       "configuration": {"source": "NDLS", "destination": "BCT", "travel_date": "2026-11-20"}
     }' | jq .
   ```
   *Expected:* HTTP 201, task in `CREATED` status, unique UUID returned. Note `task_id`.
2. Retrieve the task by ID:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/tasks/{task_id} | jq .
   ```
   *Expected:* HTTP 200, matching name and configuration.

### B.2 Execution Run Creation & Execution
1. Create a run for the task:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/tasks/{task_id}/runs | jq .
   ```
   *Expected:* HTTP 201, run in `PENDING` status. Note `run_id`.
2. Execute the run through the agent orchestrator:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/runs/{run_id}/execute | jq .
   ```
   *Expected:* HTTP 200, run status transitions to `COMPLETED`.
3. Check task status:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/tasks/{task_id} | jq .
   ```
   *Expected:* Task status is `COMPLETED`.

### B.3 Terminal Immutability Guards
1. Attempt to re-execute the completed run:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/runs/{run_id}/execute | jq .
   ```
   *Expected:* HTTP 409 Conflict. Completed runs cannot be re-executed.

### B.4 Task Cancellation Cascade
1. Create a fresh task and run:
   ```bash
   TASK2_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/tasks -H "Content-Type: application/json" -d '{"name": "Cancel Test", "task_type": "test"}' | jq -r .data.id)
   RUN2_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/tasks/$TASK2_ID/runs | jq -r .data.id)
   ```
2. Cancel the task:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/tasks/$TASK2_ID/cancel | jq .
   ```
   *Expected:* HTTP 200, task status is `CANCELLED`.
3. Inspect the run:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/runs/$RUN2_ID | jq .
   ```
   *Expected:* Run status was automatically cascaded to `CANCELLED`.

---

## C. Tools and Skills

### C.1 Tool Listing & Health
1. List all registered tool adapters:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/tools | jq .
   ```
   *Expected:* List contains `browser` and `desktop` tools with capabilities.
2. Check browser tool health:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/tools/browser/health | jq .
   ```
   *Expected:* `healthy: true`, status 200.

### C.2 Skills Listing & Inspection
1. List registered skills:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/skills | jq .
   ```
   *Expected:* Declarative skills (e.g. `browser_inspection`) listed.
2. Get skill definition:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/skills/browser_inspection | jq .
   ```
   *Expected:* Steps, input schemas, and required tools returned.

---

## D. Recovery & Resilience

### D.1 Circuit Breaker Status
1. Retrieve circuit breaker metrics:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/integrations/circuit-breakers | jq .
   ```
   *Expected:* All registered circuit breakers reported in `CLOSED` state with 0 failure counts.

### D.2 Unknown-Outcome Idempotency
1. Check that repeated non-idempotent actions cannot be blindly retried:
   * Check logs for `is_action_idempotent` evaluations during orchestrator retries.

---

## E. Audit and Evidence

### E.1 Audit Trail Verification
1. List audit events for the task created in B.1:
   ```bash
   curl -s "http://127.0.0.1:8000/api/v1/audit/tasks/{task_id}/events" | jq .
   ```
   *Expected:* Complete chronological sequence of events: `task.created` -> `run.created` -> `task.ready` -> `task.running` -> `run.running` -> `run.completed` -> `task.completed`.
2. Verify secret redaction:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/security/redact \
     -H "Content-Type: application/json" \
     -d '{"payload": {"password": "SecretPass123", "card_number": "4111111111111234", "otp": "987654"}}' | jq .
   ```
   *Expected:* Sensitive keys replaced with `[REDACTED]`.

### E.2 Evidence Artifact & Cryptographic Integrity
1. List evidence records:
   ```bash
   curl -s "http://127.0.0.1:8000/api/v1/evidence?task_id={task_id}" | jq .
   ```
   *Expected:* `EXECUTION_SUMMARY` evidence record with relative storage path and SHA-256 digest. Note `evidence_id`.
2. Verify cryptographic checksum:
   ```bash
   curl -s -X POST "http://127.0.0.1:8000/api/v1/evidence/{evidence_id}/verify" | jq .
   ```
   *Expected:* `status: "VERIFIED"`, `valid: true`.
3. Download artifact safely:
   ```bash
   curl -s "http://127.0.0.1:8000/api/v1/evidence/{evidence_id}/download" | jq .
   ```
   *Expected:* Complete JSON execution summary with step records.

---

## F. Integration Behavior & Train Catalog

### F.1 Train Comparison & Ranking
1. Compare trains on standard test route:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/trains/compare \
     -H "Content-Type: application/json" \
     -d '{
       "source_station": "Roorkee",
       "destination_station": "Haridwar",
       "travel_date": "2026-11-20",
       "quota": "TATKAL"
     }' | jq .
   ```
   *Expected:* Static sample catalog trains returned, ranked with verified availability first.
   *Note:* Train data is based on static catalog fixtures, **not live IRCTC production data**.

### F.2 Tatkal Scheduler Calculator
1. Calculate Tatkal opening timings:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/scheduler/calculate \
     -H "Content-Type: application/json" \
     -d '{
       "journey_date": "2026-11-20",
       "travel_class": "3A",
       "reminder_minutes_before": 5
     }' | jq .
   ```
   *Expected:* Opening time calculated as 10:00 AM IST on departure day minus 1, with pre-alert at 09:55 AM IST. Both IST and UTC timestamps returned.

---

## G. Security & Path Traversal Protections

### G.1 Path Traversal Rejection
1. Attempt path traversal on evidence download:
   ```bash
   curl -s "http://127.0.0.1:8000/api/v1/evidence/../../etc/passwd" -i
   ```
   *Expected:* HTTP 404 or 422. No arbitrary filesystem paths can be read.

### G.2 Prohibited Actions Enforcement
1. Test automated payment prohibition:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/security/check \
     -H "Content-Type: application/json" \
     -d '{"action": "auto_approve_payment", "actor": "agent"}' | jq .
   ```
   *Expected:* `allowed: false`, reason mentions security policy prohibition.
2. Test CAPTCHA bypass prohibition:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/security/check \
     -H "Content-Type: application/json" \
     -d '{"action": "captcha_bypass", "actor": "agent"}' | jq .
   ```
   *Expected:* `allowed: false`, strictly prohibited.

---

## H. Safety Boundaries

### H.1 Booking Execution Enforces Human Handoff
1. Execute booking plan:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/booking/execute \
     -H "Content-Type: application/json" \
     -d '{
       "task_id": "test-safety-check",
       "passenger_count": 2,
       "journey_details": {"train_number": "12001", "travel_date": "2026-11-20", "travel_class": "3A"}
     }' | jq .
   ```
   *Expected:* `success: false`, `requires_human: true`. Live booking paused before payment. Human checkpoints include `captcha_verification` and `payment_authorization`.

---

## I. Final Readiness Checklist

| Test ID | Test Objective | Preconditions | Steps | Expected Result | Actual Result | Pass/Fail | Notes |
|---|---|---|---|---|---|---|---|
| **ENV-01** | Python 3.10+ and dependency check | Virtualenv activated | `python --version`, `pip check` | Clean dependencies, supported version | Pending | [ ] | |
| **ENV-02** | Database & directories initialisation | Fresh or dev database | Check `tatkal_agent.db`, `data/`, `artifacts/` | Files present, tables created | Pending | [ ] | |
| **ENV-03** | Server startup & Swagger | Port 8000 open | Start Uvicorn, visit `/docs` | OpenAPI UI loads all routes | Pending | [ ] | |
| **ENV-04** | Health probes (Live/Ready) | Server running | `GET /health`, `/liveness`, `/readiness` | 200 OK across all probes | Pending | [ ] | |
| **LIF-01** | Task creation and retrieval | Server running | `POST /tasks`, `GET /tasks/{id}` | Task created with `CREATED` status | Pending | [ ] | |
| **LIF-02** | Run creation and execution | Task created | `POST /tasks/{id}/runs`, `POST /runs/{id}/execute` | Run transitions through loop to `COMPLETED` | Pending | [ ] | |
| **LIF-03** | Re-execution rejection | Run completed | `POST /runs/{id}/execute` | 409 Conflict, cannot re-execute terminal run | Pending | [ ] | |
| **LIF-04** | Cascading cancellation | Task & run active | `POST /tasks/{id}/cancel` | Both task and active run are `CANCELLED` | Pending | [ ] | |
| **TOL-01** | Tool discovery and health | Server running | `GET /tools`, `GET /tools/browser/health` | Browser and desktop listed and healthy | Pending | [ ] | |
| **SKL-01** | Declarative skill loading | YAML definitions loaded | `GET /skills`, `GET /skills/browser_inspection` | Valid skill workflows returned | Pending | [ ] | |
| **REC-01** | Circuit breakers operational | Server running | `GET /integrations/circuit-breakers` | Breakers in `CLOSED` state | Pending | [ ] | |
| **AUD-01** | Structured audit event trail | Run executed | `GET /audit/tasks/{id}/events` | Chronological lifecycle trail persisted | Pending | [ ] | |
| **AUD-02** | Deep secret redaction | Server running | `POST /security/redact` | Passwords, cards, OTPs redacted | Pending | [ ] | |
| **EVI-01** | Cryptographic SHA-256 verification | Artifact stored | `POST /evidence/{id}/verify` | `VERIFIED` and `valid: true` | Pending | [ ] | |
| **EVI-02** | Safe artifact download | Evidence verified | `GET /evidence/{id}/download` | Binary stream matches checksum | Pending | [ ] | |
| **SEC-01** | Prohibited actions rejection | Server running | `POST /security/check` with `auto_approve_payment` | Blocked by security policy | Pending | [ ] | |
| **SAF-01** | Booking requires human approval | Server running | `POST /booking/execute` | Pauses for human CAPTCHA and payment | Pending | [ ] | |
| **SAF-02** | Live payment disabled | Architecture guard | Attempt live payment execution | No automated execution path exists | Pending | [ ] | |
| **AUT-01** | 12-point pre-flight diagnostics | Task configured | `POST /tasks/{id}/prepare` | 12 checks evaluated, report persisted | Passed (Automated) | [x] | |
| **AUT-02** | Tatkal window calculation | AC vs Non-AC | Check 10:00 vs 11:00 AM calculation | Exactly 1 day prior at 10/11 AM IST | Passed (Automated) | [x] | |
| **AUT-03** | CAPTCHA safety halt (Step 4) | Autonomous run | Execute run past step 3 | Halts at Step 4 `WAITING_FOR_HUMAN` | Passed (Automated) | [x] | |
| **AUT-04** | Payment boundary halt (Step 6) | Run resumed | Execute run past step 5 | Halts at Step 6 `AWAITING_PAYMENT_APPROVAL` | Passed (Automated) | [x] | |
| **AUT-05** | Persistent scheduler engine | Server running | `POST /tasks/{id}/schedule` | Background scheduler triggers execution | Passed (Automated) | [x] | |

---

## J. Autonomous Tatkal Agent Manual Verification Procedures

### J.1 12-Point Pre-Flight Diagnostics
1. Configure a safe test journey with origin `NDLS`, destination `BCT`, travel class `3A`, and 2 passengers.
2. In the UI or via curl, trigger preparation:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/tasks/{TASK_ID}/prepare | jq .
   ```
3. Verify that:
   - All 12 checks are evaluated.
   - Authority provenance is reported as `STATIC_DATASET` / `official_open_data`.
   - The 7-step proposed execution plan is returned with Step 4 and Step 6 marked as human intervention boundaries.

### J.2 Persistent Background Scheduling
1. Schedule the task for an upcoming Tatkal window:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/tasks/{TASK_ID}/schedule \
     -H "Content-Type: application/json" \
     -d '{"execute_at": "2026-12-19T10:00:00+05:30"}' | jq .
   ```
2. Verify task status transitions to `SCHEDULED`.
3. Verify unscheduling sets task back to `IDLE`:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/tasks/{TASK_ID}/unschedule | jq .
   ```

### J.3 Autonomous Goal Execution & Safety Halts
1. Create a run for the task:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/tasks/{TASK_ID}/runs | jq .
   ```
2. Execute the run slice:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/runs/{RUN_ID}/execute \
     -H "Content-Type: application/json" \
     -d '{"max_steps": 10}' | jq .
   ```
3. Verify that:
   - Browser navigation, inspection, and station typing execute.
   - Run halts at Step 4 with status `WAITING_FOR_HUMAN` due to CAPTCHA challenge.
   - Anti-bot bypass is NOT attempted.
4. Resume the run after simulating operator solving:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/v1/runs/{RUN_ID}/resume | jq .
   curl -s -X POST http://127.0.0.1:8000/api/v1/runs/{RUN_ID}/execute \
     -H "Content-Type: application/json" \
     -d '{"max_steps": 10}' | jq .
   ```
5. Verify that:
   - Run halts at Step 6 with status `WAITING_FOR_HUMAN` and reason `PAYMENT_STAGE_REACHED`.
   - Parent task transitions to `AWAITING_PAYMENT_APPROVAL`.
   - Automated payment execution remains DISABLED.

