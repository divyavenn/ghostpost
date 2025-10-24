import { useMemo, useRef, useEffect, useState } from 'react';
import { motion, useMotionValue, useTransform, animate } from 'framer-motion';
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

  // Scale border radius dynamically based on card width
  const scale = w / 90;
  const borderRadius = Math.max(4, Math.round(8 * scale));

  // Wheel view: Show ONLY the image (full bleed, no text or styling)
  return (
    <motion.button
      type="button"
      className="absolute left-1/2 top-1/2 cursor-pointer focus:outline-none overflow-hidden"
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
      <img
        src={card.image}
        alt={card.heading}
        className="w-full h-full object-cover"
      />
    </motion.button>
  );
}

function shortest(deg: number) {
  let d = ((deg + 180) % 360) - 180; // -180..180
  if (d < -180) d += 360;
  return d;
}
