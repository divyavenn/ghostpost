import { useEffect, useState } from 'react';

export interface ScrollProgress {
  scrollY: number;
  scrollProgress: number; // 0 to 1 representing total scroll progress
  rotationDegrees: number; // Total rotation in degrees
  zoomLevel: number; // 0 = zoomed out (initial view), 1 = zoomed into cards, 0 = zoomed out again (loop)
  cardIndex: number; // Which card is currently focused when zoomed in
  phase: 'intro' | 'zooming-in' | 'rotating' | 'zooming-out'; // Current phase of scroll
  shouldAdvanceCard: boolean; // Trigger to advance to next card
}

/**
 * Hook to track scroll progress and calculate card rotation/zoom state
 * Handles: intro -> zoom in -> rotate through cards -> zoom out -> loop
 * @param totalCards - Total number of cards in the circle (for rendering)
 * @param cardsToShow - Number of unique cards to scroll through (default 6)
 */
export function useScrollProgress(totalCards: number = 50, cardsToShow: number = 6): ScrollProgress {
  const [scrollState, setScrollState] = useState<ScrollProgress>({
    scrollY: 0,
    scrollProgress: 0,
    rotationDegrees: 0,
    zoomLevel: 0,
    cardIndex: 0,
    phase: 'intro',
    shouldAdvanceCard: false,
  });

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY;
      const windowHeight = window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight;
      const maxScroll = documentHeight - windowHeight;

      // Calculate scroll progress (0 to 1)
      const scrollProgress = maxScroll > 0 ? scrollY / maxScroll : 0;

      // Define scroll phases (in viewport heights)
      const zoomInEnd = windowHeight * 1; // Zoom in takes 1 viewport
      const rotationStart = zoomInEnd;
      const rotationEnd = rotationStart + (windowHeight * cardsToShow * 0.8); // 0.8vh per card to show
      const zoomOutEnd = rotationEnd + windowHeight * 1; // Zoom out takes 1 viewport

      let phase: 'intro' | 'zooming-in' | 'rotating' | 'zooming-out' = 'intro';
      let zoomLevel = 0;
      let rotationDegrees = 0;
      let cardIndex = 0;

      if (scrollY < zoomInEnd) {
        // Phase 1: Zooming in
        phase = 'zooming-in';
        zoomLevel = scrollY / zoomInEnd; // 0 to 1
        rotationDegrees = 0;
        cardIndex = 0;
      } else if (scrollY < rotationEnd) {
        // Phase 2: Rotating through cards (zoomed in)
        phase = 'rotating';
        zoomLevel = 1;
        const rotationScrollDistance = scrollY - rotationStart;
        const pixelsPerCard = windowHeight * 0.8;
        const degreesPerCard = 360 / totalCards;

        cardIndex = Math.min(Math.floor(rotationScrollDistance / pixelsPerCard), cardsToShow - 1);

        // Rotate the wheel so the current card is always at the top (12 o'clock = -90 degrees)
        // We want card 0 at top initially, so subtract (cardIndex * degreesPerCard)
        rotationDegrees = -(cardIndex * degreesPerCard);
      } else if (scrollY < zoomOutEnd) {
        // Phase 3: Zooming out - back to original view
        phase = 'zooming-out';
        const zoomOutProgress = (scrollY - rotationEnd) / windowHeight;
        zoomLevel = 1 - zoomOutProgress; // 1 to 0

        // Keep the last card rotation during zoom out
        const degreesPerCard = 360 / totalCards;
        rotationDegrees = -((cardsToShow - 1) * degreesPerCard);
        cardIndex = cardsToShow - 1;
      } else {
        // Phase 4: Back to intro (looped)
        phase = 'intro';
        zoomLevel = 0;
        rotationDegrees = 0;
        cardIndex = 0;
      }

      setScrollState({
        scrollY,
        scrollProgress,
        rotationDegrees,
        zoomLevel,
        cardIndex: Math.min(cardIndex, cardsToShow - 1),
        phase,
        shouldAdvanceCard: false,
      });
    };

    // Initial call
    handleScroll();

    // Add scroll listener
    window.addEventListener('scroll', handleScroll, { passive: true });

    return () => window.removeEventListener('scroll', handleScroll);
  }, [totalCards, cardsToShow]);

  return scrollState;
}
