/**
 * Keeps query strings and fragments out of what we send to Sentry.
 *
 * Three pages receive a single-use credential in their address
 * (`/delete-account/confirm?token=`, `/verify-email?key=`,
 * `/unsubscribe?token=`), and Sentry records page and request URLs in error
 * events, transactions, breadcrumbs and session replays. Every URL is
 * scrubbed, not just those three: a path is enough to debug with, and a list
 * of routes would miss the next page that takes a token.
 */

// A URL (absolute, or a path) followed by a query string or fragment. Text
// that only happens to contain "?" or "#" does not match.
const URL_WITH_QUERY = /((?:https?:\/\/|\/)[^\s?#"']*)[?#][^\s"']*/g;

// Span attribute keys whose whole value is a query string or fragment.
const QUERY_ONLY_KEYS = new Set(['http.query', 'http.fragment', 'url.query', 'url.fragment']);

const MAX_DEPTH = 8;

export function scrubUrlText(text: string): string {
  return text.replace(URL_WITH_QUERY, '$1');
}

function scrubDeep<T>(value: T, depth = 0): T {
  if (typeof value === 'string') {
    return scrubUrlText(value) as T;
  }
  if (depth >= MAX_DEPTH || value === null || typeof value !== 'object') {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => scrubDeep(item, depth + 1)) as T;
  }
  const scrubbed: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    if (QUERY_ONLY_KEYS.has(key) || key === 'query_string') {
      continue;
    }
    scrubbed[key] = scrubDeep(item, depth + 1);
  }
  return scrubbed as T;
}

/** The parts of a Sentry event that can hold a URL. */
export interface ScrubbableEvent {
  type?: string;
  transaction?: string;
  request?: { url?: string; query_string?: unknown; headers?: Record<string, string> };
  breadcrumbs?: unknown[];
  spans?: unknown[];
  contexts?: Record<string, unknown>;
  urls?: string[];
  exception?: unknown;
  extra?: Record<string, unknown>;
  tags?: Record<string, unknown>;
}

/** For `beforeSend`, `beforeSendTransaction` and replay events. */
export function scrubEvent<T extends ScrubbableEvent>(event: T): T {
  const scrubbed = { ...event };
  if (scrubbed.transaction) scrubbed.transaction = scrubUrlText(scrubbed.transaction);
  if (scrubbed.request) scrubbed.request = scrubDeep(scrubbed.request);
  if (scrubbed.breadcrumbs) scrubbed.breadcrumbs = scrubDeep(scrubbed.breadcrumbs);
  if (scrubbed.spans) scrubbed.spans = scrubDeep(scrubbed.spans);
  if (scrubbed.contexts) scrubbed.contexts = scrubDeep(scrubbed.contexts);
  if (scrubbed.urls) scrubbed.urls = scrubbed.urls.map(scrubUrlText);
  // An error message can quote the URL it failed on.
  if (scrubbed.exception) scrubbed.exception = scrubDeep(scrubbed.exception);
  if (scrubbed.extra) scrubbed.extra = scrubDeep(scrubbed.extra);
  if (scrubbed.tags) scrubbed.tags = scrubDeep(scrubbed.tags);
  return scrubbed;
}

/** For `beforeBreadcrumb`. */
export function scrubBreadcrumb<T extends { data?: unknown; message?: string }>(crumb: T): T {
  return scrubDeep(crumb);
}

// rrweb event types: 4 is the page meta (it holds `href`), 5 is a custom event
// (Sentry's breadcrumbs and request/navigation spans).
const REPLAY_META = 4;
const REPLAY_CUSTOM = 5;

/**
 * For the replay integration's `beforeAddRecordingEvent`. The library calls
 * it for custom events only (checked in @sentry/replay 10.73), so the meta
 * event's `href` never arrives here: sentry.ts does not record a page opened
 * with a query string or fragment for that reason. Meta events are still
 * handled in case a later version passes them.
 */
export function scrubRecordingEvent<T extends { type: number; data?: unknown }>(event: T): T {
  if (event.type !== REPLAY_META && event.type !== REPLAY_CUSTOM) {
    return event;
  }
  return { ...event, data: scrubDeep(event.data) };
}
