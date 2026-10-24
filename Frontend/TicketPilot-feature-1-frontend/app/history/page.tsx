'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { BookingOutcomeRecord, BookingStatus } from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { AuditEvidenceInspector } from '@/components/audit/AuditEvidenceInspector';
import {
  History,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  FileText,
  Info,
  ShieldCheck,
  FileCheck,
} from 'lucide-react';
import Link from 'next/link';

export default function HistoryAndAuditPage() {
  const [history, setHistory] = useState<BookingOutcomeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  useEffect(() => {
    async function loadHistory() {
      setLoading(true);
      const res = await api.getBookingHistory();
      setHistory(res.data || []);
      setLoading(false);
    }
    loadHistory();
  }, []);

  const filteredHistory = history.filter((item) => {
    if (statusFilter === 'ALL') return true;
    return item.status === statusFilter;
  });

  const getStatusIcon = (status: BookingStatus) => {
    switch (status) {
      case 'CONFIRMED':
        return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-rose-600" />;
      case 'IN_PROGRESS':
        return <Clock className="w-4 h-4 text-amber-600" />;
      default:
        return <AlertCircle className="w-4 h-4 text-stone-500" />;
    }
  };

  const getStatusBadgeVariant = (status: BookingStatus) => {
    switch (status) {
      case 'CONFIRMED':
        return 'success';
      case 'FAILED':
        return 'error';
      case 'IN_PROGRESS':
        return 'warning';
      default:
        return 'neutral';
    }
  };

  return (
    <div className="space-y-10 pb-12">
      {/* SECTION 1: Backend Audit Trail & Cryptographic Evidence Inspector */}
      <section className="space-y-4">
        <AuditEvidenceInspector />
      </section>

      {/* SECTION 2: Personal Booking History Records */}
      <section className="space-y-4 pt-4 border-t border-stone-200/80">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-stone-200/60">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <History className="w-5 h-5 text-accent-emerald" />
              <h2 className="text-xl font-extrabold text-ink tracking-tight">
                Personal Travel Records & Booking Archive
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-ink-muted">
              Manually recorded outcomes, 10-digit PNR references, and official booking status notes.
            </p>
          </div>

          {/* Filter Controls */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-ink-muted uppercase tracking-wider">
              Status:
            </span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs bg-white border border-stone-200 rounded-xl px-3 py-2 text-ink font-semibold focus:outline-none focus:ring-2 focus:ring-accent-emerald"
            >
              <option value="ALL">All Outcomes ({history.length})</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="FAILED">Failed</option>
              <option value="IN_PROGRESS">In Progress</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-3 border-accent-emerald border-t-transparent mb-2" />
            <p className="text-xs font-semibold text-ink">Loading history records...</p>
          </div>
        ) : filteredHistory.length === 0 ? (
          <GlassCard className="text-center py-10">
            <History className="w-10 h-10 text-stone-300 mx-auto mb-2" />
            <h3 className="font-bold text-sm text-ink">No Personal Travel Records</h3>
            <p className="text-xs text-ink-muted mt-1 max-w-sm mx-auto">
              Outcomes can be recorded from the Assisted Booking Desk after completing an official
              booking.
            </p>
            <Link
              href="/booking"
              className="mt-3 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-accent-emerald text-white text-xs font-semibold"
            >
              <span>Go to Booking Desk</span>
            </Link>
          </GlassCard>
        ) : (
          <div className="space-y-3">
            {filteredHistory.map((item) => (
              <GlassCard key={item.id} depth={1} className="p-4 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-stone-100">
                  <div className="flex items-center gap-2.5">
                    {getStatusIcon(item.status)}
                    <h3 className="font-bold text-sm text-ink">
                      Train #{item.trainNumber} {item.trainName && `(${item.trainName})`}
                    </h3>
                    <StatusBadge label={item.travelClass} variant="info" />
                  </div>

                  <div className="flex items-center gap-2">
                    <StatusBadge
                      label={item.status}
                      variant={getStatusBadgeVariant(item.status)}
                    />
                    {item.isManuallyRecorded ? (
                      <StatusBadge label="Manually Recorded" variant="neutral" hint="Logged by user" />
                    ) : (
                      <StatusBadge label="API Verified" variant="success" hint="Verified via backend" />
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-stone-600">
                  <div>
                    <span className="text-[10px] text-stone-400 uppercase font-semibold block">
                      Journey Date
                    </span>
                    <strong className="text-ink">{item.journeyDate}</strong>
                  </div>

                  <div>
                    <span className="text-[10px] text-stone-400 uppercase font-semibold block">
                      10-Digit PNR Reference
                    </span>
                    {item.pnr ? (
                      <strong className="text-ink font-mono tracking-wider">{item.pnr}</strong>
                    ) : (
                      <span className="text-stone-400 italic">None provided</span>
                    )}
                  </div>

                  <div>
                    <span className="text-[10px] text-stone-400 uppercase font-semibold block">
                      Logged Timestamp
                    </span>
                    <span className="text-stone-700">
                      {new Date(item.recordedAt).toLocaleString()}
                    </span>
                  </div>
                </div>

                {item.notes && (
                  <div className="text-xs text-stone-700 bg-amber-50/60 p-2.5 rounded-lg border border-amber-200/60">
                    <span className="font-semibold text-amber-900 block mb-0.5">Booking Notes:</span>
                    <p>{item.notes}</p>
                  </div>
                )}
              </GlassCard>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
