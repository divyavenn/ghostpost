import { type ReactNode } from 'react';

interface BackgroundProps {
  children: ReactNode;
  className?: string;
}

export function Background({ children, className = '' }: BackgroundProps) {
  return (
    <div className={`min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-920 ${className}`}>
      {children}
    </div>
  );
}
