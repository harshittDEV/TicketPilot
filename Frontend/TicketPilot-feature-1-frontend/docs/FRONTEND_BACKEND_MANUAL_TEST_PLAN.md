# FRONTEND & BACKEND INTEGRATED MANUAL TEST PLAN (PHASE 9)

**Project:** Tatkal Agent — General-Purpose Computer-Use Agent with a Railway Booking Assistance Use Case  
**Target Environment:** Local macOS / Linux Developer Workstation  
**Backend:** FastAPI (Python 3.10+ / 3.15, SQLAlchemy, SQLite, Pydantic v2) on `http://127.0.0.1:8000`  
**Frontend:** Next.js 14 (App Router, TypeScript, Tailwind CSS, Lucide React) on `http://localhost:3001`  
**Document Version:** Phase 9 Release Candidate  

---

## 1. Prerequisites & System Dependencies

- **Node.js:** v18.0.0 or higher (Verified on v26.12.0 with npm 11.20.0)
- **Python:** 3.10 to 3.15 (Virtualenv at `tatkal-agent-backend/venv`)
- **Web Browser:** Google Chrome, Brave, Safari, or Chromium with WebGL support
- **Terminal Shell:** bash or zsh

---

## 2. Environment Configuration

### Backend (`tatkal-agent-backend`)
File: `tatkal-agent-backend/.env` (or defaults in `app/core/config.py`)
```env
HOST=127.0.0.1
PORT=8000
APP_ENV=development
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///data/tatkal_agent.db
ALLOWED_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:3001","http://127.0.0.1:3001","http://localhost:5173","http://127.0.0.1:5173"]
```

### Frontend (`Frontend/TicketPilot-feature-1-frontend`)
File: `Frontend/TicketPilot-feature-1-frontend/.env.local`
```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_DEMO_MODE=false
```

---

## 3. Service Startup Commands

Run each service in its own dedicated terminal window:

### Terminal 1: Backend Server
```bash
cd ~/TicketPIlot/tatkal-agent-backend
source venv/bin/activate
./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Expected log output:*
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2: Frontend Server
```bash
cd ~/TicketPIlot/Frontend/TicketPilot-feature-1-frontend
npm run dev
# OR for production mode:
# npm run build && npm run start
```
*Expected terminal output:*
```
- Ready in 400ms
- Local: http://localhost:3001
```

---

## 4. Local URLs & Endpoints

| Component | Local URL | Role |
|---|---|---|
| **Frontend Web Application** | `http://localhost:3001` | Mission Control, Orchestrator, Booking Desk, Audit |
| **Backend REST API Root** | `http://127.0.0.1:8000/api/v1` | FastAPI v1 Router |
| **Backend Health Endpoint** | `http://127.0.0.1:8000/api/v1/health` | System & Database Health Check |
| **Interactive API Documentation** | `http://127.0.0.1:8000/docs` | Swagger / OpenAPI Spec Inspector |
| **OpenAPI Raw Specification** | `http://127.0.0.1:8000/openapi.json` | JSON Schema for All 41 Endpoints |

---

## 5. Comprehensive Step-by-Step Verification Checklist

### Step 1: Health & API Connectivity
- [ ] Open `http://localhost:3001` in your browser.
- [ ] Verify the header banner displays:
  `FASTAPI BACKEND ONLINE • v1 • DB CONNECTED` with a pulsating green indicator.
- [ ] Click "Check Status" in the top bar to verify live round-trip latency.
- [ ] Verify the API Health badge in the top right reads: `API Online`.

### Step 2: Spatial 3D Execution Pipeline Visualizer
- [ ] Observe the 3D pipeline hero section on the Mission Control dashboard.
- [ ] Move mouse across the visualizer: verify cards tilt smoothly in 3D perspective.
- [ ] Click the "3D Spatial View / Flat 2D View" toggle: verify immediate, stable transition to flat 2D layout without layout shifts.
- [ ] Verify all 5 pipeline stages are clearly visible:
  1. `Observer` (State Perception)
  2. `Planner` (Skill Synthesis)
  3. `Verifier` (Safety Guardrails)
  4. `Tool Adapter` (Execution Engine)
  5. `Human Gate` (Resilience & Handoff)

### Step 3: Task Creation & Persistence
- [ ] Scroll to the **Agent Execution & Run Control** section.
- [ ] Click **"+ New Task"**.
- [ ] Fill in:
  - Task Name: `Tatkal Mumbai Rajdhani Verification`
  - Origin: `NDLS - New Delhi`
  - Destination: `BCT - Mumbai Central`
  - Travel Date: select a future date (e.g. +2 days)
  - Class: `3A`
  - Passengers: `2`
- [ ] Click **"Submit Task to Backend"**.
- [ ] Verify that the task is immediately created, displayed in the task queue on the left, and assigned a persistent UUID and status `READY` or `CREATED`.
- [ ] Refresh the browser page (`Cmd+R` / `F5`) and confirm the task persists from the SQLite database.

### Step 4: Execution Run Lifecycle & Stepping
- [ ] Select the newly created task from the left task queue.
- [ ] In the right-hand inspection card, click **"Launch New Run"**.
- [ ] Confirm a new execution run appears with status `CREATED` or `RUNNING`.
- [ ] Click **"Execute Next Step"**:
  - Verify the step executes via `POST /api/v1/runs/{id}/execute`.
  - Verify the completed steps counter increments.
- [ ] Test the **"Pause Run"** button: confirm status transitions to `PAUSED`.
- [ ] Test the **"Resume Run"** button: confirm status transitions back to `RUNNING`.
- [ ] Test the **"Cancel"** button: confirm status transitions to `CANCELLED`.

### Step 5: Tools & Declarative Skills System
- [ ] Scroll to the **Tools & Declarative Skills System** section.
- [ ] Verify that all registered tool adapters are displayed:
  - `browser` (Available)
  - `desktop` (Unavailable / Requires display permissions)
  - `scheduler` (Available)
  - `security` (Available)
  - `train_comparison` (Available)
  - `booking_assistance` (Available)
- [ ] Click **"Run Diagnostics"** on the `browser` tool: verify live health diagnostic JSON returns `{"available": true}`.
- [ ] Scroll to Declarative Skills: select `browser_inspection`.
- [ ] Verify the 4 declarative steps are rendered with tool actions, parameters, and expected outcomes.
- [ ] Verify the **Resilience & Circuit Breakers** cards display current failure counts and `CLOSED` states.

### Step 6: Tatkal Countdown & Scheduler Calculation
- [ ] Scroll to the **Tatkal Opening Window & Journey Readiness** section.
- [ ] Verify the countdown widget renders with days, hours, minutes, and seconds.
- [ ] Confirm the opening time is formatted correctly:
  - `10:00 AM IST` for AC classes (`1A`, `2A`, `3A`, `3E`, `CC`, `EC`).
  - `11:00 AM IST` for Non-AC classes (`SL`, `2S`).
- [ ] Verify that the schedule calculation source states:
  `Calculated via Member 3 Tatkal Scheduler for [DATE] ([CLASS])`.

### Step 7: Train Intelligence & Timetable Comparison
- [ ] Click **"Train Intelligence"** in the top navigation bar (`/trains`).
- [ ] Select or switch sectors in the sector dropdown.
- [ ] Confirm the train candidate comparison table displays:
  - Train numbers and train names
  - Departure and arrival timings
  - Total Tatkal fares (base fare + Tatkal surcharge)
  - Availability status badges
  - Recommendation explanation badges (e.g. `TOP_RECOMMENDATION`)
- [ ] Test sorting by duration and sorting by fare.

### Step 8: Assisted Booking Desk & Human-in-the-Loop Gate
- [ ] Click **"Assisted Booking"** in the top navigation bar (`/booking`).
- [ ] Click **"Generate Plan"**:
  - Verify the backend `POST /api/v1/booking/plan` endpoint returns 5 steps:
    1. `login_and_navigate` (Automated)
    2. `train_selection` (Automated)
    3. `passenger_entry` (Automated)
    4. `captcha_verification` (Human Required)
    5. `payment_authorization` (Human Required)
- [ ] Click **"Execute Assisted Booking (Stops at Human Gate)"**:
  - Verify execution pauses immediately before sensitive operations.
  - Verify the prominent **Human Intervention Gate** appears.
  - Verify clear warnings: automated payment execution and automated CAPTCHA bypass are disabled.
- [ ] Verify that the "Confirm & Resume" button is disabled until the operator checks the verification checkbox.
- [ ] Fill out the "Record Official Booking Outcome" form:
  - Select status `CONFIRMED`.
  - Enter a valid 10-digit PNR: `284-9182371`.
  - Enter booking notes.
  - Click **"Save Verified Outcome Record"**.
  - Confirm the record is saved.

### Step 9: Audit Trail & Cryptographic Evidence Inspector
- [ ] Click **"Audit & Evidence"** in the top navigation bar (`/history`).
- [ ] Verify the **Audit Trail** tab lists immutable events with UTC timestamps, event types, categories (`TASK`, `RUN`, `TOOL`, `SKILL`, `RECOVERY`), and outcomes (`SUCCESS`, `BLOCKED`).
- [ ] Switch between category filters (`TASK`, `RUN`, `TOOL`, `SKILL`, `RECOVERY`): confirm the table filters accordingly.
- [ ] Click the **"Evidence Artifacts"** tab.
- [ ] Locate an evidence artifact (e.g. `EXECUTION_SUMMARY` or `SCREENSHOT`).
- [ ] Click **"Verify SHA-256"**:
  - Verify the backend verifies the file hash on disk.
  - Verify the status badge displays `VERIFIED` (or `MISSING`/`TAMPERED` if the file was modified).
- [ ] Click the download icon button:
  - Confirm the file streams securely via `/api/v1/evidence/{id}/download` with strict path traversal prevention.

### Step 10: Backend Disconnection & Error Handling
- [ ] In Terminal 1, stop the backend temporarily using `Ctrl+C`.
- [ ] In the browser, click "Check Status" in the banner.
- [ ] Confirm the banner switches to:
  `BACKEND OFFLINE • LOCAL DEMO MODE` with an amber warning.
- [ ] Confirm the UI does NOT crash or white-screen. Form inputs remain usable, and polite network failure messages are displayed rather than fake successes.
- [ ] In Terminal 1, restart the backend (`./venv/bin/uvicorn app.main:app --port 8000`).
- [ ] In the browser, click "Check Status": confirm the green `FASTAPI BACKEND ONLINE` badge restores immediately.

### Step 11: Responsiveness & Keyboard Navigation
- [ ] Resize the browser window to mobile width (<640px):
  - Confirm the desktop navigation collapses into the hamburger menu drawer.
  - Confirm all grid layouts stack vertically without horizontal clipping or scroll traps.
- [ ] Use `Tab` and `Shift+Tab` to navigate through interactive elements:
  - Confirm the "Skip to main content" link appears at the top on first focus.
  - Confirm clear emerald focus rings outline focused buttons and inputs.
- [ ] Test in Safari / Chrome with reduced motion enabled in macOS Accessibility settings:
  - Confirm all transitions and 3D tilts respect `prefers-reduced-motion`.

---

## 6. Safety & Ethical Restrictions Audit

- **Live Payment Execution:** Strictly disabled. No button, API endpoint, or agent tool initiates a financial transaction.
- **Unattended Live Booking:** Strictly disabled. No automated submission is dispatched to live IRCTC checkout.
- **CAPTCHA Bypass:** Strictly prohibited. Anti-bot barriers halt execution in `WAITING_FOR_HUMAN` state.
- **Data Privacy:** Client storage never logs card CVVs, netbanking PINs, or IRCTC passwords.

---

## 7. Pass / Fail Verification Sign-off Table

| Check ID | Verification Area | Tester | Result | Notes |
|---|---|---|---|---|
| TC-01 | Backend Startup & Health Probe (`/api/v1/health`) | Developer | [ ] PASS / [ ] FAIL | |
| TC-02 | Frontend Production Build & Server Start (port 3001) | Developer | [ ] PASS / [ ] FAIL | |
| TC-03 | Apple Glassmorphism Aesthetic & Translucent Cards | Developer | [ ] PASS / [ ] FAIL | |
| TC-04 | 3D Spatial Pipeline Visualizer & 2D Fallback | Developer | [ ] PASS / [ ] FAIL | |
| TC-05 | Task Creation & SQLite Database Persistence | Developer | [ ] PASS / [ ] FAIL | |
| TC-06 | Execution Run Stepping, Pause, Resume, and Cancel | Developer | [ ] PASS / [ ] FAIL | |
| TC-07 | Tools Discovery & Browser Tool Health Diagnostics | Developer | [ ] PASS / [ ] FAIL | |
| TC-08 | Declarative Skills Inspection (`browser_inspection`) | Developer | [ ] PASS / [ ] FAIL | |
| TC-09 | Tatkal Countdown Calculation via Scheduler Adapter | Developer | [ ] PASS / [ ] FAIL | |
| TC-10 | Train Candidate Timetable Comparison & Ranking | Developer | [ ] PASS / [ ] FAIL | |
| TC-11 | Booking Plan Generation (5 steps with checkpoints) | Developer | [ ] PASS / [ ] FAIL | |
| TC-12 | Human-in-the-Loop Intervention Gate (`WAITING_FOR_HUMAN`) | Developer | [ ] PASS / [ ] FAIL | |
| TC-13 | Immutable Audit Trail Filtering by Category | Developer | [ ] PASS / [ ] FAIL | |
| TC-14 | Evidence Cryptographic SHA-256 Verification | Developer | [ ] PASS / [ ] FAIL | |
| TC-15 | Safe Controlled Evidence File Download | Developer | [ ] PASS / [ ] FAIL | |
| TC-16 | Backend Disconnection Recovery & Fallback | Developer | [ ] PASS / [ ] FAIL | |
| TC-17 | Responsive Mobile Layout & Hamburger Drawer | Developer | [ ] PASS / [ ] FAIL | |
| TC-18 | Payment Disabled & CAPTCHA Compliance Sign-off | Developer | [ ] PASS / [ ] FAIL | |
