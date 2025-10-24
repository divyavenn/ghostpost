import { useEffect, useRef } from 'react';
import { Flip } from 'number-flip';

interface AnimatedNumberProps {
  value: number;
  className?: string;
}

export function AnimatedNumber({ value, className = '' }: AnimatedNumberProps) {
  const nodeRef = useRef<HTMLDivElement>(null);
  const flipInstance = useRef<Flip | null>(null);
  const previousValue = useRef<number>(value);

  useEffect(() => {
    if (!nodeRef.current) return;

    // Initialize Flip instance on first render
    if (!flipInstance.current) {
      flipInstance.current = new Flip({
        node: nodeRef.current,
        from: value,
        duration: 0.3,
        direct: false, // Animate through each number
      });
      previousValue.current = value;
    }
  }, [value]);

  useEffect(() => {
    if (!flipInstance.current || value === previousValue.current) return;

    // Animate to new value
    flipInstance.current.flipTo({
      to: value,
      duration: 0.3,
      direct: false,
    });

    previousValue.current = value;
  }, [value]);

  return <div ref={nodeRef} className={className} />;
}
