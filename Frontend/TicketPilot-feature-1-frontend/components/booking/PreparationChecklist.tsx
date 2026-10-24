'use client';

import React, { useState } from 'react';
import { CheckSquare, Square, ExternalLink, ShieldAlert, Key, CreditCard, Users, Wifi } from 'lucide-react';

interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const CHECKLIST_ITEMS: ChecklistItem[] = [
  {
    id: 'irctc_login',
    label: 'IRCTC Account Pre-Login',
    description: 'Login to official IRCTC portal 10 minutes prior to verify session and avoid CAPTCHA delays.',
    icon: <Key className="w-4 h-4 text-accent-emerald" />,
  },
  {
    id: 'master_list',
    label: 'Master Passenger List Pre-Saved',
    description: 'Ensure passenger names, ages, and IDs are added to your IRCTC "Master List" for 1-click addition.',
    icon: <Users className="w-4 h-4 text-accent-emerald" />,
  },
  {
    id: 'payment_ready',
    label: 'Payment Method Pre-Configured',
    description: 'Keep IRCTC iMudra, UPI App, or NetBanking OTP device active. Fast payment is essential in Tatkal.',
    icon: <CreditCard className="w-4 h-4 text-accent-emerald" />,
  },
  {
    id: 'network_stability',
    label: 'Stable Internet Connection',
    description: 'Use a low-latency connection. Avoid frequent page refreshes during payment processing.',
    icon: <Wifi className="w-4 h-4 text-accent-emerald" />,
  },
];

export function PreparationChecklist() {
  const [checked, setChecked] = useState<Record<string, boolean>>({
    irctc_login: false,
    master_list: false,
    payment_ready: false,
    network_stability: true,
  });

  const toggle = (id: string) => {
    setChecked(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const completedCount = Object.values(checked).filter(Boolean).length;
  const progressPercent = Math.round((completedCount / CHECKLIST_ITEMS.length) * 100);

  const handleOpenIrctc = () => {
    window.open('https://www.irctc.co.in/', '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="space-y-4">
      {/* Progress Indicator */}
      <div className="flex items-center justify-between text-xs font-medium text-ink-muted mb-1">
        <span>Readiness Checklist</span>
        <span>{completedCount} of {CHECKLIST_ITEMS.length} Completed ({progressPercent}%)</span>
      </div>
      <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden border border-stone-200">
        <div
          className="bg-accent-emerald h-2 transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Checklist items */}
      <div className="space-y-2.5">
        {CHECKLIST_ITEMS.map((item) => {
          const isDone = !!checked[item.id];
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => toggle(item.id)}
              className={`w-full text-left p-3 rounded-xl border flex items-start gap-3 transition-colors ${
                isDone
                  ? 'bg-emerald-50/70 border-emerald-200/90 text-emerald-950'
                  : 'bg-white/80 border-stone-200/90 hover:bg-stone-50 text-ink'
              }`}
            >
              <span className="mt-0.5 shrink-0">
                {isDone ? (
                  <CheckSquare className="w-5 h-5 text-emerald-700" />
                ) : (
                  <Square className="w-5 h-5 text-stone-400" />
                )}
              </span>
              <div className="flex-1">
                <div className="flex items-center gap-1.5 font-semibold text-sm">
                  {item.icon}
                  <span>{item.label}</span>
                </div>
                <p className="text-xs text-stone-600 mt-0.5">{item.description}</p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Prominent Official IRCTC Launcher */}
      <div className="pt-2">
        <button
          type="button"
          onClick={handleOpenIrctc}
          className="w-full py-3.5 px-4 rounded-xl bg-ink hover:bg-stone-800 text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-sm transition-all focus:ring-2 focus:ring-accent-emerald focus:ring-offset-2"
        >
          <span>Open Official IRCTC Portal</span>
          <ExternalLink className="w-4 h-4" aria-hidden="true" />
        </button>

        {/* Clear boundaries notice */}
        <div className="mt-3 p-3 rounded-xl bg-amber-50/80 border border-amber-200 text-xs text-amber-950 flex items-start gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="text-[11px] leading-relaxed">
            <strong>Security Boundary Notice:</strong> Clicking this button will securely open{' '}
            <code className="bg-amber-100/90 px-1 py-0.5 rounded font-mono">https://www.irctc.co.in/</code>{' '}
            in a separate tab. All authentication, CAPTCHA entry, and payments are strictly performed by you directly on IRCTC. Opening IRCTC does <strong>not</strong> book a ticket, record a confirmed PNR, or store your passwords.
          </div>
        </div>
      </div>
    </div>
  );
}
