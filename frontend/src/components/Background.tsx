import { type ReactNode } from 'react';

interface BackgroundProps {
  children: ReactNode;
  className?: string;
}

export function Background({ children, className = '' }: BackgroundProps) {
  return (
    <div
      className={`min-h-screen relative overflow-hidden ${className}`}
      style={{
        backgroundColor: '#0b0c10',
        backgroundImage: `
          radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
          linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.25))
        `,
        backgroundSize: '3px 3px, 100% 100%',
        backgroundBlendMode: 'overlay',
      }}
    >
      {/* optional vignette */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(circle at center, rgba(0,0,0,0) 40%, rgba(0,0,0,0.45) 100%)',
          zIndex: 0,
        }}
      ></div>

      {/* content */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </div>
    </div>
  );
}