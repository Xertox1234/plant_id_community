import Button from '../ui/Button';

interface ForumErrorStateProps {
  /** The error message to display. */
  message: string;
  /** Called when the user clicks Retry — should re-run the failed fetch. */
  onRetry: () => void;
  /** Bold lead-in before the message, e.g. "Error loading categories". */
  title?: string;
}

/**
 * ForumErrorState
 *
 * A forum error panel with a working Retry affordance. Every forum page
 * previously rendered a static error box whose only recovery was a full page
 * reload (audit 2026-07-11 H18); this gives each a first-class retry.
 */
export default function ForumErrorState({
  message,
  onRetry,
  title = 'Error',
}: ForumErrorStateProps) {
  return (
    <div className="bg-error/10 border border-error/30 text-ink px-4 py-3 rounded">
      <p>
        <strong>{title}:</strong> {message}
      </p>
      <Button variant="outline" onClick={onRetry} className="mt-3 min-h-11">
        Retry
      </Button>
    </div>
  );
}
