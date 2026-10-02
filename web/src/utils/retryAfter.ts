/**
 * The two `Retry-After` helpers, in one place (todo 433). They were copied
 * between messageService / forumService and NewGroupConversationForm /
 * ThreadSummaryPanel, and the second copy of the formatter had already
 * drifted ("about 1 minutes").
 */

/**
 * Integer seconds from a `Retry-After` header, or null. Only the delta form
 * is read (the HTTP-date form is legal but the API never sends it); the
 * `headers?.get?.` guard keeps hand-rolled test responses without a
 * `Headers` object from throwing inside the error path.
 */
export function readRetryAfter(response: Response): number | null {
  const raw = response.headers?.get?.('Retry-After');
  if (!raw || !/^\d+$/.test(raw.trim())) return null;
  return Number.parseInt(raw, 10);
}

/**
 * A wait for people: whole seconds under a minute, otherwise minutes rounded
 * UP (never promise a retry sooner than the server allows), each with its
 * plural — "1 minute", "2 minutes", "45 seconds".
 */
export function describeWait(seconds: number): string {
  if (seconds < 60) return `${seconds} second${seconds === 1 ? '' : 's'}`;
  const minutes = Math.ceil(seconds / 60);
  return `${minutes} minute${minutes === 1 ? '' : 's'}`;
}
