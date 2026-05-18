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
