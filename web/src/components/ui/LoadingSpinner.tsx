interface LoadingSpinnerProps {
  /** Status text under the spinner. Defaults to "Loading...". */
  label?: string;
  /** Outer-wrapper sizing/spacing classes. Defaults to "min-h-[50vh]". */
  className?: string;
}

/**
 * LoadingSpinner Component
 *
 * Displays a centered loading spinner for lazy-loaded routes.
 * Used as fallback for React.Suspense boundaries.
 */
export default function LoadingSpinner({
  label = 'Loading...',
  className = 'min-h-[50vh]',
}: LoadingSpinnerProps = {}) {
  return (
    <div
      className={`flex items-center justify-center ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-line border-t-primary rounded-full animate-spin" />
        <p className="text-ink-3 font-medium">{label}</p>
      </div>
    </div>
  );
}
