import React from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  interactive?: boolean;
  depth?: 1 | 2;
  id?: string;
}

export function GlassCard({
  children,
  className = '',
  interactive = false,
  depth,
  id,
}: GlassCardProps) {
  const depthClass = depth === 2 ? 'shadow-glass-elevated' : depth === 1 ? 'shadow-glass-card' : 'shadow-glass';
  const interactiveClass = interactive ? 'glass-card-interactive cursor-pointer' : 'glass-card';

  return (
    <div
      id={id}
      className={`${interactiveClass} ${depthClass} p-5 md:p-6 text-ink ${className}`}
    >
      {children}
    </div>
  );
}
