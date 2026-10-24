import React from 'react';

export type BadgeVariant = 
  | 'success' 
  | 'warning' 
  | 'error' 
  | 'info' 
  | 'neutral' 
  | 'ac' 
  | 'nonac';

interface StatusBadgeProps {
  label: string;
  variant?: BadgeVariant;
  icon?: React.ReactNode;
  hint?: string;
  className?: string;
}

export function StatusBadge({
  label,
  variant = 'neutral',
  icon,
  hint,
  className = '',
}: StatusBadgeProps) {
  const variantStyles: Record<BadgeVariant, string> = {
    success: 'bg-emerald-50 text-emerald-800 border-emerald-200/80',
    warning: 'bg-amber-50 text-amber-900 border-amber-200/80',
    error: 'bg-rose-50 text-rose-800 border-rose-200/80',
    info: 'bg-sky-50 text-sky-800 border-sky-200/80',
    neutral: 'bg-stone-100 text-stone-700 border-stone-200',
    ac: 'bg-emerald-900 text-emerald-100 border-emerald-800',
    nonac: 'bg-amber-900 text-amber-100 border-amber-800',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${variantStyles[variant]} ${className}`}
      title={hint}
      role="status"
    >
      {icon && <span aria-hidden="true">{icon}</span>}
      <span>{label}</span>
      {hint && <span className="sr-only">({hint})</span>}
    </span>
  );
}
