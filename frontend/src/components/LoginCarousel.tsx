import { useMemo, useRef, useEffect, useState } from 'react';
import { motion, useMotionValue, useTransform, animate } from 'framer-motion';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import type { LoginCard } from '../data/loginCards';
import { CardLightbox } from './CardLightbox';

interface LoginCarouselProps {
  cards: LoginCard[];
  radius?: number;
  cardSize?: { w: number; h: number };
  sensitivity?: number;
}

export function LoginCarousel({
  cards,
  radius = 500, // Larger radius to prevent overlap
  cardSize = { w: 90, h: 130 }, // Smaller cards to fit 50 in circle
  sensitivity = 0.08,
}: LoginCarouselProps) {
  const totalCardsToShow = 30;

  // Repeat cards to fill 50 slots
  const repeatedCards = useMemo(() => {
    const result: LoginCard[] = [];
    while (result.length < totalCardsToShow) {
      for (const card of cards) {
        if (result.length >= totalCardsToShow) break;
        result.push({ ...card, id: result.length });
      }
    }
    return result;
  }, [cards]);

  const N = repeatedCards.length;
  const angle = useMotionValue(0); // degrees; 0 means card 0 at top
  const containerRef = useRef<HTMLDivElement>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  // Layout: equally spaced angles around circle, 0° at top, increasing clockwise
  const itemAngles = useMemo(() => Array.from({ length: N }, (_, i) => (360 / N) * i), [N]);

  // Handle wheel -> rotate ring with easing/inertia
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY || 0;
      // Scroll down moves clockwise (positive degrees)
      const by = delta * sensitivity;
      // Smoothly animate a small step from current value
      const current = angle.get();
      animate(angle, current + by, { type: 'spring', stiffness: 200, damping: 28, mass: 0.6 });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [angle, sensitivity]);

  // Keyboard support: left/right to rotate
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowRight') {
      animate(angle, angle.get() + 360 / N, { type: 'spring', stiffness: 220, damping: 26 });
    } else if (e.key === 'ArrowLeft') {
      animate(angle, angle.get() - 360 / N, { type: 'spring', stiffness: 220, damping: 26 });
    }
  };

  // Helper: compute shortest angular distance (degrees, -180..180)
  const deltaDeg = (a: number, b: number) => {
    let d = (a - b) % 360;
    if (d > 180) d -= 360;
    else if (d < -180) d += 360;
    return d;
  };

  // Snap a given item index to the top (0°) keeping continuity
  const snapToIndex = (i: number) => {
    const aNow = angle.get();
    const targetAngleForI = itemAngles[i];
    const d = deltaDeg(aNow % 360, targetAngleForI);
    const goal = aNow - d;
    animate(angle, goal, { type: 'spring', stiffness: 260, damping: 30 });
  };

  return (
    <>
      <div
        ref={containerRef}
        tabIndex={0}
        onKeyDown={onKeyDown}
        className="relative mx-auto h-screen w-full select-none outline-none pointer-events-auto"
        aria-label="Circular card gallery. Use mouse wheel or arrow keys to rotate."
      >
        {/* Cards positioned on a ring */}
        <div className="absolute inset-0">
          {repeatedCards.map((card, i) => (
            <WheelCard
              key={`${card.id}-${i}`}
              index={i}
              card={card}
              itemAngle={itemAngles[i]}
              ringAngle={angle}
              radius={radius}
              cardSize={cardSize}
              onClick={() => {
                snapToIndex(i);
                // Open lightbox after a short delay to let snap animation finish
                // Map back to original card index
                const originalIndex = i % cards.length;
                setTimeout(() => setLightboxIndex(originalIndex), 400);
              }}
            />
          ))}
        </div>
      </div>

      {/* Lightbox modal */}
      {lightboxIndex !== null && (
        <CardLightbox
          cards={cards}
          currentIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onPrevious={() => setLightboxIndex((lightboxIndex - 1 + cards.length) % cards.length)}
          onNext={() => setLightboxIndex((lightboxIndex + 1) % cards.length)}
        />
      )}
    </>
  );
}

function WheelCard({
  index,
  card,
  itemAngle,
  ringAngle,
  radius,
  cardSize,
  onClick,
}: {
  index: number;
  card: LoginCard;
  itemAngle: number;
  ringAngle: ReturnType<typeof useMotionValue<number>>;
  radius: number;
  cardSize: { w: number; h: number };
  onClick: () => void;
}) {
  // Effective angle of this card = (itemAngle - ringAngle)
  const eff = useTransform(ringAngle, (a: number) => itemAngle - a);

  // Convert polar to CSS transforms: rotate(eff) then translateY(-radius)
  // Keep the rotation so cards follow the circle curve
  const transform = useTransform(
    eff,
    (deg: number) =>
      `translate(-50%, -50%) rotate(${deg}deg) translateY(-${radius}px)`
  );

  // Scale and depth based on proximity to 0° (top)
  const dist = useTransform(eff, (deg: number) => Math.abs(shortest(deg)));
  const opacity = useTransform(dist, [0, 60, 120, 180], [1, 0.9, 0.7, 0.5]);
  const zIndex = useTransform(dist, (d: number) => String(1000 - Math.round(d * 2)));
  const shadow = useTransform(dist, [0, 40, 90, 180], [
    '0 20px 60px rgba(0,0,0,0.4)',
    '0 10px 25px rgba(0,0,0,0.3)',
    '0 5px 12px rgba(0,0,0,0.2)',
    '0 2px 6px rgba(0,0,0,0.15)',
  ]);

  const { w, h } = cardSize;

  // Scale all dimensions dynamically based on card width
  // Base reference: w=90 (current size)
  const scale = w / 90;
  const padding = Math.max(2, Math.round(8 * scale));
  const animationSize = Math.max(8, Math.round(32 * scale));
  const numberFontSize = Math.max(6, Math.round(8 * scale));
  const headingFontSize = Math.max(8, Math.round(10 * scale));
  const subheadingFontSize = Math.max(6, Math.round(8 * scale));
  const spacing = Math.max(1, Math.round(4 * scale));
  const borderRadius = Math.max(4, Math.round(8 * scale));

  const getTextStyleClass = (textStyle: string) => {
    switch (textStyle) {
      case 'bold':
        return 'font-black tracking-tight';
      case 'italic':
        return 'italic font-light';
      case 'underline':
        return 'underline decoration-2 underline-offset-4 font-semibold';
      case 'gradient':
        return 'font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-cyan-400 bg-clip-text text-transparent';
      case 'handwritten':
        return 'font-serif italic';
      case 'minimal':
        return 'font-thin tracking-widest uppercase text-xs';
      default:
        return 'font-semibold';
    }
  };

  return (
    <motion.button
      type="button"
      className="absolute left-1/2 top-1/2 cursor-pointer bg-slate-800/90 backdrop-blur-sm ring-2 ring-slate-700/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      style={{
        width: w,
        height: h,
        transform,
        zIndex,
        opacity,
        boxShadow: shadow,
        borderRadius: `${borderRadius}px`,
      }}
      onClick={onClick}
      aria-label={`Focus card ${index + 1}: ${card.heading}`}
    >
      <div
        className="relative h-full w-full overflow-hidden flex flex-col items-center justify-center"
        style={{
          padding: `${padding}px`,
          borderRadius: `${borderRadius}px`,
        }}
      >
        {card.animation && (
          <div style={{
            width: `${animationSize}px`,
            height: `${animationSize}px`,
            marginBottom: `${spacing}px`,
          }}>
            <DotLottieReact src={card.animation} loop autoplay />
          </div>
        )}
        <div
          className="text-gray-500"
          style={{
            fontSize: `${numberFontSize}px`,
            marginBottom: `${spacing}px`,
          }}
        >
          {String(index + 1).padStart(2, '0')}
        </div>
        <h3
          className={`leading-tight text-center ${card.accentColor} ${getTextStyleClass(
            card.textStyle
          )}`}
          style={{
            fontSize: `${headingFontSize}px`,
            marginBottom: `${spacing}px`,
          }}
        >
          {card.heading}
        </h3>
        {card.subheading && (
          <p
            className={`leading-tight text-gray-300 text-center ${getTextStyleClass(card.textStyle)}`}
            style={{
              fontSize: `${subheadingFontSize}px`,
            }}
          >
            {card.subheading}
          </p>
        )}
      </div>
    </motion.button>
  );
}

function shortest(deg: number) {
  let d = ((deg + 180) % 360) - 180; // -180..180
  if (d < -180) d += 360;
  return d;
}
