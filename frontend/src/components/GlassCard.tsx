import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  glow?: 'primary' | 'secondary' | 'none';
}

/**
 * Flat surface card — replaces the old glassmorphism card.
 * The `glow` prop is kept for API compatibility but no longer adds visual effects.
 * Active state uses a slightly lighter border instead.
 */
export function GlassCard({ children, className, glow = 'none' }: GlassCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-card',
        glow === 'primary' ? 'border-white/20' : 'border-border',
        className
      )}
    >
      {children}
    </div>
  );
}
