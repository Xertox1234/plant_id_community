interface InlineErrorProps {
  message: string | null | undefined;
  className?: string;
}

/**
 * A failure shown next to the control that caused it (audit F57). Render it
 * unconditionally: a live region is only announced when its text changes
 * after it is mounted, so it stays in the DOM, visually hidden while empty.
 */
export default function InlineError({ message, className = '' }: InlineErrorProps) {
  return (
    <p
      aria-live="polite"
      aria-atomic="true"
      className={message ? `text-sm text-error break-words ${className}` : 'sr-only'}
    >
      {message}
    </p>
  );
}
