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
- **DraftStateMixin fixtures: `objects.create()` is born `live=True`** — it
  bypasses the draft→moderation→publish flow entirely, so workflow/counter
  tests built on it can stay green while the real API path (born `live=False`)
  is broken. Cover every moderated behavior through the HTTP endpoint at least
  once, and assert the PARENT object's liveness, not a derived status string.
- **A response-shape change breaks consumers OUTSIDE the diff.** Renaming a
  response key (e.g. `{results}` → `{topics, posts}`) is a cross-file contract
  change — grep the WHOLE suite for the old key and run the full app suite, not
  just the touched files. Diff-scoped review (human or kimi) structurally can't
  see out-of-diff consumers; only the full-suite run catches them.
- **`.live().public()` filtering costs one extra query** (a `PageViewRestriction`
  lookup). An exact `assertNumQueries`/`captured_queries` pin on any endpoint that
  gates visibility via `.public()` must include it — a topic-detail endpoint
  measured 4, not the naive 3.
