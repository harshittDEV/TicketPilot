'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { BackendTool, BackendSkill } from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import {
  Wrench,
  Sparkles,
  ShieldCheck,
  Activity,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Cpu,
  RefreshCw,
  Zap,
} from 'lucide-react';

export function ToolsSkillsHub() {
  const [tools, setTools] = useState<BackendTool[]>([]);
  const [skills, setSkills] = useState<BackendSkill[]>([]);
  const [circuitBreakers, setCircuitBreakers] = useState<Record<string, any>>({});
  const [selectedSkill, setSelectedSkill] = useState<BackendSkill | null>(null);

  const [loading, setLoading] = useState(true);
  const [healthChecking, setHealthChecking] = useState<string | null>(null);
  const [diagnosticsResult, setDiagnosticsResult] = useState<{ tool: string; data: any } | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [toolsRes, skillsRes, cbRes] = await Promise.all([
        api.getTools(),
        api.getSkills(),
        api.getCircuitBreakers(),
      ]);

      if (toolsRes.success && toolsRes.data) {
        setTools(toolsRes.data);
      }
      if (skillsRes.success && skillsRes.data) {
        setSkills(skillsRes.data);
        if (skillsRes.data.length > 0 && !selectedSkill) {
          setSelectedSkill(skillsRes.data[0]);
        }
      }
      if (cbRes.success && cbRes.data) {
        setCircuitBreakers(cbRes.data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunDiagnostics = async (toolName: string) => {
    setHealthChecking(toolName);
    try {
      const res = await api.getToolHealth(toolName);
      setDiagnosticsResult({ tool: toolName, data: res.data || res.error });
    } finally {
      setHealthChecking(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-2 border-b border-stone-200/60">
        <div className="flex items-center gap-2">
          <Wrench className="w-5 h-5 text-accent-emerald" />
          <div>
            <h3 className="text-base font-extrabold text-ink tracking-tight">
              Tools & Declarative Skills System
            </h3>
            <p className="text-xs text-ink-muted">
              Live inspection of registered tool adapters, declarative agent skills, and integration circuit breakers.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-stone-50 border border-stone-200 text-xs font-semibold text-stone-700 shadow-2xs transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Registry</span>
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-xl bg-stone-200/60 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Registered Tools Grid */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="w-4 h-4 text-accent-emerald" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-ink">
                Registered Tool Adapters ({tools.length})
              </h4>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {tools.map((tool) => (
                <GlassCard key={tool.name} depth={1} className="p-4 space-y-3 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono text-xs font-bold text-ink">{tool.name}</span>
                      <StatusBadge
                        label={tool.is_available ? 'Available' : 'Unavailable'}
                        variant={tool.is_available ? 'success' : 'warning'}
                      />
                    </div>
                    <p className="text-xs text-stone-600 leading-relaxed mb-3">
                      {tool.description}
                    </p>
                    {tool.capabilities && tool.capabilities.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {tool.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="text-[10px] font-mono px-2 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200"
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="pt-2 border-t border-stone-100 flex items-center justify-between">
                    <span className="text-[10px] text-ink-muted">v{tool.version}</span>
                    <button
                      type="button"
                      onClick={() => handleRunDiagnostics(tool.name)}
                      disabled={healthChecking === tool.name}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-accent-emerald hover:underline"
                    >
                      <Activity className={`w-3 h-3 ${healthChecking === tool.name ? 'animate-spin' : ''}`} />
                      <span>{healthChecking === tool.name ? 'Diagnosing...' : 'Run Diagnostics'}</span>
                    </button>
                  </div>
                </GlassCard>
              ))}
            </div>
          </div>

          {/* Diagnostics Modal / Popup Banner */}
          {diagnosticsResult && (
            <div className="p-4 rounded-xl bg-white border border-stone-200 shadow-glass space-y-2">
              <div className="flex items-center justify-between border-b border-stone-100 pb-2">
                <span className="text-xs font-bold text-ink">
                  Diagnostics Report: {diagnosticsResult.tool}
                </span>
                <button
                  type="button"
                  onClick={() => setDiagnosticsResult(null)}
                  className="text-stone-400 hover:text-stone-700 text-xs font-semibold"
                >
                  Close
                </button>
              </div>
              <pre className="text-[11px] font-mono bg-stone-900 text-emerald-400 p-3 rounded-lg overflow-x-auto">
                {JSON.stringify(diagnosticsResult.data, null, 2)}
              </pre>
            </div>
          )}

          {/* Skills Discovery & Steps Explorer */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-accent-emerald" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-ink">
                Declarative Agent Skills ({skills.length})
              </h4>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              {/* Skill Selector (4 cols) */}
              <div className="lg:col-span-4 space-y-2">
                {skills.map((skill) => {
                  const isSelected = selectedSkill?.name === skill.name;
                  return (
                    <div
                      key={skill.name}
                      onClick={() => setSelectedSkill(skill)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-white border-accent-emerald shadow-sm ring-1 ring-accent-emerald'
                          : 'bg-white/80 hover:bg-white border-stone-200'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-ink">{skill.name}</span>
                        <span className="text-[10px] font-mono text-stone-500">v{skill.version}</span>
                      </div>
                      <p className="text-[11px] text-stone-600 line-clamp-2">
                        {skill.description}
                      </p>
                    </div>
                  );
                })}
              </div>

              {/* Skill Details & Steps View (8 cols) */}
              <div className="lg:col-span-8">
                {selectedSkill ? (
                  <GlassCard depth={1} className="space-y-4">
                    <div>
                      <h4 className="text-sm font-extrabold text-ink mb-1">
                        {selectedSkill.name} (v{selectedSkill.version})
                      </h4>
                      <p className="text-xs text-stone-700 leading-relaxed">
                        {selectedSkill.description}
                      </p>
                    </div>

                    {/* Steps Sequence */}
                    <div>
                      <span className="text-[11px] font-bold uppercase tracking-wider text-ink-muted block mb-2">
                        Skill Execution Pipeline Steps ({selectedSkill.steps.length})
                      </span>
                      <div className="space-y-2">
                        {selectedSkill.steps.map((st, i) => (
                          <div
                            key={st.step_id}
                            className="p-3 rounded-lg bg-stone-50 border border-stone-200/80 flex items-start gap-3 text-xs"
                          >
                            <span className="w-5 h-5 rounded-full bg-white text-ink text-[10px] font-bold flex items-center justify-center border border-stone-200 shrink-0 mt-0.5">
                              {i + 1}
                            </span>
                            <div className="flex-1 space-y-0.5">
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-ink">{st.description}</span>
                                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-stone-200 text-stone-800">
                                  {st.tool_name}:{st.action_type}
                                </span>
                              </div>
                              <p className="text-[11px] text-stone-600">
                                Expected: {st.expected_outcome}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </GlassCard>
                ) : (
                  <GlassCard className="text-center py-8">
                    <p className="text-xs text-ink-muted">Select a skill to inspect its declarative steps.</p>
                  </GlassCard>
                )}
              </div>
            </div>
          </div>

          {/* Circuit Breakers Status */}
          {Object.keys(circuitBreakers).length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Zap className="w-4 h-4 text-accent-emerald" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-ink">
                  Resilience & Circuit Breakers State
                </h4>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(circuitBreakers).map(([name, cb]) => (
                  <div
                    key={name}
                    className="p-3 rounded-xl bg-white border border-stone-200 shadow-2xs space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-ink truncate">{name}</span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          cb.state === 'CLOSED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {cb.state}
                      </span>
                    </div>
                    <p className="text-[11px] text-stone-500">
                      Failures: {cb.failure_count} / {cb.failure_threshold}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
