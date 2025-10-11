import { DotLottieReact } from '@lottiefiles/dotlottie-react';
import growthLottie from '../assets/growth.lottie';

export function NoModelError() {
  const handleGoBack = () => {
    // Clear any stored username and go back to login
    localStorage.removeItem('username');
    window.location.href = '/';
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-950 p-6">
      <div className="text-center max-w-md">
        <div className="mb-8">
          <div className="w-[250px] h-[250px] mx-auto mb-6">
            <DotLottieReact
              src={growthLottie}
              loop
              autoplay
            />
          </div>
          <h1 className="text-3xl font-bold text-white mb-4">Great Things Await</h1>
            <p className="text-lg text-neutral-300 mb-6">
            Your custom modal hasn't been baked yet! To get started with GhostPost, email us at{' '}
            <a
              href="mailto:divya@aibread.com"
              className="text-sky-400 hover:text-sky-300 font-semibold text-lg transition"
            >
              divya@aibread.com
            </a>
            </p>
        </div>
        <button
          onClick={handleGoBack}
          className="rounded-full bg-neutral-800 px-8 py-3 text-lg font-semibold text-white transition hover:bg-neutral-700"
        >
          back
        </button>
      </div>
    </div>
  );
}
