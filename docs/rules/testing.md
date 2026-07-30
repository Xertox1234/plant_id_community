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
- **Backend tests run via pytest** (`pytest.ini`; `manage.py test apps.forum_host
  wagtail_forum` finds 0 forum tests). `pytest --reuse-db` against a test DB built
  for a *different/narrower* app subset gives mass PHANTOM failures (a 235 run hit
  81 fake forum failures — the reused DB lacked the forum migrations +
  `post_migrate` bootstrap). When changing the app subset, use `pytest --create-db`
  before blaming the code. See `docs/LEARNINGS.md` 2026-06-22.
- **Test the golden path AND edge cases** — invalid input, auth failures,
  empty results, boundary values.
- Pin query counts on any endpoint touched by a performance change.
- Web: Vitest for units, Playwright for e2e. Mobile: `flutter test`.
- **Freeze time in count-to-limit rate-limit tests** (`freezegun.freeze_time`) so
  all N requests share one window — django-ratelimit's jittered window can roll
  over mid-hammer and flake the `assertEqual(..., 429)`. Mechanism (verified in
  `_get_window`): the limiter buckets by a window END (`ts - (ts % period) +
  crc32(key) % period`) that `_make_cache_key` folds into the cache key, so
  crossing it swaps the key and RESETS the count to zero — the request that
  should be the (N+1)th is seen as the 1st and returns the endpoint's normal
  status. Took down `main` on 2026-07-30 with `401 != 429`.
  **Use the context-manager form, never the bare `@freeze_time()` decorator**:
  `freeze_time()` resolves "now" when the object is CONSTRUCTED, and a decorator
  is constructed at import time — so `@freeze_time()` pins the test to whenever
  the module was imported, not to when the test runs (measured: a decorator
  built 1.2s before the call froze to the construction instant). `with
  freeze_time():` resolves in `__enter__`, which is what you want.
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
- **Testing a `useAuth`/context page**: create the mock fn with `vi.hoisted` (the
  `vi.mock` factory is hoisted above imports, so a bare top-level `const` throws),
  wrap in `MemoryRouter` for `useNavigate`/`useLocation`, and query by
  placeholder/role — `getByLabelText` is brittle when a label carries a
  required-`*` span. See `web/docs/patterns/testing.md`.
- **Test a rich-editor serializer against the REAL editor's output, not
  hand-written HTML.** When code parses `editor.getHTML()` (e.g. splitting TipTap
  HTML into StreamField blocks), unit tests fed crafted HTML strings + page tests
  that mock the editor both miss the actual seam. Instantiate the real editor
  headlessly (`new Editor({ extensions: [StarterKit, …] })` works in jsdom) and
  assert `parse(editor.getHTML())` round-trips — that's the only test that catches
  an inline-vs-block node or a dropped custom attribute before prod.
- **drf-spectacular views bind `permission_classes` at import time.**
  `SpectacularAPIView`/Swagger/Redoc read `permission_classes = SERVE_PERMISSIONS`
  at class-definition, so `@override_settings(SPECTACULAR_SETTINGS=…)` is INERT and
  can't flip the gate — test the REAL configured behavior (and a test that overrides
  `SERVE_PERMISSIONS` back to `AllowAny` and asserts STILL-denied is a valid pin of
  the binding). An `IsAdminUser` endpoint denies an *anonymous* request with **401**
  (the first authenticator, e.g. JWT, supplies a `WWW-Authenticate` header) but an
  *authenticated non-staff* request with **403** — assert the exact code, not a
  `(401, 403)` set. See `test_schema_endpoint_authz.py` (todo 248).
- **`force_login()` bypasses passwords — omit `password=` in `create_user(...)`
  test fixtures.** A literal password kwarg trips the `detect-secrets` pre-commit
  gate (which aborts the commit, with the real reason often scrolled off the top of
  the hook output); `force_login(user)` authenticates without one, so drop it.
- **jsdom: don't `vi.spyOn(window.location, 'assign')`** — `assign`/`replace`/
  `reload` are non-configurable, so the spy throws `Cannot redefine property:
  assign`. Replace the whole `window.location` property via `Object.defineProperty`
  in `beforeEach` (restore in `afterEach`). See `web/docs/patterns/testing.md`.
- **`getByRole` `name` as a regex is a SUBSTRING match → ambiguous when two
  controls share a label.** `{ name: /sign in/i }` matches both `"Sign in"` and
  `"Sign in with Google"` → "Found multiple elements". Use an exact string
  (`{ name: 'Sign in' }`) once a page has both.
- **Pin a `swagger_fake_view` guard with a direct `view.get_queryset()` unit
  test.** Schema-content tests can't detect the guard's removal —
  drf-spectacular resolves the model from `serializer_class` and never calls
  `get_queryset`. Instantiate the view, set `view.swagger_fake_view = True`,
  call `get_queryset()` with no request/kwargs wired: it only survives if the
  guard short-circuits (guard missing → `KeyError` on `self.kwargs` → red).
  See `wagtail_forum/tests/api/test_schema.py`.
- **An ambient framework fallback makes an explicit override
  unfalsifiable-by-omission end-to-end — pin the override with a direct unit
  test.** Second instance of the bullet above, so treat it as the rule: when
  your code sets a value the framework would also supply by default on the
  tested path, an outcome assertion pins the *framework*, not your override.
  Prefer `.get(key)` to `[key]` there — a `KeyError` is weaker mutation
  evidence than a value mismatch. See
  `wagtail_forum/tests/test_admin.py::test_bulk_unpublish_action_execution_context_carries_acting_user`
  and `docs/LEARNINGS.md` 2026-07-29 (todo 265).
- **"Comment out `permission_classes`" can be a NO-OP mutation.** With
  `DEFAULT_PERMISSION_CLASSES = IsAuthenticatedOrReadOnly`, a view with its
  `permission_classes` removed still blocks anonymous writes — the 401 test
  keeps passing and proves nothing. To verify an auth test is non-vacuous,
  mutate to `permission_classes = [AllowAny]`, and check the DRF default
  before trusting any mutation-based verification.
- **An unsaved Django model instance (`Model(fk=saved_obj)`, no `.save()`) has
  FK attributes set correctly but `.pk`/`.id` stays `None`.** `topic_id` resolves
  immediately because the FK is assigned at construction, so a test asserting
  only on the FK looks fine — but any code in the same path that reads the
  instance's OWN `.pk`/`.id` (e.g. serializing an id into a notification
  payload) silently gets `None`/`"None"` instead of a real value. Save the
  instance if anything downstream might read its own primary key.
- **A TipTap `suggestion.render()`'s `onStart`/`onUpdate` DOM lifecycle isn't
  exercised by a headless `Editor` test.** Those callbacks fire only when a
  real ProseMirror view is mounted (actual cursor movement); a Vitest test
  that only drives pure-logic helpers (item resolution, `renderHTML`/
  `renderText`) gives false confidence that the whole extension is covered.
  Verify DOM-lifecycle guards (e.g. an orphan-dropdown `shouldRender` check)
  via Playwright, or flag explicitly in the Work Log that it's
  reasoning-verified, not test-exercised. See `web/docs/patterns/testing.md`.
- **Never mark a test `django_db(transaction=True)`** — its teardown flush (and
  any Django `TransactionTestCase`, e.g. blog `test_analytics.py`) deletes
  Wagtail's migration-seeded root page/collection/Site rows, so the test passes
  standalone but fails (or breaks LATER tests) in the full suite. For
  concurrency-shaped logic, simulate the interleaving deterministically instead
  — monkeypatch the fast-path check to miss once and assert the locked re-check
  reuses the existing row (see `wagtail_forum/tests/test_collections.py`).
- **Running backend tests from a git worktree needs two guards:** (1) the venv's
  `wagtail_forum` is an *editable install pointing at the main checkout* — prepend
  `PYTHONPATH=<worktree>/backend/packages/wagtail_forum` or the worktree's package
  edits are silently NOT under test (import-file-mismatch collection errors are
  the tell); (2) never run two pytest sessions concurrently — they share the one
  `test_plant_community` Postgres DB and cross-kill with phantom connection
  errors/DuplicateDatabase. See `docs/LEARNINGS.md` 2026-07-17.
- **A "docs must mention X" coverage test needs a word boundary, not `in`.**
  `f"PREFIX_{name}" not in text` passes for a typo that *appends* characters —
  `WAGTAILFORUM_MENTION_MAX_PER_POSTX` contains the real name as a prefix, so the
  test stayed green on a broken README (todo 262). Use
  `re.search(rf"PREFIX_{name}\b", text)`. Same trap for any
  substring-based name/route/key coverage assertion.
- **A Playwright `*.spec.ts` NEVER runs authenticated.** The authenticated projects
  select on `testMatch: /(forum-authenticated|auth)\.spec\.js/` — `.js` only — so a
  TypeScript spec always runs under the anonymous projects with no `storageState`,
  silently and while passing. A new spec that needs a signed-in view must be named
  `*.spec.js`, or widen the authenticated `testMatch` **and** the anonymous
  projects' `testIgnore` together. Never cite an E2E spec as evidence for auth-gated
  UI without confirming its project via `npx playwright test --list`. See
  `docs/LEARNINGS.md` 2026-07-29 (todo 270) and 2026-07-25 (todo 261).
- **Grep for call sites, not the `def`, before crediting a symbol as shipped.**
  A doc/comment citing `path.py:411` can resolve perfectly and still be false — that
  line was `def send_forum_mention_notification`, a method with zero callers, cited
  as the live mention-delivery path (todo 270). A resolving line number is a
  syntactic check; whether the code runs is a semantic one. **And read the
  enclosing function before citing a grep hit** — the first repair of that same
  paragraph cited `notifications.py:82` as a `create_notifications` call because
  grep matched `NotificationVerb.MENTION` there; line 82 is an argument to
  `send_forum_push_batch.delay(...)`, a different mechanism. A grep hit gives you
  a line, not a callee.
- **Mutation-check restore: stage or commit FIRST, then `git checkout -- <path>`.**
  The commit-first half is load-bearing, not ceremony. `git checkout --` reverts
  to the INDEX, so with unstaged work in that file it silently discards the whole
  edit, not just your mutation — no error, exit 0. That ate 12 views' worth of an
  uncommitted refactor on todo 277, and surfaced only as a test that passed in
  isolation but failed in the suite. If you cannot stage first, copy to an
  ABSOLUTE path outside the repo and restore from that — the reason to distrust
  `cp` is relative paths (a `cp` after a `cd` in the same one-liner silently fails
  when the shell resets cwd, and re-running then overwrites the good backup with
  the already-mutated file), not `cp` itself. Either way, finish by asserting
  `git status` is clean, not just that the test passes.
- **Test coverage can differ PER URLCONF — enumerate the mounts before claiming
  "no test catches this".** Every forum view sets `versioning_class = None`. Under
  this project's `NamespaceVersioning` + `ALLOWED_VERSIONS = ["v1","v2"]`, dropping
  that opt-out 404s the *package* API suite (its test urlconf resolves to
  `wagtail_forum_api`, not an allowed version) but is completely invisible on the
  *host* mount (`v1:wagtail_forum_api` — `NamespaceVersioning` splits on `:` and
  accepts `v1`). So host-only views and throttled host subclasses have nothing
  behind them: reordering `SimilarTopicsView`'s bases left its own 18 tests and all
  251 package API tests green. Two lessons: (a) when an attribute's correct value is
  indistinguishable from its default **on the mount that ships**, assert the
  STRUCTURE — `apps/forum_host/tests/test_forum_versioning_optout.py` walks the host
  urlconf and also pins MRO ORDER, since DRF's `APIView` declares
  `versioning_class` in its own class body and a mixin listed after it silently
  loses; (b) verify a "nothing catches this" claim against every urlconf, and make
  sure your control actually exercises the code — my first measurement paired a
  real API test with `test_boards.py`, which makes zero API calls (todo 277 / L20).
- **When two validators can return the SAME status, assert the message, not just
  the code.** A test posting 5,000 tags asserted only `400` — and kept passing with
  the new early-bound guard removed, because the ordinary max-count check rejects
  that payload too. The test named one guard and pinned another. Mutation-testing
  is what exposed it (neuter the guard, expect red); a status-only assertion on an
  endpoint with layered validation is close to a tautology. Assert the specific
  error text so the test fails for the reason it claims (todo 276).
