'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { AuditEventRecord, EvidenceItem, EvidenceVerifyResult } from '@/lib/types';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import {
  ShieldCheck,
  FileCheck,
  AlertOctagon,
  Download,
  RefreshCw,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  Clock,
  Layers,
  FileText,
  FileCode,
  Image,
} from 'lucide-react';

export function AuditEvidenceInspector() {
  const [activeTab, setActiveTab] = useState<'audit' | 'evidence'>('audit');

  // Audit state
  const [auditEvents, setAuditEvents] = useState<AuditEventRecord[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [loadingAudit, setLoadingAudit] = useState(true);

  // Evidence state
  const [evidenceRecords, setEvidenceRecords] = useState<EvidenceItem[]>([]);
  const [loadingEvidence, setLoadingEvidence] = useState(true);
  const [verificationMap, setVerificationMap] = useState<Record<string, EvidenceVerifyResult>>({});
  const [verifyingId, setVerifyingId] = useState<string | null>(null);

  const loadAuditEvents = async () => {
    setLoadingAudit(true);
    try {
      const res = await api.getAuditEvents({
        event_category: selectedCategory === 'ALL' ? undefined : selectedCategory,
        page_size: 25,
      });
      if (res.success && res.data?.events) {
        setAuditEvents(res.data.events);
      }
    } finally {
      setLoadingAudit(false);
    }
  };

  const loadEvidence = async () => {
    setLoadingEvidence(true);
    try {
      const res = await api.getEvidence({ page_size: 25 });
      if (res.success && res.data?.records) {
        setEvidenceRecords(res.data.records);
      }
    } finally {
      setLoadingEvidence(false);
    }
  };

  useEffect(() => {
    loadAuditEvents();
  }, [selectedCategory]);

  useEffect(() => {
    loadEvidence();
  }, []);

  const handleVerifyEvidence = async (evidenceId: string) => {
    setVerifyingId(evidenceId);
    try {
      const res = await api.verifyEvidenceIntegrity(evidenceId);
      if (res.success && res.data) {
        setVerificationMap((prev) => ({
          ...prev,
          [evidenceId]: res.data as EvidenceVerifyResult,
        }));
      }
    } finally {
      setVerifyingId(null);
    }
  };

  const getEvidenceIcon = (type: string) => {
    switch (type.toUpperCase()) {
      case 'SCREENSHOT':
        return Image;
      case 'DOM_SNAPSHOT':
        return FileCode;
      default:
        return FileText;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Tab switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-stone-200/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-5 h-5 text-accent-emerald" />
            <h3 className="text-base font-extrabold text-ink tracking-tight">
              Audit Trail & Cryptographic Evidence
            </h3>
          </div>
          <p className="text-xs text-ink-muted">
            Immutable operation log, verifiable execution evidence, and SHA-256 tamper verification.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-stone-100 border border-stone-200/80">
          <button
            type="button"
            onClick={() => setActiveTab('audit')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'audit'
                ? 'bg-white text-ink shadow-xs'
                : 'text-stone-600 hover:text-ink'
            }`}
          >
            Audit Trail ({auditEvents.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('evidence')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'evidence'
                ? 'bg-white text-ink shadow-xs'
                : 'text-stone-600 hover:text-ink'
            }`}
          >
            Evidence Artifacts ({evidenceRecords.length})
          </button>
        </div>
      </div>

      {activeTab === 'audit' && (
        <div className="space-y-4">
          {/* Category Filter Pills */}
          <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1">
            <div className="flex items-center gap-1.5">
              {['ALL', 'TASK', 'RUN', 'TOOL', 'SKILL', 'RECOVERY'].map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                    selectedCategory === cat
                      ? 'bg-accent-emerald text-white shadow-2xs'
                      : 'bg-white text-stone-700 hover:bg-stone-50 border border-stone-200/80'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={loadAuditEvents}
              disabled={loadingAudit}
              className="p-1.5 rounded-lg bg-white hover:bg-stone-50 border border-stone-200 text-stone-600 shadow-2xs transition-colors shrink-0"
              title="Refresh audit events"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingAudit ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Audit Events Table */}
          {loadingAudit ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-14 rounded-xl bg-stone-100 animate-pulse" />
              ))}
            </div>
          ) : auditEvents.length === 0 ? (
            <GlassCard className="text-center py-10">
              <Clock className="w-8 h-8 text-stone-300 mx-auto mb-2" />
              <p className="text-xs font-semibold text-ink">No Audit Events Found</p>
              <p className="text-[11px] text-ink-muted mt-0.5">
                Execute a task or run to populate the immutable audit log.
              </p>
            </GlassCard>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-stone-200/80 bg-white/90 shadow-2xs">
              <table className="w-full text-left text-xs text-ink">
                <thead className="bg-stone-50/90 text-stone-600 text-[11px] uppercase tracking-wider font-bold border-b border-stone-200/80">
                  <tr>
                    <th className="py-2.5 px-3">Timestamp (UTC)</th>
                    <th className="py-2.5 px-3">Event Type</th>
                    <th className="py-2.5 px-3">Category</th>
                    <th className="py-2.5 px-3">Task / Run ID</th>
                    <th className="py-2.5 px-3">Outcome</th>
                    <th className="py-2.5 px-3">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 font-medium">
                  {auditEvents.map((e) => (
                    <tr key={e.id} className="hover:bg-stone-50/70 transition-colors">
                      <td className="py-2.5 px-3 font-mono text-[11px] text-stone-500 whitespace-nowrap">
                        {new Date(e.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-ink">
                        {e.event_type}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-stone-100 border border-stone-200 text-stone-700">
                          {e.event_category}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-stone-600">
                        {e.task_id ? `${e.task_id.slice(0, 8)}...` : '—'}
                      </td>
                      <td className="py-2.5 px-3">
                        <StatusBadge
                          label={e.outcome}
                          variant={
                            e.outcome === 'SUCCESS'
                              ? 'success'
                              : e.outcome === 'BLOCKED'
                              ? 'warning'
                              : 'error'
                          }
                        />
                      </td>
                      <td className="py-2.5 px-3 text-[11px] text-stone-600 max-w-xs truncate">
                        {e.details ? JSON.stringify(e.details) : 'None'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'evidence' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-muted">
              Artifact storage files and cryptographic SHA-256 verification.
            </span>
            <button
              type="button"
              onClick={loadEvidence}
              disabled={loadingEvidence}
              className="p-1.5 rounded-lg bg-white hover:bg-stone-50 border border-stone-200 text-stone-600 shadow-2xs transition-colors shrink-0"
              title="Refresh evidence list"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingEvidence ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {loadingEvidence ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-xl bg-stone-100 animate-pulse" />
              ))}
            </div>
          ) : evidenceRecords.length === 0 ? (
            <GlassCard className="text-center py-10">
              <FileCheck className="w-8 h-8 text-stone-300 mx-auto mb-2" />
              <p className="text-xs font-semibold text-ink">No Evidence Artifacts Stored</p>
              <p className="text-[11px] text-ink-muted mt-0.5">
                Screenshots and DOM snapshots captured by agent runs will appear here.
              </p>
            </GlassCard>
          ) : (
            <div className="space-y-3">
              {evidenceRecords.map((ev) => {
                const Icon = getEvidenceIcon(ev.evidence_type);
                const verification = verificationMap[ev.id];
                const isTampered =
                  ev.integrity_status === 'TAMPERED' || verification?.status === 'TAMPERED';
                const isMissing =
                  ev.integrity_status === 'MISSING' || verification?.status === 'MISSING';
                const isVerified =
                  verification?.status === 'VERIFIED' ||
                  (!verification && ev.integrity_status === 'VERIFIED');

                return (
                  <GlassCard key={ev.id} depth={1} className="p-4 space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-lg bg-stone-100 text-stone-700">
                          <Icon className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-ink">{ev.evidence_type}</span>
                            <span className="text-[10px] font-mono text-stone-500">
                              ({ev.file_size_bytes} bytes)
                            </span>
                          </div>
                          <p className="text-[11px] font-mono text-stone-600 truncate max-w-md">
                            {ev.file_path}
                          </p>
                        </div>
                      </div>

                      {/* Integrity Status Pill & Action Buttons */}
                      <div className="flex items-center gap-2">
                        {isTampered ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-800 bg-rose-100 px-2.5 py-0.5 rounded-full border border-rose-300">
                            <AlertOctagon className="w-3.5 h-3.5 text-rose-600" />
                            <span>TAMPERED</span>
                          </span>
                        ) : isMissing ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-800 bg-amber-100 px-2.5 py-0.5 rounded-full border border-amber-300">
                            <Clock className="w-3.5 h-3.5 text-amber-600" />
                            <span>STORAGE MISSING</span>
                          </span>
                        ) : isVerified ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full border border-emerald-300">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            <span>VERIFIED</span>
                          </span>
                        ) : null}

                        <button
                          type="button"
                          onClick={() => handleVerifyEvidence(ev.id)}
                          disabled={verifyingId === ev.id}
                          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-white hover:bg-stone-100 text-stone-800 border border-stone-200 shadow-2xs transition-colors"
                        >
                          <ShieldCheck
                            className={`w-3.5 h-3.5 text-emerald-600 ${
                              verifyingId === ev.id ? 'animate-spin' : ''
                            }`}
                          />
                          <span>{verifyingId === ev.id ? 'Checking...' : 'Verify SHA-256'}</span>
                        </button>

                        <a
                          href={api.getEvidenceDownloadUrl(ev.id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-stone-100 hover:bg-stone-200 text-stone-800 transition-colors"
                          title="Safely stream/download artifact"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    </div>

                    {/* Cryptographic SHA-256 Hash Display */}
                    <div className="p-2 rounded-lg bg-stone-50 border border-stone-200/60 flex items-center justify-between text-[11px] font-mono text-stone-600">
                      <span className="truncate">SHA-256: {ev.sha256_checksum}</span>
                      <span className="text-stone-400 shrink-0 ml-2">
                        {new Date(ev.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    {/* Verification result message if available */}
                    {verification && (
                      <p
                        className={`text-[11px] font-medium ${
                          verification.valid ? 'text-emerald-700' : 'text-rose-700'
                        }`}
                      >
                        Result: {verification.message}
                      </p>
                    )}
                  </GlassCard>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
