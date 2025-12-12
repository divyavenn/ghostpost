import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { AnimatedText } from './WordStyles';
import desktopLottie from '../assets/desktop.lottie';
import writingLottie from '../assets/writing.lottie';

interface LoadingOverlayProps {
  phase: 'scraping' | 'generating' | null;
  statusData: {
    type: 'account' | 'query' | 'generating' | 'complete' | 'idle' | 'home_timeline' | 'discovering' | 'scraping' | 'error';
    value: string;
    summary?: string;
  } | null;
  onDismiss?: () => void;
}

export function LoadingOverlay({ phase, statusData, onDismiss }: LoadingOverlayProps) {
  // Don't render if no loading phase
  if (!phase) return null;

  // Derive status text from phase and status data
  const getStatusText = (): string => {
    if (!statusData) {
      return phase === 'scraping' ? 'Scraping tweets' : 'Generating replies';
    }

    switch (statusData.type) {
      case 'account':
        return `Scraping tweets from @${statusData.value}`;
      case 'query':
        // Use summary if available, otherwise fall back to full query
        const displayText = statusData.summary || statusData.value;
        return `Scraping tweets related to "${displayText}"`;
      case 'generating':
        return `Generating replies${statusData.value ? ` (${statusData.value})` : ''}`;
      case 'complete':
        return 'Done!';
      default:
        return phase === 'scraping' ? 'Scraping tweets' : 'Generating replies';
    }
  };

  const statusText = getStatusText();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70">
      {/* X button to dismiss overlay */}
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="absolute top-6 right-6 text-white/60 hover:text-white transition-colors z-50"
          aria-label="Dismiss loading overlay"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-8 w-8"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
      <div className="flex flex-col items-center gap-6">
        <div className={phase === 'scraping' ? 'mt-[-230px] w-[700px] h-[700px]' : 'w-[250px] h-[250px]'}>
          <DotLottieReact
            src={phase === 'scraping' ? desktopLottie : writingLottie}
            loop
            autoplay
          />
        </div>
        <AnimatedText
          text={statusText}
          className={phase === 'scraping' ? "text-white text-xl mt-[-150px] text-center" : "text-white text-xl text-center"}
        />
      </div>
    </div>
  );
}
