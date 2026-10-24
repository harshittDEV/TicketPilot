'use client';

import React, { useState } from 'react';
import { Eye, Brain, CheckCircle2, Wrench, ShieldAlert, Sparkles, Layers } from 'lucide-react';

export interface SpatialPipelineVisualizerProps {
  activeStep?: string | null;
  status?: string;
  onStepSelect?: (step: string) => void;
  className?: string;
}

export function SpatialPipelineVisualizer({
  activeStep,
  status = 'READY',
  onStepSelect,
  className = '',
}: SpatialPipelineVisualizerProps) {
  const [tilt, setTilt] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [is3DEnabled, setIs3DEnabled] = useState(true);

  const steps = [
    {
      id: 'observer',
      label: 'Observer',
      subtitle: 'State Perception',
      icon: Eye,
      color: 'from-blue-500/20 to-sky-500/10 border-blue-400/30 text-blue-700',
      activeColor: 'bg-blue-500/15 border-blue-500 text-blue-900 shadow-blue-500/20',
      description: 'Captures DOM snapshots, visual geometry, and UI state signals without side-effects.',
    },
    {
      id: 'planner',
      label: 'Planner',
      subtitle: 'Skill Synthesis',
      icon: Brain,
      color: 'from-indigo-500/20 to-purple-500/10 border-indigo-400/30 text-indigo-700',
      activeColor: 'bg-indigo-500/15 border-indigo-500 text-indigo-900 shadow-indigo-500/20',
      description: 'Evaluates goals, synthesizes tool commands, and enforces bounded execution plans.',
    },
    {
      id: 'verifier',
      label: 'Verifier',
      subtitle: 'Safety Guardrails',
      icon: CheckCircle2,
      color: 'from-emerald-500/20 to-teal-500/10 border-emerald-400/30 text-emerald-700',
      activeColor: 'bg-emerald-500/15 border-emerald-500 text-emerald-900 shadow-emerald-500/20',
      description: 'Validates preconditions, guarantees safety boundaries, and confirms expected postconditions.',
    },
    {
      id: 'tools',
      label: 'Tool Adapter',
      subtitle: 'Execution Engine',
      icon: Wrench,
      color: 'from-amber-500/20 to-orange-500/10 border-amber-400/30 text-amber-700',
      activeColor: 'bg-amber-500/15 border-amber-500 text-amber-900 shadow-amber-500/20',
      description: 'Invokes browser, desktop, and teammate modules with timeout controls and circuit breakers.',
    },
    {
      id: 'recovery',
      label: 'Human Gate',
      subtitle: 'Resilience & Handoff',
      icon: ShieldAlert,
      color: 'from-rose-500/20 to-pink-500/10 border-rose-400/30 text-rose-700',
      activeColor: 'bg-rose-500/15 border-rose-500 text-rose-900 shadow-rose-500/20',
      description: 'Enforces human authorization for CAPTCHA challenges and final payment checkpoints.',
    },
  ];

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!is3DEnabled) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    // Bounded tilt angles between -8 and +8 deg
    setTilt({
      x: Math.max(-8, Math.min(8, -(y / rect.height) * 16)),
      y: Math.max(-8, Math.min(8, (x / rect.width) * 16)),
    });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  return (
    <div className={`relative ${className}`}>
      {/* 3D / 2D Control Pill */}
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-wider text-ink-muted">
            Agent Execution Pipeline Architecture
          </span>
        </div>
        <button
          type="button"
          onClick={() => setIs3DEnabled(!is3DEnabled)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-white/80 hover:bg-white text-stone-700 border border-stone-200/80 shadow-2xs transition-colors"
          title="Toggle 3D perspective depth effect"
        >
          <Layers className="w-3 h-3 text-stone-500" />
          <span>{is3DEnabled ? '3D Spatial View' : 'Flat 2D View'}</span>
        </button>
      </div>

      {/* Spatial Stage Container */}
      <div
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{
          perspective: is3DEnabled ? '1000px' : 'none',
        }}
        className="w-full transition-transform duration-200 ease-out"
      >
        <div
          style={{
            transform: is3DEnabled
              ? `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`
              : 'none',
            transformStyle: 'preserve-3d',
            transition: 'transform 0.15s ease-out',
          }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 p-4 rounded-2xl bg-white/70 backdrop-blur-xl border border-stone-200/70 shadow-glass shadow-[inset_0_1px_0_0_rgba(255,255,255,0.8)]"
        >
          {steps.map((step, idx) => {
            const Icon = step.icon;
            const isCurrent =
              activeStep?.toLowerCase().includes(step.id) ||
              (status === 'WAITING_FOR_HUMAN' && step.id === 'recovery') ||
              (status === 'RUNNING' && step.id === 'tools');

            return (
              <div
                key={step.id}
                onClick={() => onStepSelect?.(step.id)}
                style={{
                  transform: is3DEnabled ? `translateZ(${isCurrent ? 24 : 10}px)` : 'none',
                  transition: 'transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease',
                }}
                className={`relative group cursor-pointer p-4 rounded-xl border transition-all ${
                  isCurrent
                    ? `${step.activeColor} ring-2 ring-emerald-500/40 shadow-lg`
                    : `bg-gradient-to-b ${step.color} hover:bg-white/90 hover:shadow-md border-stone-200/60`
                }`}
              >
                {/* Step Index Badge */}
                <div className="flex items-center justify-between mb-3">
                  <span className="w-5 h-5 rounded-full bg-white/90 text-ink text-[10px] font-bold flex items-center justify-center border border-stone-200/80 shadow-2xs">
                    0{idx + 1}
                  </span>
                  {isCurrent && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-extrabold uppercase tracking-wider text-emerald-800 bg-emerald-100/80 px-2 py-0.5 rounded-full border border-emerald-200">
                      Active
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 mb-1.5">
                  <div
                    className={`p-1.5 rounded-lg ${
                      isCurrent ? 'bg-white shadow-2xs' : 'bg-white/70'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-ink tracking-tight leading-tight">
                      {step.label}
                    </h4>
                    <p className="text-[10px] text-ink-muted leading-tight font-medium">
                      {step.subtitle}
                    </p>
                  </div>
                </div>

                <p className="text-[11px] text-stone-600 line-clamp-2 mt-2 leading-relaxed">
                  {step.description}
                </p>

                {/* Subtle Glass Floor Depth Effect */}
                {is3DEnabled && (
                  <div className="absolute inset-x-2 -bottom-1 h-1 bg-black/5 rounded-full blur-[2px] opacity-0 group-hover:opacity-100 transition-opacity" />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
