'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Trip, TripCreateInput, TravelClass, PreferenceChoice } from '@/lib/types';
import { Calendar, Users, Train, Clock, DollarSign, AlertCircle, Save, ArrowRight } from 'lucide-react';

interface TripFormProps {
  initialData?: Partial<Trip>;
  onSubmit: (data: TripCreateInput) => Promise<boolean>;
  isSubmitting?: boolean;
  submitButtonText?: string;
  cancelHref?: string;
}

const TRAVEL_CLASSES: { code: TravelClass; label: string; isAC: boolean }[] = [
  { code: '1A', label: '1A - AC First Class', isAC: true },
  { code: '2A', label: '2A - AC 2 Tier', isAC: true },
  { code: '3A', label: '3A - AC 3 Tier', isAC: true },
  { code: '3E', label: '3E - AC 3 Economy', isAC: true },
  { code: 'CC', label: 'CC - AC Chair Car', isAC: true },
  { code: 'EC', label: 'EC - Exec. Chair Car', isAC: true },
  { code: 'SL', label: 'SL - Sleeper Class (Non-AC)', isAC: false },
  { code: '2S', label: '2S - Second Sitting (Non-AC)', isAC: false },
];

export function TripForm({
  initialData,
  onSubmit,
  isSubmitting = false,
  submitButtonText = 'Save Journey Details',
  cancelHref = '/trips',
}: TripFormProps) {
  const [sourceStation, setSourceStation] = useState(initialData?.sourceStation || '');
  const [destStation, setDestStation] = useState(initialData?.destStation || '');
  const [stationOptions, setStationOptions] = useState<string[]>([]);
  const [journeyDate, setJourneyDate] = useState(initialData?.journeyDate || '');
  const [travelClass, setTravelClass] = useState<TravelClass>(initialData?.travelClass || '3A');
  const [passengerCount, setPassengerCount] = useState<number>(initialData?.passengerCount || 1);
  const [preferredTrainNumber, setPreferredTrainNumber] = useState(initialData?.preferredTrainNumber || '');
  const [preferredTrainName, setPreferredTrainName] = useState(initialData?.preferredTrainName || '');
  const [fareVsDurationPreference, setFareVsDurationPreference] = useState<PreferenceChoice>(
    initialData?.fareVsDurationPreference || 'balanced'
  );
  const [preferredDepartureTime, setPreferredDepartureTime] = useState(initialData?.preferredDepartureTime || '');

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    async function loadInitialStations() {
      const res = await api.searchStations('', 20);
      if (res.success && res.data) {
        setStationOptions(res.data.map(s => `${s.code} - ${s.name} (${s.state})`));
      }
    }
    loadInitialStations();
  }, []);

  const handleStationInput = async (val: string, setter: (v: string) => void, field: string) => {
    setter(val);
    if (fieldErrors[field]) setFieldErrors(prev => ({ ...prev, [field]: '' }));
    if (val.trim().length >= 2) {
      const res = await api.searchStations(val.trim(), 15);
      if (res.success && res.data && res.data.length > 0) {
        setStationOptions(res.data.map(s => `${s.code} - ${s.name} (${s.state})`));
      }
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!sourceStation.trim()) {
      errors.sourceStation = 'Origin station is required.';
    }

    if (!destStation.trim()) {
      errors.destStation = 'Destination station is required.';
    } else if (sourceStation.trim().toLowerCase() === destStation.trim().toLowerCase()) {
      errors.destStation = 'Destination cannot be the same as origin station.';
    }

    if (!journeyDate) {
      errors.journeyDate = 'Journey date is required.';
    } else {
      const selectedDate = new Date(journeyDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (isNaN(selectedDate.getTime()) || selectedDate < today) {
        errors.journeyDate = 'Journey date cannot be in the past.';
      }
    }

    if (!passengerCount || passengerCount < 1 || passengerCount > 4) {
      errors.passengerCount = 'Tatkal rules restrict bookings to 1 to 4 passengers per PNR.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!validate()) {
      return;
    }

    const payload: TripCreateInput = {
      sourceStation: sourceStation.trim(),
      destStation: destStation.trim(),
      journeyDate,
      travelClass,
      passengerCount: Number(passengerCount),
      preferredTrainNumber: preferredTrainNumber.trim() || undefined,
      preferredTrainName: preferredTrainName.trim() || undefined,
      fareVsDurationPreference,
      preferredDepartureTime: preferredDepartureTime.trim() || undefined,
    };

    try {
      const success = await onSubmit(payload);
      if (!success) {
        setFormError('Submission failed. Please check form values.');
      }
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'An unexpected error occurred');
    }
  };

  const selectedClassMeta = TRAVEL_CLASSES.find(c => c.code === travelClass);

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      {formError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-sm flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-rose-700 shrink-0 mt-0.5" />
          <span>{formError}</span>
        </div>
      )}

      {/* Origin & Destination Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="sourceStation" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
            Origin Station *
          </label>
          <input
            id="sourceStation"
            type="text"
            list="sourceStationsList"
            placeholder="e.g. NDLS - New Delhi"
            value={sourceStation}
            onChange={(e) => handleStationInput(e.target.value, setSourceStation, 'sourceStation')}
            className={`w-full text-sm bg-white border rounded-xl px-3.5 py-2.5 text-ink placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-accent-emerald ${
              fieldErrors.sourceStation ? 'border-rose-400 ring-1 ring-rose-300' : 'border-stone-200'
            }`}
            required
            aria-invalid={!!fieldErrors.sourceStation}
            aria-describedby={fieldErrors.sourceStation ? 'sourceStation-error' : undefined}
          />
          <datalist id="sourceStationsList">
            {stationOptions.map(s => <option key={s} value={s} />)}
          </datalist>
          {fieldErrors.sourceStation && (
            <p id="sourceStation-error" className="text-xs text-rose-600 mt-1">{fieldErrors.sourceStation}</p>
          )}
        </div>

        <div>
          <label htmlFor="destStation" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
            Destination Station *
          </label>
          <input
            id="destStation"
            type="text"
            list="destStationsList"
            placeholder="e.g. BCT - Mumbai Central"
            value={destStation}
            onChange={(e) => handleStationInput(e.target.value, setDestStation, 'destStation')}
            className={`w-full text-sm bg-white border rounded-xl px-3.5 py-2.5 text-ink placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-accent-emerald ${
              fieldErrors.destStation ? 'border-rose-400 ring-1 ring-rose-300' : 'border-stone-200'
            }`}
            required
            aria-invalid={!!fieldErrors.destStation}
            aria-describedby={fieldErrors.destStation ? 'destStation-error' : undefined}
          />
          <datalist id="destStationsList">
            {stationOptions.map(s => <option key={s} value={s} />)}
          </datalist>
          {fieldErrors.destStation && (
            <p id="destStation-error" className="text-xs text-rose-600 mt-1">{fieldErrors.destStation}</p>
          )}
        </div>
      </div>

      {/* Journey Date & Class Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label htmlFor="journeyDate" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
            Journey Date *
          </label>
          <div className="relative">
            <input
              id="journeyDate"
              type="date"
              value={journeyDate}
              onChange={(e) => {
                setJourneyDate(e.target.value);
                if (fieldErrors.journeyDate) setFieldErrors(prev => ({ ...prev, journeyDate: '' }));
              }}
              className={`w-full text-sm bg-white border rounded-xl px-3.5 py-2.5 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald ${
                fieldErrors.journeyDate ? 'border-rose-400 ring-1 ring-rose-300' : 'border-stone-200'
              }`}
              required
              aria-invalid={!!fieldErrors.journeyDate}
              aria-describedby={fieldErrors.journeyDate ? 'journeyDate-error' : undefined}
            />
          </div>
          {fieldErrors.journeyDate && (
            <p id="journeyDate-error" className="text-xs text-rose-600 mt-1">{fieldErrors.journeyDate}</p>
          )}
        </div>

        <div>
          <label htmlFor="travelClass" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
            Travel Class *
          </label>
          <select
            id="travelClass"
            value={travelClass}
            onChange={(e) => setTravelClass(e.target.value as TravelClass)}
            className="w-full text-sm bg-white border border-stone-200 rounded-xl px-3.5 py-2.5 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
          >
            {TRAVEL_CLASSES.map(tc => (
              <option key={tc.code} value={tc.code}>{tc.label}</option>
            ))}
          </select>
          <p className="text-[11px] text-stone-500 mt-1">
            {selectedClassMeta?.isAC ? 'Opens at 10:00 AM IST (AC Quota)' : 'Opens at 11:00 AM IST (Non-AC Quota)'}
          </p>
        </div>

        <div>
          <label htmlFor="passengerCount" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
            Passenger Count (1-4) *
          </label>
          <input
            id="passengerCount"
            type="number"
            min={1}
            max={4}
            value={passengerCount}
            onChange={(e) => {
              setPassengerCount(parseInt(e.target.value, 10) || 1);
              if (fieldErrors.passengerCount) setFieldErrors(prev => ({ ...prev, passengerCount: '' }));
            }}
            className={`w-full text-sm bg-white border rounded-xl px-3.5 py-2.5 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald ${
              fieldErrors.passengerCount ? 'border-rose-400 ring-1 ring-rose-300' : 'border-stone-200'
            }`}
            required
            aria-invalid={!!fieldErrors.passengerCount}
            aria-describedby={fieldErrors.passengerCount ? 'passengerCount-error' : undefined}
          />
          {fieldErrors.passengerCount && (
            <p id="passengerCount-error" className="text-xs text-rose-600 mt-1">{fieldErrors.passengerCount}</p>
          )}
        </div>
      </div>

      {/* Optional Preferences Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-stone-200/60">
        <div>
          <label htmlFor="preferredTrainNumber" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
            Preferred Train No. (Optional)
          </label>
          <input
            id="preferredTrainNumber"
            type="text"
            placeholder="e.g. 12952"
            value={preferredTrainNumber}
            onChange={(e) => setPreferredTrainNumber(e.target.value)}
            className="w-full text-sm bg-white border border-stone-200 rounded-xl px-3.5 py-2.5 text-ink font-mono placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-accent-emerald"
          />
        </div>

        <div>
          <label htmlFor="preferredTrainName" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
            Preferred Train Name (Optional)
          </label>
          <input
            id="preferredTrainName"
            type="text"
            placeholder="e.g. Mumbai Rajdhani"
            value={preferredTrainName}
            onChange={(e) => setPreferredTrainName(e.target.value)}
            className="w-full text-sm bg-white border border-stone-200 rounded-xl px-3.5 py-2.5 text-ink placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-accent-emerald"
          />
        </div>

        <div>
          <label htmlFor="fareVsDuration" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
            Comparison Preference
          </label>
          <select
            id="fareVsDuration"
            value={fareVsDurationPreference}
            onChange={(e) => setFareVsDurationPreference(e.target.value as PreferenceChoice)}
            className="w-full text-sm bg-white border border-stone-200 rounded-xl px-3.5 py-2.5 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
          >
            <option value="balanced">Balanced (Fare & Duration)</option>
            <option value="fastest">Fastest Travel Time</option>
            <option value="cheapest">Lowest Fare Tier</option>
          </select>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-end gap-3 pt-4 border-t border-stone-200">
        <a
          href={cancelHref}
          className="px-4 py-2.5 rounded-xl border border-stone-200 text-stone-700 hover:bg-stone-50 text-sm font-medium transition-colors"
        >
          Cancel
        </a>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-6 py-2.5 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white font-semibold text-sm flex items-center gap-2 shadow-sm transition-all focus:ring-2 focus:ring-accent-emerald focus:ring-offset-2 disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          <span>{isSubmitting ? 'Saving...' : submitButtonText}</span>
        </button>
      </div>
    </form>
  );
}
