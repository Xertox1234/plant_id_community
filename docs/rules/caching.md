# Caching — binding rules

Compact checklist auto-injected before edits. Long-form:
`backend/docs/patterns/architecture/caching.md`.

- **Redis is required** (port 6379) — caching and distributed locks depend on it.
- **Invalidate on write.** Any signal/handler that changes cached data must clear
  both the individual-object key and any list keys that include it.
- **Cache-key isolation** — keys include every input that changes the result
  (user/tenant id, filters, page). Never let one user read another's cached data.
- **`isinstance()` checks in signals**, not `hasattr()` — multi-table inheritance
  (Wagtail pages) makes `hasattr` match unintended subclasses.
- Log cache operations with the `[CACHE]` prefix (`HIT`/`MISS`/`DELETE`).
- Set explicit TTLs; never cache without expiry.
- **Shared/CDN cache (`Cache-Control: public, s-maxage`) is ANON-ONLY, and `Vary`
  must cover EVERY auth scheme the project accepts.** `CookieJWTAuthentication`
  falls back to the `Authorization` header (the cookie-less mobile client), so
  `Vary: Cookie` alone lets a shared cache serve the anonymous copy to a
  header-authenticated request — leaking the anon baseline. Emit
  `Vary: Cookie, Authorization`, gate the `public` branch on an anonymous request
  AND `status_code < 400`, and give every authenticated response `private,
  no-store`. See `backend/docs/patterns/architecture/caching.md`.
- **Never `public`-cache a read with a per-request side effect or one whose
  content can be moderated away with no CDN purge.** A cached `view_count`-
  incrementing detail view undercounts a user-visible metric; a cached post/topic
  keeps serving unpublished/report-hidden content until the TTL. Mark those
  `private, no-store` so every hit reaches the origin.
