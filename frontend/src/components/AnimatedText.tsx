import { useEffect, useState } from 'react';

interface AnimatedTextProps {
  text: string;
  className?: string;
}

export function AnimatedText({ text, className = '' }: AnimatedTextProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const letters = text.split('');

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % (letters.length + 3)); // +3 for the dots
    }, 150);

    return () => clearInterval(interval);
  }, [letters.length]);

  const getLetterColor = (index: number) => {
    const blueShades = [
      'text-sky-300',
      'text-sky-400',
      'text-sky-500',
      'text-blue-400',
      'text-blue-500',
      'text-cyan-400',
      'text-cyan-500',
    ];

    // Calculate distance from active index
    const distance = Math.abs(index - activeIndex);

    if (distance === 0) return blueShades[6]; // brightest
    if (distance === 1) return blueShades[5];
    if (distance === 2) return blueShades[4];
    if (distance === 3) return blueShades[3];

    return 'text-white'; // default
  };

  const getLetterAnimation = (index: number) => {
    const distance = Math.abs(index - activeIndex);

    if (distance === 0) return '-translate-y-2';
    if (distance === 1) return '-translate-y-1';

    return 'translate-y-0';
  };

  const dots = ['·', '·', '·'];

  return (
    <div className={className}>
      {letters.map((letter, index) => (
        <span
          key={index}
          className={`inline-block transition-all duration-200 ${getLetterColor(index)} ${getLetterAnimation(index)}`}
        >
          {letter === ' ' ? '\u00A0' : letter}
        </span>
      ))}
      {dots.map((dot, index) => {
        const dotIndex = letters.length + index;
        const isVisible = activeIndex >= dotIndex && activeIndex < dotIndex + 3;
        return (
          <span
            key={`dot-${index}`}
            className={`inline-block transition-all duration-200 ${
              isVisible ? getLetterColor(dotIndex) : 'text-transparent'
            } ${getLetterAnimation(dotIndex)}`}
          >
            {dot}
          </span>
        );
      })}
    </div>
  );
}
