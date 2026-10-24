'use client';

import React, { useState, useMemo } from 'react';
import { TrainComparisonResult, TravelClass, DataFreshness } from '@/lib/types';
import { StatusBadge } from '../ui/StatusBadge';
import { ArrowUpDown, Clock, DollarSign, Sparkles, AlertCircle, Info, ExternalLink } from 'lucide-react';

interface TrainComparisonTableProps {
  trains: TrainComparisonResult[];
  isLoading?: boolean;
  error?: string | null;
  onSelectTrain?: (train: TrainComparisonResult) => void;
  selectedTrainNumber?: string;
  sourceStation: string;
  destStation: string;
}

type SortField = 'fare' | 'duration' | 'departure';
type SortOrder = 'asc' | 'desc';

export function TrainComparisonTable({
  trains,
  isLoading = false,
  error = null,
  onSelectTrain,
  selectedTrainNumber,
  sourceStation,
  destStation,
}: TrainComparisonTableProps) {
  const [sortField, setSortField] = useState<SortField>('duration');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [selectedClassFilter, setSelectedClassFilter] = useState<string>('ALL');

  // Presentation-only sorting (does not alter or substitute Member 4 ranking logic)
  const sortedAndFilteredTrains = useMemo(() => {
    let result = [...trains];

    if (selectedClassFilter !== 'ALL') {
      result = result.filter(t => t.travelClass === selectedClassFilter);
    }

    result.sort((a, b) => {
      let comp = 0;
      if (sortField === 'fare') {
        comp = a.totalFare - b.totalFare;
      } else if (sortField === 'duration') {
        comp = a.durationMinutes - b.durationMinutes;
      } else if (sortField === 'departure') {
        comp = a.departureTime.localeCompare(b.departureTime);
      }
      return sortOrder === 'asc' ? comp : -comp;
    });

    return result;
  }, [trains, sortField, sortOrder, selectedClassFilter]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const availableClasses = useMemo(() => {
    const set = new Set<string>();
    trains.forEach(t => set.add(t.travelClass));
    return Array.from(set);
  }, [trains]);

  const getProvenanceBadge = (provenance: DataFreshness) => {
    switch (provenance) {
      case 'verified':
        return <StatusBadge label="Verified Data" variant="success" hint="Direct official timetable match" />;
      case 'estimated':
        return <StatusBadge label="Estimated Quota" variant="warning" hint="Historical statistical estimate" />;
      case 'stale':
        return <StatusBadge label="Stale Cache" variant="error" hint="Data > 30 minutes old" />;
      case 'unavailable':
      default:
        return <StatusBadge label="Unavailable" variant="neutral" hint="No recent fetch available" />;
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center rounded-2xl bg-white/70 border border-stone-200">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-3 border-accent-emerald border-t-transparent mb-3" />
        <p className="text-sm font-medium text-ink">Retrieving train comparisons from Member 4 Engine...</p>
        <p className="text-xs text-ink-muted mt-1">Verifying routes between {sourceStation} and {destStation}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900">
        <div className="flex items-center gap-2 mb-2 font-semibold">
          <AlertCircle className="w-5 h-5 text-rose-700" />
          <span>Train Comparison Error</span>
        </div>
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (trains.length === 0) {
    return (
      <div className="p-8 text-center rounded-2xl bg-white/60 border border-stone-200 text-ink-muted">
        <p className="font-medium text-ink">No train comparisons available for this sector.</p>
        <p className="text-xs mt-1">
          {sourceStation && destStation
            ? `No trains found matching ${sourceStation} → ${destStation}. Verify stations or add trip parameters.`
            : 'Select an origin and destination to view train comparisons.'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls Bar: Sort & Filter */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-white/70 backdrop-blur-md rounded-xl border border-stone-200/80">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-ink-muted uppercase tracking-wider">Filter Class:</span>
          <select
            value={selectedClassFilter}
            onChange={(e) => setSelectedClassFilter(e.target.value)}
            className="text-xs bg-white border border-stone-200 rounded-lg px-2.5 py-1 text-ink focus:outline-none focus:ring-1 focus:ring-accent-emerald"
            aria-label="Filter trains by travel class"
          >
            <option value="ALL">All Classes ({trains.length})</option>
            {availableClasses.map(cls => (
              <option key={cls} value={cls}>{cls}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-ink-muted uppercase tracking-wider mr-1">Sort:</span>
          <button
            onClick={() => toggleSort('duration')}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 border transition-colors ${
              sortField === 'duration'
                ? 'bg-accent-emerald text-white border-accent-emerald'
                : 'bg-white text-ink border-stone-200 hover:bg-stone-50'
            }`}
            aria-label={`Sort by duration, currently ${sortField === 'duration' ? sortOrder : 'inactive'}`}
          >
            <Clock className="w-3 h-3" />
            Duration {sortField === 'duration' && (sortOrder === 'asc' ? '↑' : '↓')}
          </button>
          <button
            onClick={() => toggleSort('fare')}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 border transition-colors ${
              sortField === 'fare'
                ? 'bg-accent-emerald text-white border-accent-emerald'
                : 'bg-white text-ink border-stone-200 hover:bg-stone-50'
            }`}
            aria-label={`Sort by total fare, currently ${sortField === 'fare' ? sortOrder : 'inactive'}`}
          >
            <DollarSign className="w-3 h-3" />
            Fare {sortField === 'fare' && (sortOrder === 'asc' ? '↑' : '↓')}
          </button>
        </div>
      </div>

      {/* Train Cards List */}
      <div className="space-y-3" role="list" aria-label="Available Trains Comparison">
        {sortedAndFilteredTrains.map((train) => {
          const isSelected = selectedTrainNumber === train.trainNumber;

          return (
            <div
              key={`${train.trainNumber}-${train.travelClass}`}
              role="listitem"
              onClick={() => onSelectTrain && onSelectTrain(train)}
              className={`p-5 rounded-xl border transition-all ${
                isSelected
                  ? 'bg-emerald-50/90 border-accent-emerald ring-2 ring-accent-emerald/20 shadow-glass-hover'
                  : 'bg-white/80 border-stone-200/90 hover:border-stone-300 hover:shadow-xs'
              } ${onSelectTrain ? 'cursor-pointer' : ''}`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                {/* Train Identifiers & Badges */}
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-stone-100 text-stone-800 border border-stone-200">
                      #{train.trainNumber}
                    </span>
                    <h4 className="font-bold text-ink text-base">{train.trainName}</h4>
                    <StatusBadge label={train.travelClass} variant="info" />
                    {getProvenanceBadge(train.dataProvenance)}
                  </div>

                  {/* Route & Times */}
                  <div className="flex items-center gap-4 text-sm text-ink-muted pt-1">
                    <div>
                      <strong className="text-ink font-mono text-base">{train.departureTime}</strong>
                      <span className="text-xs block text-stone-500">{train.originStation}</span>
                    </div>
                    <div className="flex flex-col items-center px-2">
                      <span className="text-[11px] font-medium text-stone-600 bg-stone-100 px-2 py-0.5 rounded-full">
                        {train.duration}
                      </span>
                      <div className="w-16 h-0.5 bg-stone-300 my-1 relative">
                        <div className="absolute right-0 -top-1 w-2 h-2 border-t-2 border-r-2 border-stone-400 rotate-45" />
                      </div>
                    </div>
                    <div>
                      <strong className="text-ink font-mono text-base">{train.arrivalTime}</strong>
                      <span className="text-xs block text-stone-500">{train.destinationStation}</span>
                    </div>
                  </div>
                </div>

                {/* Fare & Availability */}
                <div className="flex flex-row md:flex-col items-end justify-between border-t md:border-t-0 pt-3 md:pt-0 border-stone-100 gap-2 min-w-[160px]">
                  <div className="text-right">
                    <span className="text-xs text-ink-muted block">Total Tatkal Fare</span>
                    <span className="text-xl font-extrabold text-ink font-mono">₹{train.totalFare}</span>
                    <span className="text-[10px] text-stone-500 block">
                      (Base: ₹{train.baseFare} + Tatkal: ₹{train.tatkalCharge})
                    </span>
                  </div>

                  <div className="text-right">
                    <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                      {train.availabilityStatus}
                    </span>
                  </div>
                </div>
              </div>

              {/* Recommendation Panel from Member 4 Comparison Engine */}
              {train.recommendation && (
                <div className="mt-3.5 pt-3 border-t border-stone-200/60 bg-amber-50/60 -mx-5 -mb-5 px-5 py-2.5 rounded-b-xl flex items-start gap-2 text-xs text-amber-950">
                  <Sparkles className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" aria-hidden="true" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <strong className="text-amber-900 font-semibold">
                        {train.recommendation.badge.replace(/_/g, ' ')}
                      </strong>
                      <span className="text-[10px] text-amber-700">({train.recommendation.engineProvenance})</span>
                    </div>
                    <p className="mt-0.5 text-stone-700">{train.recommendation.reason}</p>
                  </div>
                  {onSelectTrain && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectTrain(train);
                      }}
                      className="shrink-0 px-3 py-1 bg-ink text-white hover:bg-stone-800 text-xs font-medium rounded-lg transition-colors"
                    >
                      {isSelected ? 'Selected' : 'Select Train'}
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="text-[11px] text-stone-500 flex items-center gap-1.5 pt-2">
        <Info className="w-3.5 h-3.5 text-stone-400" aria-hidden="true" />
        <span>
          Sorting controls are presentation aids only. Recommendations and availability allocations are generated by Member 4 comparison engine.
        </span>
      </div>
    </div>
  );
}
