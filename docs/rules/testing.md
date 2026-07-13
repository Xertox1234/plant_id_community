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
