# Tatkal Assistant — Personal Railway Booking Preparation & Readiness Desk

> **Member 1 (Frontend Engineer & UI Architect)**  
> Next.js 14 (App Router) • React 18 • TypeScript • Tailwind CSS • Lucide React

Tatkal Assistant is a personal Indian Railways Tatkal preparation and booking-assistance application. It helps travelers organize upcoming journeys, calculate the configured Tatkal opening countdown (10:00 AM IST for AC classes, 11:00 AM IST for Non-AC classes), review authorized train comparisons and recommendations, run through an interactive readiness checklist, safely launch the official IRCTC booking portal, and record booking outcomes and PNR references.

---

## 🌟 Visual Direction: Bright 3D Glass Travel Workspace

The user interface follows a modern glassmorphic travel-planning aesthetic:
- **Color Palette**: Warm ivory/pearl background (`#FAF8F5`), lightly translucent white glass surfaces (`rgba(255, 255, 255, 0.78)`), deep ink text (`#18221D`), botanical emerald accents (`#1B5E3C`), soft sky blue (`#0284C7`), warm coral highlights (`#E05D44`), and muted lavender (`#7C6A96`).
- **3D Depth & Elevation**: Multi-layered surfaces with soft glass shadows, subtle highlight borders (`inset 0 1px 0 0 rgba(255, 255, 255, 0.95)`), and gentle hover lifts.
- **Single-Axis Vertical Navigation**: Native, unobstructed vertical scrolling with smooth in-page transitions. No horizontal overflow, no scroll-jacking, and no forced snap points.
- **Accessibility & Reduced Motion**: Full `prefers-reduced-motion` support, visible high-contrast focus rings (`:focus-visible`), text-first status indicators, and screen-reader ARIA live announcements for countdown milestones (no second-by-second audio spam).

---

## 🏗️ Team Ownership & Architecture Boundaries

This application is built by a four-member engineering team:

| Team Member | Role & Module | Responsibilities & Boundaries |
|:---|:---|:---|
| **Member 1 (This Module)** | **Frontend & UI Architecture** | Pages (`/`, `/trips`, `/trains`, `/booking`, `/history`, `/settings`, `/threeui-preview`), forms, UI state, countdown widget, typed API client, demo adapter, accessibility, visual design system. |
| **Member 2** | **Backend & Persistence** | Express APIs, SQLite database, persistence models, backend validation, data deletion endpoints, and receipt/proof reference storage. |
| **Member 3** | **Scheduler & Timing Engine** | Authoritative opening-time calculation, train-origin departure date offsets, system notifications, missed-reminder recovery, and scheduling daemon. |
| **Member 4** | **Comparison & Security QA** | Train timetable data ingestion, quota allocations, multi-objective comparison scoring, recommendation generation, and security checks. |

---

## 🔒 Security & IRCTC Compliance Boundaries

Tatkal Assistant is strictly a **preparation tool**. It never promises guaranteed ticket confirmation.
- **Never Implemented**:
  - No automated IRCTC login or bot sessions.
  - No automated form submissions or booking scripts.
  - No CAPTCHA or OTP bypass mechanisms.
  - No storage or transmission of IRCTC passwords, Aadhaar OTPs, credit/debit card numbers, CVVs, or UPI PINs.
- **User-Controlled Official Booking**:
  - Clicking the **"Open Official IRCTC Portal"** button securely launches `https://www.irctc.co.in/` with `rel="noopener noreferrer"`.
  - All credentials and payments are entered by the user directly on the official IRCTC portal.
  - Opening the IRCTC link **never** marks a trip as booked, does not infer payment success, and does not invent confirmed PNRs.

---

## 🎨 ThreeUI Component Integration Status

### Registered Component
- **Component**: `MengToSketchbookLandingPage`
- **Package**: `@designcodeio/threeui`
- **Canonical HTML URL**: `https://threeui.com/landing-pages/meng-to-sketchbook.html`
- **Registered Source Bundle**: `https://threeui.com/source-code/meng-to-sketchbook-landing-page.json`
- **Provided Source Revision Identifier**: `SHA-256 e0330548b1ac`

### Files Extracted & Maintained
1. `src/shaders/landing-pages/LandingPages.tsx` (Complete source bundle)
2. `src/shaders/landing-pages/pageTypography.ts` (Controls & font specifications)
3. `src/shaders/landing-pages/pageRecipes.ts` (Theme recipes)
4. `src/shaders/landing-pages/LandingPageFrame.tsx` (Sandboxed iframe frame component)
5. `public/landing-pages/meng-to-sketchbook.html` (Canonical source HTML)
6. `src/shaders/threeui.css` (Shared ThreeUI stylesheet)

### Architectural Reconciliation & Isolation Policy
- The original ThreeUI component depicts a Singapore sketchbook portfolio with landmark illustrations. 
- In strict adherence to product boundaries, **the original sketchbook template is preserved separately in isolation** (`/threeui-preview`) and is **never** disguised as functional Tatkal railway product content.
- Template CSS is isolated inside the frame container to avoid polluting functional railway dashboard styles.

---

## 🔌 API Integration: Proposed vs. Verified Contracts

The frontend uses a typed API service layer (`lib/api.ts`) supporting both **Live API** and **Transparent Demo Mode**:

| Endpoint | Method | Status | Payload / Return Type |
|:---|:---|:---|:---|
| `/trips` | `GET` | Proposed (Member 2) | Returns `Trip[]` |
| `/trips` | `POST` | Proposed (Member 2) | Body: `TripCreateInput`, Returns: `Trip` |
| `/trips/:id` | `GET` | Proposed (Member 2) | Returns `Trip` |
| `/trips/:id` | `PUT` | Proposed (Member 2) | Body: `TripUpdateInput`, Returns: `Trip` |
| `/trips/:id` | `DELETE`| Proposed (Member 2) | Returns `{ deletedId: string }` |
| `/scheduler/trip/:id` | `GET` | Proposed (Member 3) | Returns `SchedulerOpeningInfo` |
| `/trains/compare` | `GET` | Proposed (Member 4) | Query: `source`, `destination`, `class`, Returns `TrainComparisonResult[]` |
| `/booking/history` | `GET` | Proposed (Member 2) | Returns `BookingOutcomeRecord[]` |
| `/booking/record` | `POST` | Proposed (Member 2) | Body: `BookingOutcomeRecord`, Returns saved record |
| `/settings` | `GET` / `PUT` | Proposed (Member 2) | Returns `UserSettings` |

### Demo Mode Policy
- When `NEXT_PUBLIC_DEMO_MODE=true` (or when `NEXT_PUBLIC_API_BASE_URL` is unset), the application runs via an in-memory & `localStorage` demo adapter.
- A persistent amber banner informs reviewers that demo mode is active.
- Real API network failures **never** silently fall back to mock data; errors are surfaced with full diagnostic details.
- Demo data can be reset at any time via the "Reset Demo Data" button.

---

## 🚀 Getting Started

### Prerequisites
- Node.js LTS (v20+ or v24+)
- npm or npm.cmd

### Installation
```bash
# Clone or navigate to the project
cd tatkal-assistant

# Install dependencies
npm install
```

### Environment Configuration
Create a `.env.local` file:
```env
# FastAPI Backend URL (default: http://127.0.0.1:8000/api/v1)
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1

# Demo Mode Toggle ('false' for live backend and authentic railway data; 'true' for offline reviewer preview)
NEXT_PUBLIC_DEMO_MODE=false
```

### Development Server
```bash
npm run dev
# Starts dev server on http://localhost:3001
```

### Automated Tests
```bash
npm test
# Runs the full 24-point test suite covering validation, countdowns, sorting, safety, ThreeUI, API envelopes, human intervention gates, evidence verification, and zero-mock invariant
```

### Production Build
```bash
npm run build
npm start
```

---

## 📱 Application Routes

- `/` — **Mission Control Dashboard**: Active journey profile, live Tatkal countdown, 3D Spatial Agent Pipeline Visualizer, live Task & Run Orchestrator Console, Tools & Skills Hub, and Tamper-Proof Audit Evidence Inspector.
- `/trains` — **Train Timetable & Comparison**: Interactive station autocomplete search, authentic train timetables from Official IR Open Data, stop-by-stop intermediate schedule drawer modal, live running status telemetry check, and PNR status inquiry.
- `/trips` — **My Trips**: Saved journey cards with class badges, date summaries, and deletion confirmation dialogs.
- `/trips/new` — **Create Journey**: Accessible form with live backend station search, Tatkal passenger limit check (1-4 max), and class selection.
- `/trips/[id]` — **Trip Details & Edit**: Parameter editing and route reconfiguration.
- `/booking` — **Booking Desk**: Interactive checklist, countdown timer, automated booking plan generation, and safe human-in-the-loop checkpoints.
- `/history` — **Booking History & Audit**: Cryptographic SHA-256 evidence inspector and chronological archive of booking records.
- `/settings` — **Settings & Privacy**: Travel class preferences, backend diagnostics, and local data reset controls.
- `/threeui-preview` — **ThreeUI Showcase**: Sandboxed iframe preview of `MengToSketchbookLandingPage`.

---

## 🧪 Verification Summary

- **Production Build**: Compiled and statically optimized (11 routes, 0 errors).
- **Unit & Logic Tests**: 24 tests passing (0 failures).
- **HTTP Endpoint Validation**: All routes verified responding with HTTP 200.
- **Backend Connection**: Verified live integration with FastAPI backend on port 8000.
- **Safety Restrictions**: Automated payment and booking execution strictly disabled. All secrets preserved server-side.
