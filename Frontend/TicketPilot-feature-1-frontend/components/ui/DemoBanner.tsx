'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { BackendHealth } from '@/lib/types';
import { ShieldCheck, AlertCircle, RotateCcw, Activity, ShieldAlert } from 'lucide-react';

export function DemoBanner() {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [checking, setChecking] = useState(true);
  const [isDemo, setIsDemo] = useState(api.isDemoActive());

  const checkConnection = async () => {
    setChecking(true);
    try {
      const res = await api.checkBackendHealth(true);
      if (res.success && res.data) {
        setHealth(res.data);
      } else {
        setHealth(null);
      }
      setIsDemo(api.isDemoActive());
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      role="region"
      aria-label="Application backend status banner"
      className="w-full bg-stone-900 text-stone-200 border-b border-stone-800 px-4 py-2 text-xs"
    >
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {health && health.status === 'ok' ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40 shadow-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              FASTAPI BACKEND ONLINE • v{health.api_version} • DB {health.database.toUpperCase()}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40">
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              BACKEND OFFLINE • LOCAL DEMO MODE
            </span>
          )}

          <span className="text-stone-400 hidden sm:inline">
            | Safety Policy: Live IRCTC submission & automated payments remain strictly disabled.
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={checkConnection}
            disabled={checking}
            className="inline-flex items-center gap-1 text-[11px] font-semibold text-stone-300 hover:text-white transition-colors"
          >
            <RotateCcw className={`w-3 h-3 ${checking ? 'animate-spin' : ''}`} />
            <span>{checking ? 'Checking...' : 'Check Status'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
