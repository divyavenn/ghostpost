import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import type { LoginCard } from '../data/loginCards';

interface FeatureCardProps {
  card: LoginCard;
  angle: number; // Base angle position in circle (0-360)
  rotationOffset: number; // Current rotation from scroll
  zoomLevel: number; // 0 = zoomed out, 1 = zoomed in
  currentCardIndex: number; // Which card is currently focused
}

export function FeatureCard({ card, angle, rotationOffset, zoomLevel, currentCardIndex }: FeatureCardProps) {
  // Calculate final angle with rotation offset
  const finalAngle = angle + rotationOffset;
  const angleRad = (finalAngle * Math.PI) / 180;

  // When zoomed out: arrange in circle
  // When zoomed in: arrange horizontally at top (like a carousel)
  let x: number, y: number;

  if (zoomLevel < 0.1) {
    // Zoomed out: circular arrangement
    const baseRadius = 600;
    x = Math.cos(angleRad) * baseRadius;
    y = Math.sin(angleRad) * baseRadius;
  } else {
    // Zoomed in: horizontal carousel at top
    // Cards spread out horizontally based on their angle
    const horizontalSpacing = 450; // Space between cards
    x = Math.cos(angleRad) * horizontalSpacing;
    y = -200; // Fixed Y position at top (slightly above center)
  }

  // Determine if this is the currently focused card
  const isCurrentCard = (card.id - 1) === currentCardIndex;

  // Calculate depth (cards at top are "closer", bottom are "farther")
  const depthFactor = (Math.sin(angleRad) + 1) / 2;

  // Calculate distance from center (0 degrees after rotation)
  const normalizedAngle = ((finalAngle % 360) + 360) % 360; // Normalize to 0-360
  const distanceFromCenter = Math.min(
    Math.abs(normalizedAngle),
    Math.abs(normalizedAngle - 360)
  );

  // Scale: consistent size when zoomed in, depth-based when zoomed out
  let scale: number;
  if (zoomLevel < 0.1) {
    // Zoomed out: all cards small with depth
    scale = 0.5 + (depthFactor * 0.3);
  } else {
    // Zoomed in: consistent size (no scaling based on focus)
    scale = 0.8;
  }

  // Opacity based on distance from center when zoomed in
  let opacity: number;
  if (zoomLevel < 0.1) {
    // Zoomed out: all visible with depth
    opacity = 0.6 + (depthFactor * 0.4);
  } else {
    // Zoomed in: fade based on distance from center
    // Cards directly at center (distanceFromCenter = 0) are fully visible
    // Cards far from center fade out
    if (distanceFromCenter < 30) {
      opacity = 1; // Center card fully visible
    } else if (distanceFromCenter < 90) {
      opacity = 0.7; // Adjacent cards visible
    } else {
      opacity = 0; // Far cards invisible
    }
  }

  // Z-index based on focus and depth
  const zIndex = isCurrentCard ? 100 : Math.floor(depthFactor * 50);

  // Text style classes based on card style
  const getTextStyleClass = () => {
    switch (card.textStyle) {
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
    <div
      className="absolute w-[350px] h-[450px] pointer-events-auto"
      style={{
        transform: `translate(${x}px, ${y}px) rotate(0deg) scale(${scale})`,
        opacity,
        zIndex,
        transition: 'transform 0.3s ease-out, opacity 0.3s ease-out',
      }}
    >
      <div className="w-full h-full bg-slate-800/80 backdrop-blur-sm rounded-2xl shadow-2xl border-2 border-slate-700/50 p-6 flex flex-col items-center justify-center hover:bg-slate-800/90 hover:border-slate-600 transition-all">
        {/* Lottie animation */}
        {card.animation && (
          <div className="w-24 h-24 mb-4">
            <DotLottieReact
              src={card.animation}
              loop
              autoplay
            />
          </div>
        )}

        {/* Card number */}
        <div className="text-gray-500 text-sm mb-3">
          {String(card.id + 1).padStart(2, '0')}
        </div>

        {/* Heading */}
        <h3 className={`text-2xl text-center mb-3 ${card.accentColor} ${getTextStyleClass()}`}>
          {card.heading}
        </h3>

        {/* Subheading */}
        {card.subheading && (
          <p className={`text-lg text-gray-300 text-center ${getTextStyleClass()}`}>
            {card.subheading}
          </p>
        )}
      </div>
    </div>
  );
}
