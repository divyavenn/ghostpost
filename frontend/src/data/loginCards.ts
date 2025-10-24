export type LoginCard = {
  id: number;
  heading: string;
  subheading?: string;
  animation?: string; // Path to Lottie file
  textStyle: 'bold' | 'italic' | 'underline' | 'handwritten' | 'minimal' | 'gradient';
  accentColor: string; // Tailwind color class
};

export const loginCards: LoginCard[] = [
  {
    id: 0,
    heading: 'Nobody knows you exist.',
    subheading: 'We can fix that.',
    textStyle: 'bold',
    accentColor: 'text-purple-400',
  },
  {
    id: 1,
    heading: 'Ghostposter is the future of writing.',
    animation: '/cat.lottie',
    textStyle: 'bold',
    accentColor: 'text-purple-400',
  },
  {
    id: 2,
    heading: 'We build you a bespoke langauge model',
    subheading: 'Your unique style baked in.',
    animation: '/running.lottie',
    textStyle: 'underline',
    accentColor: 'text-cyan-400',
  },
  {
    id: 3,
    heading: 'We find the people who need to know about you',
    subheading: 'And tell them your story in your voice',
    animation: '/cat.lottie',
    textStyle: 'gradient',
    accentColor: 'text-pink-400',
  },
  {
    id: 4,
    heading: 'No AI slop,',
    subheading: 'no spam.',
    animation: '/cat.lottie',
    textStyle: 'bold',
    accentColor: 'text-red-400',
  },
  {
    id: 6,
    heading: 'Just influence that scales',
    subheading: 'and the reputation you deserve.',
    animation: '/running.lottie',
    textStyle: 'minimal',
    accentColor: 'text-green-400',
  },
];

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
