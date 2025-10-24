import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import type { LoginCard } from '../data/loginCards';

interface CardLightboxProps {
  cards: LoginCard[];
  currentIndex: number;
  onClose: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

export function CardLightbox({ cards, currentIndex, onClose, onPrevious, onNext }: CardLightboxProps) {
  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') onPrevious();
      else if (e.key === 'ArrowRight') onNext();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, onPrevious, onNext]);

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

  // Get previous, current, and next cards
  const prevIndex = (currentIndex - 1 + cards.length) % cards.length;
  const nextIndex = (currentIndex + 1) % cards.length;

  const prevCard = cards[prevIndex];
  const currentCard = cards[currentIndex];
  const nextCard = cards[nextIndex];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/70 backdrop-blur-md z-[2000] flex items-center justify-center"
        onClick={onClose}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-8 right-8 text-white text-4xl hover:text-gray-300 transition-colors z-10"
          aria-label="Close"
        >
          ×
        </button>

        {/* Card navigation */}
        <div className="flex items-center justify-center gap-8 max-w-7xl w-full px-8" onClick={(e) => e.stopPropagation()}>
          {/* Previous arrow */}
          <button
            onClick={onPrevious}
            className="text-white text-6xl hover:text-gray-300 transition-colors p-4"
            aria-label="Previous card"
          >
            ←
          </button>

          {/* Three cards */}
          <div className="flex items-center justify-center gap-6">
            {/* Previous card (smaller) */}
            <motion.div
              key={`prev-${prevIndex}`}
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 0.5, x: 0, scale: 0.85 }}
              exit={{ opacity: 0, x: -50 }}
              transition={{ duration: 0.3 }}
              className="w-[280px] h-[380px] bg-slate-800/90 backdrop-blur-sm rounded-2xl shadow-2xl border-2 border-slate-700/50 p-6 flex flex-col items-center justify-center"
            >
              {prevCard.animation && (
                <div className="w-20 h-20 mb-3">
                  <DotLottieReact src={prevCard.animation} loop autoplay />
                </div>
              )}
              <div className="text-gray-500 text-sm mb-2">{String(prevIndex + 1).padStart(2, '0')}</div>
              <h3 className={`text-xl text-center mb-2 ${prevCard.accentColor} ${getTextStyleClass(prevCard.textStyle)}`}>
                {prevCard.heading}
              </h3>
              {prevCard.subheading && (
                <p className={`text-base text-gray-300 text-center ${getTextStyleClass(prevCard.textStyle)}`}>
                  {prevCard.subheading}
                </p>
              )}
            </motion.div>

            {/* Current card (largest) */}
            <motion.div
              key={`current-${currentIndex}`}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.3 }}
              className="w-[400px] h-[520px] bg-slate-800/95 backdrop-blur-sm rounded-2xl shadow-2xl border-2 border-slate-600/50 p-8 flex flex-col items-center justify-center"
            >
              {currentCard.animation && (
                <div className="w-32 h-32 mb-6">
                  <DotLottieReact src={currentCard.animation} loop autoplay />
                </div>
              )}
              <div className="text-gray-400 text-sm mb-4">{String(currentIndex + 1).padStart(2, '0')}</div>
              <h3 className={`text-3xl text-center mb-4 ${currentCard.accentColor} ${getTextStyleClass(currentCard.textStyle)}`}>
                {currentCard.heading}
              </h3>
              {currentCard.subheading && (
                <p className={`text-xl text-gray-300 text-center ${getTextStyleClass(currentCard.textStyle)}`}>
                  {currentCard.subheading}
                </p>
              )}
            </motion.div>

            {/* Next card (smaller) */}
            <motion.div
              key={`next-${nextIndex}`}
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 0.5, x: 0, scale: 0.85 }}
              exit={{ opacity: 0, x: 50 }}
              transition={{ duration: 0.3 }}
              className="w-[280px] h-[380px] bg-slate-800/90 backdrop-blur-sm rounded-2xl shadow-2xl border-2 border-slate-700/50 p-6 flex flex-col items-center justify-center"
            >
              {nextCard.animation && (
                <div className="w-20 h-20 mb-3">
                  <DotLottieReact src={nextCard.animation} loop autoplay />
                </div>
              )}
              <div className="text-gray-500 text-sm mb-2">{String(nextIndex + 1).padStart(2, '0')}</div>
              <h3 className={`text-xl text-center mb-2 ${nextCard.accentColor} ${getTextStyleClass(nextCard.textStyle)}`}>
                {nextCard.heading}
              </h3>
              {nextCard.subheading && (
                <p className={`text-base text-gray-300 text-center ${getTextStyleClass(nextCard.textStyle)}`}>
                  {nextCard.subheading}
                </p>
              )}
            </motion.div>
          </div>

          {/* Next arrow */}
          <button
            onClick={onNext}
            className="text-white text-6xl hover:text-gray-300 transition-colors p-4"
            aria-label="Next card"
          >
            →
          </button>
        </div>

        {/* Card counter */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-white text-sm">
          {currentIndex + 1} / {cards.length}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
