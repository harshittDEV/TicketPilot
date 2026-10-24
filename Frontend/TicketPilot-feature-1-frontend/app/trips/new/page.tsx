'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { TripCreateInput } from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { TripForm } from '@/components/trips/TripForm';
import { Train, ArrowLeft, ShieldCheck } from 'lucide-react';
import Link from 'next/link';

export default function NewTripPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCreate = async (input: TripCreateInput): Promise<boolean> => {
    setIsSubmitting(true);
    const res = await api.createTrip(input);
    setIsSubmitting(false);

    if (res.success && res.data) {
      router.push('/trips');
      return true;
    }
    return false;
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Breadcrumb & Navigation */}
      <div>
        <Link
          href="/trips"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-stone-600 hover:text-ink transition-colors mb-2"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to My Trips</span>
        </Link>
        <h1 className="text-2xl font-extrabold text-ink tracking-tight">Configure New Journey</h1>
        <p className="text-xs sm:text-sm text-ink-muted mt-0.5">
          Enter your sector, journey date, and class preferences to calculate Tatkal opening timings.
        </p>
      </div>

      <GlassCard depth={2}>
        <div className="flex items-center gap-2 mb-4 pb-3 border-b border-stone-200/70">
          <Train className="w-5 h-5 text-accent-emerald" />
          <h2 className="font-bold text-base text-ink">Journey Configuration Details</h2>
        </div>

        <TripForm
          onSubmit={handleCreate}
          isSubmitting={isSubmitting}
          submitButtonText="Create Journey Profile"
          cancelHref="/trips"
        />
      </GlassCard>

      <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200/80 text-xs text-amber-950 flex items-start gap-2.5">
        <ShieldCheck className="w-4 h-4 text-amber-800 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <strong>Tatkal Quota Rule:</strong> AC Tatkal booking opens at 10:00 AM IST and Non-AC opens at 11:00 AM IST, exactly one day prior to journey departure from the train&apos;s origin station. If your train departs its originating station a day earlier, Tatkal opens accordingly.
        </div>
      </div>
    </div>
  );
}
