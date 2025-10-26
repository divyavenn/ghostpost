import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { AnimatedText } from './AnimatedText';
import desktopLottie from '../assets/desktop.lottie';
import writingLottie from '../assets/writing.lottie';

interface LoadingOverlayProps {
  phase: 'scraping' | 'generating';
  statusText: string;
}

export function LoadingOverlay({ phase, statusText }: LoadingOverlayProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70">
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
