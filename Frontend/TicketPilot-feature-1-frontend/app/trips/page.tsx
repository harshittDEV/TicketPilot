'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Trip } from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Train, Plus, Trash2, Edit3, ArrowRight, Calendar, Users, AlertCircle, CheckCircle } from 'lucide-react';

export default function MyTripsPage() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadTrips = async () => {
    setLoading(true);
    const res = await api.getTrips();
    setTrips(res.data || []);
    setLoading(false);
  };

  useEffect(() => {
    loadTrips();
  }, []);

  const handleDelete = async (id: string) => {
    const res = await api.deleteTrip(id);
    if (res.success) {
      setActionMessage('Trip deleted successfully.');
      setDeleteConfirmId(null);
      loadTrips();
      setTimeout(() => setActionMessage(null), 3000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-stone-200/60">
        <div>
          <h1 className="text-2xl font-extrabold text-ink tracking-tight">My Saved Journeys</h1>
          <p className="text-xs sm:text-sm text-ink-muted mt-0.5">
            Manage your upcoming railway trips and configured Tatkal countdown windows.
          </p>
        </div>

        <Link
          href="/trips/new"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white text-xs font-semibold shadow-xs transition-colors self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>New Journey</span>
        </Link>
      </div>

      {actionMessage && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-600" />
          <span>{actionMessage}</span>
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-3 border-accent-emerald border-t-transparent mb-2" />
          <p className="text-sm font-medium text-ink">Loading trips...</p>
        </div>
      ) : trips.length === 0 ? (
        <GlassCard className="text-center py-12">
          <Train className="w-12 h-12 text-stone-300 mx-auto mb-3" />
          <h3 className="font-bold text-base text-ink">No Journeys Configured</h3>
          <p className="text-xs text-ink-muted mt-1 max-w-sm mx-auto">
            You haven&apos;t added any journeys yet. Add your travel origin, destination, and journey date to track Tatkal timings.
          </p>
          <Link
            href="/trips/new"
            className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-accent-emerald text-white text-xs font-semibold"
          >
            <Plus className="w-4 h-4" />
            <span>Create First Journey</span>
          </Link>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {trips.map((trip) => {
            const isDeleting = deleteConfirmId === trip.id;

            return (
              <GlassCard key={trip.id} depth={1} className="relative flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <StatusBadge
                      label={trip.isAC ? 'AC Quota (10 AM)' : 'Non-AC Quota (11 AM)'}
                      variant={trip.isAC ? 'ac' : 'nonac'}
                    />
                    <StatusBadge
                      label={trip.status.toUpperCase()}
                      variant={trip.status === 'ready' ? 'success' : 'neutral'}
                    />
                  </div>

                  <h3 className="text-base font-bold text-ink mt-1">
                    {trip.sourceStation} → {trip.destStation}
                  </h3>

                  <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-stone-100 text-xs text-stone-600">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-stone-400" />
                      <span>{trip.journeyDate}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Users className="w-3.5 h-3.5 text-stone-400" />
                      <span>{trip.passengerCount} Passenger{trip.passengerCount > 1 ? 's' : ''}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Train className="w-3.5 h-3.5 text-stone-400" />
                      <span>Class {trip.travelClass}</span>
                    </div>
                    <div>
                      <span className="text-stone-400">Pref: </span>
                      <span className="capitalize font-medium text-stone-700">{trip.fareVsDurationPreference}</span>
                    </div>
                  </div>
                </div>

                {/* Card Actions */}
                <div className="mt-4 pt-3 border-t border-stone-200/60 flex items-center justify-between">
                  {isDeleting ? (
                    <div className="flex items-center gap-2 w-full justify-between bg-rose-50 p-2 rounded-lg border border-rose-200">
                      <span className="text-xs text-rose-800 font-medium">Confirm deletion?</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleDelete(trip.id)}
                          className="px-2.5 py-1 bg-rose-700 text-white text-xs font-semibold rounded hover:bg-rose-800"
                        >
                          Delete
                        </button>
                        <button
                          onClick={() => setDeleteConfirmId(null)}
                          className="px-2 py-1 bg-stone-200 text-stone-700 text-xs rounded hover:bg-stone-300"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/trips/${trip.id}`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-stone-200 text-stone-700 hover:bg-stone-50 text-xs font-medium"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          <span>Edit</span>
                        </Link>
                        <button
                          onClick={() => setDeleteConfirmId(trip.id)}
                          className="p-1.5 rounded-lg text-stone-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                          title="Delete trip"
                          aria-label={`Delete trip from ${trip.sourceStation} to ${trip.destStation}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      <Link
                        href={`/booking`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-accent-emerald hover:underline"
                      >
                        <span>Prepare Booking</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </>
                  )}
                </div>
              </GlassCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
