import { useEffect, useState } from 'react';
import type { ComponentType } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Navigation, Keyboard, EffectCards } from 'swiper/modules';
import type { LoginCard } from '../data/loginCards';
import type { Swiper as SwiperType } from 'swiper';

// Import Swiper styles
import 'swiper/css';
import 'swiper/css/navigation';
import 'swiper/css/effect-cards';

interface CardLightboxProps {
  cards: LoginCard[];
  currentIndex: number;
  onClose: () => void;
}

export function CardLightbox({ cards, currentIndex, onClose }: CardLightboxProps) {
  const [activeIndex, setActiveIndex] = useState(currentIndex);

  // Keyboard navigation for ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

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

        {/* Swiper carousel */}
        <div className="max-w-2xl w-full mx-auto flex items-center justify-center h-[600px]" onClick={(e) => e.stopPropagation()}>
          <Swiper
            modules={[Navigation, Keyboard, EffectCards]}
            effect="cards"
            grabCursor={true}
            loop={true}
            initialSlide={currentIndex}
            onSlideChange={(swiper) => setActiveIndex(swiper.realIndex)}
            cardsEffect={{
              perSlideOffset: 8,
              perSlideRotate: 2,
              rotate: true,
              slideShadows: true,
            }}
            style={{
              width: '450px',
              height: '550px',
            }}
            keyboard={{
              enabled: true,
              onlyInViewport: true,
            }}
            navigation={{
              prevEl: '.swiper-button-prev-custom',
              nextEl: '.swiper-button-next-custom',
            }}
            className="!pb-0"
          >
            {cards.map((card, index) => (
              <SwiperSlide key={card.id} className="!rounded-2xl !overflow-hidden">
                <div className="w-full h-full">
                  {card.component ? (
                    // Render full component (Poster) for lightbox
                    (() => {
                      const Component = card.component as ComponentType;
                      const isActive = index === activeIndex;
                      return (
                        <div key={isActive ? `active-${card.id}` : `inactive-${card.id}`} className="w-full h-full">
                          <Component />
                        </div>
                      );
                    })()
                  ) : card.image ? (
                    // Render full-size lightbox image
                    <img
                      src={card.image}
                      alt={card.heading}
                      className="w-full h-full object-contain bg-slate-900"
                    />
                  ) : (
                    // Fallback: render preview image
                    <img
                      src={card.image}
                      alt={card.heading}
                      className="w-full h-full object-cover"
                    />
                  )}
                </div>
              </SwiperSlide>
            ))}
          </Swiper>

          {/* Custom navigation buttons */}
          <button
            className="swiper-button-prev-custom absolute left-4 top-1/2 -translate-y-1/2 text-white text-6xl hover:text-gray-300 transition-colors p-4 z-10"
            aria-label="Previous card"
          >
            ←
          </button>
          <button
            className="swiper-button-next-custom absolute right-4 top-1/2 -translate-y-1/2 text-white text-6xl hover:text-gray-300 transition-colors p-4 z-10"
            aria-label="Next card"
          >
            →
          </button>
        </div>

        {/* Card counter */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-white text-sm">
          {activeIndex + 1} / {cards.length}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
