/**
 * LoadingSpinner Component
 *
 * Displays a centered loading spinner for lazy-loaded routes.
 * Used as fallback for React.Suspense boundaries.
 */
export default function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-line border-t-primary rounded-full animate-spin" />
        <p className="text-ink-3 font-medium">Loading...</p>
      </div>
    </div>
  );
}
