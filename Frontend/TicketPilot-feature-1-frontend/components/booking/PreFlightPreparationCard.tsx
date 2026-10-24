'use client';

import React, { useState } from 'react';
import { api } from '@/lib/api';
import { PreparationReport, CheckResult, PreparationPlanStep } from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Calendar,
  Clock,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  Database,
  Cpu,
  Layers,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';

interface PreFlightPreparationCardProps {
  taskId: string;
  initialReport?: PreparationReport | null;
  onPrepared?: (report: PreparationReport) => void;
  className?: string;
}

export function PreFlightPreparationCard({
  taskId,
  initialReport,
  onPrepared,
  className = '',
}: PreFlightPreparationCardProps) {
  const [report, setReport] = useState<PreparationReport | null>(initialReport || null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showAllChecks, setShowAllChecks] = useState(false);
  const [showPlan, setShowPlan] = useState(true);

  const handleRunPreparation = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.prepareTask(taskId);
      if (res.success && res.data) {
        setReport(res.data);
        onPrepared?.(res.data);
      } else {
        setErrorMsg(res.error?.message || 'Preparation diagnostics failed');
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Network failure during preparation');
    } finally {
      setLoading(false);
    }
  };

  const plan = report?.execution_plan || report?.proposed_execution_plan || [];
  const isReady = report?.overall_ready ?? report?.is_ready ?? report?.can_proceed_to_booking ?? false;
  const passedCount = report?.checks?.filter((c) => c.passed).length || 0;
  const totalChecks = report?.checks?.length || 12;
  const timeStr = report?.prepared_at || report?.timestamp;
  const summaryText =
    report?.summary ||
    (isReady
      ? 'All 12 pre-flight checks evaluated. Journey is ready for autonomous booking execution.'
      : 'Prerequisites require attention before booking window.');

  return (
    <GlassCard depth={2} className={`space-y-5 p-5 border-emerald-500/20 ${className}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-stone-200/80">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-accent-emerald bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
              <Cpu className="w-3.5 h-3.5" />
              12-Point Autonomous Pre-Flight Engine
            </span>
            {timeStr && (
              <span className="text-[10px] text-ink-muted">
                Checked at: {new Date(timeStr).toLocaleTimeString()}
              </span>
            )}
          </div>
          <h3 className="text-base font-extrabold text-ink tracking-tight">
            Journey Preparation & Prerequisites Verification
          </h3>
          <p className="text-xs text-ink-muted mt-0.5">
            Authentic backend validation of station codes, train roster, credentials, anti-bot checkpoints, and timing rules.
          </p>
        </div>

        <button
          type="button"
          onClick={handleRunPreparation}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white text-xs font-semibold shadow-xs transition-colors shrink-0 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>{report ? 'Re-Run Preparation Checks' : 'Run Pre-Flight Diagnostics'}</span>
        </button>
      </div>

      {/* Error alert */}
      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Overall Status Banner */}
      {report && (
        <div
          className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
            isReady
              ? 'bg-emerald-50/80 border-emerald-200/90 text-emerald-950'
              : 'bg-amber-50/80 border-amber-200/90 text-amber-950'
          }`}
        >
          <div className="flex items-start gap-3">
            {isReady ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            )}
            <div>
              <div className="flex items-center gap-2 font-bold text-sm">
                <span>
                  {isReady
                    ? 'Pre-Flight Diagnostics Passed - Journey Fully Prepared'
                    : 'Prerequisites Require Attention Before Booking Window'}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold bg-white/80 border">
                  {passedCount} / {totalChecks} Checks Passed
                </span>
              </div>
              <p className="text-xs opacity-90 mt-0.5">{summaryText}</p>
            </div>
          </div>

          <div className="text-right shrink-0">
            <span className="text-[11px] font-bold block">
              {report.is_ready ? 'EXECUTION READY' : 'PRE-FLIGHT INCOMPLETE'}
            </span>
            <span className="text-[10px] text-ink-muted">
              Source: Railway Open Data & Vault
            </span>
          </div>
        </div>
      )}

      {/* Checks Grid / List */}
      {report && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-ink-muted">
            <span>Diagnostic Verification Roster</span>
            <button
              type="button"
              onClick={() => setShowAllChecks(!showAllChecks)}
              className="inline-flex items-center gap-1 text-accent-emerald hover:underline font-semibold"
            >
              <span>{showAllChecks ? 'Collapse Details' : 'View All 12 Checks'}</span>
              {showAllChecks ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {(showAllChecks ? report.checks : report.checks.slice(0, 4)).map((check) => (
              <div
                key={check.check_id}
                className={`p-3 rounded-xl border transition-colors ${
                  check.passed
                    ? 'bg-white/70 border-stone-200/80 hover:border-emerald-200'
                    : check.severity === 'ERROR'
                    ? 'bg-rose-50/50 border-rose-200 text-rose-950'
                    : 'bg-amber-50/50 border-amber-200 text-amber-950'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  {check.passed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  ) : check.severity === 'ERROR' ? (
                    <XCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1 mb-0.5">
                      <span className="font-bold text-xs text-ink truncate">{check.name}</span>
                      <span
                        className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-semibold uppercase ${
                          check.passed
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {check.passed ? 'PASSED' : check.severity}
                      </span>
                    </div>
                    <p className="text-[11px] text-stone-600 line-clamp-2 leading-relaxed">
                      {check.details}
                    </p>
                    {check.remediation && (
                      <p className="text-[10px] text-amber-800 bg-amber-50/70 p-1 rounded mt-1.5 border border-amber-200/60">
                        <strong>Remediation:</strong> {check.remediation}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Proposed 7-Step Autonomous Execution Plan */}
      {report && plan && plan.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-stone-200/70">
          <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-ink-muted">
            <div className="flex items-center gap-1.5 text-ink">
              <Layers className="w-3.5 h-3.5 text-accent-emerald" />
              <span>Proposed Autonomous Execution Plan ({plan.length} Steps)</span>
            </div>
            <button
              type="button"
              onClick={() => setShowPlan(!showPlan)}
              className="text-accent-emerald hover:underline text-[11px] font-semibold"
            >
              {showPlan ? 'Hide Plan' : 'Show Plan'}
            </button>
          </div>

          {showPlan && (
            <div className="rounded-xl border border-stone-200 overflow-hidden bg-white/90 text-xs shadow-2xs">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-200 text-[10px] font-bold text-ink-muted uppercase">
                    <th className="py-2 px-3 w-12 text-center">Step</th>
                    <th className="py-2 px-3">Action & Tool</th>
                    <th className="py-2 px-3">Description</th>
                    <th className="py-2 px-3 text-right">Safety Boundary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 font-sans">
                  {plan.map((step) => {
                    const isCaptcha = step.step === 4;
                    const isPayment = step.step === 6;
                    return (
                      <tr
                        key={step.step}
                        className={`transition-colors ${
                          isCaptcha
                            ? 'bg-rose-50/30 font-medium'
                            : isPayment
                            ? 'bg-amber-50/40 font-medium'
                            : 'hover:bg-stone-50/50'
                        }`}
                      >
                        <td className="py-2 px-3 text-center font-mono font-bold text-stone-500">
                          {step.step}
                        </td>
                        <td className="py-2 px-3">
                          <span className="font-mono font-semibold text-accent-emerald text-[11px] block">
                            {step.action}
                          </span>
                          <span className="text-[10px] text-ink-muted">{step.target}</span>
                        </td>
                        <td className="py-2 px-3 text-[11px] text-stone-700 leading-snug">
                          {step.description}
                        </td>
                        <td className="py-2 px-3 text-right shrink-0">
                          {isCaptcha ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-700 bg-rose-100/80 px-2 py-0.5 rounded-full border border-rose-200">
                              <ShieldAlert className="w-3 h-3" />
                              CAPTCHA Checkpoint
                            </span>
                          ) : isPayment ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-800 bg-amber-100/80 px-2 py-0.5 rounded-full border border-amber-300">
                              <ShieldCheck className="w-3 h-3" />
                              Payment Boundary (Halt)
                            </span>
                          ) : (
                            <span className="text-[10px] text-stone-400 font-mono">
                              Automated
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* When no report exists yet */}
      {!report && !loading && (
        <div className="text-center py-6 bg-stone-50/70 rounded-xl border border-dashed border-stone-300 space-y-2">
          <Info className="w-6 h-6 text-stone-400 mx-auto" />
          <p className="text-xs text-ink-muted max-w-md mx-auto">
            Click <strong>&quot;Run Pre-Flight Diagnostics&quot;</strong> to evaluate Indian Railways station codes, train timetable availability, passenger quotas, and security boundaries.
          </p>
        </div>
      )}
    </GlassCard>
  );
}
