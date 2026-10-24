'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { BackendTask, BackendRun, TaskCreatePayload } from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { HumanInterventionGate } from './HumanInterventionGate';
import {
  ListTodo,
  Play,
  Pause,
  RotateCcw,
  Plus,
  RefreshCw,
  XCircle,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  Terminal,
  Activity,
  Layers,
} from 'lucide-react';

export interface TaskRunConsoleProps {
  onTaskSelect?: (task: BackendTask) => void;
  className?: string;
}

export function TaskRunConsole({ onTaskSelect, className = '' }: TaskRunConsoleProps) {
  const [tasks, setTasks] = useState<BackendTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<BackendTask | null>(null);
  const [runs, setRuns] = useState<BackendRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<BackendRun | null>(null);

  const [loadingTasks, setLoadingTasks] = useState(true);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // New task modal / inline form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTaskName, setNewTaskName] = useState('Tatkal Mumbai Express');
  const [newOrigin, setNewOrigin] = useState('NDLS - New Delhi');
  const [newDest, setNewDest] = useState('BCT - Mumbai Central');
  const [stationSuggestions, setStationSuggestions] = useState<string[]>([]);
  const [newDate, setNewDate] = useState(
    new Date(Date.now() + 86400000 * 2).toISOString().slice(0, 10)
  );
  const [newClass, setNewClass] = useState('3A');
  const [newPassengers, setNewPassengers] = useState(2);

  // Polling control
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    async function loadStations() {
      const res = await api.searchStations('', 25);
      if (res.success && res.data) {
        setStationSuggestions(res.data.map(s => `${s.code} - ${s.name} (${s.state})`));
      }
    }
    loadStations();
  }, []);

  const loadTasks = async () => {
    setErrorMsg(null);
    setLoadingTasks(true);
    try {
      const res = await api.getTasks({ page_size: 20 });
      if (res.success && res.data?.tasks) {
        setTasks(res.data.tasks);
        if (res.data.tasks.length > 0 && !selectedTask) {
          const first = res.data.tasks[0];
          setSelectedTask(first);
          onTaskSelect?.(first);
          await loadRuns(first.id);
        }
      } else {
        setErrorMsg(res.error?.message || 'Unable to retrieve tasks from backend.');
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Network error');
    } finally {
      setLoadingTasks(false);
    }
  };

  const loadRuns = async (taskId: string) => {
    setLoadingRuns(true);
    try {
      const res = await api.getTaskRuns(taskId);
      if (res.success && res.data?.runs) {
        setRuns(res.data.runs);
        if (res.data.runs.length > 0) {
          setSelectedRun(res.data.runs[0]);
        } else {
          setSelectedRun(null);
        }
      }
    } finally {
      setLoadingRuns(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, []);

  // Bounded polling when a run is active
  useEffect(() => {
    if (!selectedRun || ['COMPLETED', 'FAILED', 'CANCELLED'].includes(selectedRun.status)) {
      setIsPolling(false);
      return;
    }

    setIsPolling(true);
    const interval = setInterval(async () => {
      if (selectedRun && selectedTask) {
        const res = await api.getRunById(selectedRun.id);
        if (res.success && res.data) {
          setSelectedRun(res.data);
          // Also refresh runs list
          await loadRuns(selectedTask.id);
        }
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [selectedRun?.id, selectedRun?.status]);

  const handleSelectTask = async (task: BackendTask) => {
    setSelectedTask(task);
    onTaskSelect?.(task);
    await loadRuns(task.id);
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newOrigin.trim().toLowerCase() === newDest.trim().toLowerCase()) {
      setErrorMsg('Origin and destination stations must be different.');
      return;
    }

    setActionBusy(true);
    setErrorMsg(null);
    try {
      const payload: TaskCreatePayload = {
        name: newTaskName,
        task_type: 'train_booking',
        description: `Tatkal booking workflow for ${newPassengers} passenger(s) on ${newDate}`,
        configuration: {
          source: newOrigin,
          destination: newDest,
          travel_date: newDate,
          travel_class: newClass,
          passenger_count: newPassengers,
          quota: 'TATKAL',
        },
      };

      const res = await api.createTask(payload);
      if (res.success && res.data) {
        setShowCreateForm(false);
        await loadTasks();
        setSelectedTask(res.data);
        onTaskSelect?.(res.data);
        await loadRuns(res.data.id);
      } else {
        setErrorMsg(res.error?.message || 'Failed to create task');
      }
    } finally {
      setActionBusy(false);
    }
  };

  const handleStartNewRun = async () => {
    if (!selectedTask) return;
    setActionBusy(true);
    try {
      const res = await api.createRun(selectedTask.id);
      if (res.success && res.data) {
        await loadRuns(selectedTask.id);
        setSelectedRun(res.data);
      } else {
        setErrorMsg(res.error?.message || 'Could not start new run');
      }
    } finally {
      setActionBusy(false);
    }
  };

  const handleExecuteStep = async () => {
    if (!selectedRun) return;
    setActionBusy(true);
    try {
      const res = await api.executeRunStep(selectedRun.id, { max_steps: 1 });
      if (res.success && res.data) {
        setSelectedRun(res.data);
        if (selectedTask) await loadRuns(selectedTask.id);
      } else {
        setErrorMsg(res.error?.message || 'Step execution failed');
      }
    } finally {
      setActionBusy(false);
    }
  };

  const handlePauseRun = async () => {
    if (!selectedRun) return;
    setActionBusy(true);
    try {
      const res = await api.pauseRun(selectedRun.id);
      if (res.success && res.data) {
        setSelectedRun(res.data);
        if (selectedTask) await loadRuns(selectedTask.id);
      }
    } finally {
      setActionBusy(false);
    }
  };

  const handleResumeRun = async () => {
    if (!selectedRun) return;
    setActionBusy(true);
    try {
      const res = await api.resumeRun(selectedRun.id);
      if (res.success && res.data) {
        setSelectedRun(res.data);
        if (selectedTask) await loadRuns(selectedTask.id);
      }
    } finally {
      setActionBusy(false);
    }
  };

  const handleCancelRun = async () => {
    if (!selectedRun) return;
    setActionBusy(true);
    try {
      const res = await api.cancelRun(selectedRun.id);
      if (res.success && res.data) {
        setSelectedRun(res.data);
        if (selectedTask) await loadRuns(selectedTask.id);
      }
    } finally {
      setActionBusy(false);
    }
  };

  const getStatusBadgeVariant = (status: string): any => {
    switch (status) {
      case 'COMPLETED':
        return 'success';
      case 'RUNNING':
      case 'STARTING':
        return 'info';
      case 'WAITING_FOR_HUMAN':
      case 'PAUSED':
        return 'warning';
      case 'FAILED':
      case 'CANCELLED':
        return 'error';
      default:
        return 'neutral';
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Error Announcement Banner */}
      {errorMsg && (
        <div
          role="alert"
          className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center justify-between gap-3 shadow-xs"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMsg(null)}
            className="text-rose-700 hover:text-rose-900 font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Human Intervention Gate when required */}
      {selectedRun?.status === 'WAITING_FOR_HUMAN' && (
        <HumanInterventionGate
          taskId={selectedTask?.id}
          runId={selectedRun?.id}
          checkpointType={
            selectedRun.error_code === 'CAPTCHA_REQUIRED'
              ? 'CAPTCHA'
              : selectedRun.error_code === 'PAYMENT_REQUIRED'
              ? 'PAYMENT'
              : 'CAPTCHA'
          }
          description={selectedRun.error_summary || 'Operator approval needed before proceeding.'}
          onResume={handleResumeRun}
          onCancel={handleCancelRun}
        />
      )}

      {/* Main Orchestrator Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Tasks Queue (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ListTodo className="w-4 h-4 text-accent-emerald" />
              <h3 className="text-sm font-extrabold uppercase tracking-wider text-ink">
                Orchestrator Tasks Queue
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={loadTasks}
                disabled={loadingTasks}
                className="p-1.5 rounded-lg bg-white hover:bg-stone-100 text-stone-600 border border-stone-200 shadow-2xs transition-colors"
                title="Refresh task list"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingTasks ? 'animate-spin' : ''}`} />
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(!showCreateForm)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New Task</span>
              </button>
            </div>
          </div>

          {/* Inline Create Task Form */}
          {showCreateForm && (
            <GlassCard depth={2} className="p-4 border-emerald-300 bg-emerald-50/40">
              <form onSubmit={handleCreateTask} className="space-y-3">
                <div className="flex items-center justify-between border-b border-emerald-200/60 pb-2">
                  <h4 className="text-xs font-bold text-ink">Configure New Agent Task</h4>
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="text-stone-400 hover:text-stone-700 text-xs"
                  >
                    Cancel
                  </button>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                    Task Name
                  </label>
                  <input
                    type="text"
                    required
                    value={newTaskName}
                    onChange={(e) => setNewTaskName(e.target.value)}
                    className="w-full text-xs px-3 py-1.5 rounded-lg bg-white border border-stone-200 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                      Origin Station
                    </label>
                    <input
                      type="text"
                      required
                      list="taskOriginStations"
                      value={newOrigin}
                      onChange={(e) => setNewOrigin(e.target.value)}
                      className="w-full text-xs px-2.5 py-1.5 rounded-lg bg-white border border-stone-200 text-ink"
                    />
                    <datalist id="taskOriginStations">
                      {stationSuggestions.map((s) => (
                        <option key={s} value={s} />
                      ))}
                    </datalist>
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                      Destination Station
                    </label>
                    <input
                      type="text"
                      required
                      list="taskDestStations"
                      value={newDest}
                      onChange={(e) => setNewDest(e.target.value)}
                      className="w-full text-xs px-2.5 py-1.5 rounded-lg bg-white border border-stone-200 text-ink"
                    />
                    <datalist id="taskDestStations">
                      {stationSuggestions.map((s) => (
                        <option key={s} value={s} />
                      ))}
                    </datalist>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                      Travel Date
                    </label>
                    <input
                      type="date"
                      required
                      value={newDate}
                      onChange={(e) => setNewDate(e.target.value)}
                      className="w-full text-xs px-2 py-1.5 rounded-lg bg-white border border-stone-200 text-ink"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                      Class
                    </label>
                    <select
                      value={newClass}
                      onChange={(e) => setNewClass(e.target.value)}
                      className="w-full text-xs px-2 py-1.5 rounded-lg bg-white border border-stone-200 text-ink"
                    >
                      <option value="1A">1A (First AC)</option>
                      <option value="2A">2A (2-Tier AC)</option>
                      <option value="3A">3A (3-Tier AC)</option>
                      <option value="3E">3E (3 AC Economy)</option>
                      <option value="CC">CC (AC Chair)</option>
                      <option value="SL">SL (Sleeper)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                      Passengers
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={4}
                      value={newPassengers}
                      onChange={(e) => setNewPassengers(Number(e.target.value))}
                      className="w-full text-xs px-2 py-1.5 rounded-lg bg-white border border-stone-200 text-ink"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={actionBusy}
                  className="w-full py-2 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white text-xs font-bold transition-colors shadow-2xs"
                >
                  {actionBusy ? 'Creating Task...' : 'Submit Task to Backend'}
                </button>
              </form>
            </GlassCard>
          )}

          {/* Tasks List */}
          {loadingTasks ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-xl bg-stone-200/60 animate-pulse" />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <GlassCard className="text-center py-8">
              <ListTodo className="w-8 h-8 text-stone-300 mx-auto mb-2" />
              <p className="text-xs font-semibold text-ink">No Tasks Found in Backend</p>
              <p className="text-[11px] text-ink-muted mt-0.5">
                Create a new task above to initialize the orchestration pipeline.
              </p>
            </GlassCard>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {tasks.map((task) => {
                const isSelected = selectedTask?.id === task.id;
                return (
                  <div
                    key={task.id}
                    onClick={() => handleSelectTask(task)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-white border-accent-emerald shadow-md ring-1 ring-accent-emerald'
                        : 'bg-white/80 hover:bg-white border-stone-200/80 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-extrabold text-ink truncate max-w-[200px]">
                        {task.name || task.task_type}
                      </span>
                      <StatusBadge
                        label={task.status}
                        variant={getStatusBadgeVariant(task.status)}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-ink-muted">
                      <span className="font-mono">{task.id.slice(0, 8)}...</span>
                      <span>{new Date(task.created_at).toLocaleTimeString()}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Active Task Details & Execution Runs (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          {selectedTask ? (
            <GlassCard depth={1} className="space-y-4">
              {/* Task Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-stone-200/70">
                <div>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[10px] font-mono uppercase bg-stone-100 text-stone-700 px-2 py-0.5 rounded border border-stone-200">
                      ID: {selectedTask.id}
                    </span>
                    <span className="text-[10px] font-semibold text-ink-muted">
                      Version: {selectedTask.version}
                    </span>
                  </div>
                  <h3 className="text-base font-extrabold text-ink tracking-tight">
                    {selectedTask.name || selectedTask.task_type}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleStartNewRun}
                    disabled={actionBusy}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white text-xs font-semibold shadow-xs transition-colors"
                  >
                    <Play className="w-3.5 h-3.5" />
                    <span>Launch New Run</span>
                  </button>
                </div>
              </div>

              {/* Task Configuration Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-stone-50/70 p-3 rounded-xl border border-stone-200/60">
                <div>
                  <span className="text-[10px] text-ink-muted uppercase block font-semibold">
                    Task Type
                  </span>
                  <span className="font-bold text-ink">{selectedTask.task_type}</span>
                </div>
                <div>
                  <span className="text-[10px] text-ink-muted uppercase block font-semibold">
                    Current Status
                  </span>
                  <span className="font-bold text-ink">{selectedTask.status}</span>
                </div>
                <div>
                  <span className="text-[10px] text-ink-muted uppercase block font-semibold">
                    Created At
                  </span>
                  <span className="font-bold text-ink">
                    {new Date(selectedTask.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-ink-muted uppercase block font-semibold">
                    Current Step
                  </span>
                  <span className="font-bold text-ink">
                    {selectedTask.current_step || 'Idle'}
                  </span>
                </div>
              </div>

              {/* Runs Section */}
              <div className="pt-2">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <Activity className="w-4 h-4 text-accent-emerald" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-ink">
                      Execution Runs ({runs.length})
                    </h4>
                  </div>
                  {isPolling && (
                    <span className="flex items-center gap-1 text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                      Live Polling
                    </span>
                  )}
                </div>

                {loadingRuns ? (
                  <div className="h-20 rounded-xl bg-stone-100 animate-pulse" />
                ) : runs.length === 0 ? (
                  <div className="text-center py-6 bg-stone-50/60 rounded-xl border border-dashed border-stone-300">
                    <p className="text-xs text-ink-muted">No execution runs launched for this task yet.</p>
                    <button
                      type="button"
                      onClick={handleStartNewRun}
                      disabled={actionBusy}
                      className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-accent-emerald hover:underline"
                    >
                      <Play className="w-3 h-3" />
                      <span>Start First Execution Run</span>
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {/* Run Selector Tabs */}
                    <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                      {runs.map((r) => {
                        const isRunSelected = selectedRun?.id === r.id;
                        return (
                          <button
                            key={r.id}
                            type="button"
                            onClick={() => setSelectedRun(r)}
                            className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition-colors shrink-0 ${
                              isRunSelected
                                ? 'bg-ink text-white shadow-2xs'
                                : 'bg-stone-100 text-stone-700 hover:bg-stone-200'
                            }`}
                          >
                            Run: {r.id.slice(0, 8)} ({r.status})
                          </button>
                        );
                      })}
                    </div>

                    {/* Active Run Inspector Box */}
                    {selectedRun && (
                      <div className="p-4 rounded-xl bg-white border border-stone-200 space-y-3 shadow-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-stone-100">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-ink">
                              {selectedRun.id}
                            </span>
                            <StatusBadge
                              label={selectedRun.status}
                              variant={getStatusBadgeVariant(selectedRun.status)}
                            />
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] text-ink-muted">
                              Steps Completed: <strong>{selectedRun.steps_completed}</strong>
                            </span>
                          </div>
                        </div>

                        {/* Interactive Run Action Toolbar */}
                        <div className="flex flex-wrap items-center gap-2 pt-1">
                          {selectedRun.status === 'RUNNING' || selectedRun.status === 'CREATED' || selectedRun.status === 'PAUSED' ? (
                            <>
                              <button
                                type="button"
                                onClick={handleExecuteStep}
                                disabled={actionBusy}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-2xs transition-colors"
                              >
                                <Play className="w-3 h-3" />
                                <span>Execute Next Step</span>
                              </button>
                              {selectedRun.status === 'RUNNING' && (
                                <button
                                  type="button"
                                  onClick={handlePauseRun}
                                  disabled={actionBusy}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold shadow-2xs transition-colors"
                                >
                                  <Pause className="w-3 h-3" />
                                  <span>Pause Run</span>
                                </button>
                              )}
                              {selectedRun.status === 'PAUSED' && (
                                <button
                                  type="button"
                                  onClick={handleResumeRun}
                                  disabled={actionBusy}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold shadow-2xs transition-colors"
                                >
                                  <RotateCcw className="w-3 h-3" />
                                  <span>Resume Run</span>
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={handleCancelRun}
                                disabled={actionBusy}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 text-xs font-semibold shadow-2xs transition-colors"
                              >
                                <XCircle className="w-3 h-3" />
                                <span>Cancel</span>
                              </button>
                            </>
                          ) : (
                            <span className="text-xs text-ink-muted italic">
                              Run is in terminal state ({selectedRun.status}). Launch a new run to execute again.
                            </span>
                          )}
                        </div>

                        {/* Error info if present */}
                        {selectedRun.error_summary && (
                          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900">
                            <strong>{selectedRun.error_code || 'Error'}:</strong>{' '}
                            {selectedRun.error_summary}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </GlassCard>
          ) : (
            <GlassCard className="text-center py-12">
              <Layers className="w-10 h-10 text-stone-300 mx-auto mb-2" />
              <h3 className="font-bold text-sm text-ink">Select a Task</h3>
              <p className="text-xs text-ink-muted mt-1 max-w-sm mx-auto">
                Choose a task from the left queue to inspect its configuration and run execution steps.
              </p>
            </GlassCard>
          )}
        </div>
      </div>
    </div>
  );
}
