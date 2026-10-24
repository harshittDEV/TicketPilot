'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
  TravelClass,
  PassengerDetails,
  BookingPreferences,
  SchedulingPreferences,
  Station,
  BackendTask,
} from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import {
  Train,
  Calendar,
  Users,
  Plus,
  Trash2,
  Clock,
  ShieldCheck,
  AlertCircle,
  Sliders,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  Send,
} from 'lucide-react';

interface JourneyConfigurationFormProps {
  onTaskCreated: (task: BackendTask) => void;
  className?: string;
}

const TRAVEL_CLASSES: { code: TravelClass; label: string; isAC: boolean }[] = [
  { code: '3A', label: '3 Tier AC (3A)', isAC: true },
  { code: '2A', label: '2 Tier AC (2A)', isAC: true },
  { code: '1A', label: 'First Class AC (1A)', isAC: true },
  { code: '3E', label: '3 AC Economy (3E)', isAC: true },
  { code: 'CC', label: 'AC Chair Car (CC)', isAC: true },
  { code: 'EC', label: 'Executive Chair Car (EC)', isAC: true },
  { code: 'SL', label: 'Sleeper Class (SL)', isAC: false },
  { code: '2S', label: 'Second Sitting (2S)', isAC: false },
];

export function JourneyConfigurationForm({
  onTaskCreated,
  className = '',
}: JourneyConfigurationFormProps) {
  // Sector and Journey Details
  const [originSearch, setOriginSearch] = useState('NDLS - New Delhi');
  const [destSearch, setDestSearch] = useState('BCT - Mumbai Central');
  const [originStation, setOriginStation] = useState<Station | null>(null);
  const [destStation, setDestStation] = useState<Station | null>(null);
  const [stationSuggestions, setStationSuggestions] = useState<Station[]>([]);

  // Default travel date: tomorrow + 2 days
  const defaultDate = new Date(Date.now() + 86400000 * 2).toISOString().slice(0, 10);
  const [journeyDate, setJourneyDate] = useState(defaultDate);
  const [travelClass, setTravelClass] = useState<TravelClass>('3A');
  const [bookingQuota, setBookingQuota] = useState<'TATKAL' | 'GENERAL' | 'PREMIUM_TATKAL'>('TATKAL');

  // Passenger Roster (Min 1, Max 4 for Tatkal)
  const [passengers, setPassengers] = useState<PassengerDetails[]>([
    {
      name: 'Rohan Sharma',
      age: 32,
      gender: 'M',
      berth_preference: 'LOWER',
      food_preference: 'VEG',
      senior_citizen_concession: false,
    },
  ]);

  // Booking Preferences
  const [allowAlternativeTrains, setAllowAlternativeTrains] = useState(true);
  const [allowAlternativeClasses, setAllowAlternativeClasses] = useState(false);
  const [maxAcceptableFare, setMaxAcceptableFare] = useState<number | ''>(2500);
  const [autoUpgradation, setAutoUpgradation] = useState(true);

  // Scheduling Preferences
  const [prepLeadMinutes, setPrepLeadMinutes] = useState(15);
  const [autoTrigger, setAutoTrigger] = useState(true);

  // Form State
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load initial station suggestions from official backend directory
  useEffect(() => {
    async function fetchStations() {
      const res = await api.searchStations('', 30);
      if (res.success && res.data) {
        setStationSuggestions(res.data);
      }
    }
    fetchStations();
  }, []);

  // Tatkal Opening Window Calculation:
  // AC classes open at 10:00 AM IST 1 day before journey date
  // Non-AC classes open at 11:00 AM IST 1 day before journey date
  const isSelectedAC = TRAVEL_CLASSES.find((c) => c.code === travelClass)?.isAC ?? true;
  const openingHour = isSelectedAC ? '10:00 AM IST' : '11:00 AM IST';

  let calculatedOpeningDateStr = '';
  try {
    const d = new Date(journeyDate);
    if (!isNaN(d.getTime())) {
      d.setDate(d.getDate() - 1);
      calculatedOpeningDateStr = `${d.toLocaleDateString('en-IN', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })} at ${openingHour}`;
    }
  } catch {
    calculatedOpeningDateStr = 'Invalid Date';
  }

  const handleAddPassenger = () => {
    if (passengers.length >= 4) return;
    setPassengers([
      ...passengers,
      {
        name: '',
        age: 30,
        gender: 'M',
        berth_preference: 'NO_PREFERENCE',
        food_preference: 'VEG',
        senior_citizen_concession: false,
      },
    ]);
  };

  const handleRemovePassenger = (index: number) => {
    if (passengers.length <= 1) return;
    setPassengers(passengers.filter((_, i) => i !== index));
  };

  const handlePassengerChange = (
    index: number,
    field: keyof PassengerDetails,
    val: any
  ) => {
    const updated = [...passengers];
    updated[index] = { ...updated[index], [field]: val };
    setPassengers(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    // Validation
    const cleanOrigin = originSearch.split('-')[0].trim().toUpperCase();
    const cleanDest = destSearch.split('-')[0].trim().toUpperCase();

    if (!cleanOrigin || cleanOrigin.length < 2) {
      setErrorMsg('Please select a valid origin station code');
      return;
    }
    if (!cleanDest || cleanDest.length < 2) {
      setErrorMsg('Please select a valid destination station code');
      return;
    }
    if (cleanOrigin === cleanDest) {
      setErrorMsg('Origin and destination stations must be distinct');
      return;
    }

    for (let i = 0; i < passengers.length; i++) {
      const p = passengers[i];
      if (!p.name || p.name.trim().length === 0) {
        setErrorMsg(`Passenger #${i + 1} must have a valid full name.`);
        return;
      }
      if (p.age < 1 || p.age > 125) {
        setErrorMsg(`Passenger #${i + 1} age must be between 1 and 125.`);
        return;
      }
    }

    setSubmitting(true);
    try {
      const payload = {
        name: `Tatkal Agent: ${cleanOrigin} → ${cleanDest} (${travelClass})`,
        task_type: 'train_booking',
        description: `Goal-driven autonomous Tatkal booking for ${passengers.length} passenger(s) on ${journeyDate}`,
        configuration: {
          source: cleanOrigin,
          destination: cleanDest,
          travel_date: journeyDate,
          travel_class: travelClass,
          quota: bookingQuota,
          autonomous_agent: true,
          passenger_count: passengers.length,
          passengers: passengers.map((p) => ({
            name: p.name.trim(),
            age: Number(p.age),
            gender: p.gender,
            berth_preference: p.berth_preference || 'NO_PREFERENCE',
            food_preference: p.food_preference || 'NO_FOOD',
            senior_citizen_concession: Boolean(p.senior_citizen_concession),
          })),
          preferences: {
            allow_alternative_trains: allowAlternativeTrains,
            allow_alternative_classes: allowAlternativeClasses,
            max_acceptable_fare: maxAcceptableFare ? Number(maxAcceptableFare) : null,
            auto_upgradation: autoUpgradation,
          },
          scheduling: {
            tatkal_window_override: isSelectedAC ? 'AC' : 'NON_AC',
            timezone: 'Asia/Kolkata',
            preparation_window_minutes: prepLeadMinutes,
            auto_trigger_at_window: autoTrigger,
            deadline_seconds: 1800,
          },
        },
      };

      const res = await api.createTask(payload);
      if (res.success && res.data) {
        onTaskCreated(res.data);
      } else {
        setErrorMsg(res.error?.message || 'Failed to create journey configuration');
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Network error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <GlassCard depth={1} className={`p-6 border-emerald-500/20 ${className}`}>
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Title */}
        <div className="flex items-center justify-between pb-3 border-b border-stone-200/80">
          <div>
            <h2 className="text-lg font-black text-ink tracking-tight flex items-center gap-2">
              <Train className="w-5 h-5 text-accent-emerald" />
              Configure Autonomous Tatkal Journey
            </h2>
            <p className="text-xs text-ink-muted mt-0.5">
              Specify complete journey details, passenger roster, booking constraints, and Tatkal opening parameters.
            </p>
          </div>
          <span className="text-[10px] font-mono uppercase bg-emerald-50 text-accent-emerald px-2.5 py-1 rounded-full border border-emerald-200 font-bold">
            Goal-Driven Mode
          </span>
        </div>

        {/* Error message */}
        {errorMsg && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Section 1: Journey Details */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5">
            <Train className="w-3.5 h-3.5 text-accent-emerald" />
            1. Sector & Date Selection
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            {/* Origin Station */}
            <div>
              <label className="block text-[11px] font-bold text-ink mb-1">
                Origin Station (From)
              </label>
              <input
                type="text"
                list="station-list"
                value={originSearch}
                onChange={(e) => setOriginSearch(e.target.value)}
                placeholder="e.g. NDLS - New Delhi"
                className="w-full px-3 py-2 text-xs rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-accent-emerald bg-white"
                required
              />
            </div>

            {/* Destination Station */}
            <div>
              <label className="block text-[11px] font-bold text-ink mb-1">
                Destination Station (To)
              </label>
              <input
                type="text"
                list="station-list"
                value={destSearch}
                onChange={(e) => setDestSearch(e.target.value)}
                placeholder="e.g. BCT - Mumbai Central"
                className="w-full px-3 py-2 text-xs rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-accent-emerald bg-white"
                required
              />
            </div>

            {/* Journey Date */}
            <div>
              <label className="block text-[11px] font-bold text-ink mb-1">
                Journey Date
              </label>
              <input
                type="date"
                value={journeyDate}
                onChange={(e) => setJourneyDate(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-accent-emerald bg-white font-mono"
                required
              />
            </div>

            {/* Travel Class */}
            <div>
              <label className="block text-[11px] font-bold text-ink mb-1">
                Preferred Class
              </label>
              <select
                value={travelClass}
                onChange={(e) => setTravelClass(e.target.value as TravelClass)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-accent-emerald bg-white font-semibold"
              >
                {TRAVEL_CLASSES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <datalist id="station-list">
            {stationSuggestions.map((s) => (
              <option key={s.code} value={`${s.code} - ${s.name} (${s.state})`} />
            ))}
          </datalist>

          {/* Resolved Tatkal Opening Time Preview Card */}
          <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200/80 flex items-center justify-between text-xs text-emerald-950">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-emerald-700 shrink-0" />
              <div>
                <span className="font-bold">Calculated Tatkal Opening Window:</span>{' '}
                <span className="font-mono font-semibold">{calculatedOpeningDateStr}</span>
              </div>
            </div>
            <span className="text-[10px] uppercase font-bold bg-white/90 px-2 py-0.5 rounded border border-emerald-300 text-emerald-800">
              {isSelectedAC ? 'AC Quota Rule (10:00 AM)' : 'Non-AC Quota Rule (11:00 AM)'}
            </span>
          </div>
        </div>

        {/* Section 2: Passenger Details Roster */}
        <div className="space-y-3 pt-2 border-t border-stone-200/70">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-accent-emerald" />
              2. Passenger Roster ({passengers.length} of 4 Max for Tatkal)
            </h3>
            <button
              type="button"
              onClick={handleAddPassenger}
              disabled={passengers.length >= 4}
              className="inline-flex items-center gap-1 text-xs font-semibold text-accent-emerald hover:underline disabled:opacity-40"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Passenger</span>
            </button>
          </div>

          <div className="space-y-2.5">
            {passengers.map((p, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl border border-stone-200 bg-stone-50/60 grid grid-cols-1 sm:grid-cols-12 gap-2.5 items-center text-xs"
              >
                <div className="sm:col-span-1 text-center font-bold text-ink-muted font-mono">
                  #{idx + 1}
                </div>

                <div className="sm:col-span-4">
                  <label className="block text-[10px] text-ink-muted font-semibold mb-0.5">
                    Full Name (As per Govt ID)
                  </label>
                  <input
                    type="text"
                    value={p.name}
                    onChange={(e) => handlePassengerChange(idx, 'name', e.target.value)}
                    placeholder="e.g. Priya Sharma"
                    className="w-full px-2.5 py-1.5 rounded-lg border border-stone-300 bg-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-accent-emerald"
                    required
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-[10px] text-ink-muted font-semibold mb-0.5">
                    Age
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={125}
                    value={p.age}
                    onChange={(e) =>
                      handlePassengerChange(idx, 'age', parseInt(e.target.value) || 1)
                    }
                    className="w-full px-2.5 py-1.5 rounded-lg border border-stone-300 bg-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-accent-emerald"
                    required
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-[10px] text-ink-muted font-semibold mb-0.5">
                    Gender
                  </label>
                  <select
                    value={p.gender}
                    onChange={(e) => handlePassengerChange(idx, 'gender', e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-stone-300 bg-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-accent-emerald"
                  >
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                    <option value="T">Transgender</option>
                  </select>
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-[10px] text-ink-muted font-semibold mb-0.5">
                    Berth Pref
                  </label>
                  <select
                    value={p.berth_preference || 'NO_PREFERENCE'}
                    onChange={(e) =>
                      handlePassengerChange(idx, 'berth_preference', e.target.value)
                    }
                    className="w-full px-2.5 py-1.5 rounded-lg border border-stone-300 bg-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-accent-emerald"
                  >
                    <option value="NO_PREFERENCE">No Preference</option>
                    <option value="LOWER">Lower</option>
                    <option value="MIDDLE">Middle</option>
                    <option value="UPPER">Upper</option>
                    <option value="SIDE_LOWER">Side Lower</option>
                    <option value="SIDE_UPPER">Side Upper</option>
                    <option value="WINDOW">Window (CC)</option>
                  </select>
                </div>

                <div className="sm:col-span-1 text-right">
                  <button
                    type="button"
                    onClick={() => handleRemovePassenger(idx)}
                    disabled={passengers.length <= 1}
                    className="p-1.5 rounded-lg text-stone-400 hover:text-rose-600 hover:bg-rose-50 transition-colors disabled:opacity-30"
                    title="Remove Passenger"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 3: Booking Preferences & Safeguards */}
        <div className="space-y-3 pt-2 border-t border-stone-200/70">
          <h3 className="text-xs font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-accent-emerald" />
            3. Autonomous Booking Preferences & Budget Constraints
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <label className="p-3 rounded-xl border border-stone-200 bg-stone-50/50 flex items-start gap-2.5 cursor-pointer hover:bg-stone-100/50">
              <input
                type="checkbox"
                checked={allowAlternativeTrains}
                onChange={(e) => setAllowAlternativeTrains(e.target.checked)}
                className="mt-0.5 rounded text-accent-emerald focus:ring-accent-emerald"
              />
              <div>
                <span className="font-bold block text-ink">Allow Alternative Trains</span>
                <span className="text-[10px] text-ink-muted">
                  Agent may pick secondary train on the sector if primary has no seats.
                </span>
              </div>
            </label>

            <label className="p-3 rounded-xl border border-stone-200 bg-stone-50/50 flex items-start gap-2.5 cursor-pointer hover:bg-stone-100/50">
              <input
                type="checkbox"
                checked={autoUpgradation}
                onChange={(e) => setAutoUpgradation(e.target.checked)}
                className="mt-0.5 rounded text-accent-emerald focus:ring-accent-emerald"
              />
              <div>
                <span className="font-bold block text-ink">Auto Upgradation</span>
                <span className="text-[10px] text-ink-muted">
                  Opt into free Indian Railways class upgradation if berths open.
                </span>
              </div>
            </label>

            <div className="p-3 rounded-xl border border-stone-200 bg-stone-50/50 space-y-1">
              <span className="font-bold block text-ink">Max Acceptable Fare (₹)</span>
              <input
                type="number"
                value={maxAcceptableFare}
                onChange={(e) =>
                  setMaxAcceptableFare(e.target.value ? Number(e.target.value) : '')
                }
                placeholder="No max limit"
                className="w-full px-2.5 py-1 text-xs rounded-lg border border-stone-300 bg-white font-mono focus:outline-none focus:ring-1 focus:ring-accent-emerald"
              />
              <span className="text-[10px] text-ink-muted block">
                Agent halts if fare exceeds budget.
              </span>
            </div>
          </div>
        </div>

        {/* Section 4: Mandatory Safety Boundaries Notice */}
        <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-300/80 text-amber-950 text-xs space-y-1.5">
          <div className="flex items-center gap-2 font-bold text-xs text-amber-900">
            <ShieldCheck className="w-4 h-4 text-amber-700 shrink-0" />
            <span>Strict Safety and Ethical Operation Guarantees</span>
          </div>
          <ul className="text-[11px] space-y-0.5 list-disc pl-5 opacity-90">
            <li>
              <strong>CAPTCHA Anti-Bot Compliance:</strong> At step 4, the agent pauses for human solving. Anti-bot bypass is prohibited.
            </li>
            <li>
              <strong>Final Payment Stage Boundary:</strong> The agent strictly halts before payment submission. You review the final itinerary and complete payment yourself.
            </li>
          </ul>
        </div>

        {/* Submit Button */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-stone-200/80">
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white font-bold text-xs shadow-md transition-all disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            <span>{submitting ? 'Persisting Configuration...' : 'Save & Configure Agent Task'}</span>
          </button>
        </div>
      </form>
    </GlassCard>
  );
}
