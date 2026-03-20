import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  glow?: 'primary' | 'secondary' | 'none';
}

export function GlassCard({ children, className, glow = 'none' }: GlassCardProps) {
  return (
    <div
      className={cn(
        glow === 'primary' ? 'glass-card-glow' : glow === 'secondary' ? 'glass-card-secondary' : 'glass-card',
        className
      )}
    >
      {children}
    </div>
  );
}
