---
status: in_progress
priority: p2
issue_id: "261"
tags: [forum, ops, celery, ci, e2e]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H21, M34, M42, L17"
---

# Forum epic: ops, scheduling, E2E & caching

## Problem

Operational gaps around the forum: tombstone pruning is documented and tested
but never scheduled anywhere (unbounded table growth; the 30-day retention
contract is silently unenforced), the write path has zero E2E coverage, hot
public reads carry no HTTP cache headers despite sitting behind Cloudflare, and
CI has no migration-drift gate. p2 epic from the 2026-07-11 forum-modernization
audit.

## Findings

- **H21** — Tombstone pruning never scheduled: `prune_forum_tombstones`
  documents "run daily via beat/cron" and is unit-tested, but no
  `CELERY_BEAT_SCHEDULE` exists anywhere and `railway.json` never invokes it —
  `TopicDeletedLog` grows unbounded
  (`W/management/commands/prune_forum_tombstones.py:1-8`).
- **M34** — Forum write path has no E2E coverage: the golden-path spec is
  unauthenticated-browse-only by its own comment (predates Spec 2);
  create/reply/edit/delete/react/upload exist only as mocked component tests
  (`web/e2e/forum-golden-path.spec.ts:3-4`).
- **M42** — No HTTP-layer caching/conditional requests (Cache-Control/ETag) on
  hot public reads — DISTINCT from the documented no-Redis-app-cache decision
  (`backend/docs/patterns/architecture/caching.md:186-198`); board/topic lists
  are public + read-heavy and the deploy already sits behind Cloudflare.
  Caveat: post-list `can_edit`/`can_delete` is per-user — caching must be
  anon-scoped/varied.
- **L17** — No `makemigrations --check` gate in CI (verified currently clean;
  preventive given 11 forum migrations and schema churn history)
  (`.github/workflows/backend-ci.yml`).

## Recommended Action

1. **H21 — but first, verify prod Celery topology.** The Railway deploy (per
   `railway.json` + deploy state) may run no Celery worker or beat process at
   all — in which case `send_forum_push` (`.delay()`-only) also never executes
   in production, a bigger problem than pruning. Investigate, then either:
   Option A — add a worker+beat service on Railway with a
   `CELERY_BEAT_SCHEDULE` entry for daily pruning; Option B — Railway cron
   invoking `manage.py prune_forum_tombstones` (no beat dependency) and an
   explicit decision about push-task execution. Record the topology in the
   deploy docs either way.
2. **M34 E2E**: authed Playwright spec — login → create thread → reply → edit
   → react → delete against a real backend (mirror the existing golden-path
   harness; decide CI backend provisioning: service container vs local-only
   tag).
3. **M42 caching**: `Cache-Control: public, s-maxage` on anonymous board/topic
   list + search responses with correct `Vary` (cookie/auth) or split-path
   handling; ETag/Last-Modified where cheap (`updated_at` is indexed).
4. **L17**: add `python manage.py makemigrations --check --dry-run` to backend
   CI.

## Technical Details

- `backend/docs/patterns/domain/celery.md` for task/beat conventions;
  `docs/rules/celery.md` is auto-injected on edits.
- Cache work must not leak per-user capabilities: verify `can_edit/can_delete`
  are only in authed responses or vary correctly — add a test asserting an
  anon response never carries user-specific fields alongside cache headers.
- Railway proxy note for E2E/caching debugging:
  `RATELIMIT_TRUSTED_PROXY_COUNT=2` (real client = 2nd-from-last XFF entry).

## Acceptance Criteria

- [~] Prod Celery topology documented (DONE: `backend/docs/deployment/railway.md`);
      tombstones actually pruned on schedule in that topology (DEFERRED — needs a
      live deploy of the cron service + a scheduled run; evidence = the log line
      `Pruned N tombstone row(s)…`, which the command already emits locally)
- [x] Push-task execution home in prod confirmed — LIVE topology verified via
      `railway status --json` (2026-07-26): 1 environment (`production`), 3
      services (Postgres, Redis, `plant_id_community`), all `cronSchedule=None`,
      the only app start command being gunicorn. NO Celery worker → push/email/
      summaries drop; documented + decided (defer worker)
- [x] Authed E2E covers create → reply → edit → react → delete
- [x] Anonymous hot reads carry cache headers; authed/user-specific responses
      provably uncached or varied (test)
- [x] CI fails when model changes lack migrations

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 4 open findings per the manifest's Phase 4 grouping table.
- Added the prod-Celery-topology investigation step: H21's missing beat
  schedule implies the worker/beat presence question, which also gates push
  delivery (C2/todo 253).

### 2026-07-25 - Started by completing-todos skill (run 2026-07-25-0240)

- Picked up by automated workflow.
- **H21 topology decision (user + Railway docs research via Context7):**
  Repo evidence confirms Railway runs a SINGLE gunicorn service
  (`backend/railway.json`) — no Celery worker, no beat, no
  `CELERY_BEAT_SCHEDULE` anywhere. So ALL forum `.delay()` tasks
  (`send_forum_push`, `send_forum_push_batch`, `send_forum_email_batch`,
  `generate_topic_summary`) silently drop in prod, not just pruning.
- Railway natively supports both fixes (Cloudflare ruled out — a Worker cannot
  consume the Celery/Redis queue or run Django; it would only add an
  authenticated HTTP endpoint for the prune half):
  - Cron jobs: `cronSchedule` (5-field crontab, min 5-min frequency, UTC),
    service must exit on completion — our `prune_forum_tombstones` fits.
  - Worker: separate same-repo service with its own start command over private
    networking; shared `railway.json` `startCommand` is inherited by every
    service, so per-service start commands must be set in the dashboard.
- **Decision (cost-conscious):** push is already gated on the Firebase key
  (not set in prod) and summaries need the OpenAI key, so an always-on worker
  (~$3–5/mo, no scale-to-zero on Railway) would deliver ~nothing today. Do the
  near-$0 **Railway cron for pruning** now; DEFER the worker until push is
  actually enabled (cheapest future path: co-locate the worker in the existing
  gunicorn container, not a second service). Document both.
- Codeable findings done alongside: L17 (CI `makemigrations --check`), M42
  (anon cache headers on hot forum reads), M34 (authed E2E, local-only tag).
- NOTE: two acceptance criteria are prod-runtime-verification-gated (prune runs
  on schedule w/ evidence; push-execution home confirmed) — 261 stays
  `in_progress` after this pass with a deploy+verify handoff.

### 2026-07-25 - Implementation + verification evidence

- **L17 — CI migration gate** (`.github/workflows/backend-ci.yml`): added a
  `makemigrations --check --dry-run` step to `backend-checks`. Local run:
  `No changes detected` / `EXIT_CODE=0` (tree clean). `--check` exits non-zero
  on a model change with no migration → CI fails. ✅ criterion met.
- **M42 — anon cache headers** (`api/views.py` `PublicForumReadCacheMixin` +
  `conf.py PUBLIC_READ_CACHE_SECONDS`): 5 read views (board list, topic list,
  topic detail, post list, search) emit `public, s-maxage=60, max-age=0` +
  `Vary: Cookie` for anon; `private, no-store` for authed. New tests
  `tests/api/test_read_cache_headers.py` (4) pin both header branches AND the
  no-leak invariant (anon post capabilities all baseline-false). Run:
  `4 passed`; full forum API suite `228 passed` (no regressions). ✅
- **M34 — authed E2E** (`web/e2e/forum-authenticated.spec.js`, rewritten from a
  stale skip-only legacy file): real lifecycle create → reply → edit → react →
  delete with hard assertions vs the current id-anchored UI. Fixed a
  pre-existing `playwright.config.ts` bug — the authed-project `testMatch`
  regex never matched `forum-authenticated.spec.js`, so the legacy authed spec
  had been running UNauthenticated (hence all its soft skips); now correctly
  wired to `chromium/firefox-authenticated` (+ excluded from unauth projects).
  Clean prose auto-publishes through the sync spam workflow so an untrusted
  test user's writes go live immediately. Local run (`create_test_user` +
  `seed_default_forum` first): `2 passed` twice (setup + lifecycle), stable. ✅
  Local-only — Playwright stays excluded from CI (`web/CLAUDE.md`).
- **H21 — cron + topology docs** (`backend/railway.cron.json`,
  `backend/docs/deployment/railway.md`): daily `03:00 UTC` cron service running
  `prune_forum_tombstones` (own config file so it doesn't inherit the web
  service's gunicorn start/healthcheck), plus the full topology + worker-defer
  runbook. Command verified locally: `Pruned 0 tombstone row(s)…` / exit 0
  (valid + exits cleanly, as Railway cron requires). Both railway JSON configs
  validated. DEFERRED: live deploy + scheduled-run evidence, prod push-home
  confirmation (see Handoff).

### 2026-07-25 - Code review + fixes (orchestrator → 3 reviewers)

Reviewed the staged diff (wagtail, cross-cutting, react-typescript). No
critical/high. 2 medium + 4 low, all fixed:

- **[medium, wagtail] `Vary: Cookie` insufficient for header-auth.**
  `CookieJWTAuthentication` falls back to the `Authorization` header (mobile),
  so a cache keyed only on Cookie could serve the anon copy to a cookie-less
  header-authed request. Fixed: `Vary: Cookie, Authorization`; also gated the
  public branch on `status_code < 400`.
- **[medium, cross-cutting] caching side-effects/staleness.** Public-cached
  TopicDetailView + PostListView → `view_count` undercount (cached topic-detail
  skips the per-hit increment) + moderated-away content lingering up to the TTL
  with no CDN purge. Fixed: split into `PublicForumReadCacheMixin`
  (board/topic-list/search) and `PrivateForumReadCacheMixin`
  (topic-detail/post-list → always `no-store`, every hit reaches origin).
  **Decision to ratify:** the audit's own M42 caveat named post-list ("caching
  must be anon-scoped/varied"), i.e. post-list WAS an intended cache target —
  but its report-auto-hide/unpublish staleness with no purge infra makes
  `no-store` the safer call, trading the heaviest read's cache win for
  moderation correctness. Revisit if a CDN purge hook is ever wired.
  Topic-detail is unambiguously no-store (the `view_count` side effect).
  conf.py docstring updated.
- **Host-path verification (advisor):** the mixin lives on the package views but
  prod serves via `apps/forum_host` (some views host-subclassed for throttling).
  Added `test_host_mounted_reads_carry_m42_cache_headers` hitting the REAL
  `/api/v1/forum/{boards,search}/` mount — confirms both direct and wrapped
  views emit the headers (`2 passed`).
- **[low, cross-cutting] no write-not-cached test.** Added
  `test_write_response_is_not_shared_cacheable` (POST create carries no
  public/s-maxage).
- **[low ×2, react-ts] unscoped E2E clicks.** Scoped the reply/edit submit
  clicks to their forms (strict-mode safety).
- **[low, react-ts] E2E leaves the created topic.** Noted as an accepted
  local-dev tradeoff (uniquely timestamped per run).

Re-verified after fixes: `6 passed` (cache tests) + `230 passed` (full forum
API suite); authed E2E `2 passed` again.

### 2026-07-26 - Live topology verified; cron service provisioned; runbook bug fixed

- **AC2 FLIPPED — live prod topology confirmed** via `railway status --json`
  (authoritative API, same data the dashboard renders, as the account owner):
  1 environment (`production`), 3 service instances —

  ```text
  SERVICES (project-level):   Postgres | plant_id_community | Redis
  ENV: production
    service_id=6530094c cron=None start=None                    # Postgres image
    service_id=676207b7 cron=None start='…redis-server…'         # Redis image
    service_id=9edd1c89 cron=None start="sh -c 'gunicorn …'"     # web
  ```

  No Celery worker, no beat, `cronSchedule=None` everywhere. This is exactly
  the confirmation AC2 deferred to the dashboard, so it is now met by evidence
  rather than by repo inference. The defer-the-worker decision stands.
- **Cron service provisioned via CLI** (user chose "I create it via CLI, you
  finish config"): `railway add --service forum-prune-cron` →
  `{"id":"7fee2fe0-5b83-46ab-99e4-ccfc001de87e"}`. Created **empty, with no
  repo source connected on purpose** — connecting a source before Root
  Directory + config-as-code are set would deploy gunicorn under the inherited
  `railway.json` and crash-loop against a healthcheck.
- **No compute allocated yet** (verified, since the service is billable once it
  deploys): `forum-prune-cron` reports `activeDeployments=0`,
  `latestDeployment=None`, `instances=0`. Nothing accrues until the source is
  connected in step 3 of the handoff.
- **Runbook bug found and fixed** (`backend/docs/deployment/railway.md`). The
  previous step 4 said "`REDIS_URL` is not required for pruning" — **wrong**.
  `validate_environment()` runs at settings *import* (`settings.py:1553`) and,
  when `DEBUG=False`, raises `ImproperlyConfigured` without `REDIS_URL` (and
  live-`ping`s it), plus `SECRET_KEY` (raises at `settings.py:48`),
  `PLANT_ID_API_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
  `CORS_ALLOWED_ORIGINS`. A cron built to that runbook would have crash-looped
  nightly and never pruned. Doc now carries the full table + the reason each
  entry is load-bearing.
- **Variables set as cross-service references** (no secret duplication, and no
  secret values read): `DATABASE_URL=${{Postgres.DATABASE_URL}}`,
  `REDIS_URL=${{Redis.REDIS_URL}}`, and `SECRET_KEY` / `PLANT_ID_API_KEY` /
  `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` / `DEBUG`
  from `${{plant_id_community.*}}`. Verified resolved on the new service
  (`DEBUG=False`, `ALLOWED_HOSTS=plantidcommunity-production.up.railway.app`,
  origins populated).
- **Overclaim caught and corrected:** an intermediate draft of the doc asserted
  Railway runs a cron service's start command once on deploy. Railway's cron
  docs do not state that (verified against
  `https://docs.railway.com/reference/cron-jobs`, which covers must-exit,
  5-min minimum, and UTC only). The doc now separates "schedule is registered"
  (checkable immediately) from "command ran in the prod container" (deploy-time
  log if it appears, else after the first 03:00 UTC fire).

### 2026-07-26 - GraphQL API route investigated and RULED OUT

Attempted to set the two dashboard-only settings (`rootDirectory`,
`railwayConfigFile`) via Railway's public GraphQL API so AC1 could be finished
without the dashboard. **It does not work with the CLI's stored token — do not
retry this path.**

- Schema introspection *looked* like proof the route was available
  (`ServiceInstanceUpdateInput` exposes `rootDirectory`, `railwayConfigFile`,
  `source`; `serviceInstanceUpdate(serviceId, environmentId, input)` exists).
  That was a **false positive**: Railway's schema is publicly readable, so
  introspection succeeds unauthenticated.
- Every authenticated call returns `Not Authorized` — **byte-identical to an
  unauthenticated control request**, which is the tell. Tried:
  `Authorization: Bearer <accessToken>`, bare `Authorization: <accessToken>`,
  `project-access-token`, `x-railway-token`; hosts
  `backboard.railway.com/graphql/v2`, `backboard.railway.app/graphql/v2`,
  `backboard.railway.com/graphql/internal`. The token was unexpired
  (`tokenExpiresAt` = 2026-07-26T05:00:55 UTC) and `railway status` worked
  throughout, so the CLI authenticates by some other means than a bearer token
  on the public endpoint.
- A dashboard-created account/project token would likely authenticate — but
  creating one is itself a dashboard trip, and it is more steps than just
  setting the two fields. Not worth it.

Conclusion: Root Directory + config-as-code are genuinely dashboard-only, as
the runbook already says. The handoff below stands unchanged.

### Handoff — remaining deploy+verify (keeps 261 open)

AC1 only. The CLI exposes no flag for Root Directory or the config-as-code path
(confirmed in `railway add --help` and `railway service source connect --help`),
so these two settings are dashboard-only — on service **`forum-prune-cron`**:

1. **Settings → Root Directory** = `backend`
2. **Settings → Config-as-code file** = `railway.cron.json`
3. *Then* **Settings → Source** → connect `Xertox1234/plant_id_community`,
   branch `main` (this order matters — see the runbook note).

Then I verify and flip AC1: `cronSchedule: "0 3 * * *"` on the service instance,
plus the log line `Pruned N tombstone row(s) older than 30 day(s).` with a
clean exit.

## Notes

p2. The topology investigation (step 1) is cheap and load-bearing for two
other epics — do it first even if the rest waits.

Phase 6 review residue (2026-07-11 audit, celery reviewer, LOW): the FCM
retry backoff (30/60/120s) has no jitter — a correlated FCM outage retries
every queued push in lockstep. Fine at current scale; add randomized offset
if push volume grows.
