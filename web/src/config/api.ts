/**
 * The API's origin, read once (todo 449 item 4). Every service used to read
 * `VITE_API_URL` itself, each with its own fallback and trailing-slash
 * handling. A trailing slash is stripped so `${API_ORIGIN}/api/...` never
 * doubles it.
 */
export const API_ORIGIN = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(
  /\/+$/,
  ''
);
