'use client';

import React, { useState } from 'react';
import { BookingStatus, TravelClass } from '@/lib/types';
import { api } from '@/lib/api';
import { CheckCircle2, AlertCircle, FileText, Send, Info } from 'lucide-react';

interface BookingOutcomeFormProps {
  tripId: string;
  trainNumber: string;
  trainName?: string;
  journeyDate: string;
  travelClass: TravelClass;
  onSuccess?: () => void;
}

export function BookingOutcomeForm({
  tripId,
  trainNumber,
  trainName = 'Express Train',
  journeyDate,
  travelClass,
  onSuccess,
}: BookingOutcomeFormProps) {
  const [status, setStatus] = useState<BookingStatus>('CONFIRMED');
  const [pnr, setPnr] = useState('');
  const [proofReference, setProofReference] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    // Validate PNR if status is confirmed
    const cleanedPnr = pnr.trim();
    if (status === 'CONFIRMED' && cleanedPnr && !/^\d{3}-?\d{7}$/.test(cleanedPnr)) {
      setErrorMessage('Please enter a standard 10-digit Indian Railways PNR (e.g. 123-4567890 or 1234567890).');
      setIsSubmitting(false);
      return;
    }

    try {
      const res = await api.recordBookingOutcome({
        tripId,
        trainNumber,
        trainName,
        journeyDate,
        travelClass,
        status,
        isManuallyRecorded: true,
        pnr: cleanedPnr || undefined,
        proofReference: proofReference.trim() || undefined,
        bookingTimestamp: new Date().toISOString(),
        notes: notes.trim() || undefined,
      });

      if (!res.success) {
        setErrorMessage(res.error?.message || 'Failed to record booking outcome.');
      } else {
        setSubmitSuccess(true);
        if (onSuccess) onSuccess();
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitSuccess) {
    return (
      <div className="p-6 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-center">
        <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto mb-2" />
        <h4 className="font-bold text-base">Booking Outcome Recorded Successfully</h4>
        <p className="text-xs text-emerald-800 mt-1 max-w-md mx-auto">
          Your outcome has been saved to your local Booking History. You can view or audit it at any time in the Booking History tab.
        </p>
        <button
          onClick={() => setSubmitSuccess(false)}
          className="mt-4 px-4 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-medium transition-colors"
        >
          Record Another Outcome
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {errorMessage && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Outcome Status Selector */}
      <div>
        <label className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
          Booking Outcome Status *
        </label>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as BookingStatus)}
          className="w-full text-sm bg-white border border-stone-200 rounded-xl px-3 py-2 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
          required
        >
          <option value="CONFIRMED">Confirmed Ticket</option>
          <option value="IN_PROGRESS">In Progress / Awaiting Payment Resolution</option>
          <option value="FAILED">Failed / Quota Exhausted / Gateway Timeout</option>
          <option value="UNKNOWN">Unknown / Not Completed</option>
          <option value="NOT_STARTED">Not Started</option>
        </select>
      </div>

      {/* PNR Field (only for manual entry) */}
      <div>
        <label className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
          10-Digit PNR Number (Optional)
        </label>
        <input
          type="text"
          placeholder="e.g. 284-9182371 or 2849182371"
          value={pnr}
          onChange={(e) => setPnr(e.target.value)}
          className="w-full text-sm bg-white border border-stone-200 rounded-xl px-3 py-2 font-mono text-ink placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-accent-emerald"
          maxLength={12}
        />
        <p className="text-[11px] text-stone-500 mt-1">
          Manually recorded for your personal travel logs. Never shared with unauthorized third parties.
        </p>
      </div>

      {/* Proof Reference (alphanumeric transaction or receipt ID) */}
      <div>
        <label className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
          Proof / Transaction Reference (Optional)
        </label>
        <input
          type="text"
          placeholder="e.g. IRCTC Transaction ID: TXN109823912"
          value={proofReference}
          onChange={(e) => setProofReference(e.target.value)}
          className="w-full text-sm bg-white border border-stone-200 rounded-xl px-3 py-2 text-ink placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-accent-emerald"
        />
        <p className="text-[11px] text-stone-500 mt-1">
          Reference code only. File uploads are not stored or transmitted without explicit backend support.
        </p>
      </div>

      {/* Notes */}
      <div>
        <label className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
          Booking Notes & Experience
        </label>
        <textarea
          rows={2}
          placeholder="e.g. Completed payment via SBI UPI in 42 seconds; Coach B3 Berth 21."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full text-sm bg-white border border-stone-200 rounded-xl px-3 py-2 text-ink placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-accent-emerald"
        />
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full py-2.5 px-4 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-sm transition-all focus:ring-2 focus:ring-accent-emerald focus:ring-offset-2 disabled:opacity-50"
      >
        <Send className="w-4 h-4" />
        <span>{isSubmitting ? 'Recording Outcome...' : 'Save Booking Outcome'}</span>
      </button>

      <div className="flex items-start gap-1.5 text-[11px] text-stone-500 pt-1">
        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        <span>
          This records a manually entered outcome for your records. It is flagged as <em>manually recorded</em> and not independently verified against IRCTC databases.
        </span>
      </div>
    </form>
  );
}
