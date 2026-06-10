# Testing — binding rules

Compact checklist auto-injected before edits.

- **Never mock the database.** Tests hit a real test DB so migrations and ORM
  behavior are exercised. Mocked DB tests hide broken migrations.
- **Strict assertions** — `assertEqual`/`assertNumQueries(exact)`, not `assertTrue`
  or `<=` bounds. A test that can't fail isn't a test.
- **No hollow tests.** A test named for behavior X must assert X and fail if X
  regresses. Banned shapes (2026-06-09 audit found 6): an empty body that ends in
  `pass` (or `if cond: pass`); a tautology asserting a locally-declared literal
  (`const X=30000; expect(X).toBe(30000)` — import the real subject, assert
  `httpClient.defaults.timeout`); asserting only that a mock `toBeDefined()`. For
  env/dev-gated code (`import.meta.env.DEV`), force the real branch with
  `vi.stubEnv('DEV', false)` and assert the real call. An empty placeholder test
  for an unbuilt feature is noise — delete it, don't leave a green stub.
- **Rebuild a stale test DB** with `--noinput` after migration changes
  (`python manage.py test apps.foo --noinput`) — otherwise `FieldError`.
- **Test the golden path AND edge cases** — invalid input, auth failures,
  empty results, boundary values.
- Pin query counts on any endpoint touched by a performance change.
- Web: Vitest for units, Playwright for e2e. Mobile: `flutter test`.
- **Freeze time in count-to-limit rate-limit tests** (`freezegun.freeze_time`) so
  all N requests share one window — django-ratelimit's jittered window can roll
  over mid-hammer and flake the `assertEqual(..., 429)`.
