import { AnimatedText } from './WordStyles';

interface BackgroundActionButtonProps {
  onClick: () => void;
  isLoading: boolean;
  label: string;
  loadingLabel: string;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
  className?: string;
}

export function BackgroundActionButton({
  onClick,
  isLoading,
  label,
  loadingLabel,
  variant = 'primary',
  disabled = false,
  className = '',
}: BackgroundActionButtonProps) {
  const baseClasses = 'rounded-full px-5 py-2.5 text-base font-bold transition';

  const variantClasses = {
    primary: isLoading
      ? 'bg-slate-900 border-2 border-blue-500 cursor-not-allowed'
      : 'bg-blue-600 text-white hover:bg-blue-700',
    secondary: isLoading
      ? 'bg-slate-900 border-2 border-sky-400 cursor-not-allowed'
      : 'bg-neutral-800 text-white hover:bg-neutral-700 border-2 border-transparent',
  };

  return (
    <button
      onClick={onClick}
      disabled={isLoading || disabled}
      className={`${baseClasses} ${variantClasses[variant]} ${className}`}
      aria-label={isLoading ? loadingLabel : label}
      title={isLoading ? loadingLabel : label}
    >
      {isLoading ? (
        <AnimatedText text={loadingLabel} />
      ) : (
        label
      )}
    </button>
  );
}
