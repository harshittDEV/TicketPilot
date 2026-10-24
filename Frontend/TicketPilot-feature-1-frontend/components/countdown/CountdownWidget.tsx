'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Clock, AlertTriangle, CheckCircle, Info, Sparkles } from 'lucide-react';
import { SchedulerOpeningInfo } from '@/lib/types';
import { StatusBadge } from '../ui/StatusBadge';

interface CountdownWidgetProps {
  schedulerInfo?: SchedulerOpeningInfo;
  journeyTitle?: string;
  travelClass?: string;
  onWindowOpen?: () => void;
  className?: string;
}

interface TimeRemaining {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  totalMs: number;
  isExpired: boolean;
}

export function CountdownWidget({
  schedulerInfo,
  journeyTitle = 'Selected Journey',
  travelClass = '3A',
  onWindowOpen,
  className = '',
}: CountdownWidgetProps) {
  const [time, setTime] = useState<TimeRemaining>({
    days: 0,
    hours: 0,
    minutes: 0,
    seconds: 0,
    totalMs: 0,
    isExpired: false,
  });

  const [announcedMessage, setAnnouncedMessage] = useState<string>('');
  const lastAnnouncedMinute = useRef<number | null>(null);

  useEffect(() => {
    if (!schedulerInfo?.openingTimestampIST) return;

    const targetDate = new Date(schedulerInfo.openingTimestampIST).getTime();

    const calculateTime = () => {
      const now = Date.now();
      const diff = targetDate - now;

      if (diff <= 0) {
        setTime({
          days: 0,
          hours: 0,
          minutes: 0,
          seconds: 0,
          totalMs: 0,
          isExpired: true,
        });
        if (onWindowOpen && diff > -10000) {
          onWindowOpen();
        }
        return;
      }

      const totalSeconds = Math.floor(diff / 1000);
      const days = Math.floor(totalSeconds / 86400);
      const hours = Math.floor((totalSeconds % 86400) / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const seconds = totalSeconds % 60;

      setTime({
        days,
        hours,
        minutes,
        seconds,
        totalMs: diff,
        isExpired: false,
      });

      // Accessible Screen Reader Announcement:
      // Only announce every 5 minutes when far out, every minute when <= 15m, and at 30s.
      // Avoids overwhelming screen reader users with every second ticking!
      if (lastAnnouncedMinute.current !== minutes) {
        lastAnnouncedMinute.current = minutes;
        if (days === 0 && hours === 0 && minutes <= 15) {
          setAnnouncedMessage(`Tatkal preparation alert: ${minutes} minute${minutes !== 1 ? 's' : ''} remaining until official opening.`);
        } else if (minutes % 10 === 0) {
          setAnnouncedMessage(`Tatkal countdown update: ${hours} hours and ${minutes} minutes remaining.`);
        }
      }
    };

    calculateTime();
    const timer = setInterval(calculateTime, 1000);

    return () => clearInterval(timer);
  }, [schedulerInfo?.openingTimestampIST, onWindowOpen]);

  if (!schedulerInfo) {
    return (
      <div className={`p-6 rounded-2xl bg-stone-50 border border-stone-200 text-stone-600 ${className}`}>
        <div className="flex items-center gap-2 mb-2">
          <Clock className="w-5 h-5 text-stone-400" />
          <h3 className="font-semibold text-stone-700">Opening Time Unavailable</h3>
        </div>
        <p className="text-sm">
          Awaiting trip selection or sync with Member 3 Scheduler module to receive authoritative opening timestamp.
        </p>
      </div>
    );
  }

  const isAC = schedulerInfo.targetClassType === 'AC';
  const openTimeIST = schedulerInfo.openingTimeFormatted || (isAC ? '10:00 AM IST' : '11:00 AM IST');

  // Milestone preparation alerts
  const isWithin15Min = !time.isExpired && time.days === 0 && time.hours === 0 && time.minutes < 15;
  const isWithin5Min = !time.isExpired && time.days === 0 && time.hours === 0 && time.minutes < 5;

  return (
    <div
      role="region"
      aria-label="Tatkal Booking Opening Countdown"
      className={`relative overflow-hidden rounded-2xl p-6 border transition-all ${
        time.isExpired
          ? 'bg-emerald-50/90 border-emerald-300 text-emerald-950'
          : isWithin5Min
          ? 'bg-amber-50/90 border-amber-300 text-amber-950 shadow-glass-hover'
          : 'bg-white/80 border-glass-border shadow-glass'
      } ${className}`}
    >
      {/* Hidden ARIA Live region for non-intrusive screen reader updates */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {announcedMessage}
      </div>

      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Clock className={`w-5 h-5 ${time.isExpired ? 'text-emerald-700' : 'text-accent-emerald'}`} aria-hidden="true" />
            <h3 className="font-semibold text-ink text-base">
              {time.isExpired ? 'Tatkal Booking Window Open' : 'Tatkal Opening Countdown'}
            </h3>
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            {journeyTitle} • <span className="font-medium">{travelClass} ({isAC ? 'AC Quota' : 'Non-AC Quota'})</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge
            label={isAC ? 'AC: 10:00 AM IST' : 'Non-AC: 11:00 AM IST'}
            variant={isAC ? 'ac' : 'nonac'}
          />
          {schedulerInfo.isAuthoritative ? (
            <StatusBadge label="Member 3 Verified" variant="success" hint="Calculated by Scheduler module" />
          ) : (
            <StatusBadge label="Configured Default" variant="warning" hint="Awaiting Member 3 origin verification" />
          )}
        </div>
      </div>

      {/* Countdown Digits */}
      {time.isExpired ? (
        <div className="py-4 px-5 rounded-xl bg-emerald-100/80 border border-emerald-300 text-center">
          <div className="flex items-center justify-center gap-2 text-emerald-800 font-bold text-lg mb-1">
            <CheckCircle className="w-5 h-5" aria-hidden="true" />
            Official Booking Active on IRCTC
          </div>
          <p className="text-xs text-emerald-700">
            The configured opening threshold ({openTimeIST}) has passed. Proceed immediately to the official IRCTC portal.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-2 sm:gap-4 my-3 text-center">
          <div className="bg-white/90 border border-stone-200/90 rounded-xl p-2.5 sm:p-3 shadow-xs">
            <span className="block text-2xl sm:text-3xl font-extrabold text-ink font-mono tracking-tight">
              {String(time.days).padStart(2, '0')}
            </span>
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Days</span>
          </div>
          <div className="bg-white/90 border border-stone-200/90 rounded-xl p-2.5 sm:p-3 shadow-xs">
            <span className="block text-2xl sm:text-3xl font-extrabold text-ink font-mono tracking-tight">
              {String(time.hours).padStart(2, '0')}
            </span>
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Hours</span>
          </div>
          <div className="bg-white/90 border border-stone-200/90 rounded-xl p-2.5 sm:p-3 shadow-xs">
            <span className="block text-2xl sm:text-3xl font-extrabold text-ink font-mono tracking-tight">
              {String(time.minutes).padStart(2, '0')}
            </span>
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Minutes</span>
          </div>
          <div className="bg-white/90 border border-stone-200/90 rounded-xl p-2.5 sm:p-3 shadow-xs">
            <span className="block text-2xl sm:text-3xl font-extrabold text-accent-emerald font-mono tracking-tight">
              {String(time.seconds).padStart(2, '0')}
            </span>
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Seconds</span>
          </div>
        </div>
      )}

      {/* Target Timestamp & Timezone Notice */}
      <div className="mt-4 pt-3 border-t border-stone-200/70 flex flex-wrap items-center justify-between text-xs text-ink-muted gap-2">
        <span>
          Target: <strong className="text-ink">{openTimeIST}</strong> on {schedulerInfo.openingTimestampIST.slice(0, 10)}
        </span>
        <span className="flex items-center gap-1 text-stone-500">
          <Info className="w-3.5 h-3.5" aria-hidden="true" />
          Indian Standard Time (UTC+05:30)
        </span>
      </div>

      {/* Origin Date Notice */}
      {schedulerInfo.originDateNotice && (
        <div className="mt-2 text-[11px] text-amber-800/90 bg-amber-50/80 p-2 rounded-lg border border-amber-200 flex items-start gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-700" aria-hidden="true" />
          <span>{schedulerInfo.originDateNotice}</span>
        </div>
      )}

      {/* Readiness Alert when < 15 minutes */}
      {isWithin15Min && !time.isExpired && (
        <div className="mt-3 p-3 rounded-xl bg-amber-100/90 border border-amber-300 text-amber-950 text-xs flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-700 shrink-0" aria-hidden="true" />
          <span>
            <strong>Preparation Window Active:</strong> Log into IRCTC now, verify Master Passenger list is saved, and keep payment instrument ready.
          </span>
        </div>
      )}
    </div>
  );
}
