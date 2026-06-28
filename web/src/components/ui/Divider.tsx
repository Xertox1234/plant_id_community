interface DividerProps {
  /** Optional centered label (e.g. "or"). When omitted, renders a single line. */
  label?: string;
}

/**
 * Horizontal divider with an optional centered label. Decorative
 * (`aria-hidden`) — it separates content visually, not semantically.
 */
export default function Divider({ label }: DividerProps) {
  if (!label) {
    return <div className="my-6 h-px bg-line" aria-hidden="true" />;
  }

  return (
    <div className="my-6 flex items-center gap-4" aria-hidden="true">
      <div className="h-px flex-1 bg-line" />
      <span className="text-xs uppercase tracking-wide text-ink-3">{label}</span>
      <div className="h-px flex-1 bg-line" />
    </div>
  );
}
