'use client';

import React from 'react';
import { GlassCard } from '@/components/ui/GlassCard';
import {
  ShieldCheck,
  CreditCard,
  Train,
  Users,
  ExternalLink,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileText,
} from 'lucide-react';

interface PaymentBoundaryModalProps {
  taskId: string;
  runId: string;
  taskConfiguration?: Record<string, any> | null;
  extractedSummary?: string | null;
  onComplete: () => void;
  onCancel: () => void;
  className?: string;
}

export function PaymentBoundaryModal({
  taskId,
  runId,
  taskConfiguration,
  extractedSummary,
  onComplete,
  onCancel,
  className = '',
}: PaymentBoundaryModalProps) {
  const cfg = taskConfiguration || {};
  const passengers = cfg.passengers || [];
  const src = cfg.source || 'NDLS';
  const dst = cfg.destination || 'BCT';
  const travelDate = cfg.travel_date || '2026-12-20';
  const travelClass = cfg.travel_class || '3A';
  const quota = cfg.quota || 'TATKAL';

  const handleOpenOfficialPortal = () => {
    window.open('https://www.irctc.co.in/nget/booking/review-booking', '_blank', 'noopener,noreferrer');
  };

  return (
    <div className={`p-6 rounded-2xl bg-amber-50 border-2 border-amber-400 text-amber-950 shadow-xl space-y-5 ${className}`}>
      {/* Header Banner */}
      <div className="flex items-start justify-between gap-4 border-b border-amber-300 pb-4">
        <div className="flex items-start gap-3">
          <div className="p-2.5 rounded-xl bg-amber-200/80 text-amber-900 shrink-0">
            <CreditCard className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-200 text-amber-900 px-2.5 py-0.5 rounded-full font-mono border border-amber-400">
                Mandatory Safety Boundary Reached
              </span>
              <span className="text-[10px] font-mono text-amber-800">
                Run ID: {runId.slice(0, 8)}...
              </span>
            </div>
            <h3 className="text-lg font-black text-amber-950 tracking-tight">
              Automation Halted: Operator Payment Authorization Required
            </h3>
            <p className="text-xs text-amber-900 mt-0.5">
              TicketPilot has prepared and navigated the reservation workflow up to the payment gateway. Automated payment submission is strictly disabled.
            </p>
          </div>
        </div>
      </div>

      {/* Verified Journey Itinerary Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        <div className="p-3 rounded-xl bg-white/80 border border-amber-200 space-y-1">
          <span className="text-[10px] uppercase font-bold text-amber-800 block">Sector & Date</span>
          <div className="font-bold text-ink flex items-center gap-1.5 text-sm">
            <Train className="w-4 h-4 text-accent-emerald" />
            <span>{src} → {dst}</span>
          </div>
          <span className="text-stone-600 block">{travelDate}</span>
        </div>

        <div className="p-3 rounded-xl bg-white/80 border border-amber-200 space-y-1">
          <span className="text-[10px] uppercase font-bold text-amber-800 block">Class & Quota</span>
          <div className="font-bold text-ink text-sm">
            {travelClass} • {quota}
          </div>
          <span className="text-stone-600 block">Tatkal Allocation</span>
        </div>

        <div className="p-3 rounded-xl bg-white/80 border border-amber-200 space-y-1">
          <span className="text-[10px] uppercase font-bold text-amber-800 block">Passenger Roster</span>
          <div className="font-bold text-ink text-sm">
            {passengers.length} Passenger{passengers.length > 1 ? 's' : ''}
          </div>
          <span className="text-stone-600 block truncate">
            {passengers.map((p: any) => p.name).join(', ') || 'Roster populated'}
          </span>
        </div>
      </div>

      {/* Extracted Portal Observations / Fare Breakdown */}
      {extractedSummary && (
        <div className="p-3.5 rounded-xl bg-amber-100/70 border border-amber-300 space-y-1.5 text-xs">
          <div className="flex items-center gap-1.5 font-bold text-amber-950 text-xs">
            <FileText className="w-3.5 h-3.5 text-amber-800" />
            <span>Observed Portal Reservation Summary:</span>
          </div>
          <p className="font-mono text-[11px] text-amber-900 whitespace-pre-wrap leading-relaxed">
            {extractedSummary}
          </p>
        </div>
      )}

      {/* Safety Compliance Statement */}
      <div className="p-3 rounded-xl bg-white/90 border border-amber-300 text-xs space-y-1">
        <div className="flex items-center gap-2 font-bold text-amber-900">
          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>Payment Protection & Anti-Fraud Guarantee</span>
        </div>
        <p className="text-[11px] text-stone-700 leading-relaxed">
          No bank credentials, credit cards, or UPI PINs were transmitted or saved. You must review the booking summary in the browser and authenticate payment through your authorized bank/UPI app.
        </p>
      </div>

      {/* Interactive Actions */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <button
          type="button"
          onClick={handleOpenOfficialPortal}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-amber-800 hover:bg-amber-900 text-white font-bold text-xs shadow-md transition-all"
        >
          <ExternalLink className="w-4 h-4" />
          <span>Open Portal & Authorize Payment Manually</span>
        </button>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-xl bg-white hover:bg-stone-100 text-stone-700 font-semibold text-xs border border-stone-300 transition-colors"
          >
            Abort Booking
          </button>
          <button
            type="button"
            onClick={onComplete}
            className="px-5 py-2 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white font-bold text-xs shadow-xs transition-colors"
          >
            Mark Workflow Completed
          </button>
        </div>
      </div>
    </div>
  );
}
