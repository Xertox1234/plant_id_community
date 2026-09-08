# Security — binding rules

Compact checklist auto-injected before edits. Long-form: `backend/docs/patterns/security/`.

- **ViewSet `get_permissions()` MUST call `super().get_permissions()`** for custom
  `@action` endpoints. Overriding without `super()` silently drops action-level
  `permission_classes` — a real auth hole. See `architecture/viewsets.md`.
- **Never f-string table/column names into raw SQL** (migrations included). Use
  `psycopg2.sql.Identifier()` plus an explicit whitelist of allowed names.
- **Don't manually escape SQL `LIKE` wildcards before `__icontains`/`__startswith`/
  `__endswith` (or their `i`-prefixed forms)** — Django's ORM already
  auto-escapes `%`/`_`/`\` for all six (`PatternLookup.process_rhs()`,
  verified against this project's PostgreSQL backend). Stacking
  `escape_search_query()` on top double-escapes and silently breaks matches
  containing a literal `%`/`_`/`\`. Reserve manual escaping for lookups that
  bypass `PatternLookup` (raw SQL, `.extra()`, a custom `Lookup`). See
  `backend/docs/patterns/security/input-validation.md`.
- **File uploads: all 4 validation layers** — extension, MIME type, size, and a
  PIL/Pillow decode check. Never trust the client-sent content type alone.
- **No secrets in code, logs, or commits.** API keys and `SECRET_KEY` come from
  `.env`. `SECRET_KEY` must be ≥50 chars and must not contain `django-insecure`.
- **Sanitize all rendered HTML** with DOMPurify (web) before injecting; never
  `dangerouslySetInnerHTML` with unsanitized content.
- **Auth-sensitive code is never delegated** to the cheap worker — review by hand.
- Redact PII (emails, tokens) from logs; GDPR redaction applies to Firebase auth.
- **Never create user accounts in migrations or any other deploy-time path.**
  Blog migration 0004 auto-created superuser `plant_care_admin` with a hardcoded
  password on every `migrate` until 2026-06-10. Dev/demo/E2E seed commands must
  refuse to run in production (`if not settings.DEBUG: raise CommandError(...)`),
  and byline-only accounts get `set_unusable_password()` — never a literal password.
- **Try a bump before suppressing a vuln.** pip-audit's empty "Fix Versions"
  column does NOT mean unfixable — the advisory's affected range may exclude a
  newer release (bleach `GHSA-g75f-g53v-794x` showed no fix at 6.3.0 but was gone
  at 6.4.0). Only when no bump clears it, add an entry to
  **`.github/security-suppressions.yml`** — NOT an `--ignore-vuln` flag in the
  workflow, which is generated from that file by
  `scripts/check_suppressions.py --emit-flags`. A hand-added flag is invisible to
  the expiry recheck. Every entry needs `expires` (<=180 days from `added`),
  `owner`, `reason`, `clears_when`, and a `tracked_by` naming a todo `issue_id`
  that is still OPEN; `--validate` enforces all of it. Run `npm audit fix`
  WITHOUT `--force` (`--force` pulls breaking majors).
- **A suppression must be able to expire, and its tracker must be resolvable.**
  `--ignore-vuln` hides an advisory unconditionally — including after a fix
  ships, which makes the gate blind to the very thing it was told to watch. Eight
  suppressions carried the note "revisit when a patched release ships (tracked in
  todo 089)"; todo 089 was real, and completed, and archived. A pointer to a
  CLOSED artifact reads as live tracking, so nobody rechecked, and Twisted 26.4.0
  shipped against a suppression whose own text said "remove when 26.4.0 stable
  releases". Verify with the UNSUPPRESSED pip-audit report
  (`--recheck --report backend/pip-audit-report.json`), not with "a newer release
  exists" — the two disagree in both directions.
- **Two advisory databases, two answers — keep both scanners.** pip-audit reads
  OSV/PyPI; Dependabot reads the GitHub Advisory Database. Dependabot surfaced 71
  advisories pip-audit's ignore list hid, and pip-audit reports a Django advisory
  (fix 6.0.8) that Dependabot does not report at all. Neither is a superset.
- **This repo has TWO npm manifests; a scanner that names one is blind to the
  other.** `package.json` at the ROOT is the Cloudflare Workers deploy artifact —
  Workers Builds runs `npm clean-install` there and ships `npx wrangler versions
  upload` from it — and `web/package.json` is the React app. Every npm step in
  `security-scan.yml` hardcoded `web/`, so the weekly hard-fail never read the
  root tree, and 14 root advisories (11 x undici, sharp, ws, esbuild) sat visible
  only to Dependabot. Name BOTH wherever you name one — including the
  "Run locally:" line in a PR comment, which taught humans the same blind spot.
  The set is `NPM_MANIFEST_DIRS` in `scripts/new_vuln_gate.py`, with a drift test
  that fails if a third lockfile appears; loop over it, never write a directory
  name into the workflow (todo 356).
- **A scope predicate that says "relevant" plus an action pointed at a different
  tree is a FALSE GREEN, not a skip.** `new-vuln-gate`'s scope step matched the
  root lockfile and set `npm=true`; its audit step then read `web/` regardless,
  compared `web/` to `web/`, and printed a confident `0 advisories on base, 0 on
  head, 0 new` about a tree the PR never touched (PR #669). The `pip-audit` half
  printed an honest `skipped (no manifest change in this PR)` on the same run —
  the vocabulary was there and went unused, because detection was right and only
  the action was wrong. When a gate reports a *number*, prove the number came
  from the file the diff changed: derive the scope and the work from ONE tested
  function, and let a missing artefact fail loudly rather than letting a
  stand-in tree answer (todo 356).
- **A FAILED `npm audit --json` is a NON-EMPTY report that parses to zero
  advisories.** It writes `{"message": "...", "error": {...}}` to stdout and
  exits 1 — and exit 1 is also what it returns when advisories merely exist, so
  the `|| true` every caller needs cannot tell them apart, and an `[ -s "$f" ]`
  size assertion passes on the 186-byte error object. A transient registry
  failure on the HEAD side then prints `15 on base, 0 on head, 0 new` and passes.
  Guard by REJECTING a top-level `error` key when loading the report
  (`new_vuln_gate.py:_load`), not by checking the file's size. Direction matters:
  a BASE-side failure inverts into a loud false red, so only the head side is
  silent (todo 356).
- **`npm audit --package-lock-only` audits the LOCKFILE, so it cannot see a
  dependency declared in `package.json` and missing from the lock** — it exits 0
  with `found 0 vulnerabilities` for a package it never looked at. `npm ci` used
  to hard-fail on that skew, so removing an install removes the guard: pair
  `--package-lock-only` with `npm ls --package-lock-only` (exit 1,
  `ELSPROBLEMS`). `web/` gets this from `web-ci.yml`'s `npm ci`; the ROOT tree
  had no install anywhere in CI, only Cloudflare Workers Builds after merge
  (todo 356).
- **Never promote a pattern into `*/docs/patterns/` without reading the code
  that enforces it.** The pattern library is trusted, so promotion is exactly
  what makes the next reader stop checking — a wishful sentence copied in
  becomes load-bearing. Rescuing `.env.example`'s `REQUIRED__*` placeholders
  from an archived doc, the enforcement table asserted `JWT_SECRET_KEY` was
  rejected at boot and `FIELD_ENCRYPTION_KEY` failed inside `Fernet()`; review
  found `INSECURE_PATTERNS` is applied to `SECRET_KEY` ALONE
  (`settings.py:94`), JWT's own checks (set / `!= SECRET_KEY` / `len >= 50`) all
  pass on the 66-char placeholder, and nothing reads `FIELD_ENCRYPTION_KEY` at
  all. Reason from the enforcing code, never from the value's shape (todo 367).
- **A guard that works by coincidence is not a guard.** The only `.env.example`
  placeholder production rejects is `SECRET_KEY`, and only because
  `INSECURE_PATTERNS` contains a word its *generation hint text* happens to
  include — reword the hint and the check silently stops firing. When you find
  a check passing, confirm it matches on the property you meant, not on
  incidental text (todo 367).
- **A top-level workflow `permissions:` block REPLACES the repo default, it does
  not narrow it.** With `default_workflow_permissions: read`, adding
  `permissions: contents: read` REVOKES every other read scope. Enumerate what the
  jobs actually need: `mobile-ci.yml` uses `dorny/paths-filter`, which requires
  `pull-requests: read`, and it backs the required `mobile-ci-gate` — omitting it
  blocks every PR.
- **A ruleset has no additive sub-resource.** `PUT /repos/{o}/{r}/rulesets/{id}`
  REPLACES the whole `rules` array — the same hazard as `PATCH`ing branch
  protection with a partial payload, but with no narrow endpoint to fall back on.
  Prefer the UI; if you must use the API, `GET` → append → `PUT` → `GET` and diff.
- **Trust only provider-verified emails.** Never match or create a Django
  account from a provider-supplied email the provider hasn't marked verified;
  fail closed when the verification signal is absent. Each OAuth/federated path
  enforces this with its own local guard (strip / set-if-verified /
  `ImmediateHttpResponse` / 403) — a shared *policy*, not shared code, so do not
  collapse the four guards into one provider-switch helper. When a guard strips
  the email, the downstream user lookup MUST treat a missing email as a hard
  stop. Canonical: `backend/docs/patterns/security/authentication.md` → "Trust
  only provider-verified emails".
- **A shared resource container (collection/bucket/folder) is not an ownership
  check.** Validating that a referenced object lives in the right *container*
  (e.g. an upload collection) closes an existence-guessing IDOR but does not
  stop one user from referencing another user's object BY ID within that same
  container. If the object records an owner/uploader, check it explicitly —
  don't assume container membership implies ownership. Canonical:
  `backend/docs/patterns/domain/forum.md` → "Image blocks are scoped to an
  allowed-uploader set" (audit L21).
- **Gate the drf-spectacular schema/docs endpoints.** `SpectacularAPIView`,
  `SpectacularSwaggerView`, and `SpectacularRedocView` default to
  `SERVE_PERMISSIONS = [AllowAny]`, so the full OpenAPI schema (every path,
  parameter, and the documented auth schemes) plus the interactive Swagger/Redoc
  UIs are anonymous-readable in production. Gate them with
  `SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]`
  — one knob covers all three views (and any future one). `SERVE_INCLUDE_SCHEMA=False`
  does NOT gate them (it only hides the schema's own path). Surfaced in prod (todo 248).
- **Don't trust `claude-code-security-review`'s own `results-file`/`findings-count`
  step outputs.** *(Retired 2026-07-30 — the action was removed from CI for cost;
  kept here in case it is ever reinstated.)* The action's composite step hardcodes `results-file` to a stale
  relative-path string it never updates, and captures the script's own internal
  severity exit code into a shell variable without ever re-raising it — the job
  always exits success regardless of findings. Read
  `${{ github.workspace }}/claudecode-results.json` directly (unconditionally
  copied there) and parse `.findings[].severity` yourself — the enum is
  `HIGH|MEDIUM|LOW` only, `CRITICAL` is never emitted. See `docs/LEARNINGS.md`
  2026-07-13.
- **Promoting a soft-fail CI step to a blocking gate: audit every exit-0
  "can't verify" branch, not just the one that prompted the change.** A
  soft-fail gate's fail-open branches never get exercised by whatever
  validated its trip condition — they're invisible until the step can
  actually fail the job. See `docs/LEARNINGS.md` 2026-07-14.
- **Never `PATCH` GitHub's branch-protection endpoint with a partial
  payload** — omitted fields reset to default, silently clobbering
  `enforce_admins`, existing required checks, and PR-review settings. Use
  the narrow sub-resource endpoints (e.g.
  `.../required_status_checks/contexts`) for additive changes, and `GET`
  before AND after to diff the before/after state. See `docs/LEARNINGS.md`
  2026-07-14.
- **Never hardcode cookie attributes (`samesite=`, `secure=`) in app code —
  mirror `settings.SESSION_COOKIE_SAMESITE`** (forcing `secure=True` whenever
  samesite is `"None"`), and scope any cookie `path=` to the live `/api/v1/`
  mount, pinned in a test via `reverse()`. A hardcoded `Strict` silently
  killed all email/password auth on the split-domain prod deploy while every
  test stayed green. See `docs/LEARNINGS.md` 2026-08-13.
- **A management-command option meant for orchestrator-only use (never the
  CLI) is a `Command.stealth_options` entry, never an `add_argument()` flag.**
  `stealth_options` is Django's own mechanism (`call_command()` validates
  passed kwargs against `dest_parameters | stealth_options`) for a value
  settable ONLY via `call_command(..., real_users_verified=True)` — never
  registered on the argparse parser, so it cannot be typed as a real CLI
  flag. Used to skip a duplicate guard check an orchestrator already ran
  without weakening the guard itself for a standalone/CLI invocation. Pin
  the CLI-unreachability itself: `command.create_parser(...).parse_args([...])`
  with the flag must raise (Django's `CommandParser.error()` raises
  `CommandError`, not argparse's default `SystemExit`).
- **`detect-secrets` fires on any quoted `SECRET`-ish key mapped to a quoted
  value, even when that value is an option NAME — and it scans Markdown too.**
  A dict entry mapping the env var `R2_SECRET_ACCESS_KEY` to django-storages'
  option name `secret_key` is a Secret Keyword hit, and it fires again on every
  doc or todo that *quotes* that line — it blocked three separate commits in
  todo 321, from the test, the archived todo, and this rules file. Mark a real
  false positive inline (`# pragma: allowlist secret`, or
  `<!-- pragma: allowlist secret -->` in Markdown); in prose, prefer describing
  the mapping (`X` → `y`) over reproducing the literal `"key": "value"` pair,
  so the doc doesn't trip the scanner for the next editor. Never silence it by
  regenerating `.secrets.baseline` to make the hit disappear (todo 321).
- **A test helper that prints resolved settings must blank credential env vars
  before applying its overrides, not rely on callers passing all of them.**
  `decouple.config()` falls through to `backend/.env` for an ABSENT key, so a
  partial-override caller on a machine that followed the R2 rotation runbook
  dumps real credentials into test stdout. Blank (`env[key] = ""`, never
  `pop()`) every var the code may read, then `env.update(overrides)` — a
  structural guard, not caller discipline (todo 321).
- **A bootstrapped role must hold the permissions of every model its UI links
  into — grant per model, and prove the click-through as a group member.**
  `forum_host/bootstrap.py`'s "Forum Moderators" group granted topic/post perms
  only, so the Report snippet views (and later the moderation queue's row
  links) were superuser-only from the day reports shipped — with every admin
  test green, because they all log in as a superuser. When a listing, report,
  or dashboard links to model X's views, add `view_X`/`change_X` to the group
  in the same PR and add a test that GETs the linked URL as a member of that
  GROUP, not a hand-assembled permission set (todo 345).
- **oEmbed/video embeds: network once at write time under a hard timeout,
  reads DB-only, never deliver provider HTML.** Wagtail's oEmbed finder calls
  `requests.get` with no timeout and `EmbedValue.html`/`get_embed` fetch on a
  cache miss — so resolve into the `Embed` table while the author waits
  (`TimeoutOEmbedFinder` puts a real socket timeout on the request AND a
  shared bounded pool + `EMBED_FETCH_TIMEOUT_SECONDS` bounds the author's wait;
  cap distinct URLs per body), read only that table on
  the serve path, and derive the player URL server-side from the ORIGINAL
  url onto a known host (`youtube-nocookie.com`, `player.vimeo.com`); clients
  iframe that with `sandbox` and fall back to thumbnail + link. The provider
  allowlist is the host's `WAGTAILEMBEDS_FINDERS` — keep it short, and gate
  the block behind a package setting that defaults OFF (todo 344).
- **"Wire up the UI" for a dormant endpoint starts with an audit of EVERY
  write path to that model, not just the one the UI will call.** The blog
  comment API had a `ModelViewSet` whose generic `POST /comments/` (and
  PUT/DELETE) bypassed `allow_comments`, spam, trust and rate limits and let
  a body choose ANY post; `parent` accepted any comment on any post at any
  depth. Close or gate every route (`ReadOnlyModelViewSet` + the one
  guarded action), make view-bound FKs read-only on the serializer, and
  validate `parent` (same object, depth cap, approved) before reusing the
  forum's spam backend + trust level at service level only (todo 352).
- **A block that REFERENCES another object (post_quote → post) is validated
  on write and resolved on read, never trusted from the body.** Write:
  visible + not block-paired with the writer + capped, with ONE generic 400
  for missing/unpublished/restricted/blocked (no existence oracle) and a
  rejection rather than a silent strip. Read: a page-level map
  (`build_forum_quote_map`) resolves the attribution; a referent that went
  away renders its stored text with `available: false` and no attribution.
  The referenced text stays plain-text-by-contract (todo 342).
- **Triage a CodeQL alert from its SARIF `codeFlows`, not its headline.** Pull
  the analysis SARIF (`gh api …/code-scanning/analyses/<id>` with
  `Accept: application/sarif+json`) and read the path: a flow that only reaches
  the sink through a test file's round-trip composition, or that carries taint
  on `[ArrayElement, value]` across differently-typed blocks, is a false
  positive — dismiss it with the traced rationale, then BREAK the path
  structurally (GitHub code scanning ignores `// codeql[...]` / `// lgtm[...]`
  suppression comments, and a dismissed alert comes back as a new number the
  moment its fingerprint shifts): e.g. `structuredClone` across a test's
  round-trip boundary; and still take any cheap hardening the trace suggests
  (todo 353).
- **A block pair inside a shared room is a POLICY decision — record it and pin
  it:** hide the blocked member's messages from the blocker's reads, previews
  and unread counts (never the room itself), refuse sends with an explicit 403
  while both are in it, and reject adding a block-paired member with the same
  generic 400 as a missing user so membership is no oracle (todo 350).
- **Never interpolate an HTTP-client exception — `str(e)` carries the request
  URL, and the URL carries your key.** `requests.HTTPError.__str__` is
  `"401 Client Error: ... for url: <prepared URL>"`, so
  `logger.error(f"API failed: {e}")` writes every query-string secret to the
  log; `logger.exception(...)` does the same, because the traceback ends with
  that message. Three services leaked this way — OpenWeather (`appid`), Trefle
  (`token`, set on `session.params` so it rides EVERY request) and PlantNet
  (`api-key`) — and the worst site was a retry decorator, which leaked once per
  attempt. Use `log_safe_api_error(exc)` from
  `apps/core/utils/pii_safe_logging.py`; `exc.response.status_code` is fine,
  the exception object is not. Header-authenticated clients are safe by
  construction, which is a reason to prefer header auth. The same rule bans
  `str(e)` in a response *body*: it reaches the client (todo 354).
  The drift guard is `apps/core/tests/test_requests_exception_drift.py`,
  and since todo 358 it sweeps every `.py` under `apps/`, `packages/` and
  `plant_community_backend/` — not just the service layer — so a handler
  written in a view or a Celery task is covered too. Know what it cannot
  see before reading green as safe: only calls prefixed `logger.` (a
  `self.logger.` wrapper is invisible), never a `raise SomeError(f"{e}")`,
  and never `logger.exception` with a constant message — that one still
  emits the exception text through the traceback, which is why both
  `get_service_status` methods branch on `isinstance(exc,
  requests.RequestException)` instead.
- **"Not `str(e)`" is not the same as "any attribute of `e`".**
  `e.response.url` and `e.request.url` ARE the prepared URL, and
  `e.args[0]` IS the string `str(e)` returns — all three rebuild the leak
  while looking like the approved `e.response.status_code` shape. The guard's
  first version marked safe every name under any attribute access and let all
  three through; it now matches an explicit `APPROVED_SHAPES` allowlist
  (`type(e).__name__`, `e.response.status_code`, `e.response.text`,
  `log_safe_api_error(e)`) and reports everything else. Sensitivity is a
  property of the *value*, not of the syntax that reaches it — an allowlist
  fails closed on the shape nobody thought of, a denylist does not (todo 358
  review).
- **Log a connection URL's parts, never the URL.** `REDIS_URL`, `DATABASE_URL`,
  `CELERY_BROKER_URL` and signed asset URLs carry the password in the userinfo
  component. `validate_environment()` logged `REDIS_URL` verbatim on every
  process start — gunicorn *and* the co-located Celery worker. Use
  `urlsplit(u)` and emit `.hostname`/`.port`/`.path` (`.port` is `None` when the
  URL omits one, so fall back rather than printing "None"). Sensitivity is a
  property of what a value *contains*, not what it is named: URL-shaped and
  exception-shaped values are exactly the class a taint scanner does not
  follow, which is why CodeQL flagged 16 logging sites here and none of the
  four that carried credentials (todo 354).
- **The step that produces an artefact must assert it produced it — `|| true`
  turns "the tool crashed" into "the tool found nothing".** `new-vuln-gate`'s
  pip half had never returned a result: it ran `pip-audit -r
  backend/requirements.txt` from the repo ROOT, pip resolves a relative
  requirement path against the CWD (so `-e ./packages/wagtail_forum` was
  invalid), both audits died, `|| true` swallowed it, and the failure surfaced
  two steps later as a missing file. Any command whose non-zero exit is
  *expected* needs an explicit `[ -s "$out" ]` check in the same step, where the
  failing output is still on screen (todo 354, PR #678).
- **A bump that closes an advisory must clear its suppression in the same PR.**
  `.github/security-suppressions.yml` kept a Twisted entry reading
  `clears_when: Twisted >= 26.4.0 stable releases` after 26.4.0 shipped — its
  `pinned:` field simply false, suppressing an advisory that no longer existed.
  Grep the package name in that file whenever you bump it; `expires` will catch
  it eventually, months late (todo 354).
- **Choose fix-vs-dismiss on a scanner alert by whether the CODE should change,
  never by which one you predict will clear the alert.** Todo 354 fixed 8
  `py/url-redirection` alerts with a provider allowlist specifically because a
  fix is durable and a dismissal is not — and closed zero of them, because
  CodeQL does not model a `frozenset` membership test as a sanitizer (nor a
  hand-rolled `escapeHtml`, todo 353). It models its own sanitizer list and
  structural impossibility. Re-count after the merge; do not trust the plan.
- **When a single-package bump cannot resolve, read the constraint before trying
  another version.** `cryptography==50.0.0` failed; 49.0.0 (the other listed fix
  version) fails identically, because `pyOpenSSL==26.2.0` caps it at `<49`. Bump
  the capping package instead. And never merge an `rc`/`a`/`b` version into
  production requirements without checking for a stable sibling — Dependabot
  proposed `Twisted==26.4.0rc2` with green CI while 26.4.0 stable existed.
  `pip install --dry-run -r <file>` proves resolution in seconds without
  touching the venv; it does not prove behaviour (todo 354).
- **In `validate_environment()`, classify by consequence, not confidence:
  anything that lets the service boot and serve wrong or empty data goes in
  `critical_errors` (fatal when `not DEBUG`), never `warnings`.** "SQLite while
  `DEBUG=False`" sat in `warnings` and stopped nothing — and the deploy does not
  save you: `railway.json`'s `preDeployCommand` (`migrate --noinput` +
  `seed_default_forum` + `seed_default_badges`) all exit **0** against SQLite,
  because the `connection.vendor` guards that make SQLite dev work also make the
  Postgres-only DDL self-skip. A dropped `DATABASE_URL` yields a green deploy
  serving an empty site. Copy the shape at `settings.py:1509-1521` (R2
  credentials): build one `message`, then `critical_errors` if `not DEBUG` else
  `warnings`. Rate such a bug by RUNNING the real deploy command sequence
  against the broken config, never by predicting that it would crash (todo 359).
- **Never assess a suppressed advisory with the suppressed audit.**
  `check_suppressions.py --emit-flags` emits `--ignore-vuln` for *every* id in
  `.github/security-suppressions.yml`, so the documented "RUN LOCALLY" command —
  the one that file's own header shows, and the one `sync_alarm_todo.py:111`
  templates into every generated alarm todo — cannot report the entries it is
  meant to re-assess. It returns clean by construction. A re-assessment
  procedure written that way shipped in todo 366 and was caught only in review;
  `docs/rules/security.md` *already* said to verify against the unsuppressed
  report, and the canonical incantation won anyway. Two commands, two questions:
  suppressed asks "is the gate green?", unsuppressed
  (`pip-audit … --format json --output <f>` then
  `check_suppressions.py --recheck --report <f>`) asks "is this entry still
  true?". Only the second can close a suppression (todo 355 slice 6).
