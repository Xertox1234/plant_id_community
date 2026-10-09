/**
 * Blog newsletter (todo 409) — signup, and the confirm/unsubscribe links.
 *
 * Every request goes out as JSON without cookies: the backend accepts only
 * JSON here (so no other site's form can sign addresses up), and the signed
 * token in a link is its only credential, whoever is signed in.
 */
import { API_ORIGIN } from '@/config/api';

const NEWSLETTER_BASE = `${API_ORIGIN}/api/v1/blog/newsletter`;

/** Why a signup did not go through. The backend never says whether an
 *  address is already subscribed, so neither can this. */
export type SignupFailure = 'invalid_email' | 'rate_limited' | 'error';

export class NewsletterSignupError extends Error {
  readonly reason: SignupFailure;

  constructor(reason: SignupFailure, message: string) {
    super(message);
    this.name = 'NewsletterSignupError';
    this.reason = reason;
  }
}

/** Why a confirm/unsubscribe link cannot act. */
export type NewsletterLinkFailure = 'invalid' | 'expired' | 'rate_limited' | 'error';

export class NewsletterLinkError extends Error {
  readonly reason: NewsletterLinkFailure;

  constructor(reason: NewsletterLinkFailure, message: string) {
    super(message);
    this.name = 'NewsletterLinkError';
    this.reason = reason;
  }
}

async function postJson(url: string, payload: object): Promise<Response | null> {
  try {
    return await fetch(url, {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    return null;
  }
}

/** Ask for a confirmation email. Resolves the same way for every valid
 *  address: whether one is sent is the backend's call. */
export async function subscribeToNewsletter(email: string): Promise<void> {
  const response = await postJson(`${NEWSLETTER_BASE}/`, { email });
  if (response === null) {
    throw new NewsletterSignupError('error', 'Could not reach the server.');
  }
  if (response.status === 202) return;
  if (response.status === 400) {
    throw new NewsletterSignupError('invalid_email', 'Enter a valid email address.');
  }
  if (response.status === 429) {
    throw new NewsletterSignupError('rate_limited', 'Too many attempts.');
  }
  throw new NewsletterSignupError('error', `Request failed (HTTP ${response.status})`);
}

async function postToken(path: string, token: string): Promise<boolean> {
  const response = await postJson(`${NEWSLETTER_BASE}/${path}`, { token });
  if (response === null) {
    throw new NewsletterLinkError('error', 'Could not reach the server.');
  }
  const body: unknown = await response.json().catch(() => null);
  const record = body && typeof body === 'object' ? (body as Record<string, unknown>) : null;
  if (response.ok && typeof record?.subscribed === 'boolean') return record.subscribed;
  const code = record?.code;
  if (response.status === 400 && (code === 'invalid' || code === 'expired')) {
    throw new NewsletterLinkError(code, code);
  }
  if (response.status === 429) {
    throw new NewsletterLinkError('rate_limited', 'Too many attempts.');
  }
  throw new NewsletterLinkError('error', `Request failed (HTTP ${response.status})`);
}

/** Confirm a subscription from the emailed link. Idempotent. */
export function confirmNewsletter(token: string): Promise<boolean> {
  return postToken('confirm/', token);
}

/** Unsubscribe from the link in a newsletter. Idempotent. */
export function unsubscribeNewsletter(token: string): Promise<boolean> {
  return postToken('unsubscribe/', token);
}
