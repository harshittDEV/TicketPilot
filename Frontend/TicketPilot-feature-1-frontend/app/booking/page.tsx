'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import {
  Trip,
  SchedulerOpeningInfo,
  BackendTask,
  BackendRun,
  PreparationReport,
  AuditEventRecord,
} from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { JourneyConfigurationForm } from '@/components/booking/JourneyConfigurationForm';
import { PreFlightPreparationCard } from '@/components/booking/PreFlightPreparationCard';
import { PaymentBoundaryModal } from '@/components/booking/PaymentBoundaryModal';
import { HumanInterventionGate } from '@/components/agent/HumanInterventionGate';
import { PreparationChecklist } from '@/components/booking/PreparationChecklist';
import {
  CheckSquare,
  Train,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  Key,
  FileCheck,
  ArrowRight,
  Layers,
  Play,
  RotateCcw,
  AlertTriangle,
  Clock,
  Cpu,
  Calendar,
  Users,
  Terminal,
  Activity,
  Plus,
  RefreshCw,
  Sliders,
  CheckCircle2,
} from 'lucide-react';
import Link from 'next/link';

export default function AutonomousTatkalAgentPage() {
  const [activeTab, setActiveTab] = useState<'agent' | 'configure' | 'checklist'>('agent');
  const [tasks, setTasks] = useState<BackendTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<BackendTask | null>(null);
  const [activeRun, setActiveRun] = useState<BackendRun | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEventRecord[]>([]);

  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load tasks from FastAPI backend
  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getTasks({ page_size: 20 });
      if (res.success && res.data?.tasks) {
        setTasks(res.data.tasks);
        if (res.data.tasks.length > 0) {
          // If no task selected, or selected task is still in list, select appropriately
          setSelectedTask((prev) => {
            if (prev) {
              const found = res.data!.tasks.find((t) => t.id === prev.id);
              return found || res.data!.tasks[0];
            }
            return res.data!.tasks[0];
          });
        }
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // Load runs and audit events for selected task
  const loadTaskDetails = useCallback(async (taskId: string) => {
    const [runsRes, eventsRes] = await Promise.all([
      api.getTaskRuns(taskId),
      api.getAuditEvents({ task_id: taskId, page_size: 20 }),
    ]);

    if (runsRes.success && runsRes.data?.runs && runsRes.data.runs.length > 0) {
      setActiveRun(runsRes.data.runs[0]);
    } else {
      setActiveRun(null);
    }

    if (eventsRes.success && eventsRes.data?.events) {
      setAuditEvents(eventsRes.data.events);
    } else {
      setAuditEvents([]);
    }
  }, []);

  useEffect(() => {
    if (selectedTask) {
      loadTaskDetails(selectedTask.id);
    }
  }, [selectedTask, loadTaskDetails]);

  // Handle task created from JourneyConfigurationForm
  const handleTaskCreated = (newTask: BackendTask) => {
    setTasks((prev) => [newTask, ...prev]);
    setSelectedTask(newTask);
    setActiveTab('agent');
    setSuccessMessage(`Journey task "${newTask.name}" configured and saved securely.`);
  };

  // Schedule task at Tatkal window
  const handleScheduleTask = async () => {
    if (!selectedTask) return;
    setScheduling(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await api.scheduleTask(selectedTask.id);
      if (res.success && res.data) {
        setSuccessMessage(
          `Task scheduled for autonomous execution at: ${new Date(
            res.data.scheduled_execution_time
          ).toLocaleString('en-IN')}`
        );
        await loadTasks();
      } else {
        setErrorMessage(res.error?.message || 'Failed to schedule task');
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Network error');
    } finally {
      setScheduling(false);
    }
  };

  // Unschedule task
  const handleUnscheduleTask = async () => {
    if (!selectedTask) return;
    setScheduling(true);
    try {
      const res = await api.unscheduleTask(selectedTask.id);
      if (res.success) {
        setSuccessMessage('Scheduled execution cancelled. Task set to IDLE.');
        await loadTasks();
      }
    } finally {
      setScheduling(false);
    }
  };

  // Launch real autonomous agent run
  const handleLaunchAutonomousRun = async () => {
    if (!selectedTask) return;
    setExecuting(true);
    setErrorMessage(null);
    try {
      // 1. Create run
      const runRes = await api.createRun(selectedTask.id);
      if (!runRes.success || !runRes.data) {
        throw new Error(runRes.error?.message || 'Could not initialize run');
      }

      const run = runRes.data;
      setActiveRun(run);

      // 2. Execute run slice (the backend orchestrator executes up to the CAPTCHA step or limits)
      const execRes = await api.executeRunStep(run.id, { max_steps: 10 });
      if (execRes.success && execRes.data) {
        setActiveRun(execRes.data);
      }

      await loadTasks();
      await loadTaskDetails(selectedTask.id);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Execution failed');
    } finally {
      setExecuting(false);
    }
  };

  // Resume run after human operator action (e.g. after CAPTCHA)
  const handleResumeAutonomousRun = async () => {
    if (!activeRun || !selectedTask) return;
    setExecuting(true);
    try {
      const resumeRes = await api.resumeRun(activeRun.id);
      if (resumeRes.success && resumeRes.data) {
        setActiveRun(resumeRes.data);
        // Execute next slice up to the payment boundary
        const execRes = await api.executeRunStep(activeRun.id, { max_steps: 10 });
        if (execRes.success && execRes.data) {
          setActiveRun(execRes.data);
        }
      }
      await loadTasks();
      await loadTaskDetails(selectedTask.id);
    } finally {
      setExecuting(false);
    }
  };

  const handleCancelRun = async () => {
    if (!activeRun || !selectedTask) return;
    try {
      await api.cancelRun(activeRun.id);
      await loadTasks();
      await loadTaskDetails(selectedTask.id);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Cancel error');
    }
  };

  // Status badge variant
  const getStatusVariant = (st?: string): any => {
    switch (st) {
      case 'COMPLETED':
        return 'success';
      case 'RUNNING':
        return 'info';
      case 'WAITING_FOR_HUMAN':
      case 'AWAITING_HUMAN':
      case 'AWAITING_PAYMENT_APPROVAL':
        return 'warning';
      case 'SCHEDULED':
        return 'info';
      case 'FAILED':
      case 'CANCELLED':
        return 'error';
      default:
        return 'neutral';
    }
  };

  const isCaptchaWaiting =
    activeRun?.status === 'WAITING_FOR_HUMAN' &&
    (!activeRun?.error_summary || !activeRun.error_summary.includes('PAYMENT_STAGE_REACHED'));

  const isPaymentBoundaryWaiting =
    activeRun?.status === 'WAITING_FOR_HUMAN' &&
    activeRun?.error_summary?.includes('PAYMENT_STAGE_REACHED');

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-stone-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-mono uppercase bg-emerald-50 text-accent-emerald px-2.5 py-0.5 rounded-full font-bold border border-emerald-200">
              Autonomous Agent Orchestration
            </span>
            <span className="text-[10px] text-ink-muted">
              Computer-Use Tatkal Assistant
            </span>
          </div>
          <h1 className="text-2xl font-black text-ink tracking-tight">
            TicketPilot Autonomous Workspace
          </h1>
          <p className="text-xs text-ink-muted mt-1 max-w-2xl">
            Goal-driven autonomous railway booking agent. Pre-flight diagnostics, persistent scheduling, browser automation, human CAPTCHA checkpoint, and strict halting at the final payment boundary.
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-stone-100 border border-stone-200 shrink-0">
          <button
            type="button"
            onClick={() => setActiveTab('agent')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'agent'
                ? 'bg-white text-ink shadow-xs'
                : 'text-stone-600 hover:text-ink'
            }`}
          >
            Agent Workspace
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('configure')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'configure'
                ? 'bg-white text-ink shadow-xs'
                : 'text-stone-600 hover:text-ink'
            }`}
          >
            Configure Journey
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('checklist')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'checklist'
                ? 'bg-white text-ink shadow-xs'
                : 'text-stone-600 hover:text-ink'
            }`}
          >
            Manual Checklist
          </button>
        </div>
      </div>

      {/* Global Alerts */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="text-rose-700 hover:text-rose-900 font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-700 hover:text-emerald-900 font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* TAB 1: CONFIGURE JOURNEY */}
      {activeTab === 'configure' && (
        <div className="space-y-4">
          <JourneyConfigurationForm onTaskCreated={handleTaskCreated} />
        </div>
      )}

      {/* TAB 2: MANUAL CHECKLIST */}
      {activeTab === 'checklist' && (
        <GlassCard depth={1} className="p-6">
          <div className="max-w-3xl mx-auto space-y-4">
            <h2 className="text-base font-bold text-ink">Operator Tatkal Manual Readiness</h2>
            <p className="text-xs text-ink-muted">
              For manual operators who prefer to book themselves on IRCTC rather than using the autonomous agent.
            </p>
            <PreparationChecklist />
          </div>
        </GlassCard>
      )}

      {/* TAB 3: AGENT WORKSPACE (PRIMARY) */}
      {activeTab === 'agent' && (
        <div className="space-y-6">
          {/* Active Task Selector Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-white border border-stone-200 shadow-2xs">
            <div className="flex items-center gap-2 min-w-0">
              <Train className="w-4 h-4 text-accent-emerald shrink-0" />
              <span className="text-xs font-bold text-ink-muted uppercase shrink-0">
                Active Journey Task:
              </span>
              {tasks.length > 0 ? (
                <select
                  value={selectedTask?.id || ''}
                  onChange={(e) => {
                    const found = tasks.find((t) => t.id === e.target.value);
                    if (found) setSelectedTask(found);
                  }}
                  className="px-2.5 py-1 text-xs font-bold rounded-lg border border-stone-300 bg-stone-50 text-ink focus:outline-none focus:ring-1 focus:ring-accent-emerald truncate max-w-sm"
                >
                  {tasks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.status})
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-xs text-ink-muted italic">
                  No tasks configured yet.{' '}
                  <button
                    type="button"
                    onClick={() => setActiveTab('configure')}
                    className="text-accent-emerald font-bold underline ml-1"
                  >
                    Configure First Journey
                  </button>
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={loadTasks}
                disabled={loading}
                className="p-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 text-stone-600 transition-colors"
                title="Refresh tasks"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('configure')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-emerald hover:bg-emerald-800 text-white text-xs font-bold shadow-2xs transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New Journey Setup</span>
              </button>
            </div>
          </div>

          {selectedTask && (
            <>
              {/* Task Overview Card */}
              <GlassCard depth={1} className="p-5 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-stone-200/80">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-mono uppercase bg-stone-100 text-stone-700 px-2 py-0.5 rounded border border-stone-200">
                        Task ID: {selectedTask.id}
                      </span>
                      <StatusBadge
                        label={selectedTask.status}
                        variant={getStatusVariant(selectedTask.status)}
                      />
                      {selectedTask.scheduled_execution_time && (
                        <span className="text-[10px] font-mono bg-blue-50 text-blue-800 border border-blue-200 px-2 py-0.5 rounded flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Scheduled: {new Date(selectedTask.scheduled_execution_time).toLocaleTimeString()}
                        </span>
                      )}
                    </div>
                    <h2 className="text-lg font-black text-ink tracking-tight">
                      {selectedTask.name}
                    </h2>
                  </div>

                  {/* Top Action Toolbar */}
                  <div className="flex items-center gap-2 shrink-0">
                    {selectedTask.scheduled_execution_time ? (
                      <button
                        type="button"
                        onClick={handleUnscheduleTask}
                        disabled={scheduling}
                        className="px-3 py-1.5 rounded-xl border border-rose-300 bg-rose-50 hover:bg-rose-100 text-rose-800 font-bold text-xs transition-colors"
                      >
                        Cancel Schedule
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={handleScheduleTask}
                        disabled={scheduling}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-xs transition-colors"
                      >
                        <Clock className="w-3.5 h-3.5" />
                        <span>Schedule at Tatkal Window</span>
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={handleLaunchAutonomousRun}
                      disabled={executing}
                      className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white font-bold text-xs shadow-xs transition-colors disabled:opacity-50"
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>{executing ? 'Executing Run...' : 'Launch Autonomous Agent'}</span>
                    </button>
                  </div>
                </div>

                {/* Configuration Specs Bar */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-stone-50/80 p-3.5 rounded-xl border border-stone-200/60">
                  <div>
                    <span className="text-[10px] text-ink-muted uppercase block font-bold">
                      Sector & Quota
                    </span>
                    <span className="font-bold text-ink">
                      {selectedTask.configuration?.source || 'NDLS'} →{' '}
                      {selectedTask.configuration?.destination || 'BCT'} (
                      {selectedTask.configuration?.quota || 'TATKAL'})
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-ink-muted uppercase block font-bold">
                      Journey Date
                    </span>
                    <span className="font-bold text-ink">
                      {selectedTask.configuration?.travel_date || '2026-12-20'}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-ink-muted uppercase block font-bold">
                      Class & Passengers
                    </span>
                    <span className="font-bold text-ink">
                      {selectedTask.configuration?.travel_class || '3A'} •{' '}
                      {selectedTask.configuration?.passengers?.length ||
                        selectedTask.configuration?.passenger_count ||
                        1}{' '}
                      Passenger(s)
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-ink-muted uppercase block font-bold">
                      Current Step
                    </span>
                    <span className="font-mono font-bold text-accent-emerald">
                      {activeRun?.current_step !== undefined
                        ? `Step ${activeRun.current_step}`
                        : 'Idle'}
                    </span>
                  </div>
                </div>
              </GlassCard>

              {/* Checkpoint Banner: CAPTCHA Human Gate */}
              {isCaptchaWaiting && activeRun && (
                <HumanInterventionGate
                  taskId={selectedTask.id}
                  runId={activeRun.id}
                  checkpointType="CAPTCHA"
                  description={
                    activeRun.error_summary ||
                    'Anti-bot challenge encountered. Indian Railways regulations require CAPTCHA to be solved manually. Complete verification in the browser to resume.'
                  }
                  onResume={handleResumeAutonomousRun}
                  onCancel={handleCancelRun}
                />
              )}

              {/* Checkpoint Banner: Final Payment Boundary Reached */}
              {isPaymentBoundaryWaiting && activeRun && (
                <PaymentBoundaryModal
                  taskId={selectedTask.id}
                  runId={activeRun.id}
                  taskConfiguration={selectedTask.configuration}
                  extractedSummary={activeRun.error_summary}
                  onComplete={() => {
                    setSuccessMessage('Workflow finalized. Thank you for using TicketPilot.');
                    loadTasks();
                  }}
                  onCancel={handleCancelRun}
                />
              )}

              {/* Pre-Flight 12-Point Preparation Diagnostics Panel */}
              <PreFlightPreparationCard
                taskId={selectedTask.id}
                onPrepared={() => {
                  loadTasks();
                  loadTaskDetails(selectedTask.id);
                }}
              />

              {/* Execution Run Inspector & Audit Trail Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Active Run Console (7 Cols) */}
                <div className="lg:col-span-7 space-y-4">
                  <GlassCard depth={1} className="p-4 space-y-3">
                    <div className="flex items-center justify-between pb-2 border-b border-stone-200">
                      <div className="flex items-center gap-2">
                        <Terminal className="w-4 h-4 text-accent-emerald" />
                        <h3 className="text-xs font-extrabold uppercase tracking-wider text-ink">
                          Active Run Execution State
                        </h3>
                      </div>
                      {activeRun && (
                        <StatusBadge
                          label={activeRun.status}
                          variant={getStatusVariant(activeRun.status)}
                        />
                      )}
                    </div>

                    {activeRun ? (
                      <div className="space-y-3 text-xs">
                        <div className="grid grid-cols-2 gap-2 text-[11px] p-2.5 rounded-lg bg-stone-50 border border-stone-200 font-mono">
                          <div>
                            <span className="text-stone-500 block">Run ID</span>
                            <span className="font-bold text-ink">{activeRun.id}</span>
                          </div>
                          <div>
                            <span className="text-stone-500 block">Steps Completed</span>
                            <span className="font-bold text-ink">
                              {activeRun.steps_completed}
                            </span>
                          </div>
                        </div>

                        {activeRun.error_summary && (
                          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-[11px] leading-relaxed">
                            <strong>Reason:</strong> {activeRun.error_summary}
                          </div>
                        )}

                        <div className="flex items-center gap-2 pt-2">
                          {activeRun.status === 'RUNNING' && (
                            <span className="inline-flex items-center gap-1.5 text-xs text-blue-700 font-semibold animate-pulse">
                              <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
                              Agent orchestrator executing planned actions...
                            </span>
                          )}
                          {activeRun.status === 'WAITING_FOR_HUMAN' && (
                            <button
                              type="button"
                              onClick={handleResumeAutonomousRun}
                              className="px-3 py-1.5 rounded-lg bg-accent-emerald hover:bg-emerald-800 text-white font-bold text-xs shadow-xs"
                            >
                              Resume Autonomous Agent
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={handleCancelRun}
                            className="px-3 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700 font-semibold text-xs border border-stone-300"
                          >
                            Cancel Run
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-6 text-xs text-ink-muted">
                        No active execution run. Click &quot;Launch Autonomous Agent&quot; to begin.
                      </div>
                    )}
                  </GlassCard>
                </div>

                {/* Real Persisted Audit Events Timeline (5 Cols) */}
                <div className="lg:col-span-5 space-y-4">
                  <GlassCard depth={1} className="p-4 space-y-3">
                    <div className="flex items-center justify-between pb-2 border-b border-stone-200">
                      <div className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-accent-emerald" />
                        <h3 className="text-xs font-extrabold uppercase tracking-wider text-ink">
                          Audit Trail ({auditEvents.length})
                        </h3>
                      </div>
                      <span className="text-[10px] text-ink-muted">Persisted Events</span>
                    </div>

                    <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                      {auditEvents.length === 0 ? (
                        <p className="text-xs text-stone-400 italic text-center py-4">
                          No audit events recorded for this task yet.
                        </p>
                      ) : (
                        auditEvents.map((evt) => (
                          <div
                            key={evt.id}
                            className="p-2.5 rounded-lg bg-white border border-stone-200 text-xs space-y-0.5"
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className="font-mono font-bold text-[11px] text-accent-emerald truncate">
                                {evt.event_type}
                              </span>
                              <span
                                className={`text-[9px] px-1.5 py-0.2 rounded font-mono uppercase ${
                                  evt.outcome === 'SUCCESS'
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : 'bg-amber-100 text-amber-800'
                                }`}
                              >
                                {evt.outcome}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[10px] text-ink-muted">
                              <span>Source: {evt.source}</span>
                              <span>{new Date(evt.timestamp).toLocaleTimeString()}</span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </GlassCard>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
