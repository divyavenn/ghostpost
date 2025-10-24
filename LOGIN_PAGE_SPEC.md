# Frontend Spec: Fix Scroll Behavior for Card Circle Rotation

## Problem
The current implementation scrolls down the page normally instead of rotating the card circle. The cards remain static and don't respond to scroll input.

---

## Root Cause Analysis

### Current Issues:
1. **No sticky positioning working**: The card circle container needs to be `position: fixed` or use proper sticky positioning to stay in viewport
2. **Scroll spacer not effective**: The tall spacer div allows scrolling but doesn't trigger visual updates
3. **Transform not applying**: The rotation offset isn't being properly applied to card transforms
4. **Missing scroll-to-rotate mapping**: The visual feedback loop between scroll and rotation isn't connected

---

## Updated Implementation Steps

### Step 1: Fix the Scroll Hook - Add Proper Scroll Tracking
**File:** `frontend/src/hooks/useScrollProgress.ts`

**Replace entire file with:**
```typescript
import { useEffect, useState } from 'react';

interface ScrollProgress {
  scrollY: number;
  scrollProgress: number; // 0 to 1 representing total scroll progress
  rotationDegrees: number; // Total rotation in degrees
}

export function useScrollProgress(totalScrollHeight: number = 5000): ScrollProgress {
  const [scrollState, setScrollState] = useState<ScrollProgress>({
    scrollY: 0,
    scrollProgress: 0,
    rotationDegrees: 0,
  });

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY;
      const windowHeight = window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight;
      const maxScroll = documentHeight - windowHeight;

      // Calculate scroll progress (0 to 1)
      const scrollProgress = maxScroll > 0 ? scrollY / maxScroll : 0;

      // Map scroll to rotation: 1 full rotation per 500px of scroll
      const pixelsPerRotation = 500;
      const rotationDegrees = (scrollY / pixelsPerRotation) * 360;

      setScrollState({
        scrollY,
        scrollProgress,
        rotationDegrees,
      });
    };

    // Initial call
    handleScroll();

    // Add scroll listener
    window.addEventListener('scroll', handleScroll, { passive: true });

    return () => window.removeEventListener('scroll', handleScroll);
  }, [totalScrollHeight]);

  return scrollState;
}
```

---

### Step 2: Fix Login Page Container Structure
**File:** `frontend/src/pages/Login.tsx`

**Key changes needed:**
1. Make the card circle container `fixed` so it stays in viewport
2. Ensure the spacer div exists to enable scrolling
3. Properly pass rotation to cards
4. Remove conflicting positioning

**Replace the return statement section (starting from line 160):**

```typescript
return (
  <Background className="relative">
    {/* Error Message */}
    {error && (
      <div className="fixed top-8 left-1/2 -translate-x-1/2 z-50 bg-red-500/90 backdrop-blur-sm text-white px-6 py-3 rounded-lg font-semibold max-w-md text-center">
        {error}
      </div>
    )}

    {/* FIXED Card Circle Container - Stays in viewport */}
    <div className="fixed inset-0 flex items-center justify-center pointer-events-none">
      {/* Rotating Circle of Cards */}
      <div className="relative w-full h-full flex items-center justify-center">
        {fullCircleCards.map((card, index) => {
          const baseAngle = (index / fullCircleCards.length) * 360;
          return (
            <FeatureCard
              key={card.id}
              card={card}
              angle={baseAngle}
              rotationOffset={rotationDegrees} // Apply current rotation
            />
          );
        })}
      </div>

      {/* Center Content Overlay */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 flex flex-col items-center text-center max-w-xl px-8 pointer-events-auto">
        {/* Logo */}
        <img
          src="/ghostposter_logo.png"
          alt="GhostPoster"
          className="h-24 w-auto object-contain mb-8 animate-flicker"
        />

        {/* Description */}
        <p className="text-xl text-gray-300 mb-8 font-light italic">
          GhostPoster builds you a bespoke language model and helps you
          find people who would love your brand—in your voice.
        </p>

        {/* Login Button - Always Centered */}
        <button
          onClick={handleLogin}
          className="rounded-full bg-sky-500 px-10 py-4 text-xl font-semibold text-white transition-all hover:bg-sky-600 hover:scale-105 shadow-2xl"
        >
          Login with Twitter
        </button>

        {/* Scroll Indicator */}
        <div className="mt-12 text-gray-500 text-sm animate-bounce">
          ↓ Scroll to explore ↓
        </div>
      </div>
    </div>

    {/* Invisible Spacer - Enables Scrolling */}
    <div
      className="relative"
      style={{ height: '5000vh' }}
      aria-hidden="true"
    />

    {/* Bottom CTA - Fixed Position */}
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 text-center z-10 pointer-events-none">
      <p className="text-gray-400 text-base">Ready to be seen?</p>
      <div className="mt-2 text-gray-600 text-xs">
        Scroll: {Math.round(scrollProgress * 100)}% | Rotation: {Math.round(rotationDegrees)}°
      </div>
    </div>

    <style>{`
      @keyframes flicker {
        0%, 100% { opacity: 1; }
        2% { opacity: 0.8; }
        4% { opacity: 1; }
        8% { opacity: 0.9; }
        10% { opacity: 1; }
        12% { opacity: 0.7; }
        14% { opacity: 1; }
        18% { opacity: 0.95; }
        20% { opacity: 1; }
        70% { opacity: 1; }
        72% { opacity: 0.85; }
        74% { opacity: 1; }
        76% { opacity: 0.9; }
        78% { opacity: 1; }
      }

      .animate-flicker {
        animation: flicker 4s infinite;
      }
    `}</style>
  </Background>
);
```

---

### Step 3: Fix FeatureCard Component Transform
**File:** `frontend/src/components/FeatureCard.tsx`

**Update the component to properly apply rotation:**

```typescript
import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import type { LoginCard } from '../data/loginCards';

interface FeatureCardProps {
  card: LoginCard;
  angle: number; // Base angle position in circle (0-360)
  rotationOffset: number; // Current rotation from scroll
}

export function FeatureCard({ card, angle, rotationOffset }: FeatureCardProps) {
  // Large radius for prominent circle
  const radius = 600;

  // Calculate final angle with rotation offset
  const finalAngle = angle + rotationOffset;
  const angleRad = (finalAngle * Math.PI) / 180;

  // Calculate position
  const x = Math.cos(angleRad) * radius;
  const y = Math.sin(angleRad) * radius;

  // Calculate depth (cards at top are "closer", bottom are "farther")
  // sin(angle) gives us -1 to 1, we convert to 0 to 1
  const depthFactor = (Math.sin(angleRad) + 1) / 2;

  // Scale based on depth (0.7 to 1.0)
  const scale = 0.7 + (depthFactor * 0.3);

  // Opacity based on depth (0.5 to 1.0)
  const opacity = 0.5 + (depthFactor * 0.5);

  // Z-index based on depth
  const zIndex = Math.floor(depthFactor * 100);

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
      className="absolute w-[180px] h-[240px] pointer-events-auto"
      style={{
        transform: `translate(${x}px, ${y}px) rotate(${finalAngle + 90}deg) scale(${scale})`,
        opacity,
        zIndex,
        transition: 'transform 0.1s linear, opacity 0.1s linear',
      }}
    >
      <div className="w-full h-full bg-slate-800/80 backdrop-blur-sm rounded-xl shadow-2xl border-2 border-slate-700/50 p-4 flex flex-col items-center justify-center hover:bg-slate-800/90 hover:border-slate-600 transition-all">
        {/* Lottie animation */}
        {card.animation && (
          <div className="w-16 h-16 mb-2">
            <DotLottieReact
              src={card.animation}
              loop
              autoplay
            />
          </div>
        )}

        {/* Card number */}
        <div className="text-gray-500 text-xs mb-2">
          {String(card.id).padStart(2, '0')}
        </div>

        {/* Heading */}
        <h3 className={`text-sm text-center mb-1 ${card.accentColor} ${getTextStyleClass()}`}>
          {card.heading}
        </h3>

        {/* Subheading */}
        <p className={`text-xs text-gray-300 text-center ${getTextStyleClass()}`}>
          {card.subheading}
        </p>
      </div>
    </div>
  );
}
```

---

### Step 4: Update Login Page Imports
**File:** `frontend/src/pages/Login.tsx`

**Update the imports section:**
```typescript
import { Background } from '../components/Background';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { LoginLoading } from '../components/LoginLoading';
import { FeatureCard } from '../components/FeatureCard';
import { loginCards, createFullCardCircle } from '../data/loginCards';
import { useScrollProgress } from '../hooks/useScrollProgress';

// Create the full circle of cards (50 cards by duplicating the 6 base cards)
const fullCircleCards = createFullCardCircle(loginCards, 50);
```

**Update the hook usage:**
```typescript
export function Login() {
  const navigate = useNavigate();
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { scrollY, scrollProgress, rotationDegrees } = useScrollProgress();

  // ... rest of component
```

---

### Step 5: Add Card Duplication Function
**File:** `frontend/src/data/loginCards.ts`

**Add this function at the end of the file:**

```typescript
/**
 * Create a full circle of cards by duplicating the base cards
 * @param baseCards - The original 6 cards
 * @param totalCards - Total number of cards to create (default 50)
 */
export const createFullCardCircle = (baseCards: LoginCard[], totalCards: number = 50): LoginCard[] => {
  const fullCircle: LoginCard[] = [];
  let id = 1;

  while (fullCircle.length < totalCards) {
    for (const card of baseCards) {
      if (fullCircle.length >= totalCards) break;
      fullCircle.push({
        ...card,
        id: id++, // Unique ID for each duplicated card
      });
    }
  }

  return fullCircle;
};
```

---

## Summary of Key Fixes

### What Was Wrong:
1. ❌ Cards were positioned in a normal flow container that scrolled with the page
2. ❌ No connection between scroll position and card rotation
3. ❌ `rotationOffset` prop wasn't defined in the original implementation
4. ❌ Cards were in a relative container instead of fixed

### What's Fixed:
1. ✅ **Fixed positioning**: Card circle stays in viewport while page scrolls
2. ✅ **Scroll tracking**: Hook properly calculates rotation degrees from scroll position
3. ✅ **Transform application**: Cards receive and apply `rotationOffset` prop
4. ✅ **Pointer events**: Center content is interactive, cards can be too
5. ✅ **Visual feedback**: Debug info shows scroll progress and rotation
6. ✅ **Depth perception**: Cards scale and fade based on position in circle
7. ✅ **Smooth transitions**: Using `linear` transitions for smooth rotation

---

## Testing Checklist

- [ ] Scroll down the page and verify cards rotate clockwise
- [ ] Verify cards at the top are larger/more opaque than cards at bottom
- [ ] Confirm login button stays centered and is clickable
- [ ] Check that scroll indicator is visible and animating
- [ ] Test on different viewport sizes (mobile, tablet, desktop)
- [ ] Verify debug info at bottom shows changing values when scrolling
- [ ] Confirm 50 cards are rendering (check in React DevTools)
- [ ] Test scroll performance (should be smooth, no jank)

---

## Tuning Parameters

After implementation, you can adjust these values for desired effect:

```typescript
// In useScrollProgress.ts
const pixelsPerRotation = 500; // Lower = faster rotation, Higher = slower

// In FeatureCard.tsx
const radius = 600; // Larger = bigger circle, Smaller = tighter circle
const scale = 0.7 + (depthFactor * 0.3); // Adjust scale range
const opacity = 0.5 + (depthFactor * 0.5); // Adjust fade range

// In Login.tsx
style={{ height: '5000vh' }} // More = longer scrolling, Less = shorter
```

---

## Expected Behavior After Fix

1. **Initial load**: See 50 cards arranged in a large circle, login button centered. if there are fewer than 50 cards in the list, repeat them visually to fill up the space.
2. **Scroll down**: You zoom into the cards. As you scroll, the cards rotate and the next card comes on top, upright, while the previous one tilts off to the side as it rotates down the wheel. The login button is now on the top right. 
3. **Continuous scroll**: Smooth rotation without jumps or stutters
5. Once you scroll past all cards, the card wheel zooms out again and you see the original view (logo + login button in middle)

---

## Visual Reference

### Whispers Game (Target Inspiration)
- Large circle of 50+ artistic cards
- Cards arranged in perfect circle
- Continuous rotation on scroll
- Center remains empty with text overlay
- Cards have depth perception (closer = larger/brighter)

### Current GhostPoster Implementation
- 6 unique feature cards with GhostPoster messaging
- Each card has Lottie animation
- Different text styles (bold, italic, underline, gradient, etc.)
- Accent colors for visual variety

### Final Result Should Be
- 50 cards (6 cards repeated ~8 times) in large circle
- Smooth clockwise rotation on scroll
- Login button and logo centered and always visible
- Cards show depth with scale/opacity changes
- Maintains all existing login functionality
