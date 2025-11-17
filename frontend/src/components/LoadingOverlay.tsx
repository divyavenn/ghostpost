import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import { useRecoilValue } from 'recoil';
import { AnimatedText } from './AnimatedText';
import { loadingPhaseState, loadingStatusDataState } from '../atoms';
import desktopLottie from '../assets/desktop.lottie';
import writingLottie from '../assets/writing.lottie';

export function LoadingOverlay() {
  const phase = useRecoilValue(loadingPhaseState);
  const statusData = useRecoilValue(loadingStatusDataState);

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
