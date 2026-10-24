'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import {
  Trip,
  SchedulerOpeningInfo,
  TrainComparisonResult,
  BackendTask,
  BackendHealth,
} from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { CountdownWidget } from '@/components/countdown/CountdownWidget';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { PreparationChecklist } from '@/components/booking/PreparationChecklist';
import { SpatialPipelineVisualizer } from '@/components/pipeline/SpatialPipelineVisualizer';
import { TaskRunConsole } from '@/components/agent/TaskRunConsole';
import { ToolsSkillsHub } from '@/components/tools/ToolsSkillsHub';
import { AuditEvidenceInspector } from '@/components/audit/AuditEvidenceInspector';
import {
  Train,
  Plus,
  Compass,
  Layers,
  Wrench,
  ShieldCheck,
  Activity,
  CheckCircle2,
  Calendar,
  Users,
  ExternalLink,
  ChevronRight,
  Database,
  Lock,
} from 'lucide-react';

export default function MissionControlDashboard() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [selectedTrip, setSelectedTrip] = useState<Trip | null>(null);
  const [schedulerInfo, setSchedulerInfo] = useState<SchedulerOpeningInfo | undefined>(undefined);
  const [recommendations, setRecommendations] = useState<TrainComparisonResult[]>([]);
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [selectedTask, setSelectedTask] = useState<BackendTask | null>(null);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadMissionControl() {
      setLoading(true);
      const [tripsRes, healthRes] = await Promise.all([
        api.getTrips(),
        api.checkBackendHealth(),
      ]);

      if (healthRes.success && healthRes.data) {
        setHealth(healthRes.data);
      }

      const loadedTrips = tripsRes.data || [];
      setTrips(loadedTrips);

      if (loadedTrips.length > 0) {
        const primary = loadedTrips[0];
        setSelectedTrip(primary);

        // Fetch scheduler info
        const schedRes = await api.getSchedulerStatus(primary.id);
        if (schedRes.data) {
          setSchedulerInfo(schedRes.data);
        }

        // Fetch recommendations for this sector
        const compRes = await api.getTrainComparisons(
          primary.sourceStation,
          primary.destStation,
          primary.travelClass
        );
        if (compRes.data) {
          setRecommendations(compRes.data);
        }
      }

      setLoading(false);
    }

    loadMissionControl();
  }, []);

  const handleSelectTrip = async (trip: Trip) => {
    setSelectedTrip(trip);
    const schedRes = await api.getSchedulerStatus(trip.id);
    if (schedRes.data) {
      setSchedulerInfo(schedRes.data);
    }
    const compRes = await api.getTrainComparisons(
      trip.sourceStation,
      trip.destStation,
      trip.travelClass
    );
    if (compRes.data) {
      setRecommendations(compRes.data);
    }
  };

  const topRecommendation =
    recommendations.find((t) => t.recommendation?.badge === 'TOP_RECOMMENDATION') ||
    recommendations[0];

  return (
    <div className="space-y-10 pb-16">
      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 1: Editorial Header & Live System Metrics            */}
      {/* ──────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 border-b border-stone-200/60">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100/90 px-3 py-0.5 rounded-full border border-emerald-300 shadow-2xs">
                General-Purpose Computer-Use Agent
              </span>
              <span className="text-[11px] font-mono text-stone-600 bg-stone-100 px-2.5 py-0.5 rounded-full border border-stone-200">
                Railway Booking Assistance Domain
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-ink tracking-tight">
              Mission Control & Agent Orchestrator
            </h1>
            <p className="text-xs sm:text-sm text-ink-muted mt-1.5 max-w-3xl leading-relaxed">
              Unified workspace orchestrating AI planning, browser and desktop tools, teammate
              modules, timetable recommendation models, and cryptographic evidence verification.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <Link
              href="/trips/new"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white text-xs font-bold shadow-xs transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Configure Journey</span>
            </Link>
            <a
              href="https://www.irctc.co.in/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-white hover:bg-stone-50 border border-stone-200 text-xs font-bold text-stone-800 transition-colors shadow-2xs"
            >
              <span>IRCTC Portal</span>
              <ExternalLink className="w-3.5 h-3.5 text-stone-500" />
            </a>
          </div>
        </div>

        {/* Live System Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <GlassCard depth={1} className="p-3.5 space-y-1">
            <div className="flex items-center justify-between text-stone-500">
              <span className="text-[10px] font-bold uppercase tracking-wider">FastAPI Backend</span>
              <Activity className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div className="text-base font-extrabold text-ink">
              {health?.status === 'ok' ? 'Operational' : 'Local Fallback'}
            </div>
            <p className="text-[11px] text-stone-500">
              Port 8000 • DB {health?.database?.toUpperCase() || 'CONNECTED'}
            </p>
          </GlassCard>

          <GlassCard depth={1} className="p-3.5 space-y-1">
            <div className="flex items-center justify-between text-stone-500">
              <span className="text-[10px] font-bold uppercase tracking-wider">Safety Policy</span>
              <Lock className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div className="text-base font-extrabold text-ink">Active Guardrails</div>
            <p className="text-[11px] text-stone-500">Payments & Auto-CAPTCHA Disabled</p>
          </GlassCard>

          <GlassCard depth={1} className="p-3.5 space-y-1">
            <div className="flex items-center justify-between text-stone-500">
              <span className="text-[10px] font-bold uppercase tracking-wider">Teammate Modules</span>
              <Layers className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div className="text-base font-extrabold text-ink">4 Integrated</div>
            <p className="text-[11px] text-stone-500">Scheduler • Security • Trains • Booking</p>
          </GlassCard>

          <GlassCard depth={1} className="p-3.5 space-y-1">
            <div className="flex items-center justify-between text-stone-500">
              <span className="text-[10px] font-bold uppercase tracking-wider">Evidence Auditing</span>
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div className="text-base font-extrabold text-ink">SHA-256 Verified</div>
            <p className="text-[11px] text-stone-500">Tamper-Proof Artifact Storage</p>
          </GlassCard>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 2: Spatial 3D Agent Pipeline Visualizer              */}
      {/* ──────────────────────────────────────────────────────────── */}
      <section className="space-y-3">
        <SpatialPipelineVisualizer
          activeStep={selectedTask?.current_step || 'observer'}
          status={selectedTask?.status || 'READY'}
        />
      </section>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 3: Task & Run Orchestrator Console                   */}
      {/* ──────────────────────────────────────────────────────────── */}
      <section className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-accent-emerald" />
            <h2 className="text-lg font-extrabold text-ink tracking-tight">
              Agent Execution & Run Control
            </h2>
          </div>
          <span className="text-xs text-ink-muted">
            Live interaction with backend tasks & execution runs
          </span>
        </div>
        <TaskRunConsole onTaskSelect={(t) => setSelectedTask(t)} />
      </section>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 4: Tatkal Countdown & Timetable Recommendation       */}
      {/* ──────────────────────────────────────────────────────────── */}
      <section className="space-y-4 pt-2">
        <div className="flex items-center justify-between pb-2 border-b border-stone-200/60">
          <div className="flex items-center gap-2">
            <Train className="w-5 h-5 text-accent-emerald" />
            <h2 className="text-lg font-extrabold text-ink tracking-tight">
              Tatkal Opening Window & Journey Readiness
            </h2>
          </div>
          {trips.length > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-ink-muted">Selected Sector:</span>
              <select
                value={selectedTrip?.id || ''}
                onChange={(e) => {
                  const found = trips.find((t) => t.id === e.target.value);
                  if (found) handleSelectTrip(found);
                }}
                className="text-xs bg-white border border-stone-200 rounded-xl px-3 py-1.5 text-ink font-semibold"
              >
                {trips.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.sourceStation.split('-')[0].trim()} → {t.destStation.split('-')[0].trim()}{' '}
                    ({t.journeyDate})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Countdown Widget (7 Cols) */}
          <div className="lg:col-span-7 space-y-4">
            {selectedTrip ? (
              <CountdownWidget
                schedulerInfo={schedulerInfo}
                journeyTitle={`${selectedTrip.sourceStation.split('-')[0].trim()} → ${selectedTrip.destStation.split('-')[0].trim()}`}
                travelClass={selectedTrip.travelClass}
              />
            ) : (
              <GlassCard className="text-center py-10">
                <Compass className="w-10 h-10 text-stone-300 mx-auto mb-2" />
                <p className="text-xs font-bold text-ink">No Journey Configured</p>
                <Link
                  href="/trips/new"
                  className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-accent-emerald text-white text-xs font-semibold"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Journey Profile</span>
                </Link>
              </GlassCard>
            )}

            {/* Selected Journey Profile Card */}
            {selectedTrip && (
              <GlassCard depth={1}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Train className="w-4 h-4 text-accent-emerald" />
                    <h3 className="font-bold text-sm text-ink">Journey Details</h3>
                  </div>
                  <StatusBadge
                    label={
                      selectedTrip.isAC
                        ? 'AC Quota (10:00 AM IST)'
                        : 'Non-AC Quota (11:00 AM IST)'
                    }
                    variant={selectedTrip.isAC ? 'ac' : 'nonac'}
                  />
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-stone-50 border border-stone-200/60 text-xs">
                  <div>
                    <span className="text-[10px] text-ink-muted uppercase block font-semibold">
                      Origin Station
                    </span>
                    <span className="font-bold text-ink">{selectedTrip.sourceStation}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-ink-muted uppercase block font-semibold">
                      Destination
                    </span>
                    <span className="font-bold text-ink">{selectedTrip.destStation}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-ink-muted uppercase block font-semibold">
                      Journey Date
                    </span>
                    <span className="font-bold text-ink">{selectedTrip.journeyDate}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-ink-muted uppercase block font-semibold">
                      Class & Passengers
                    </span>
                    <span className="font-bold text-ink">
                      {selectedTrip.travelClass} • {selectedTrip.passengerCount} Pax
                    </span>
                  </div>
                </div>
              </GlassCard>
            )}
          </div>

          {/* Right Column: Readiness Checklist & Top Recommendation (5 Cols) */}
          <div className="lg:col-span-5 space-y-4">
            <PreparationChecklist />

            {topRecommendation && (
              <GlassCard depth={1} className="p-4 space-y-2 border-emerald-200/80 bg-emerald-50/20">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full border border-emerald-200">
                    Recommended Train
                  </span>
                  <span className="text-xs font-mono font-bold text-ink">
                    ₹{topRecommendation.totalFare}
                  </span>
                </div>
                <h4 className="text-sm font-extrabold text-ink">
                  {topRecommendation.trainNumber} — {topRecommendation.trainName}
                </h4>
                <p className="text-[11px] text-stone-600">
                  Departs {topRecommendation.departureTime} • Arrives {topRecommendation.arrivalTime} (
                  {topRecommendation.duration})
                </p>
                <div className="pt-2 border-t border-emerald-100 flex items-center justify-between">
                  <span className="text-[10px] text-ink-muted">
                    {topRecommendation.recommendation?.engineProvenance || 'Member 4 Comparison'}
                  </span>
                  <Link
                    href="/trains"
                    className="inline-flex items-center gap-1 text-[11px] font-bold text-accent-emerald hover:underline"
                  >
                    <span>Full Comparison</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </GlassCard>
            )}
          </div>
        </div>
      </section>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 5: Tools & Declarative Skills System                 */}
      {/* ──────────────────────────────────────────────────────────── */}
      <section className="space-y-3 pt-2">
        <ToolsSkillsHub />
      </section>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 6: Audit Trail & Cryptographic Evidence Inspector    */}
      {/* ──────────────────────────────────────────────────────────── */}
      <section className="space-y-3 pt-2">
        <AuditEvidenceInspector />
      </section>
    </div>
  );
}
