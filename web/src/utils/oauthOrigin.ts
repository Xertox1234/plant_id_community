/**
 * Where a Google sign-in redirect may go (todo 706, audit 2026-11-10 L10).
 *
 * The backend builds `oauth_url` on https://accounts.google.com
 * (`backend/apps/users/oauth_views.py`), and the web app hands it straight to
 * `window.location.assign`. A server bug or a tampered response must not turn
 * that into a redirect anywhere else, so the URL is followed only when its
 * origin is exactly Google's. Never a prefix test:
 * `https://accounts.google.com.evil.com` and
 * `https://accounts.google.com@evil.com` both start with the right text.
 */
export const GOOGLE_OAUTH_ORIGIN = 'https://accounts.google.com';

/** The URL's origin, or null when it is not an absolute URL. */
export function urlOrigin(url: string): string | null {
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

/** True only for an absolute URL whose origin is exactly Google's sign-in origin. */
export function isGoogleOAuthUrl(url: unknown): url is string {
  return typeof url === 'string' && urlOrigin(url) === GOOGLE_OAUTH_ORIGIN;
}
