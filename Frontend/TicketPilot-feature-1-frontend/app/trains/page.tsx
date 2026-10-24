'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import {
  TrainComparisonResult,
  TravelClass,
  TrainSchedule,
  LiveRunningStatus,
  PnrStatus,
  ProviderStatusResponse,
} from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { TrainComparisonTable } from '@/components/trains/TrainComparisonTable';
import { StatusBadge } from '@/components/ui/StatusBadge';
import {
  Train,
  Layers,
  Search,
  Calendar,
  Filter,
  Info,
  ShieldAlert,
  Clock,
  Compass,
  CheckCircle2,
  XCircle,
  Activity,
  FileText,
  X,
  ExternalLink,
  Radio,
} from 'lucide-react';
import Link from 'next/link';

export default function CompareTrainsPage() {
  const [sourceStation, setSourceStation] = useState('NDLS - New Delhi');
  const [destStation, setDestStation] = useState('BCT - Mumbai Central');
  const [journeyDate, setJourneyDate] = useState(
    new Date(Date.now() + 86400000 * 2).toISOString().slice(0, 10)
  );
  const [travelClass, setTravelClass] = useState<string>('3A');
  const [stationOptions, setStationOptions] = useState<string[]>([]);

  const [trains, setTrains] = useState<TrainComparisonResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Provider Status & Metadata
  const [providerStatus, setProviderStatus] = useState<ProviderStatusResponse | null>(null);

  // Train Schedule Modal
  const [selectedTrainNumber, setSelectedTrainNumber] = useState<string | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleData, setScheduleData] = useState<TrainSchedule | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);

  // Live Running Status Modal
  const [liveModalTrain, setLiveModalTrain] = useState<string | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveData, setLiveData] = useState<LiveRunningStatus | null>(null);

  // PNR Lookup
  const [pnrInput, setPnrInput] = useState('');
  const [pnrLoading, setPnrLoading] = useState(false);
  const [pnrData, setPnrData] = useState<PnrStatus | null>(null);
  const [pnrError, setPnrError] = useState<string | null>(null);

  // Initial load
  useEffect(() => {
    async function loadInitial() {
      setLoading(true);
      // 1. Load station suggestions
      const stnRes = await api.searchStations('', 25);
      if (stnRes.success && stnRes.data) {
        setStationOptions(stnRes.data.map(s => `${s.code} - ${s.name} (${s.state})`));
      }

      // 2. Load provider status
      const provRes = await api.getRailwayProviderStatus();
      if (provRes.success && provRes.data) {
        setProviderStatus(provRes.data);
      }

      // 3. Search initial trains
      await executeSearch('NDLS - New Delhi', 'BCT - Mumbai Central', journeyDate, '3A' as TravelClass);
      setLoading(false);
    }
    loadInitial();
  }, []);

  const executeSearch = async (
    src: string,
    dst: string,
    date: string,
    cls?: TravelClass
  ) => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.getTrainComparisons(src, dst, cls, date);
      if (res.success && res.data) {
        setTrains(res.data);
      } else {
        setError(res.error?.message || 'Failed to retrieve train comparison data.');
        setTrains([]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Network error');
      setTrains([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (sourceStation.trim().toLowerCase() === destStation.trim().toLowerCase()) {
      setError('Origin and destination stations must be different.');
      return;
    }
    executeSearch(sourceStation, destStation, journeyDate, travelClass as TravelClass);
  };

  const handleQuickRoute = (src: string, dst: string, cls: string = '3A') => {
    setSourceStation(src);
    setDestStation(dst);
    setTravelClass(cls);
    executeSearch(src, dst, journeyDate, cls as TravelClass);
  };

  // Inspect stops schedule
  const handleOpenSchedule = async (trainNum: string) => {
    setSelectedTrainNumber(trainNum);
    setScheduleLoading(true);
    setScheduleError(null);
    setScheduleData(null);
    try {
      const res = await api.getTrainSchedule(trainNum);
      if (res.success && res.data) {
        setScheduleData(res.data);
      } else {
        setScheduleError(res.error?.message || `Schedule for train ${trainNum} not found.`);
      }
    } catch (err: unknown) {
      setScheduleError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setScheduleLoading(false);
    }
  };

  // Inspect live running status
  const handleOpenLiveStatus = async (trainNum: string) => {
    setLiveModalTrain(trainNum);
    setLiveLoading(true);
    setLiveData(null);
    try {
      const res = await api.getLiveRunningStatus(trainNum, journeyDate);
      if (res.success && res.data) {
        setLiveData(res.data);
      }
    } finally {
      setLiveLoading(false);
    }
  };

  // PNR lookup submit
  const handlePnrSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanPnr = pnrInput.replace(/-/g, '').trim();
    if (cleanPnr.length !== 10 || !/^\d+$/.test(cleanPnr)) {
      setPnrError('PNR must be an exact 10-digit number.');
      return;
    }
    setPnrError(null);
    setPnrLoading(true);
    setPnrData(null);
    try {
      const res = await api.getPnrStatus(cleanPnr);
      if (res.success && res.data) {
        setPnrData(res.data);
      } else {
        setPnrError(res.error?.message || 'PNR query failed.');
      }
    } catch (err: unknown) {
      setPnrError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setPnrLoading(false);
    }
  };

  return (
    <div className="space-y-8 pb-16">
      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 1: Page Header & Subtitle                            */}
      {/* ──────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-stone-200/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Layers className="w-5 h-5 text-accent-emerald" />
            <h1 className="text-2xl font-extrabold text-ink tracking-tight">
              Train Timetable & Fare Comparison
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-ink-muted">
            Search authentic trains across Indian Railways routes with genuine schedules, official Tatkal fare charts, and live provider status.
          </p>
        </div>

        {/* Data Source Badge */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono font-bold px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200 shadow-2xs">
            DATA SOURCE: {providerStatus?.providers[0]?.display_name || 'Official IR Open Data'}
          </span>
        </div>
      </div>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 2: Interactive Train Search Bar                      */}
      {/* ──────────────────────────────────────────────────────────── */}
      <GlassCard depth={1} className="p-5 space-y-4">
        <form onSubmit={handleSearchSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Origin Station */}
            <div>
              <label htmlFor="searchSourceStation" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
                Origin Station *
              </label>
              <input
                id="searchSourceStation"
                type="text"
                list="trainsSourceList"
                placeholder="e.g. NDLS - New Delhi"
                value={sourceStation}
                onChange={(e) => setSourceStation(e.target.value)}
                className="w-full text-xs font-semibold bg-white border border-stone-200 rounded-xl px-3 py-2 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
                required
              />
              <datalist id="trainsSourceList">
                {stationOptions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>

            {/* Destination Station */}
            <div>
              <label htmlFor="searchDestStation" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
                Destination Station *
              </label>
              <input
                id="searchDestStation"
                type="text"
                list="trainsDestList"
                placeholder="e.g. BCT - Mumbai Central"
                value={destStation}
                onChange={(e) => setDestStation(e.target.value)}
                className="w-full text-xs font-semibold bg-white border border-stone-200 rounded-xl px-3 py-2 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
                required
              />
              <datalist id="trainsDestList">
                {stationOptions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>

            {/* Journey Date */}
            <div>
              <label htmlFor="searchJourneyDate" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
                Journey Date *
              </label>
              <input
                id="searchJourneyDate"
                type="date"
                min={new Date().toISOString().slice(0, 10)}
                value={journeyDate}
                onChange={(e) => setJourneyDate(e.target.value)}
                className="w-full text-xs font-semibold bg-white border border-stone-200 rounded-xl px-3 py-2 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
                required
              />
            </div>

            {/* Travel Class */}
            <div>
              <label htmlFor="searchTravelClass" className="block text-xs font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
                Class Filter
              </label>
              <select
                id="searchTravelClass"
                value={travelClass}
                onChange={(e) => setTravelClass(e.target.value)}
                className="w-full text-xs font-semibold bg-white border border-stone-200 rounded-xl px-3 py-2 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
              >
                <option value="ALL">All Available Classes</option>
                <option value="1A">1A - AC First Class</option>
                <option value="2A">2A - AC 2 Tier</option>
                <option value="3A">3A - AC 3 Tier</option>
                <option value="3E">3E - AC 3 Economy</option>
                <option value="CC">CC - AC Chair Car</option>
                <option value="EC">EC - Exec. Chair Car</option>
                <option value="SL">SL - Sleeper (Non-AC)</option>
                <option value="2S">2S - Second Sitting (Non-AC)</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-stone-200/60">
            {/* Quick Route Shortcuts */}
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
              <span className="font-semibold text-[10px] uppercase">Popular Sectors:</span>
              <button
                type="button"
                onClick={() => handleQuickRoute('NDLS - New Delhi', 'BCT - Mumbai Central', '3A')}
                className="px-2 py-0.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-800 text-[11px] font-medium transition-colors"
              >
                Delhi ↔ Mumbai
              </button>
              <button
                type="button"
                onClick={() => handleQuickRoute('NDLS - New Delhi', 'HWH - Howrah Junction', '3A')}
                className="px-2 py-0.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-800 text-[11px] font-medium transition-colors"
              >
                Delhi ↔ Kolkata
              </button>
              <button
                type="button"
                onClick={() => handleQuickRoute('HWH - Howrah Junction', 'MAS - MGR Chennai Central', 'SL')}
                className="px-2 py-0.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-800 text-[11px] font-medium transition-colors"
              >
                Howrah ↔ Chennai
              </button>
              <button
                type="button"
                onClick={() => handleQuickRoute('NZM - Hazrat Nizamuddin', 'SBC - KSR Bengaluru City', '3A')}
                className="px-2 py-0.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-800 text-[11px] font-medium transition-colors"
              >
                Delhi ↔ Bengaluru
              </button>
              <button
                type="button"
                onClick={() => handleQuickRoute('RK - Roorkee', 'HW - Haridwar', 'CC')}
                className="px-2 py-0.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-800 text-[11px] font-medium transition-colors"
              >
                Roorkee ↔ Haridwar
              </button>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-accent-emerald hover:bg-emerald-800 text-white text-xs font-bold shadow-xs transition-colors"
            >
              <Search className="w-4 h-4" />
              <span>{loading ? 'Searching Trains...' : 'Find Trains'}</span>
            </button>
          </div>
        </form>
      </GlassCard>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 3: Active Sector Banner & Results List               */}
      {/* ──────────────────────────────────────────────────────────── */}
      <div className="p-4 rounded-xl bg-white/80 border border-stone-200 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div>
          <span className="text-stone-500 uppercase tracking-wider font-semibold block text-[10px]">Active Route Query</span>
          <strong className="text-sm text-ink font-bold">
            {sourceStation} → {destStation} ({journeyDate})
          </strong>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge label={`Class: ${travelClass}`} variant="info" />
          <StatusBadge label={`${trains.length} Train(s) Found`} variant={trains.length > 0 ? 'success' : 'neutral'} />
        </div>
      </div>

      {/* Train Comparison Table */}
      <TrainComparisonTable
        trains={trains}
        isLoading={loading}
        error={error}
        sourceStation={sourceStation}
        destStation={destStation}
      />

      {/* Action Buttons for Each Found Train */}
      {trains.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {trains.map((t) => (
            <GlassCard key={t.trainNumber} depth={1} className="p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-accent-emerald">{t.trainNumber}</span>
                <span className="text-[10px] text-stone-500 font-semibold uppercase">{t.duration}</span>
              </div>
              <h4 className="text-xs font-extrabold text-ink truncate">{t.trainName}</h4>
              <div className="flex items-center justify-between pt-1 border-t border-stone-200/60">
                <button
                  type="button"
                  onClick={() => handleOpenSchedule(t.trainNumber)}
                  className="text-[11px] font-bold text-stone-700 hover:text-accent-emerald flex items-center gap-1"
                >
                  <Clock className="w-3.5 h-3.5" />
                  <span>Stops Schedule</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleOpenLiveStatus(t.trainNumber)}
                  className="text-[11px] font-bold text-stone-700 hover:text-accent-emerald flex items-center gap-1"
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span>Live Status</span>
                </button>
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 4: Live PNR Status Check                             */}
      {/* ──────────────────────────────────────────────────────────── */}
      <GlassCard depth={1} className="p-5 space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <Search className="w-4 h-4 text-accent-emerald" />
          <h3 className="font-extrabold text-sm text-ink">PNR Status Inquiry</h3>
        </div>
        <p className="text-xs text-ink-muted">
          Check reservation chart status and coach allocation for your 10-digit Indian Railways PNR. Passenger personal details are strictly redacted for privacy compliance.
        </p>

        <form onSubmit={handlePnrSearch} className="flex flex-col sm:flex-row gap-2 max-w-xl">
          <input
            type="text"
            maxLength={10}
            placeholder="Enter 10-digit PNR number (e.g. 2849182371)"
            value={pnrInput}
            onChange={(e) => setPnrInput(e.target.value)}
            className="flex-1 text-xs font-mono bg-white border border-stone-200 rounded-xl px-3.5 py-2 text-ink focus:outline-none focus:ring-2 focus:ring-accent-emerald"
          />
          <button
            type="submit"
            disabled={pnrLoading}
            className="px-4 py-2 rounded-xl bg-stone-900 hover:bg-black text-white text-xs font-bold transition-colors shrink-0"
          >
            {pnrLoading ? 'Checking...' : 'Check Status'}
          </button>
        </form>

        {pnrError && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs">
            {pnrError}
          </div>
        )}

        {pnrData && (
          <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-ink">PNR: {pnrData.pnr_number}</span>
              <StatusBadge
                label={pnrData.booking_status}
                variant={pnrData.is_supported ? 'success' : 'neutral'}
              />
            </div>
            <p className="text-[11px] text-stone-600 leading-relaxed">{pnrData.message}</p>
            {pnrData.passengers && pnrData.passengers.length > 0 && (
              <div className="space-y-1 pt-1 border-t border-stone-200/60">
                {pnrData.passengers.map((p) => (
                  <div key={p.passenger_index} className="flex justify-between text-[11px] text-stone-700">
                    <span>Passenger {p.passenger_index}</span>
                    <span className="font-mono font-semibold">{p.current_status} {p.coach ? `(${p.coach}-${p.berth})` : ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </GlassCard>

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 5: Stop-by-Stop Schedule Drawer Modal                */}
      {/* ──────────────────────────────────────────────────────────── */}
      {selectedTrainNumber && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden border border-stone-200">
            <div className="p-4 border-b border-stone-200 flex items-center justify-between bg-stone-50/80">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-accent-emerald" />
                <h3 className="font-extrabold text-sm text-ink">
                  Train Timetable & Intermediate Stops
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedTrainNumber(null)}
                className="p-1.5 rounded-lg hover:bg-stone-200 text-stone-500 transition-colors"
                aria-label="Close timetable modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4">
              {scheduleLoading ? (
                <div className="py-12 text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-3 border-accent-emerald border-t-transparent mb-2" />
                  <p className="text-xs font-semibold text-ink">Retrieving stop timetable for Train {selectedTrainNumber}...</p>
                </div>
              ) : scheduleError ? (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs">
                  {scheduleError}
                </div>
              ) : scheduleData ? (
                <div className="space-y-4">
                  <div className="p-3 rounded-xl bg-stone-50 border border-stone-200 text-xs">
                    <div className="font-bold text-ink text-sm">
                      {scheduleData.train_number} — {scheduleData.train_name}
                    </div>
                    <div className="text-[11px] text-stone-600 mt-0.5">
                      {scheduleData.origin_station_name} ({scheduleData.origin_station_code}) →{' '}
                      {scheduleData.destination_station_name} ({scheduleData.destination_station_code})
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-[10px] font-mono bg-stone-200/80 text-stone-800 px-2 py-0.5 rounded">
                        SOURCE: {scheduleData.data_source}
                      </span>
                      <span className="text-[10px] text-stone-500 font-mono">
                        UPDATED: {new Date(scheduleData.last_updated).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  {/* Stops Table */}
                  <div className="border border-stone-200 rounded-xl overflow-hidden">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-stone-100 text-stone-600 uppercase text-[10px] tracking-wider">
                        <tr>
                          <th className="py-2 px-3">#</th>
                          <th className="py-2 px-3">Station</th>
                          <th className="py-2 px-3">Arr.</th>
                          <th className="py-2 px-3">Dep.</th>
                          <th className="py-2 px-3">Halt</th>
                          <th className="py-2 px-3">Distance</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {scheduleData.stops.map((s) => (
                          <tr key={s.stop_number} className="hover:bg-stone-50">
                            <td className="py-2 px-3 font-mono text-stone-500">{s.stop_number}</td>
                            <td className="py-2 px-3 font-bold text-ink">
                              {s.station_name} <span className="font-mono font-normal text-stone-500">({s.station_code})</span>
                            </td>
                            <td className="py-2 px-3 font-mono">{s.arrival_time}</td>
                            <td className="py-2 px-3 font-mono">{s.departure_time}</td>
                            <td className="py-2 px-3 text-stone-600">{s.halt_minutes > 0 ? `${s.halt_minutes}m` : '-'}</td>
                            <td className="py-2 px-3 font-mono text-stone-500">{s.distance_km} km</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 6: Live Running Status Modal                         */}
      {/* ──────────────────────────────────────────────────────────── */}
      {liveModalTrain && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-5 space-y-4 border border-stone-200">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <div className="flex items-center gap-2">
                <Radio className="w-5 h-5 text-accent-emerald" />
                <h3 className="font-extrabold text-sm text-ink">
                  Live Running Status (Train {liveModalTrain})
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setLiveModalTrain(null)}
                className="p-1 rounded-lg hover:bg-stone-200 text-stone-500"
                aria-label="Close live status modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {liveLoading ? (
              <div className="py-8 text-center">
                <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-accent-emerald border-t-transparent mb-2" />
                <p className="text-xs font-semibold text-ink">Querying live telemetry...</p>
              </div>
            ) : liveData ? (
              <div className="space-y-3 text-xs">
                <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-ink">{liveData.train_name}</span>
                    <StatusBadge
                      label={liveData.is_available ? 'Live Telemetry' : 'Capability Unavailable'}
                      variant={liveData.is_available ? 'success' : 'neutral'}
                    />
                  </div>
                  <p className="text-stone-700 leading-relaxed font-medium">
                    {liveData.status_message}
                  </p>
                  <p className="text-[11px] text-stone-500 font-mono">
                    Observed: {new Date(liveData.observation_timestamp).toLocaleTimeString()}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-[11px] space-y-1 leading-relaxed">
                  <div className="font-bold flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-700" />
                    <span>Compliance & Provider Disclosure</span>
                  </div>
                  <p>{liveData.disclaimer}</p>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* ──────────────────────────────────────────────────────────── */}
      {/* SECTION 7: Data Provenance & IRCTC Compliance Notice         */}
      {/* ──────────────────────────────────────────────────────────── */}
      <GlassCard className="text-xs text-stone-600 space-y-2">
        <div className="flex items-center gap-2 font-semibold text-ink">
          <ShieldAlert className="w-4 h-4 text-emerald-700" />
          <span>Data Provenance & IRCTC Compliance Notice</span>
        </div>
        <p className="leading-relaxed">
          Timetables, run times, and base fares are synchronized from official railway schedule disclosures released under the Government Open Data License - India (NDSAP). Tatkal seat allocations and waitlist statuses are estimates based on standard Indian Railways zonal quotas. This application does not claim live real-time seat locks and never overrides IRCTC official availability. Automated booking and payment submission remain strictly disabled.
        </p>
      </GlassCard>
    </div>
  );
}
