import type { ComponentType } from 'react';

/**
 * LoginCard type definition
 *
 * Display strategy:
 * - Wheel view: Always shows `image` (required) - small preview PNG
 * - Lightbox view: Shows `ComponentType` (full interactive component) OR `lightboxImage` (full-size image)
 *
 * Priority for lightbox:
 * 1. ComponentType - React component (e.g., Poster components)
 * 2. lightboxImage - Full-size image for lightbox
 * 3. Falls back to `image` if neither provided
 */
export type LoginCard = {
  id: number;
  heading: string;
  subheading?: string;
  image: string; // REQUIRED: PNG preview for wheel view
  lightboxImage?: string; // Optional: Full-size image for lightbox (if no ComponentType)
  component?: ComponentType; // Optional: React component for lightbox (highest priority)
  textStyle: 'bold' | 'italic' | 'underline' | 'handwritten' | 'minimal' | 'gradient';
  accentColor: string; // Tailwind color class
};

// Import Poster components
import PosterOne from './PosterOne';
import PosterTwo from './PosterTwo';
import PosterThree from './PosterThree';
import PosterFour from './PosterFour';
import PosterFive from './PosterFive';

// Import PNG preview images
import posterOneImg from './poster-1-preview.png';
import posterTwoImg from './poster-2-preview.png';
import posterThreeImg from './poster-3-preview.png';
import posterFourImg from './poster-4-preview.png';
import posterFiveImg from './poster-5-preview.png';

export const loginCards: LoginCard[] = [
  {
    id: 0,
    heading: 'Ghostposter is the future of writing.',
    image: posterOneImg, // Preview PNG for wheel
    component: PosterOne, // Full interactive component for lightbox
    textStyle: 'bold',
    accentColor: 'text-purple-400',
  },
  {
    id: 1,
    heading: 'We build you a bespoke language model',
    subheading: 'Your unique style baked in.',
    image: posterTwoImg, // Preview PNG for wheel
    component: PosterTwo,
    textStyle: 'underline',
    accentColor: 'text-cyan-400',
  },
  {
    id: 2,
    heading: 'We find the people who need to know about you',
    subheading: 'And tell them your story in your voice',
    image: posterThreeImg, // Preview PNG for wheel
    component: PosterThree,
    textStyle: 'gradient',
    accentColor: 'text-pink-400',
  },
  {
    id: 3,
    heading: 'No AI slop, no spam.',
    image: posterFourImg, // Preview PNG for wheel
    component: PosterFour,
    textStyle: 'bold',
    accentColor: 'text-red-400',
  },
  {
    id: 4,
    heading: 'Just influence that scales',
    subheading: 'and the reputation you deserve.',
    image: posterFiveImg, // Preview PNG for wheel
    component: PosterFive,
    textStyle: 'minimal',
    accentColor: 'text-green-400',
  },
];
