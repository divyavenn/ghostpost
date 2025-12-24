import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { api, type JobStatus } from '../api/client';
import { AnimatedText } from './WordStyles';

interface LocalProgress {
  current: number;
  total: number;
  /** Optional custom display text, defaults to "current/total" */
  displayText?: string;
}

interface JobProgressButtonProps {
  username: string;
  /** Job names to monitor (e.g., ['find_and_reply_to_new_posts']) */
  jobNames: string[];
  onClick: () => void;
  label: string;
  /** Label to show when the job is running (e.g., 'finding new posts') */
  loadingLabel: string;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
  className?: string;
  /** Polling interval in ms (default: 500) */
  pollInterval?: number;
  /** Local progress override - when provided, skips backend polling */
  localProgress?: LocalProgress | null;
}

export function JobProgressButton({
  username,
  jobNames,
  onClick,
  label,
  loadingLabel,
  variant = 'primary',
  disabled = false,
  className = '',
  pollInterval = 500,
  localProgress = null,
}: JobProgressButtonProps) {
  const [jobStatuses, setJobStatuses] = useState<Record<string, JobStatus>>({});
  const [_isPolling, setIsPolling] = useState(false);
  const [localLoading, setLocalLoading] = useState(false); // True immediately after click

  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  // Get the currently active job (running or most recently completed)
  const getActiveJob = useCallback((): { name: string; status: JobStatus } | null => {
    // First, check for any running job
    for (const jobName of jobNames) {
      const status = jobStatuses[jobName];
      if (status?.status === 'running') {
        return { name: jobName, status };
      }
    }
    return null;
  }, [jobNames, jobStatuses]);

  const activeJob = getActiveJob();
  // Check if we're using local progress mode
  const isLocalProgress = localProgress !== null;
  // Show as running if we have local progress, an active job, OR if we just clicked (localLoading)
  const isRunning = isLocalProgress || activeJob !== null || localLoading;

  // Get display text for the button using simplified format
  const getDisplayText = (): string => {
    // Local progress takes priority
    if (isLocalProgress) {
      return localProgress.displayText ?? `${localProgress.current}/${localProgress.total}`;
    }

    if (!activeJob) return label;

    const { status } = activeJob;
    const { phase, details } = status;

    // Build display text from phase + details
    if (phase && phase !== 'starting' && phase !== 'idle') {
      if (details) {
        return `${phase} ${details}`;
      }
      return phase;
    }

    return loadingLabel;
  };

  // Get progress percentage from active job or local progress
  const getProgress = (): number => {
    // Local progress takes priority
    if (isLocalProgress) {
      return localProgress.total > 0
        ? (localProgress.current / localProgress.total) * 100
        : 0;
    }

    if (!activeJob) return 0;
    return activeJob.status.percentage || 0;
  };

  // Poll job status
  const pollJobStatus = useCallback(async () => {
    if (!mountedRef.current || !username || username.trim() === '') return;

    try {
      const allStatus = await api.getJobsStatus(username);
      if (!mountedRef.current) return;

      const newStatuses: Record<string, JobStatus> = {};
      for (const jobName of jobNames) {
        const jobKey = jobName as keyof typeof allStatus.jobs;
        if (allStatus.jobs[jobKey]) {
          newStatuses[jobName] = allStatus.jobs[jobKey];
        }
      }
      setJobStatuses(newStatuses);

      // Check if any job is still running
      const stillRunning = Object.values(newStatuses).some(
        (s) => s.status === 'running'
      );

      if (stillRunning) {
        // We have a real running job, clear local loading
        setLocalLoading(false);
        // Continue polling
        pollTimeoutRef.current = setTimeout(pollJobStatus, pollInterval);
      } else {
        // No jobs running, clear all loading states
        setLocalLoading(false);
        setIsPolling(false);
      }
    } catch (error) {
      console.error('Failed to poll job status:', error);
      // Stop polling on error
      setLocalLoading(false);
      setIsPolling(false);
    }
  }, [username, jobNames, pollInterval]);

  // Start polling when button is clicked (unless using local progress)
  const handleClick = () => {
    onClick();
    // When using local progress, the parent controls the loading state
    if (isLocalProgress) return;

    // Show loading state immediately
    setLocalLoading(true);
    // Start polling after a short delay to let the job start
    if (username && username.trim() !== '') {
      setIsPolling(true);
      setTimeout(() => {
        pollJobStatus();
      }, 300); // Slightly longer delay to let job register
    }
  };

  // Initial status check on mount - only runs once per username
  const hasCheckedInitialRef = useRef(false);

  useEffect(() => {
    if (!username || username.trim() === '' || hasCheckedInitialRef.current) return;

    hasCheckedInitialRef.current = true;

    const checkInitialStatus = async () => {
      try {
        const allStatus = await api.getJobsStatus(username);
        if (!mountedRef.current) return;

        const newStatuses: Record<string, JobStatus> = {};
        for (const jobName of jobNames) {
          const jobKey = jobName as keyof typeof allStatus.jobs;
          if (allStatus.jobs[jobKey]) {
            newStatuses[jobName] = allStatus.jobs[jobKey];
          }
        }
        setJobStatuses(newStatuses);

        // If any job is running, start polling
        const anyRunning = Object.values(newStatuses).some(
          (s) => s.status === 'running'
        );
        if (anyRunning) {
          setIsPolling(true);
          pollTimeoutRef.current = setTimeout(pollJobStatus, pollInterval);
        }
      } catch (error) {
        console.error('Failed to check initial job status:', error);
      }
    };

    checkInitialStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username]); // Only re-run when username changes

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, []);

  const baseClasses = 'relative overflow-hidden rounded-full px-5 py-2.5 text-base font-bold transition';

  const variantClasses = {
    primary: isRunning
      ? 'bg-slate-900 border-2 border-blue-500 cursor-not-allowed'
      : 'bg-blue-600 text-white hover:bg-blue-700',
    secondary: isRunning
      ? 'bg-slate-900 border-2 border-sky-400 cursor-not-allowed'
      : 'bg-neutral-800 text-white hover:bg-neutral-700 border-2 border-transparent',
  };

  const progressColor = variant === 'primary' ? 'bg-blue-600' : 'bg-sky-500';
  const progress = getProgress();

  return (
    <button
      onClick={handleClick}
      disabled={isRunning || disabled}
      className={`${baseClasses} ${variantClasses[variant]} ${className}`}
      aria-label={isRunning ? getDisplayText() : label}
      title={isRunning ? `${getDisplayText()} (${Math.round(progress)}%)` : label}
    >
      {/* Progress bar - animated smoothly via framer-motion spring */}
      {isRunning && (
        <motion.div
          className={`absolute inset-0 ${progressColor} opacity-80`}
          initial={{ width: '0%' }}
          animate={{ width: `${progress}%` }}
          transition={{
            type: 'spring',
            stiffness: 50,
            damping: 15,
            mass: 0.5,
          }}
        />
      )}

      {/* Button text */}
      <span className="relative z-10">
        {isRunning ? (
          <AnimatedText text={getDisplayText()} />
        ) : (
          label
        )}
      </span>
    </button>
  );
}

export default JobProgressButton;
