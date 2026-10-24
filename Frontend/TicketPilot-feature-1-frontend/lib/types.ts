/**
 * Tatkal Assistant & Agent Orchestrator - Shared Type Definitions
 * Frontend & UI Architecture (Phase 9 Integration)
 * 
 * Strict typed contracts aligning with FastAPI Backend:
 * - Tasks & Execution Runs lifecycle
 * - Teammate Integrations (Scheduler, Train Comparison, Security, Booking Assistance)
 * - Tools & Declarative Skills System
 * - Audit Trail & Cryptographic Evidence
 * - Circuit Breakers & System Diagnostics
 */

export type TravelClass = 
  | '1A'  // First AC
  | '2A'  // 2 Tier AC
  | '3A'  // 3 Tier AC
  | '3E'  // 3 AC Economy
  | 'CC'  // AC Chair Car
  | 'EC'  // Executive Chair Car
  | 'SL'  // Sleeper (Non-AC)
  | '2S'; // Second Sitting (Non-AC)

export type PreferenceChoice = 'balanced' | 'fastest' | 'cheapest';

export interface Trip {
  id: string;
  sourceStation: string;
  destStation: string;
  journeyDate: string; // YYYY-MM-DD
  travelClass: TravelClass;
  isAC: boolean;
  passengerCount: number; // 1 to 4 max under Tatkal rules
  preferredTrainNumber?: string;
  preferredTrainName?: string;
  fareVsDurationPreference: PreferenceChoice;
  preferredDepartureTime?: string;
  status: 'planned' | 'ready' | 'booked' | 'missed';
  createdAt: string;
  updatedAt: string;
}

export type TripCreateInput = Omit<Trip, 'id' | 'isAC' | 'createdAt' | 'updatedAt' | 'status'>;
export type TripUpdateInput = Partial<TripCreateInput> & { status?: Trip['status'] };

export type SchedulerWindowStatus = 'UPCOMING' | 'OPENING_SOON' | 'WINDOW_OPEN' | 'WINDOW_CLOSED';

export interface SchedulerOpeningInfo {
  openingTimestampIST: string; // ISO 8601 string representing IST instant
  targetClassType: 'AC' | 'NON_AC';
  openingTimeFormatted: string; // e.g., "10:00 AM IST" or "11:00 AM IST"
  status: SchedulerWindowStatus;
  isAuthoritative: boolean; // false indicates configured default fallback, true means Member 3 calculation
  sourceExplanation: string;
  remindersConfigured: boolean;
  trainOriginDepartureDate?: string;
  originDateNotice?: string;
}

export type DataFreshness = 'verified' | 'estimated' | 'stale' | 'unavailable';

export interface TrainComparisonResult {
  trainNumber: string;
  trainName: string;
  originStation: string;
  destinationStation: string;
  departureTime: string;
  arrivalTime: string;
  duration: string;
  durationMinutes: number;
  travelClass: TravelClass;
  baseFare: number;
  tatkalCharge: number;
  totalFare: number;
  availabilityStatus: string;
  dataProvenance: DataFreshness;
  freshnessTimestamp: string;
  recommendation?: {
    badge: 'TOP_RECOMMENDATION' | 'FASTEST' | 'VALUE_PICK' | 'BACKUP_OPTION';
    reason: string;
    engineProvenance: string; // e.g. "Member 4 Comparison Engine v1.0"
  };
}

export type BookingStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'CONFIRMED' | 'FAILED' | 'UNKNOWN';

export interface BookingOutcomeRecord {
  id: string;
  tripId: string;
  trainNumber: string;
  trainName?: string;
  journeyDate: string;
  travelClass: TravelClass;
  status: BookingStatus;
  isManuallyRecorded: boolean;
  isIndependentlyVerified: boolean;
  pnr?: string;
  recordedAt: string;
  bookingTimestamp?: string;
  proofReference?: string;
  notes?: string;
}

export interface UserSettings {
  preferredClasses: TravelClass[];
  defaultPreference: PreferenceChoice;
  enableCountdownSeconds: boolean;
  schedulerNotificationsEnabled: boolean;
  reducedMotion: boolean;
  highContrastGlass: boolean;
  dataRetentionAcknowledged: boolean;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    fieldErrors?: Record<string, string>;
  };
  isDemoData?: boolean;
}

// ── Backend FastAPI Models (Phases 1–8) ──────────────────────────

export interface BackendHealth {
  status: string;
  api_version: string;
  database: string;
  environment?: string;
  timestamp?: string;
}

export type TaskStatus =
  | 'CREATED'
  | 'READY'
  | 'RUNNING'
  | 'PAUSED'
  | 'WAITING_FOR_HUMAN'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'UNKNOWN';

export interface BackendTask {
  id: string;
  name?: string | null;
  task_type: string;
  status: TaskStatus;
  description?: string | null;
  configuration?: Record<string, any> | null;
  current_step?: string | null;
  scheduled_execution_time?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  cancelled_at?: string | null;
  error_code?: string | null;
  error_summary?: string | null;
  version: number;
}

export interface TaskCreatePayload {
  name?: string;
  task_type: string;
  description?: string;
  configuration?: Record<string, any>;
}

export interface TaskUpdatePayload {
  name?: string;
  description?: string;
  configuration?: Record<string, any>;
}

export type RunStatus =
  | 'CREATED'
  | 'STARTING'
  | 'RUNNING'
  | 'PAUSED'
  | 'WAITING_FOR_HUMAN'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'UNKNOWN';

export interface BackendRun {
  id: string;
  task_id: string;
  status: RunStatus;
  current_step?: string | null;
  steps_completed: number;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  ended_at?: string | null;
  error_code?: string | null;
  error_summary?: string | null;
  version: number;
}

export interface RunExecutePayload {
  max_steps?: number;
  timeout_seconds?: number;
}

export interface RunTransitionPayload {
  target_status: RunStatus;
  error_code?: string;
  error_summary?: string;
  current_step?: string;
  steps_completed?: number;
}

export interface BackendTool {
  name: string;
  description: string;
  version: string;
  capabilities: string[];
  input_schema: Record<string, any>;
  is_available: boolean;
  health_status: Record<string, any>;
}

export interface SkillStep {
  step_id: string;
  tool_name: string;
  action_type: string;
  parameters: Record<string, any>;
  expected_outcome: string;
  timeout_seconds?: number | null;
  optional: boolean;
  require_human: boolean;
  description: string;
}

export interface BackendSkill {
  name: string;
  version: string;
  description: string;
  required_inputs: Array<{
    name: string;
    type: string;
    description: string;
    default?: any;
    required: boolean;
  }>;
  allowed_tools: string[];
  steps: SkillStep[];
  expected_outcomes: string[];
  timeout_seconds: number;
  human_intervention_required: boolean;
}

export interface AuditEventRecord {
  id: string;
  task_id?: string | null;
  run_id?: string | null;
  event_type: string;
  event_category: 'TASK' | 'RUN' | 'TOOL' | 'SKILL' | 'RECOVERY' | string;
  timestamp: string;
  source?: string | null;
  outcome: string;
  details?: Record<string, any> | null;
  error_code?: string | null;
  error_message?: string | null;
  recovery_action?: string | null;
}

export interface EvidenceItem {
  id: string;
  task_id?: string | null;
  run_id?: string | null;
  audit_event_id?: string | null;
  evidence_type: string;
  timestamp: string;
  file_path: string;
  content_type: string;
  file_size_bytes: number;
  sha256_checksum: string;
  capture_source: string;
  metadata_payload?: Record<string, any> | null;
  integrity_status: 'VERIFIED' | 'TAMPERED' | 'MISSING' | string;
}

export interface EvidenceVerifyResult {
  evidence_id: string;
  status: 'VERIFIED' | 'TAMPERED' | 'MISSING';
  valid: boolean;
  stored_checksum: string;
  computed_checksum: string | null;
  file_path: string;
  file_size_bytes: number;
  message: string;
}

export interface CircuitBreakerStatus {
  state: string;
  failure_count: number;
  failure_threshold: number;
  recovery_timeout: number;
  last_state_change: string;
}

export interface TatkalScheduleTimings {
  class_code: string;
  journey_origin_departure_date: string;
  opening_date: string;
  opening_time_ist: string;
  opening_datetime_ist: string;
  opening_datetime_utc: string;
  pre_alert_datetime_ist: string;
  pre_alert_datetime_utc: string;
  reminder_minutes_before: number;
}

export interface BookingPlanStep {
  step_id: number;
  name: string;
  requires_human: boolean;
  description: string;
}

export interface BookingPlanResponse {
  plan_id: string;
  task_id: string;
  train_number: string;
  travel_date: string;
  travel_class: string;
  passenger_count: number;
  steps: BookingPlanStep[];
  sanitized_journey_details: any;
}

export interface BookingExecutionResponse {
  task_id: string;
  success: boolean;
  booking_reference: string | null;
  message: string;
  evidence?: {
    plan_id?: string;
    train_number?: string;
    passenger_count?: number;
    requires_human: boolean;
    human_checkpoints?: string[];
    status: string;
  };
}

// ==========================================
// Railway Data Provider Types (Phase 9)
// ==========================================

export interface Station {
  code: string;
  name: string;
  city: string;
  state: string;
  zone: string;
}

export interface StationStop {
  stop_number: number;
  station_code: string;
  station_name: string;
  arrival_time: string;
  departure_time: string;
  halt_minutes: number;
  distance_km: number;
  day_count: number;
}

export interface TrainSchedule {
  train_number: string;
  train_name: string;
  origin_station_code: string;
  origin_station_name: string;
  destination_station_code: string;
  destination_station_name: string;
  runs_on_days: string[];
  available_classes: string[];
  stops: StationStop[];
  data_source: string;
  freshness_category: 'LIVE' | 'CACHED' | 'STATIC_DATASET' | 'STALE' | 'UNAVAILABLE';
  last_updated: string;
}

export interface TrainBetweenStations {
  train_number: string;
  train_name: string;
  source_station_code: string;
  source_station_name: string;
  destination_station_code: string;
  destination_station_name: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  duration_formatted: string;
  available_classes: string[];
  available_quotas: string[];
  base_fare?: number | null;
  tatkal_charge?: number | null;
  total_fare?: number | null;
  availability_status?: string | null;
  data_source: string;
  freshness_category: 'LIVE' | 'CACHED' | 'STATIC_DATASET' | 'STALE' | 'UNAVAILABLE';
  retrieved_at: string;
  notes?: string | null;
}

export interface LiveRunningStatus {
  train_number: string;
  train_name: string;
  journey_date: string;
  is_available: boolean;
  current_station_code?: string | null;
  current_station_name?: string | null;
  delay_departure_minutes: number;
  delay_arrival_minutes: number;
  status_message: string;
  last_reported_time?: string | null;
  is_terminated: boolean;
  data_source: string;
  freshness_category: 'LIVE' | 'CACHED' | 'STATIC_DATASET' | 'STALE' | 'UNAVAILABLE';
  observation_timestamp: string;
  disclaimer: string;
}

export interface PnrPassenger {
  passenger_index: number;
  booking_status: string;
  current_status: string;
  coach?: string | null;
  berth?: string | null;
}

export interface PnrStatus {
  pnr_number: string;
  is_supported: boolean;
  train_number?: string | null;
  train_name?: string | null;
  journey_date?: string | null;
  booking_status: string;
  chart_prepared: boolean;
  passengers: PnrPassenger[];
  data_source: string;
  freshness_category: 'LIVE' | 'CACHED' | 'STATIC_DATASET' | 'STALE' | 'UNAVAILABLE';
  retrieved_at: string;
  message: string;
}

export interface ProviderCapabilities {
  provider_id: string;
  display_name: string;
  has_station_search: boolean;
  has_timetable: boolean;
  has_trains_between: boolean;
  has_live_running: boolean;
  has_fare: boolean;
  has_availability: boolean;
  has_pnr: boolean;
  auth_configured: boolean;
  quota_limits: string;
  notes: string;
}

export interface ProviderStatusResponse {
  active_mode: string;
  providers: ProviderCapabilities[];
  cache_entries_count: number;
  cache_stats: Record<string, any>;
}

// ==========================================
// Autonomous Tatkal Agent Types (Goal-Driven)
// ==========================================

export type BerthPreference = 
  | 'LOWER'
  | 'MIDDLE'
  | 'UPPER'
  | 'SIDE_LOWER'
  | 'SIDE_UPPER'
  | 'WINDOW'
  | 'NO_PREFERENCE';

export type Gender = 'M' | 'F' | 'T';

export interface PassengerDetails {
  name: string;
  age: number;
  gender: Gender;
  berth_preference?: BerthPreference;
  food_preference?: 'VEG' | 'NON_VEG' | 'NO_FOOD';
  senior_citizen_concession?: boolean;
}

export interface BookingPreferences {
  preferred_train_order?: string[];
  preferred_class_order?: TravelClass[];
  allow_alternative_trains: boolean;
  allow_alternative_classes: boolean;
  max_acceptable_fare?: number | null;
  coach_id?: string | null;
  auto_upgradation: boolean;
}

export interface SchedulingPreferences {
  tatkal_window_override?: 'AC' | 'NON_AC' | null;
  timezone: string;
  preparation_window_minutes: number;
  auto_trigger_at_window: boolean;
  deadline_seconds: number;
}

export interface JourneyConfiguration {
  origin_station: string;
  destination_station: string;
  journey_date: string;
  travel_class: TravelClass;
  booking_quota: 'TATKAL' | 'GENERAL' | 'PREMIUM_TATKAL' | 'LADIES';
  train_number?: string;
  train_name?: string;
  passengers: PassengerDetails[];
  preferences: BookingPreferences;
  scheduling: SchedulingPreferences;
  autonomous_agent: boolean;
}

export interface CheckResult {
  check_id: string | number;
  name: string;
  passed: boolean;
  status?: string;
  severity?: 'ERROR' | 'WARNING' | 'INFO' | string;
  details: string;
  remediation?: string | null;
  data_source?: string | null;
  freshness?: string | null;
  authoritative?: boolean;
}

export interface PreparationPlanStep {
  step: number;
  action: string;
  target?: string;
  description: string;
  requires_human: boolean;
  safety_checkpoint?: string | null;
}

export interface PreparationReport {
  task_id?: string;
  is_ready?: boolean;
  overall_ready?: boolean;
  can_proceed_to_booking?: boolean;
  timestamp?: string;
  prepared_at?: string;
  summary?: string;
  checks: CheckResult[];
  unresolved_prerequisites: string[];
  proposed_execution_plan?: PreparationPlanStep[];
  execution_plan?: PreparationPlanStep[];
  resolved_source_station?: Record<string, any> | null;
  resolved_dest_station?: Record<string, any> | null;
  eligible_trains_count?: number;
  top_train?: Record<string, any> | null;
  tatkal_timings?: Record<string, any> | null;
  requires_human_at_steps?: string[];
  journey_summary?: Record<string, any>;
  execution_window?: Record<string, any>;
  prerequisites_requiring_human?: string[];
}


