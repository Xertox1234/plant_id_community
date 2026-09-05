---
status: in_progress
priority: p2
issue_id: "335"
tags: [forum, celery, ops, deploy, railway, notifications]
dependencies: []
source_review: "docs/audits/2026-09-04-forum.md"
source_finding: "H1"
---

# Provision the Celery worker (or stop enqueuing) — five forum tasks have no consumer

## Problem

No Celery worker exists in any tracked deploy config **or** in the live Railway
project, yet five forum tasks are enqueued with `.delay()` on shipped request
paths. Reply/mention/moderation pushes and reply emails never send, a premium
`GET topics/<id>/summary/` returns `202 pending` forever, and the enqueued
messages sit in the Redis broker list with no TTL. The todo-261 decision to
defer the worker "until push/email/summaries are actually turned on" went stale
once `OPENAI_API_KEY` went live for the spam backend (todo 280) — nothing ever
revisited it.

## Findings

- `backend/railway.json:8` — `startCommand` is gunicorn only; `backend/Dockerfile:66`
  `CMD` is gunicorn only; `backend/railway.cron.json` runs only
  `prune_forum_tombstones`. No Procfile / supervisor / second service anywhere.
- Live Railway project `PlantID Community` (checked 2026-09-04 via the Railway
  MCP `list-services`): exactly `plant_id_community` (web), `Postgres`, `Redis`,
  `forum-prune-cron`. No worker.
- `backend/plant_community_backend/settings.py:1101` — `CELERY_TASK_ALWAYS_EAGER`
  defaults `False`; nothing overrides it in prod.
- Enqueue sites: `apps/forum_host/notifications.py:119,144,160,278,320`
  (`send_forum_push`, `send_forum_push_batch`, `send_forum_email_batch`),
  `apps/forum_host/summary.py:116` (`generate_topic_summary`),
  `apps/forum_host/signals.py:74` (`sync_blog_page_chunks`, dark behind
  `FORUM_RAG_ENABLED`).
- `backend/docs/deployment/railway.md:110-133` documents the deferral and its
  trigger condition; `:233-240` carries the "Add the worker later" runbook.
- Celery docs (Phase 2.5 research): a published message has no expiry unless
  `expires` / `task_default_expires` is set; `visibility_timeout` only matters
  once a worker has fetched; nothing is written to the result backend at enqueue
  time. Railway Redis memory is flat at ~12 MB over the last 7 days, so the
  backlog is not a visible cost **today** at current forum traffic.
- Impact is bounded: in-app bell notifications are created synchronously
  (unaffected); no web or mobile client calls the summary endpoint (grep clean);
  push is gated on `FIREBASE_CREDENTIALS_PATH` and email on `EMAIL_HOST`, whose
  prod values were not inspected in the audit.
- Found by `celery-async-reviewer` during the 2026-09-04 forum audit; rated
  Critical by the agent, recorded High for the reasons above.

## Proposed Solutions

### Option 1: Co-locate the worker in the web container (Recommended by the runbook)

- **Implementation:** per `backend/docs/deployment/railway.md:233-240`, run
  `celery -A plant_community_backend worker --loglevel=info --concurrency=2`
  alongside gunicorn (a process manager or `celery … worker &` in the start
  command). Same image, same env — no config drift.
- **Pros:** near-zero extra cost (the container is already funded 24/7); one
  service to watch.
- **Cons:** worker and web share CPU/memory; a runaway task can starve requests.
- **Effort:** 1–2 hours incl. a deploy and a live check.
- **Risk:** low — every task already declares retry/idempotency (M8/L3 fixed in
  the audit PR); nothing destructive runs.

### Option 2: A second Railway service

- **Implementation:** same repo + root directory, custom start command
  `celery -A plant_community_backend worker …`; must carry the same env
  (`USE_R2` parity note in CLAUDE.md applies).
- **Pros:** independent scaling and restarts.
- **Cons:** ~$3–5/mo always-on; a second env surface to keep in sync.
- **Effort:** 1–2 hours.
- **Risk:** low.

### Option 3: Keep deferring, but make the gap honest

- **Implementation:** gate `TopicSummaryView` behind a `FORUM_SUMMARY_ENABLED`
  flag (503 `code: disabled` like RAG), and short-circuit `dispatch()`'s push /
  email enqueues when no worker is configured, so nothing is queued into the
  void.
- **Pros:** zero spend.
- **Cons:** three shipped features stay inert; adds flag surface for a state we
  do not actually want.
- **Effort:** 1 hour.
- **Risk:** low.

## Recommended Action

1. Decide Option 1 vs 2 (an ops/spend call — not for an automated run).
2. Confirm the prod values of `FIREBASE_CREDENTIALS_PATH` and `EMAIL_HOST`; a
   worker delivers push/email only if those are set.
3. Add the worker per the runbook; deploy; watch `celery inspect active` /
   Railway logs for the first `reply_added` fan-out.
4. Drain the accumulated backlog deliberately: `LLEN celery` on the prod Redis
   first — a large stale queue will fire old pushes/emails the moment the worker
   starts. Purge (`celery -A plant_community_backend purge`) if it is not
   trivially small. Note: `ignore_result` is baked into each message at
   enqueue time, so backlogged messages produced before the audit PR still
   carry `ignore_result: False` and will write a (1-day-expiring) result row
   each when first consumed — expected, not a sign the L3 fix missed.
5. Update `backend/docs/deployment/railway.md:110-133` (the "no worker" topology
   statement and the deferral section) and close the "Add the worker later"
   heading.

## Technical Details

- Tasks: `backend/apps/forum_host/tasks.py` — `send_forum_push` (bind, manual
  30/60/120 s backoff), `send_forum_push_batch` / `send_forum_email_batch`
  (`autoretry_for=(OperationalError,)`, factor 30 after audit M8),
  `generate_topic_summary`, `sync_blog_page_chunks`. All `ignore_result=True`
  after audit L3.
- Broker/result: `settings.py:1093-1101` — `CELERY_BROKER_URL` defaults to
  `REDIS_URL` db 1; result backend = broker.
- Related: todo 261 (archived, the original deferral), todo 280 (spam backend
  live), todo 330 (RAG enablement — `sync_blog_page_chunks` needs the worker too).

## Acceptance Criteria

- [ ] A worker process consumes the `celery` queue in production (visible in
      Railway logs / `celery inspect ping`), or Option 3 is implemented and the
      enqueue sites no-op without a worker.
- [ ] A reply on a subscribed topic in prod produces a `send_forum_push_batch`
      execution in the worker log (push delivery itself still depends on the
      Firebase key).
- [x] The pre-existing backlog was measured (`LLEN`) and either drained or
      purged deliberately, with the count recorded in the work log.
- [ ] `backend/docs/deployment/railway.md` no longer describes a worker-less
      topology as current.

## Work Log

### 2026-09-04 - Filed from the forum audit

- Forum audit (`docs/audits/2026-09-04-forum.md`) finding H1. Deferred per the
  user's instruction ("fix all the mediums and lows, file H1 as a todo") because
  the fix is a deploy-topology and spend decision, not a code change. The two
  code-side prerequisites (M8 backoff factor, L3 `ignore_result`) shipped in the
  audit PR.

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-0250)

- Picked up by automated workflow on the user's "pick up todo 335".
- Decision (user, via AskUserQuestion): **Option 1 — co-locate the worker in
  the web container**; **purge** the stale backlog before the worker starts.
- Pre-work facts (read-only probes, 2026-09-05 ~02:55 UTC):
  - Prod env: `EMAIL_HOST=smtp.resend.com` with `EMAIL_HOST_USER`/`PASSWORD`
    set (email IS live); `FIREBASE_CREDENTIALS_PATH` unset (push inert);
    `OPENAI_API_KEY` set; `CELERY_BROKER_URL` unset → `REDIS_URL` (no db
    path → db 0, shared with the cache).
  - Web container cgroup: `cpu.max 2400000 100000` (24 vCPU), `memory.max`
    24 GB, `memory.current` 451 MB — co-location has ample headroom.
  - Backlog: `LLEN celery` = **429**, `unacked` = 0, broker `used_memory`
    2.15M. By task: `send_forum_push_batch` 209, `send_forum_email_batch`
    208, `send_forum_push` 12; every message carries `ignore_result: False`
    (all pre-audit); oldest is `moderation_decided` for topic 1, newest
    `moderation_decided` for topic 42 / obj 285. Nothing worth delivering.

### 2026-09-05 - Implemented Option 1 (branch `feat/todo-335-celery-worker`)

- `backend/bin/start.sh`: gunicorn + `celery -A plant_community_backend worker
  --loglevel=info --concurrency=${CELERY_CONCURRENCY:-2} --max-tasks-per-child=500`
  as siblings via `bash -c`; SIGTERM/SIGINT forwarded to both (exit 0); if
  EITHER child exits on its own — even status 0 — the other is stopped and the
  script exits 1 so Railway's `ON_FAILURE` restarts the container.
- `backend/railway.json` `startCommand` → `bash bin/start.sh`; Dockerfile CMD
  comment updated (CMD itself stays gunicorn-only for bare `docker run`).
- `settings.py`: `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True` so a worker
  booting before Redis answers retries instead of tripping the coupling.
- `backend/bin/test-start.sh` (12 cases, pid-file based — the slim image has no
  `pgrep`), wired into `.github/workflows/backend-ci.yml` after the Django
  system checks. Local bash is 3.2 (no `wait -n`), so it ran in Docker on
  `python:3.13-slim` (bash 5.2.37, the prod base image):

  ```text
  PASS: start.sh parses
  PASS: web crash -> exit 1
  PASS: worker child stopped after the web crash
  PASS: web crash status is logged
  PASS: clean worker exit -> exit 1
  PASS: web child stopped after the worker exit
  PASS: both children running before SIGTERM
  PASS: SIGTERM -> exit 0
  PASS: both children stopped on SIGTERM
  PASS: start line announces both pids
  PASS: defaults honour PORT and CELERY_CONCURRENCY
  PASS: defaults name the real worker and web commands
  test-start: all cases passed
  ```

- Mutation check (three broken copies of `start.sh`, same Docker image):
  no crash coupling → `web crash -> expected exit 1, got TIMEOUT` +
  `worker child survived`; `kill -TERM` removed → the same two plus the
  SIGTERM case; `--concurrency=2` hard-coded → `defaults wrong: …`. All three
  fail the test; the shipped script passes.
- Worker boot smoke with the exact default command against dev Redis
  (`venv/bin/celery … --concurrency=1`, 12 s, then SIGTERM): registered all
  five `apps.forum_host.tasks.*`, `Connected to redis://127.0.0.1:6379/1`,
  `celery@… ready.`, exit 0. `python manage.py check`: no issues.
- `backend/docs/deployment/railway.md`: topology statement, "Operating the
  worker" (ping, queue depth, purge, sizing, second-service note) and a
  History section replace the todo-261 deferral text and "Add the worker
  later".

### 2026-09-05 - Review round (celery-async-reviewer) and the restart budget

- Reviewer HIGH (accepted): plain crash coupling let a worker-only crashloop
  spend `restartPolicyMaxRetries: 5` — a budget shared with the web tier — and
  exhausting it stops the whole service. `start.sh` now restarts the worker
  in-container (`WORKER_MAX_RESTARTS` 5, `WORKER_RESTART_DELAY` 5 s, each
  logged) while gunicorn keeps serving, and only escalates to exit 1 past the
  budget; a gunicorn exit still escalates immediately. Self-test grew to 20
  cases (single worker crash → restarted, web survives; crashloop → exit 1
  after the budget with the count logged; SIGTERM during the delay → prompt
  exit 0). All pass on `python:3.13-slim`; mutation check with four mutants
  (web death not escalated / worker never restarted / budget never counted /
  SIGTERM not forwarded) — each fails the test.
- Reviewer MEDIUM (accepted, config): Railway's SIGTERM→SIGKILL draining time
  defaults to **0 s** (deployment-teardown docs), so a warm shutdown never
  finished. `railway.json` gains `drainingSeconds: 60`; settings gain
  `CELERY_WORKER_PREFETCH_MULTIPLIER = 1` (early-ack tasks strand at most one
  reserved message per pool process on a hard kill; `acks_late` deliberately
  not added — a redelivered email batch would double-send, `docs/rules/celery.md`).
- Reviewer MEDIUM (accepted, ops): broker shared Redis db 0 with the Django
  cache, and django-redis `cache.clear()` is an unscoped `FLUSHDB`. Fix is the
  web-service variable `CELERY_BROKER_URL=${{Redis.REDIS_URL}}/1`
  (`--skip-deploys`, so it lands with the worker deploy).
- Reviewer MEDIUMs (documented): the healthcheck never sees the worker; a
  worker-only `control shutdown` is now a 5 s in-container restart, not an
  outage. Runbook "Operating the worker" carries both.
- **Blocked by the auto-mode classifier** (twice): the prod `celery purge -f`
  and the `railway variables --set` call. Handed to the user to run; the
  verification probes (LLEN, variable shape) stay with this session.

### 2026-09-05 - Review round 2 (cross-cutting-reviewer): 3 medium, 4 low, none blocking — all applied

- `start.sh` had no bash guard: on bash 3.2 `wait -n PID...` fails as an
  invalid option and the script would log it as "a child exited" and kill both
  healthy children. Guard added, and the threshold corrected to **5.1** (the
  pid-list form of `wait -n` is 5.1+; 4.3–5.0 silently wait for ANY job).
  Proven: `/bin/bash bin/start.sh` on this Mac (3.2) now refuses with the
  message and exit 1.
- Case 3 was hollow on the budget boundary: `>=` → `>` (one extra restart)
  still passed. Added an exact-count assertion; the `>` mutant now fails with
  `expected exactly 2 restart lines, got 3`.
- Overclaims fixed: "tasks ack early" now names the `sync_blog_page_chunks`
  `acks_late=True` exception (settings comment + runbook); the header no
  longer claims SIGINT parity with the suite; the CI step comment describes
  the asymmetric gunicorn/worker handling; the runbook's sizing bullet counts
  Postgres connections per prefork child (`CONN_MAX_AGE` 600 s, todo 331).

### 2026-09-05 - Backlog purged (user ran the command; classifier blocked this session)

- Measured `LLEN celery` = 429 at ~02:53 UTC (composition in the first entry);
  re-measured 429 immediately before the purge.
- `railway ssh -- celery -A plant_community_backend purge -f` →
  `Purged 429 messages from 1 known task queue.`
- Read-only re-check afterwards: `LLEN celery AFTER purge: 0 | unacked: 0`.

### 2026-09-05 - Broker moved to Redis db 1 (user ran the command; `--skip-deploys`)

- `railway variables --set 'CELERY_BROKER_URL=${{Redis.REDIS_URL}}/1' --skip-deploys`
  on the web service. Read-only check of the resolved value: same host/port as
  `REDIS_URL`, path `/1`, and `CELERY_BROKER_URL == REDIS_URL + "/1"` → True.
  Takes effect with the worker deploy (the running container still sees db 0,
  which is now empty).

## Notes

p2: three shipped features are silently inert in production, but nothing is
lost that a user was promised in-app (the bell works), no data is corrupted,
and the Redis backlog is not yet a measurable cost. Promote to p1 the day
push or email is announced to users.
