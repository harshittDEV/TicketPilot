'use client';

import React from 'react';
import { Scene } from '@/components/threeui/MengToSketchbookScene';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Sparkles, ShieldCheck, Code, AlertTriangle, Layers, ExternalLink } from 'lucide-react';
import Link from 'next/link';

export default function ThreeUIPreviewPage() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-stone-200/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-5 h-5 text-accent-lavender" />
            <h1 className="text-2xl font-extrabold text-ink tracking-tight">ThreeUI Source Integration Showcase</h1>
          </div>
          <p className="text-xs sm:text-sm text-ink-muted">
            Preserved, isolated implementation of <code>MengToSketchbookLandingPage</code> from <code>@designcodeio/threeui</code>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge label="Bundle SHA: e0330548b1ac" variant="info" />
          <StatusBadge label="Isolated Sandbox" variant="success" />
        </div>
      </div>

      {/* Architectural Alignment & Policy Callout */}
      <GlassCard className="border-amber-200 bg-amber-50/50">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
          <div className="space-y-1.5 text-xs text-amber-950">
            <strong className="text-sm font-bold block text-amber-900">
              Template Reconcile Policy & Architectural Separation
            </strong>
            <p className="leading-relaxed">
              As required by the UI architecture policy, the original ThreeUI component is a creative sketchbook portfolio (Singapore landmarks), not an Indian Railways operational dashboard. In accordance with strict product integrity:
            </p>
            <ul className="list-disc pl-5 space-y-1 text-stone-700">
              <li>Original source files are preserved byte-for-byte in <code className="font-mono bg-white px-1 py-0.5 rounded">src/shaders/landing-pages/</code>.</li>
              <li>Template CSS (<code className="font-mono bg-white px-1 py-0.5 rounded">threeui.css</code>) is sandboxed inside an iframe frame to prevent style leakage into functional Tatkal screens.</li>
              <li>Functional travel workspaces, countdown widgets, timetable tables, and forms are built with purpose-built 3D glass tokens, keeping this creative showcase isolated.</li>
            </ul>
          </div>
        </div>
      </GlassCard>

      {/* Live Component Render */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-ink-muted uppercase tracking-wider">
            Live Component Render (Interactive Sandboxed Canvas):
          </span>
          <a
            href="https://threeui.com/landing-pages/meng-to-sketchbook.html"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-emerald hover:underline flex items-center gap-1 font-medium"
          >
            <span>View Canonical ThreeUI Source</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        <Scene />
      </div>

      {/* Integration Technical Specifications */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GlassCard depth={1} className="text-xs space-y-2">
          <div className="flex items-center gap-2 font-bold text-ink">
            <Code className="w-4 h-4 text-accent-emerald" />
            <h3>Source Bundle Manifest</h3>
          </div>
          <div className="font-mono text-[11px] bg-stone-900 text-stone-200 p-3 rounded-xl space-y-1 overflow-x-auto">
            <div>Component: MengToSketchbookLandingPage</div>
            <div>Package: @designcodeio/threeui</div>
            <div>Canonical URL: /landing-pages/meng-to-sketchbook.html</div>
            <div>Revision SHA-256: e0330548b1ac...</div>
            <div>Files: LandingPages.tsx, pageTypography.ts, pageRecipes.ts, LandingPageFrame.tsx, threeui.css</div>
          </div>
        </GlassCard>

        <GlassCard depth={1} className="text-xs space-y-2">
          <div className="flex items-center gap-2 font-bold text-ink">
            <Layers className="w-4 h-4 text-accent-emerald" />
            <h3>Asset & Typography Resolution</h3>
          </div>
          <p className="text-stone-600 leading-relaxed">
            The canonical HTML uses custom web typography (Instrument Serif and Newsreader) and embedded illustrations. Assets are served from the registered Supabase storage bucket configured in the ThreeUI canonical bundle.
          </p>
          <div className="pt-2">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-ink text-white font-medium text-xs hover:bg-stone-800 transition-colors"
            >
              <span>Back to Tatkal Dashboard</span>
            </Link>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
