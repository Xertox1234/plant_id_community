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
- **Mutation-verify any test that claims to pin behavior X: break X, expect red,
  restore.** "It passes" only proves the test runs. Three tests this project
  shipped as coverage turned out to pin nothing, and each was found this way, not
  by reading: a query-count test that hand-rolled its own `get_or_create` instead
  of calling the production function (correct by construction, so it could never
  fail); a Flutter epoch-guard test satisfied by a *different* arm of an `and`
  (the uid check, which sign-out breaks anyway — so the generation bump could be
  deleted silently); a 400-status test that a second validator also satisfied.
  Restore the source and re-run before proceeding; assert `git status` is clean.
  Where the same mutation is worth re-running, script it (see todo 288's Work Log
  for a 6-mutant loop) rather than hand-editing.
- **A test that reimplements the call it is testing is hollow by construction.**
  Copying the production `get_or_create(defaults={...})`/request/lambda into the
  test body and asserting on *that* proves only that your copy is correct — the
  real call site can regress freely. Drive the production function and assert on
  its observable effect (captured queries, recorded calls, response), even when
  that means a looser assertion: `assert not [q for q in captured if user_table
  in q["sql"]]` beats an exact count over a hand-rolled call. Two independent
  reviewers flagged the same instance of this in todo 285.
- **`Model.objects.filter(pk=…).update(field=…)` does not touch your in-memory
  instance — and `force_authenticate(instance)` hands THAT object to the view.**
  So a test that backdates `date_joined` (or flips any field) with `.update()`
  and then authenticates the stale object silently exercises the pre-change
  value and asserts nothing. Add `instance.refresh_from_db()` with a comment
  saying it is load-bearing. Cost a full debugging cycle in todo 285; the test
  failed with a *plausible* message ("a single read collapsed the whole
  backlog"), which reads like a real bug rather than a broken fixture.
- **A query-count pin over a `select_related` chain must give the fixture data
  that traverses EVERY leg.** `serialize_forum_author` short-circuits on
  `profile.avatar_id` before ever touching `.avatar`, so a revision-list pin
  built on a profile with no avatar never exercised the `__avatar` join —
  deleting `select_related("user__wagtail_forum_profile__avatar")` from the
  view left the test green (todo 282 review). Set the optional relation in the
  fixture, then mutation-check by removing the `select_related` and confirming
  red. Same trap for any nullable FK guarded by an `_id` check.
- **Wagtail GENERATES a rendition on first access, which is indistinguishable
  from an N+1.** `prefetch_renditions()` only prefetches renditions that
  already exist, so the first request for a 4-image body pays 3 extra
  creations. Todo 282's image pin first failed `10 query(s) for 1 image, 22 for
  4` — a convincing N+1 that was measurement error. Warm EVERY request whose
  count you compare (not just one), so the pin covers the steady state.
- **A blanket `return_value=` on a shared helper stops expressing intent the
  moment the code under test calls that helper twice.** `@patch(peek_budget,
  return_value=False)` meant "the verdict budget ran out" when there was one
  budget check; todo 280 added a second `peek_budget` call for a different
  counter with the OPPOSITE posture, and the same mock silently came to mean
  "both counters are exhausted". Key the mock on its arguments instead — a
  `side_effect=lambda key, limit: key != THE_ONE_I_MEAN`. This diff was lucky:
  the test asserted publish and went red. A test asserting the fail-closed side
  would have gone **green for the wrong reason**. Whenever you add a call to an
  already-mocked shared helper, re-read every blanket mock of it.
- **The Django/DRF test client ignores cookie `path`, `samesite`, `secure`,
  and `domain` — it replays every stored cookie on every request.** Endpoint
  tests prove nothing about cookie attributes; assert them explicitly on
  `response.cookies[...]`, and pin a cookie's `path` to its endpoint with
  `reverse(...)`.startswith so mount moves can't silently strand it. See
  `docs/LEARNINGS.md` 2026-08-13.
- **TestCase classes that POST to login/auth endpoints must `cache.clear()`
  first thing in `setUp`** — django-ratelimit counters live in the shared
  cache and bleed across classes in one process (>5 logins in a run → 429s
  for whichever class runs later, an order-dependent flake).
- **Never implicit-return a mock call from a Vitest hook:** `beforeEach(() =>
  mock.mockReset())` returns the mock itself, and Vitest 4 treats a function
  returned from `beforeEach` as a TEARDOWN callback — it re-invokes the mock
  after the test, replaying a configured rejection as a fresh unhandled
  rejection (test fails even though its own assertions passed). Always use a
  block body: `beforeEach(() => { mock.mockReset(); })`. Related config trap:
  this repo sets `mockReset`/`restoreMocks: true`, which wipes return values
  chained inside a `vi.mock` factory before the first test — set
  `mockResolvedValue(...)` in `beforeEach`, not the factory. Reproduced in
  isolation twice (PR #537). Third face of the same trap: **setup.ts global
  polyfills must be PLAIN functions, never `vi.fn().mockImplementation(...)` /
  `.mockResolvedValue(...)`** — the reset wipes the implementation before every
  test, so the polyfill silently returns `undefined`; it stays green until the
  first production caller lands (`useMediaQuery` becoming matchMedia's first
  caller broke 74 tests). A bare argument-less `vi.fn()` spy is fine (nothing
  to wipe). Tests needing a different posture install their own stub and
  restore. See `web/docs/patterns/testing.md` and `docs/LEARNINGS.md`
  2026-08-15.
- **Scope forum e2e locators to `#main-content` — the AppShell header carries
  `/forum/search` and `/forum/new-thread` links on EVERY page**, so an unscoped
  `a[href^="/forum/..."]` (or `.first()`) grabs header chrome before the page's
  own link. Bit three specs across PR #536/#537. Corollary: changing a page's
  control TYPE (e.g. sort `<select>` → chip buttons) breaks e2e specs that are
  out-of-diff consumers of the old markup — grep `web/e2e/` for the page's
  selectors before shipping a control swap, and re-run the affected suite.
- **Django's `CommandParser.error()` raises `CommandError`, not argparse's
  default `sys.exit(2)`/`SystemExit`.** Testing that a management-command
  option is unregistered/rejected (e.g. pinning a `stealth_options`-only
  flag's CLI-unreachability) — `pytest.raises(SystemExit)` around
  `parser.parse_args([...])` fails even though the rejection is real; assert
  `CommandError` instead.
- **Rendition-touching tests clear the `"renditions"` cache backend first.**
  It is real-Redis-backed, long-TTL, keyed by image pk + filter spec (NOT by
  database), so it persists across pytest invocations and pk-collides with
  images from earlier runs — a test targeting the rendition cold path silently
  hits a stale cached row instead. Same trap cross-environment: a scratch DB
  sharing dev's Redis serves dev's rendition paths; give any second environment
  its own `REDIS_URL` db index. Hit twice in one session (PR #538).
- **`django_capture_on_commit_callbacks(execute=False)` + `patch()`: keep the
  patch open while you invoke the captured callbacks.** A callback that
  references a module global (`task.delay`) resolves it at CALL time, so once
  the `with patch(...)` block has exited it hits the real object — the mock
  records nothing and the test reads as "never enqueued". Nest the capture
  inside the patch. Also: under `@pytest.mark.django_db` an `on_commit`
  callback defers forever unless captured, so a receiver test without the
  fixture goes green by never running the enqueue at all (todo 289).
- **Log labels derived from a class need `getattr(cls, "__name__", …)` when
  tests patch that class** — `MagicMock` has no `__name__`, so a bare
  `cls.__name__` in a log line turns a key-free gating test into an
  `AttributeError` (todo 289).
- **A test that derives its expectations from the constant under test cannot
  catch that constant SHRINKING.** After extracting a shared
  `R2_REQUIRED_VARS` tuple, every test built its fixtures/sentinels by
  iterating it — so emptying `R2_URL_ONLY_VARS` would have stopped production
  requiring `R2_CUSTOM_DOMAIN` while the whole suite stayed green (each test
  silently checked one fewer var). Iterating the shared constant is right for
  the *grow* direction; the shrink direction needs at least one assertion
  naming a member **literally**, anchored outside the composition
  (`assertIn("R2_CUSTOM_DOMAIN is required", stderr)`). Same tautology family
  as asserting a locally-declared literal (todo 321).
- **`assertIn(value, some_dict.values())` proves presence, not wiring.** It
  passes when the value landed under the WRONG key — a swapped
  `access_key`/`secret_key` in a config dict satisfies it while breaking real
  auth. Assert by key (`self.assertEqual(options[expected_key], value)`), and
  when the key set is generated, pin the mapping itself
  (`assertEqual(tuple(VAR_TO_OPTION), SHARED_TUPLE)`) so a new member can't be
  added without stating where it belongs (todo 321).
- **Mutation-verify a drift/guard test before trusting it.** Break the thing it
  claims to pin, confirm it fails *by name*, then restore the file and `diff`
  to prove it is byte-identical. Todo 321's first drift test passed a swapped
  access_key/secret_key mutation — the weakness was invisible until the
  mutation was actually run.
- **A rate-limited endpoint's e2e cost is per-PROJECT, not per-spec.** Login is
  IP-limited to 5/15m and every POST counts, not just failures — so a spec with 2
  real logins matched by 7 Playwright projects spends 14, and the suite 429s no
  matter when the reset runs. Budget = (logins per spec x projects matching it) +
  setup projects. Scope login specs to ONE project and keep them in their own file:
  a file whose describe blocks want opposite project sets (one needs
  `storageState`, one clears it) cannot be scoped correctly at all (todo 329).
- **Two authenticated projects must never share one `storageState` file.** A logout
  test blacklists the refresh token backing whatever state it loaded, so under
  `fullyParallel` it invalidates the other project's session mid-run;
  `test.describe.configure({mode:'serial'})` only orders tests *within* a project.
  Give each authenticated project its own setup project writing its own
  `.auth/user-<browser>.json`, and verify by asserting the two files hold
  DIFFERENT refresh tokens — a green run is equally consistent with a shared token
  that simply did not race.
- **An attribute `:not([href="..."])` is an EXACT match and a query string defeats
  it.** `:not([href="/forum/new-thread"])` does not exclude
  `/forum/new-thread?category=54-general-discussion`, so a scoped-looking selector
  still clicks the CTA. Use the prefix form `:not([href^="/forum/new-thread"])`.
- **Never drive app state by writing `documentElement.dataset.*` from a spec.** A
  context provider's mount effect re-applies its own state over the write, so only
  the assertions expecting the provider's DEFAULTS pass and the rest silently
  assert against an unchanged page. Drive the real mechanism (the provider's
  storage keys) and reload. Tell: the "default" case passes while every changed
  case fails with exactly the default value.
- **`playwright test` fails at LAUNCH for a browser whose binary is missing** — it
  does not skip. Before trusting any suite-wide e2e result, confirm the binaries
  exist (`npx playwright install firefox webkit`); 4 of this repo's 7 projects had
  been silently failing to launch, so "the suite passes" covered 3 of 7.
- **This repo's dev reporter array prints `--list` output twice** (`['list']` plus
  a non-CI `['list']`), so any `--list | grep -c` count is 2x. Dedupe with
  `sort -u` before drawing a conclusion from it.
- **A negative fixture for a REGEX must contain the characters the pattern keys
  on.** Otherwise it passes for the wrong reason and pins nothing: `\s*=` silently
  matched the first character of `===` while its "must stay silent" case was
  `expect(x).toBe(y)` — the one read form with no `=` in it at all. Pick the
  adversarial neighbours (`===`, `==`, `!==`), and build the POSITIVE fixture by
  pasting the real code that motivated the rule, not a tidied version of it — a
  regex written from the lesson instead of the source can miss the very bug it
  exists for. See `docs/LEARNINGS.md` 2026-09-01.
- **A mock that fakes a thrown built-in must throw the REAL constructor.**
  `json: async () => { throw new Error('Unexpected token …') }` reads like a
  faithful `response.json()` failure and is not: `response.json()` throws a
  `SyntaxError`, so a bare `catch {}` and a narrowed `catch (e) { if (!(e
  instanceof SyntaxError)) … }` behave IDENTICALLY against the fake. The suite
  passes either way and cannot tell you which one shipped — the conflation in
  todo 310 survived a green run and was only caught in review. Throw
  `new SyntaxError(…)` (and `TypeError`, `DOMException`, …) so the type
  discrimination the production code performs is actually exercised.
- **Mutation-check every new guard: delete it and watch its own tests go red.**
  Cheaper than it sounds (one `cp` + one revert) and it is the only thing that
  distinguishes a test from a description. In todo 310 it caught nothing wrong
  — which is the point: the two guards were then known-load-bearing rather than
  assumed. It also catches the reverse case, a test that passes for a reason
  unrelated to the code under it.
- **Scope a `not.toHaveBeenCalled()` on a shared mock to the key you mean.**
  `expect(sessionStorageMock.setItem).not.toHaveBeenCalled()` fails for a
  reason that has nothing to do with the assertion's intent, because
  `getOrCreateRequestId()` writes a request id to sessionStorage on EVERY
  request (`web/src/utils/requestId.ts`). Use
  `not.toHaveBeenCalledWith('user', expect.anything())`. Todo 310.
- **Appending a test class BELOW `if __name__ == "__main__": unittest.main()`
  runs nothing, and the suite still says OK.** `unittest.main()` collects the
  module as it stands when that line executes, so classes defined after it are
  never registered — the run reports the SAME test count and a green `OK`, which
  is indistinguishable from success. The tell is the count: 56 before, 56 after
  adding six tests. Always compare `Ran N tests` before and after, and keep the
  `__main__` block last in the file. Hit while codifying todos 310/315.
