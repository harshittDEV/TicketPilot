'use client';

import React, { useState } from 'react';
import {
  ShieldAlert,
  Key,
  CreditCard,
  CheckCircle2,
  XCircle,
  Play,
  Pause,
  ExternalLink,
  Lock,
  Info,
} from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';

export interface HumanInterventionGateProps {
  taskId?: string;
  runId?: string;
  checkpointType?: 'CAPTCHA' | 'PAYMENT' | 'SESSION_VERIFY' | 'UNKNOWN_OUTCOME' | string;
  description?: string;
  onResume?: () => Promise<void> | void;
  onCancel?: () => Promise<void> | void;
  className?: string;
}

export function HumanInterventionGate({
  taskId,
  runId,
  checkpointType = 'CAPTCHA',
  description,
  onResume,
  onCancel,
  className = '',
}: HumanInterventionGateProps) {
  const [operatorConfirmed, setOperatorConfirmed] = useState(false);
  const [acting, setActing] = useState(false);

  const getCheckpointDetails = () => {
    switch (checkpointType?.toUpperCase()) {
      case 'PAYMENT':
        return {
          title: 'Human Authorization Checkpoint: Payment Disabled By Policy',
          icon: CreditCard,
          badge: 'MANDATORY SAFETY BOUNDARY',
          color: 'border-amber-300 bg-amber-50/90 text-amber-950',
          guidance:
            'Autonomous payment execution is strictly disabled in this development build. The human operator must complete payment directly on the official Indian Railways IRCTC portal.',
          actionText: 'I have completed/authorized manual payment',
        };
      case 'CAPTCHA':
      case 'CAPTCHA_VERIFICATION':
        return {
          title: 'Human In The Loop: CAPTCHA Verification Required',
          icon: ShieldAlert,
          badge: 'ANTI-BOT COMPLIANCE',
          color: 'border-rose-300 bg-rose-50/90 text-rose-950',
          guidance:
            'IRCTC anti-bot challenge encountered. Automated solving or bypassing of CAPTCHAs is prohibited. The human operator must solve the challenge in the active browser session.',
          actionText: 'I have solved the CAPTCHA in the browser',
        };
      case 'SESSION_VERIFY':
        return {
          title: 'User Authentication Checkpoint',
          icon: Key,
          badge: 'CREDENTIAL SAFETY',
          color: 'border-blue-300 bg-blue-50/90 text-blue-950',
          guidance:
            'Official 2FA or IRCTC OTP session challenge detected. Enter OTP directly on the official portal to proceed.',
          actionText: 'Session authenticated on official portal',
        };
      default:
        return {
          title: 'Human Intervention Required',
          icon: Info,
          badge: 'CHECKPOINT PAUSED',
          color: 'border-stone-300 bg-stone-50/90 text-stone-900',
          guidance:
            description ||
            'The execution engine paused because a protected boundary or unknown state requires human verification.',
          actionText: 'I have verified and wish to resume',
        };
    }
  };

  const details = getCheckpointDetails();
  const Icon = details.icon;

  const handleResume = async () => {
    if (!operatorConfirmed) return;
    setActing(true);
    try {
      if (onResume) await onResume();
    } finally {
      setActing(false);
    }
  };

  const handleCancel = async () => {
    setActing(true);
    try {
      if (onCancel) await onCancel();
    } finally {
      setActing(false);
    }
  };

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`rounded-2xl border p-5 md:p-6 shadow-glass-elevated ${details.color} backdrop-blur-xl ${className}`}
    >
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="p-2.5 rounded-xl bg-white shadow-2xs text-rose-700 shrink-0">
            <Icon className="w-6 h-6" aria-hidden="true" />
          </div>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-black/10 border border-black/10">
                {details.badge}
              </span>
              {taskId && (
                <span className="text-[11px] font-mono text-stone-600">
                  Task: {taskId.slice(0, 8)}...
                </span>
              )}
              {runId && (
                <span className="text-[11px] font-mono text-stone-600">
                  Run: {runId.slice(0, 8)}...
                </span>
              )}
            </div>
            <h3 className="text-base font-extrabold tracking-tight text-ink">
              {details.title}
            </h3>
            <p className="text-xs text-stone-700 leading-relaxed max-w-2xl">
              {details.guidance}
            </p>
          </div>
        </div>

        {/* Official Portal Quick Link */}
        <a
          href="https://www.irctc.co.in/"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-stone-50 border border-stone-300 text-xs font-semibold text-stone-800 transition-colors shadow-2xs self-start shrink-0"
        >
          <span>Open Official IRCTC</span>
          <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
        </a>
      </div>

      {/* Confirmation Checkbox */}
      <div className="mt-5 pt-4 border-t border-black/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <label className="flex items-center gap-2.5 cursor-pointer text-xs font-semibold text-ink select-none">
          <input
            type="checkbox"
            checked={operatorConfirmed}
            onChange={(e) => setOperatorConfirmed(e.target.checked)}
            className="w-4 h-4 rounded border-stone-300 text-emerald-600 focus:ring-emerald-500"
          />
          <span>{details.actionText}</span>
        </label>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={handleCancel}
            disabled={acting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white hover:bg-stone-100 text-rose-800 border border-rose-200 shadow-2xs transition-colors"
          >
            <XCircle className="w-3.5 h-3.5" />
            <span>Abort Run</span>
          </button>
          <button
            type="button"
            onClick={handleResume}
            disabled={!operatorConfirmed || acting}
            className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-2xs ${
              operatorConfirmed && !acting
                ? 'bg-emerald-700 hover:bg-emerald-800 text-white shadow-emerald-700/20'
                : 'bg-stone-300 text-stone-500 cursor-not-allowed'
            }`}
          >
            <Play className="w-3.5 h-3.5" />
            <span>{acting ? 'Resuming...' : 'Confirm & Resume Execution'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
