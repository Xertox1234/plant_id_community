---
status: pending
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
- [ ] The pre-existing backlog was measured (`LLEN`) and either drained or
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

## Notes

p2: three shipped features are silently inert in production, but nothing is
lost that a user was promised in-app (the bell works), no data is corrupted,
and the Redis backlog is not yet a measurable cost. Promote to p1 the day
push or email is announced to users.
