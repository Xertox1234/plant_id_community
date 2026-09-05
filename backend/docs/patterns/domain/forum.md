# Forum Patterns (wagtail_forum)

**Last Updated**: 2026-06-21
**Status**: Accurate for the Wagtail-native forum (post machina retirement, PR #362)

> The previous version of this doc described the **retired** `apps/forum_integration/`
> system (`TrustLevelService`, `SpamDetectionService`, `warm_moderation_cache` — none
> of which exist anymore). It is archived at
> `docs/archive/forum-patterns-trust-spam-pre-wagtail.md`. This doc points to the live
> sources rather than re-documenting them, so it can't rot the same way.

## Where the forum lives

The forum is a reusable, Wagtail-native package — no django-machina, no
`forum_integration` (both fully retired in PR #362):

- **`backend/packages/wagtail_forum/`** — the package. Boards are Wagtail **Pages**;
  topics and posts are feature-rich **snippets** (moderation workflow, revisions,
  locking, search). The package core imports nothing host-specific — it uses
  `settings.AUTH_USER_MODEL`, never a concrete user model.
  - `spam/` — pluggable spam detection (`base.py` interface, `heuristic.py` default).
  - `models/moderation.py` — moderation state + actions.
  - `api/` — optional headless DRF API: `serializers.py`, `views.py`, `urls.py`,
    `pagination.py`, `idempotency.py`, `exceptions.py`. **Body HTML is sanitized
    through `api/sanitize.py`** before storage.
  - `tests/` — `test_spam.py`, `test_moderation_task.py`, and the rest of the suite.
- **`backend/apps/forum_host/`** — the host integration: rate-limit wrappers
  (`api.py`), route mounting (`api_urls.py`), and host settings. Throttling lives
  here by design (the package is host-agnostic).
- **`backend/apps/forum/management/`** — management commands (e.g. `seed_default_forum`).

## Authoritative references (read these, not this file)

- **Package overview**: `backend/packages/wagtail_forum/README.md`.
- **Binding rules** (auto-injected before forum edits): `docs/rules/forum.md` — the
  compact always/never checklist (numeric-default footgun, savepoint-on-`IntegrityError`,
  `Ratelimited` carries no `.rate`, forum is always-on, etc.).
- **Spam / moderation / API contracts**: the package modules above and their tests
  are the source of truth — prefer reading them over any prose summary.

## Key invariants (full list in `docs/rules/forum.md`)

- **The forum is always-on** — the `ENABLE_FORUM` flag was a dead no-op and was
  removed (PR #371). Do not re-introduce a gate without wiring `INSTALLED_APPS` +
  URL mounting + CI.
- **Host applies throttling, package does not** — rate limits are `forum_host`
  wrappers; a route-parity test fails if the host doesn't mount a new package route.
- **Idempotency** for write endpoints follows `api/idempotency.py` (hash the
  user key, scope by endpoint+user, replay the original status, `cache.add()` an
  in-flight sentinel → 409 on concurrent twins).
- **Visibility**: filter page querysets with `.live().public()`; gate child-object
  queries via the visible-board set (`PageViewRestriction` is not auto-enforced in
  custom views/APIs).

## Moderation permission scope is global, deliberately (audit M19)

Moderation is one flat `"Forum Moderators"` group (`apps/forum_host/bootstrap.py`)
with `change_topic`/`change_post` etc. — there is no per-board moderator concept.
This is a **deliberate decision, not an oversight**:

- `Topic`/`Post` are snippets, not Pages — Wagtail's `GroupPagePermission` (which
  `ForumBoard`, itself a Page, could otherwise use) has no snippet analog. A
  board-scoped check would mean a new group↔board mapping model consulted from
  every permission check site (`Post.edit_block`/`delete_block`,
  `_edit_is_trusted`'s `acting_as_moderator`, the bulk-unpublish action's
  `check_perm`, the SnippetViewSet permission gate) — high blast radius through
  security-critical code.
  - `seed_default_forum` creates exactly one board. There is no product signal
    (no second board, no request for delegated moderators) that justifies that
    blast radius today (YAGNI, root `CLAUDE.md`).
- **Revisit trigger**: when a second board ships AND it needs a moderator distinct
  from the global group, design the group↔board mapping then, against a real
  requirement instead of a speculative one.

## Image blocks are scoped to an allowed-uploader set, not just collection membership (audit L21)

The forum image collection (`collections.get_forum_image_collection()`) is a
single shared collection across every member — collection-membership alone
(audit L5's IDOR-by-reference fix) stops a body from referencing an image
outside the forum entirely, but does **not** stop one member from embedding
another member's upload, since Wagtail's own `Image.uploaded_by_user` was
recorded at upload time but never checked.

`api/sanitize.py::validate_forum_body(value, allowed_uploader_ids)` now takes
a required second argument: the set of user ids (a `None` member is legal —
see below) whose uploads may be referenced. The three write serializers
(`_ForumBodyContract` in `api/serializers.py`) compute this per request:

- **Create** (`TopicCreateSerializer`/`ReplyCreateSerializer`): just the
  acting `request.user` — no post exists yet.
- **Edit** (`PostEditSerializer`): `request.user` **plus** the post's
  pre-existing `author_id` (passed via `context={"existing_author_id": ...}`
  at the view call site). PATCH resends the *entire* body — a moderator
  editing someone else's post while keeping the author's existing image
  blocks must not have them rejected just because the editor changed.

**`None` is a legal member of `allowed_uploader_ids`**, and it is handled with
an explicit `Q(uploaded_by_user_id__isnull=True)` branch, *not*
`uploaded_by_user_id__in={..., None}` — SQL's `IN (NULL)` is never true, even
for a row whose value actually is `NULL` (caught by a test before this ever
reached review). `None` matters because Wagtail's `Image.uploaded_by_user` and
`Post.author` both go `SET_NULL` together on account deletion — a deleted
author's pre-existing images grandfather in automatically without any special
casing, since `existing_author_id` is already `None` in that case.

The moderator-edit carve-out is intentionally narrow: it grandfathers the
POST's existing author, not "any image a privileged user chooses" — a
moderator cannot smuggle in a *different*, unrelated member's image while
editing someone else's post (pinned by
`test_moderator_edit_cannot_smuggle_in_a_different_members_image`).

## Unified author contract + settable avatar (todo 257 H26/M41)

Every author a client sees — a topic's `author`, its `last_post_author`, a post's
`author`, a notification's `actor` — serializes through the SINGLE helper
`serialize_forum_author(user, request)` in `api/serializers.py`. It returns one
object shape `{username, display_name, avatar, trust_level}`, and a deleted author
(`user is None`) is the `[deleted]` sentinel OBJECT, never `null` and never a bare
string. Before this, topics sent a username string (null when deleted) while posts
sent a rich object with a partial `[deleted]` dict — two shapes for one concept.

Three things make it correct and cheap:

- **Pin-flatness by nested `select_related`.** The helper reads the profile via the
  reverse OneToOne (`getattr(user, "wagtail_forum_profile", None)`) and the avatar
  via the FK. The list/detail views join the whole chain —
  `select_related("author__wagtail_forum_profile__avatar", ...)` — so those reads
  are LEFT JOINs already materialized in the page query, NOT per-row SELECTs. The
  query-count pins stay flat under N distinct authors (see query-optimization.md
  Pattern 30). Gate on `profile.avatar_id` (the loaded FK column) before touching
  `.avatar`, so the no-avatar case never issues a query.

- **Avatar is the raw `.file.url` (absolute via `request.build_absolute_uri`), NOT a
  rendition.** Inline body images use `serialize_image_for_api` renditions, but a
  `get_rendition()` per author would add a SELECT and break the flat pin. Avatars
  trade image-fidelity for pin-flatness — a conscious, documented tradeoff.

- **Settable avatar is IDOR-scoped like inline images.** `MeProfileSerializer` takes
  a write-only `avatar_id`; `validate_avatar_id` accepts it only if the image was
  `uploaded_by_user=<caller>` AND lives in `get_forum_image_collection()` — the same
  two-part membership check that gates inline images (the L21 pattern above). A bare
  id is never trusted; `None` clears the avatar with no ownership check.

`last_post_author` is the one field that returns `null` (not the sentinel) for a
deleted last-poster: the denormalized Topic fields can't tell "no posts yet" from
"last poster's account gone" without a live-post existence query that would break
the pin. See `docs/LEARNINGS.md` 2026-07-24.

## Public read-only profile endpoint (todo 257 H7)

`GET /forum/users/<username>/` (`PublicProfileView`, `AllowAny`) returns a user's
public identity + recent activity. Four load-bearing rules:

- **Read the profile via `getattr(user, "wagtail_forum_profile", None)`, NEVER
  `ForumProfile.for_user()`** — `for_user` get-or-CREATEs, so a public endpoint
  hitting it for an arbitrary username would write a row per probe. A
  real-but-profileless user serializes to defaults (like `serialize_forum_author`);
  only a **missing OR inactive** user 404s (`get_object_or_404(..., is_active=True)`).
- **Never expose `fcm_token` (a credential) or `flags_received` (a
  moderation-proximity signal, audit L12)** — build the response dict field-by-field,
  don't dump the model. Pin a `..._never_leaks_...` test.
- **Build recent-activity as lightweight dicts, NOT `PostSerializer` /
  `TopicListSerializer`.** The heavy serializers would recompute `reacted` for the
  *profile user* (meaningless — it's the viewer's state that matters) and re-trigger
  the body/author N+1s. Lightweight dicts keep the pin at ~4 (user+profile+avatar
  join, the `.public()` restriction lookup, one topics query, one posts query — the
  `board__in=_visible_boards()` subqueries inline). Filter recent activity by
  `_visible_boards()` + `live=True` (+ `topic__live=True` for posts) and pin BOTH the
  `live=False` and the restricted-board (PageViewRestriction) exclusions.
- **Single-source identity via `serialize_forum_author(user, request)`** then spread
  in bio/signature/post_count/joined_at — same absolute-URL avatar as posts.

## LLM spam backend (optional, host-side — todo 255 slice 2 / H13)

The package ships one spam check (`HeuristicSpamBackend`: banned words + link
count) and a one-setting swap, `WAGTAILFORUM_SPAM_BACKEND`. `apps/forum_host/`
adds `LLMSpamBackend` (`apps/forum_host/spam.py`), a **heuristic-first
composite** that screens what the heuristic passes through `generate_ai_text()`.
It ships **dormant** — the default stays the heuristic backend.

`check()` runs synchronously inside the moderation workflow's
`@transaction.atomic` publish path, so the LLM call is bounded by a hard
wall-clock timeout (`SPAM_LLM_TIMEOUT_SECONDS`, a `ThreadPoolExecutor` +
`future.result(timeout=…)`). Three deliberate, distinct postures:

- **Provider failure** (timeout / exception / unparseable reply) → **fail
  closed**: returns a rejected `SpamResult` so the post follows the same
  reject → pending-draft path a heuristic flag takes (a normal `reject`, not a
  raise — a raise would roll the workflow back into a limbo draft with no
  moderation-queue entry). Matches `workflow.py`'s "FAIL CLOSED" posture.
- **Forum AI budget exhausted** (`SPAM_LLM_BUDGET_LIMIT`) → **degrade to
  heuristic** (publish): a cost decision, not an outage.
- **Attempts cap tripped** (`SPAM_LLM_ATTEMPTS_LIMIT`, todo 280) → **fail
  closed**, and stop calling the provider entirely: sustained misbehaviour, so
  spend must stop without ever reaching the publish posture.

Definitive `CLEAN`/`SPAM` verdicts are cached in Redis by
`sha256(text)` + prompt version; transient failures are never cached. All
tunables live in `apps/forum_host/constants.py` (`SPAM_LLM_*`).

### Keeping the postures independent (todo 274 / H13, todo 280)

The postures above only stay distinct because **budget is consumed after the
provider answers, never before**. `AIRateLimiter.check_global_limit()`
check-and-increments in one step, so every *failed* attempt still burned
budget: a sustained outage exhausted the cap in `GLOBAL_LIMIT` failures and
flipped the backend from fail-closed (hold) to degrade-to-heuristic (**publish
LLM-unscreened**) — a spam-publishing posture reached purely by the provider
being down, and a sticky one, since every increment re-stamped the 1h TTL.

Four rules hold this together, and they must hold *together*:

1. **Peek, then consume — and only for a definitive verdict.**
   `AIRateLimiter.peek_budget(key, limit)` is read-only; `consume_budget(key,
   limit)` runs inside `_parse()`, on the `CLEAN`/`SPAM` branches only. Every
   failure mode — timeout, provider error, **and an unparseable reply** —
   returns before that line, so no provider-side failure can burn the cap.
   Unparseable is the non-obvious one: those verdicts are deliberately not
   cached, so each retry re-calls the provider, and counting them would let a
   provider stuck emitting garbage drain the budget into publish-unscreened.
   Spend during such an incident is one call per post submission — the same
   rate as healthy operation, so the cap is not protecting anything there.
   Bounding *that* is the attempts counter's job (item 4).
2. **A forum-private counter.** `SPAM_LLM_BUDGET_CACHE_KEY`
   (`ai_rate_limit:forum_spam`) is separate from the blog's shared
   `ai_rate_limit:global`, so neither subsystem can starve the other's quota and
   the forum's degrade threshold is not moved by blog traffic.
3. **An inner provider deadline.** `future.result(timeout=…)` bounds only the
   *caller*; a submitted future cannot be cancelled once running. The same
   deadline is therefore also passed to `generate_ai_text(..., timeout=…)`,
   which forwards it as a completion kwarg to the provider SDK, so a hung
   provider unblocks the worker instead of parking it. Without it,
   `SPAM_LLM_MAX_WORKERS` hung calls park the whole pool with no recovery.
4. **A separate attempts counter for the spend rule 1 leaves uncounted**
   (todo 280). `SPAM_LLM_ATTEMPTS_CACHE_KEY` (`ai_rate_limit:forum_spam_attempts`)
   is incremented in `_call_llm()`, immediately before `submit()`, for **every**
   call issued — timeouts and unparseable replies included. A
   `future.result()` expiry means the request *was* issued and is billed; the
   caller merely stopped waiting. Without this the verdict cap bounds spend
   exactly when spend is well-behaved and stops bounding it when the provider
   misbehaves. Three things about it are load-bearing:
   - It trips the **opposite** posture: exhausted attempts → **hold**, never
     the publish-degrade. Counting failures on the *verdict* counter instead is
     the sticky fail-open this whole section removed —
     `test_sustained_outage_burns_nothing_and_never_flips_to_publish` guards it.
   - It is peeked **before** the verdict budget. A half-broken provider can
     exhaust both; verdict-first would then take the publish branch while the
     provider is known bad.
   - It is peeked **after** the verdict-cache lookup. A cached verdict costs
     nothing, so the circuit must not hold it.

**Never use `cache.incr()` for these counters.** Django's `BaseCache.incr()` is
`get()` then `set(key, value)` with *no* timeout, which silently re-stamps the
entry with the backend's default `TIMEOUT` (300s here) instead of
`AIRateLimiter.TTL` (3600s) — a 12x window shrink that no test would show.
Use the explicit `cache.set(key, calls + 1, cls.TTL)` idiom.

### Every screening surface must be trust-gated (todo 280)

`get_spam_backend()` has exactly two call sites, and before enabling the LLM
backend they disagreed about who pays for a provider call:

| Surface | Call site | Trust gate |
|---------|-----------|------------|
| Topic/Post publish | `models/moderation.py` (`SpamCheckTask`) | Yes — `workflow.py::_route_revision_by_trust` only starts the workflow for `trust_level < TRUST_AUTOPUBLISH_LEVEL` |
| Direct message send | `api/direct_messages.py` (`_screen_dm_body`) | Yes, **since todo 280** — was ungated |

The DM path predates the LLM backend, so "screen every send" was free when the
only backend was the offline heuristic. It stops being free the moment
`WAGTAILFORUM_SPAM_BACKEND` names a provider-backed backend: an ungated surface
puts a synchronous, billable call on *every* message, including those from
established members the post path would never screen.

Worse, **fail-closed is not equivalent across the two surfaces**. A flagged Post
becomes a pending draft a moderator can still publish; `Message` has no
revision/workflow state to hold, so the identical verdict rejects the send with
a 400 and the text is gone. A provider timeout therefore *destroys* a DM where
it merely *delays* a post — so paying that risk for a trusted sender is the
worst trade available on this path.

The gate splits the two passes rather than skipping screening:

- **A trusted sender falls back to the package's built-in heuristic** (link
  flood, banned words) rather than skipping screening the way the post path does
  for a trusted author. That pass is cheap, offline and deterministic, so
  dropping it would trade one problem for a worse one. Pinned by
  `test_trusted_sender_dm_still_gets_the_heuristic_floor`.
- **Only the configured backend's extra pass is trust-gated**, on the same
  `TRUST_AUTOPUBLISH_LEVEL` the post path uses — one policy knob, not two.

Be precise about what that first bullet does *not* claim. An **untrusted**
sender reaches `get_spam_backend()` alone, exactly as every sender did before
the gate, so their heuristic floor is whatever the configured backend applies —
it is a property of the backend, not something this call site enforces. Both
backends in this repo supply it (`HeuristicSpamBackend` *is* the floor;
`LLMSpamBackend` is heuristic-first before any provider call), so the guarantee
holds here. A third-party host pointing `WAGTAILFORUM_SPAM_BACKEND` at a
non-chaining backend screens its untrusted senders with that backend alone —
the package's pre-existing contract, unchanged by the gate and pinned by
`test_untrusted_sender_dm_floor_comes_from_the_configured_backend`.

**Rule for any new surface that screens user content:** decide its trust gate at
the same time as its `get_spam_backend()` call, and state its fail-closed
consequence. "Screen everything" is only cheap while the backend is offline, and
which backend is configured is an ops decision made later, elsewhere, by someone
who will not re-audit the call sites.

### Enable procedure

The hardening gate above is landed, so the setting is **safe to enable**. Per
environment:

1. Confirm `OPENAI_API_KEY` is set and working in that environment.
2. Set `WAGTAILFORUM_SPAM_BACKEND=apps.forum_host.spam.LLMSpamBackend`.
3. Restart, then watch these four log lines:
   - `[SECURITY] Forum spam LLM flagged content` — flags.
   - `[ERROR] Forum spam LLM timed out` — provider health.
   - `[RATE_LIMIT] Budget exhausted for ai_rate_limit:forum_spam` — verdict cap
     hit; screening is now degrading to the heuristic and **publishing**.
   - `[CIRCUIT] Forum spam LLM attempts cap reached` — the attempts cap tripped;
     screening is **holding** every post and has stopped calling the provider.
     (`peek_budget` also emits its generic `[RATE_LIMIT] Budget exhausted for
     ai_rate_limit:forum_spam_attempts` alongside it; the `[CIRCUIT]` line is
     the one to alert on, because it names the posture.)

Operational knobs, all in `apps/forum_host/constants.py`:

| Constant | Default | Effect |
|----------|---------|--------|
| `SPAM_LLM_BUDGET_LIMIT` | 200/hr | Screens before degrading to heuristic (publish). Counts **definitive verdicts only** — see the caveat below. |
| `SPAM_LLM_ATTEMPTS_LIMIT` | 400/hr | Provider calls (any outcome) before screening trips to a **hold**. Must stay **>** `SPAM_LLM_BUDGET_LIMIT`. |
| `SPAM_LLM_TIMEOUT_SECONDS` | 8 | Caller **and** provider deadline. Bounds held-transaction time. Was 3; raised from production measurement — see below. |
| `SPAM_LLM_MAX_WORKERS` | 4 | Concurrent screens. Size for peak concurrent moderation. |
| `SPAM_LLM_CACHE_TTL_SECONDS` | 24h | Verdict cache lifetime (duplicate spam is free). |
| `SPAM_LLM_PROMPT_VERSION` | 1 | Bump to invalidate cached verdicts after a prompt change. |

`SPAM_LLM_ATTEMPTS_LIMIT` **must stay above** `SPAM_LLM_BUDGET_LIMIT` (pinned by
`test_attempts_limit_stays_above_the_verdict_limit`). Every definitive verdict is
also an attempt, so inverting them makes the attempts cap trip first under
healthy traffic — converting the intended cost-degrade (publish) into a hold on
legitimate posts.

**Size the timeout against a COLD call, not a warm one** (todo 280, measured
2026-09-03 in production: gpt-4o-mini over Railway -> OpenAI).

```
first call after a container start   3.66s   <- timed out at the then-current 3s
steady state                         1.19s, 1.48s, 1.78s, 2.33s
```

The first provider call in a fresh process pays SDK construction and a TLS
handshake on top of the completion. Railway redeploys on every merge, so a
deadline sized for steady state holds the first screened post after *every*
deploy, whatever its content — a recurring false positive that looks like a spam
flag in the moderation queue.

The non-obvious half: **a timeout below real latency saves nothing.**
`future.result(timeout=...)` cannot cancel an in-flight request — the probe above
was issued, billed, and answered 0.66s after the caller stopped listening. So
too-tight is strictly worse than generous: it spends the money, discards the
verdict it paid for, *and* holds the post. Tune this knob upward on evidence of
timeouts and downward only on evidence of transaction contention, never as a
cost control — the attempts cap is the cost control.

**The attempts cap is a sticky hold, by design.** `consume_budget` re-stamps the
1h TTL on every write, so the window is a rolling hour from the *last* issued
call. Once tripped it reopens on a fixed ~1h timer — the hold path issues no
calls, so nothing re-stamps it and continued post submissions do **not** extend
it — but it stays shut for that hour even if the provider recovers immediately.
Held posts are pending drafts in the moderation queue, not lost, so this is
degraded-but-safe. Reopen it early with
`AIRateLimiter.reset_budget(constants.SPAM_LLM_ATTEMPTS_CACHE_KEY)`.

Both counters are `get`-then-`set` (never `cache.incr()`, per the rule above), so
concurrent workers can lose updates and either cap may overshoot by roughly the
concurrency factor. That is fine here: this is a circuit breaker, not an
accountant.

One caveat remains on `SPAM_LLM_BUDGET_LIMIT` — read it before raising the
number:

- **It raises aggregate AI spend, it does not just partition it.** Forum
  screening previously shared the blog's `ai_rate_limit:global`
  (`AIRateLimiter.GLOBAL_LIMIT` = 100/hr), which capped both subsystems
  *together*. After the split the ceiling is 100 (blog) + this value (forum) —
  at 200 that is **3x** the old worst-case hourly spend. Size it against real
  forum volume rather than treating it as free headroom.

To clear an exhausted forum budget without waiting out the hour:
`AIRateLimiter.reset_budget(constants.SPAM_LLM_BUDGET_CACHE_KEY)`.

To roll back, unset `WAGTAILFORUM_SPAM_BACKEND` — the heuristic default returns
with no code change.

## One AI feature, one budget counter (todo 275 / M12, M14, AC4)

The forum now has five AI cost centres, and each owns its **own** cache key:

| Counter | Key | Unit | Degrade posture when exhausted |
|---------|-----|------|-------------------------------|
| Blog completions | `ai_rate_limit:global` | completion | blog-defined |
| Spam screening | `ai_rate_limit:forum_spam` | completion | publish via heuristic |
| Query embeddings | `ai_rate_limit:forum_embed` | embedding | empty semantic results |
| Composer assist | `ai_rate_limit:forum_compose` | completion | 429 + `Retry-After` |
| Plant-care answers (todo 289 / M13) | `ai_rate_limit:forum_rag` | completion | 429 + `Retry-After` (peeked BEFORE retrieval, so an unaffordable question spends no embedding) |

Three reasons this is a rule and not bookkeeping taste, each of which was a real
coupling before the split:

1. **Non-commensurable unit costs.** An embedding is ~3 orders of magnitude
   cheaper than a completion. One shared counter cannot express a sane cap for
   both — sized for embeddings it never protects against completion spend; sized
   for completions it throttles embeddings to uselessness.
2. **Independent degrade postures.** Look at the right-hand column: an exhausted
   embedding budget must *silently* drop semantic results while keyword search
   keeps working, whereas an exhausted composer budget must *tell the user* to
   retry later. A shared counter forces one subsystem's cap to trigger another's
   posture (the audit-H13 bug in general form).
3. **Per-feature accounting.** With one counter, "who spent the quota" is
   unanswerable, and any feature can starve any other.

**Every counter uses peek-then-consume** (`AIRateLimiter.peek_budget` before the
call, `consume_budget` only after the provider actually answered), for the reason
spelled out in the spam section above: charging on attempt lets a provider outage
drain the cap through pure failure and silently flip the feature into its
over-budget posture.

The one apparent exception is not one: `ai_rate_limit:forum_spam_attempts` is a
**health/circuit cap, not a budget**, so it is deliberately charged on attempt
and is deliberately a second key for a feature already in the table. It exists
*because* of the peek-then-consume rule — that rule leaves failed calls
uncounted, and a counter that trips a **hold** is what bounds them. The
one-budget-per-feature rule still holds: spam screening has exactly one budget
(`ai_rate_limit:forum_spam`). A feature needs a second key only when it needs a
posture the budget cannot express. `vector_indexes._scored_search()` is the
single place `search_documents()` is called in the forum precisely so this holds
for every caller: it owns the flag, the query-length cap and the embedding
budget's peek-then-consume. Its two sanctioned wrappers are
`find_similar_topics()` (pk cache + Topic visibility refetch — the compose-time
similar-topics endpoint and the M12 search section) and
`rag_retrieval.retrieve_grounding_passages()` (similarity floor + per-corpus
visibility refetch — RAG, todo 289). **Never call `search_documents()` from
anywhere else**; it bypasses the flag, the budget and the visibility refetch at
once. The core's return is tri-state on purpose — `None` = no search happened
(nothing charged) vs a `list` = searched (charged) — so a wrapper that caches
results only caches the `list` case; caching a `None` would remember a budget
outage as "no results" for the cache TTL.

Adding a counter **raises** the aggregate ceiling rather than partitioning a fixed
one — see the `SPAM_LLM_BUDGET_LIMIT` caveat above; the same arithmetic applies to
`EMBED_BUDGET_LIMIT`, `COMPOSE_BUDGET_LIMIT` and `RAG_BUDGET_LIMIT`.

## RAG guardrails are product rules, not prompt instructions (todo 289 / M13)

`apps/forum_host/rag.py` has the highest harm ceiling of any AI feature in the
repo (plant-care advice; in the blocked classes, human/animal ingestion). The
guardrails ARE the feature, and the order of operations in `post()` is the
design — see the design doc's "Implementation notes" for the full rationale:

1. **Two-flag gate** (`vector_indexes.rag_enabled()`: `FORUM_RAG_ENABLED` AND
   `FORUM_VECTOR_SEARCH_ENABLED`) → 503 `{"code": "disabled"}`. M13 is a strict
   superset of H15; with vector search off every question would silently be
   "no information".
2. **Blocked classes before retrieval** (`rag_guardrails.classify_blocked_question`,
   deterministic regexes, no LLM): ingestion/toxicity/medicinal use and
   pesticide/chemical dosing → a static referral, no retrieval, no budget. A
   prompt-level "don't answer toxicity questions" is not a control. The
   NOT-blocked table in `test_rag_guardrails.py` matters as much as the blocked
   one — "something is eating my hostas" is a care question, not an ingestion
   question.
3. **Refuse when unsourced**: nothing above `RAG_SIMILARITY_FLOOR` → 200
   `no_information` WITHOUT an LLM call. The floor is read at call time and
   `retrieve_grounding_passages` logs the top score per index on every
   question — the calibration signal for enabling (todo 330).
4. **Citation validation after generation** (`validate_citations`): invented
   `[n]` markers are dropped; zero valid citations (or the model's own
   `NO_INFORMATION`) → `passages_only`, the answer suppressed, nothing
   persisted. Only a cited answer becomes a `RagAnswer` row, so `answer_id` —
   and the report affordance — exist only for `status: answered`.
5. **The review loop is host-owned** (`RagAnswer` / `RagAnswerReport` + the
   CMS "AI answer reports" snippet listing), not a third target on the package
   `Report` (exactly-one check constraint, author-penalising `file()`, and the
   package may not import `apps.*`). The report endpoint is deliberately NOT
   flag-gated. Residual risk: injection through a passage can still yield a
   fluent wrong answer *with* valid citations — layer 5 is what catches it, so
   layers 1–4 must not be enabled without a named owner for it.

Index maintenance is host code: `VectorIndex.update()` re-registers every
source object in `ModelSourceIndex` on every call, `PgVectorProvider.add()`
never purges, and `clear()` wipes EVERY index's rows from the shared table. So
`BlogChunks.build()` purges its own `index_name` rows first and the per-page
`sync_blog_page_chunks` task embeds first, then swaps the page's key-prefix rows
in one transaction, re-checking the page's live/public state inside it
(`document_key` is the table's primary key — index-unique prefixes are what
keep `SimilarTopics` and `BlogChunks` rows apart). The receivers enqueue it
with `transaction.on_commit`, never inline: Wagtail's admin publish and
Django's `Model.delete()` cascade fire the page signals inside
`transaction.atomic()`, so an inline `.delay()` lets the worker read the
pre-publish page or re-embed a page mid-delete (PR #606 review). And
`retry_backoff=` on an `autoretry_for` task is the backoff FACTOR — `True`
means factor 1 (~1s/2s/4s), and `default_retry_delay` is ignored on that path.

## django-ai-core 0.1.5 — verified library facts (todo 289)

Read from `backend/venv/.../django_ai_core/contrib/index/` while building
`BlogChunks`; each one shaped the code and would mislead a reader of the
library's docstrings alone:

- `ModelSource.__init__` sets `self.chunk_transformer` ONLY when none is
  passed (`source.py:83`, missing `else`) — passing `chunk_transformer=`
  leaves the attribute unset and `_object_to_documents` raises
  `AttributeError`. Set it in a subclass `__init__`.
- `ModelSource` installs `SimpleChunkTransformer(1000, 100)` by default, so
  `SimilarTopics` ALREADY chunks (blind character windows), hidden by
  `find_similar_topics`' pk-dedupe. `get_metadata(obj)` is called once per
  OBJECT and reused for every chunk — per-chunk metadata (a block anchor)
  requires overriding `_object_to_documents`.
- `search_documents()` returns `BaseStorageDocument(document_key, content,
  metadata, score)` with `score = 1 - cosine_distance`, ordered ascending
  distance; an UNSLICED iteration silently stops at 20
  (`storage/base.py:24`). `search_sources()` discards scores in its dedupe.
- `CachedEmbeddingTransformer.embed_string` is content-hash cached in the DB,
  so the same query against two indexes is one provider call (and two
  `EMBED_BUDGET` units — the over-count is the safe direction).
- `PgVectorEmbedding.document_key` is the table's PRIMARY KEY across every
  index; `add()` upserts by `(index_name, document_key)`; `delete(keys)`
  ignores `index_name`; `clear()` wipes every index; `VectorIndex.update()`
  ends in `post_index_update`, which re-registers every source object in
  `ModelSourceIndex` on every call. Nothing ever purges stale keys.
- `contrib/index/signals.py` ships a `post_save` receiver that is never
  connected (`IndexConfig` has no `ready()`) and passes the model CLASS where
  an instance is expected — rebuild-on-save is 100% host code.
- `SentenceChunkTransformer` imports `llama_index` at call time; it is not
  installed, so that transformer raises `ImportError`.

## Augmenting a package read view host-side: mix in, never override (todo 275 / M12)

The premium `?semantic=1` section on `/forum/search/` is a `SemanticSearchMixin`
composed *ahead* of the package view, not a `get()` override on the throttled
subclass:

```python
@_throttled("search", "GET", key=client_ip_key)
class SearchView(SemanticSearchMixin, forum_views.SearchView): ...
```

`_throttled` is `method_decorator(..., name="get")` on the host class, so it wraps
whatever `get` the MRO resolves at class-creation time. A subclass of the
*already-decorated* host view that defines its own `get` **replaces** the wrapped
method and silently ships the endpoint unthrottled. Two further rules for this
shape:

- **Re-declare `@extend_schema`** on the mixin's `get`. The override replaces the
  package's decorated method, so without it the OpenAPI description silently
  reverts to a generic one while the response shape has changed.
- **Never widen a `PublicForumReadCacheMixin` response by entitlement without
  checking the cache headers.** Anonymous successful GETs are marked
  `public, s-maxage=…` for the CDN. An entitlement-varying key is only safe here
  because it is added *exclusively* for authenticated users, which forces
  `private, no-store` — pinned by
  `test_semantic_search.py::test_semantic_response_is_never_shared_cacheable`
  rather than left to be inferred from the mixin's docstring.
- **Guard on `response.status_code == 200` and a dict body** before augmenting: a
  throttled 429 or an error envelope must pass through untouched.

## Idempotency contract on new write surfaces (todo 258)

The reusable idempotency helpers (`api/idempotency.py` — `idempotency_cache_key`,
`fingerprint`, `reserve`, `remember`, `_replay_or_none`) apply to any unsafe write
in the same 6 steps: extract key → fingerprint → replay-or-none (409 in-flight /
422 payload-mismatch) → validate → `reserve()` right before the mutation →
`remember()` after. The package README's "Idempotency" section is authoritative;
three non-obvious points learned wiring PATCH + image upload:

- **Multipart uploads fingerprint on a CONTENT hash, not the request body.**
  `request.data` holds the `UploadedFile`, not JSON, so name+size can collide.
  `fingerprint({"name": …, "sha256": hashlib.sha256(file.read()).hexdigest()})`,
  with `file.seek(0)` BEFORE hashing (validation may have consumed the stream) AND
  after (so `.create()` stores the full file).
- **A replay must be response-faithful, not just body-faithful.** A 201 with a
  `Location` header must replay WITH that header — `remember(..., headers={…})`
  persists it and `_replay_or_none` re-applies it. See `docs/rules/api.md` +
  `docs/LEARNINGS.md` 2026-07-24.
- **`Location` reverse is namespace-agnostic** (`_created_location`): resolve
  within `request.resolver_match.namespace`, never a hardcoded `app_name` — the
  package mounts under a bare root OR a nested host namespace.

## Reference error-envelope handler ships in the package (audit M39)

`api/exception_handler.py::forum_exception_handler` produces the consistent
envelope (`{error, message, code, status_code, errors?}`) so a host that mounts
the package gets it by default instead of bare DRF `{"detail": …}`. The package
cannot import host code, so it DUPLICATES the host's envelope logic
(`apps/core/exceptions.py`) rather than sharing it — the two are byte-compatible
and interchangeable. Package tests run under the host settings, so the enveloped
shape can be pinned directly (`tests/api/test_error_envelope.py` +
`test_topic_create.py::test_oversized_body_is_rejected`).

The `readable_message` flattener (`_readable_message` in the package) is part of
that contract (todo 320): `message` is `str(exc)` only for a scalar detail; a
dict/list detail — every field-level `ValidationError`, nested serializers
included — is flattened to `field: text; other.field: text`, because `str(exc)`
there is the Python repr of `ErrorDetail` objects and every web page renders
`message` verbatim. Change it in both handlers or neither:
`apps/core/tests/test_exception_envelope.py` pins the table AND asserts both
handlers agree on it (the L16 drift-guard shape below), so a one-sided edit fails
CI. Host views that catch a DRF `ValidationError` themselves
(`plant_identification/api/simple_views.py`) reuse `readable_message` rather than
re-deriving a join.

## Cross-boundary drift guard when there is no codegen (audit L16)

There is no OpenAPI→TS codegen, so a shared literal that must match on both sides
(the web `REACTION_TYPES` vs backend `Reaction.REACTION_CHOICES`) is single-sourced
per-side and guarded by a **backend test that reads the committed web file** and
asserts equality (`apps/forum_host/tests/test_reaction_contract.py`). Honest
framing: a drift GUARD (fails CI if either side changes alone), not true
single-sourcing.

## Four list envelopes, documented rather than converged (audit M40 / todo 277)

The forum API ships four list-collection shapes — cursor `{results, next,
previous}`, flat `{results}` (boards), search `{topics, posts, *_has_more,
page}`, sync `{topics, deleted, has_more, next_since, next_since_id}`. The
resolution was to **document the divergence, not converge it**: search carries
two independently-paged result sets in one response and sync carries tombstones
plus a client-persisted compound cursor, and neither survives a single `results`
list. The contract table (which endpoint, which shape, why not cursor) lives in
the package README's `## List envelopes` — that is the authoritative statement;
`web/src/services/forumMappers.ts` points at it from the consuming side.

Sub-decision worth keeping: **search items are deliberately lighter than list
items.** The post item carries a `plain_text_excerpt` slice rather than the
`PostSerializer` body precisely so search doesn't resolve every hit's StreamField
(the per-post image bulk-fetch that helper exists to avoid), and neither section
carries an `author`. The one field actually added back was `is_pinned` — a topic
is pinned wherever it surfaces, and the web SearchPage renders the same
`ThreadCard` as the board list, whose 📌 badge could otherwise never fire. Search
order stays relevance-ranked; pinned is topic state, not list order.

## Versioning opt-out: one mixin, guarded structurally (audit L20 / todo 277)

Every forum view (17 package + 3 host AI views) inherits `versioning_class =
None` from `wagtail_forum/api/versioning.py::UnversionedForumAPIMixin`, which
states the rationale once instead of 20 times.

The guard is the interesting part, and the coverage split is not the obvious one.
This host sets `DEFAULT_VERSIONING_CLASS = NamespaceVersioning` with
`ALLOWED_VERSIONS = ["v1", "v2"]`. Whether a dropped opt-out is *visible* then
depends entirely on which urlconf a test goes through:

| Mount | Namespace | Opt-out dropped |
|---|---|---|
| Package test urlconf (`wagtail_forum.tests.api.urls`) | `wagtail_forum_api` (auto from the package `app_name`) — not an allowed version | **404s** — the package API suite catches it, as an undiagnosed mass-404 |
| Real host mount (`plant_community_backend/urls.py`) | `v1:wagtail_forum_api` — `NamespaceVersioning` splits on `:` and accepts `v1` | **200, unchanged** — nothing behavioural fails |

So the package's own suite happens to cover *package* views — an accident of its
test urlconf's namespace, not a designed guarantee. What it cannot cover is the
host-mounted surface: the three host-only AI views
(`summary`/`compose_assist`/`similar`) and every throttled host subclass. Measured:
reordering `SimilarTopicsView`'s bases left its own 18 tests **and** all 251
package API tests green — only the structural guard failed.

Hence `apps/forum_host/tests/test_forum_versioning_optout.py`: it walks the
**host** urlconf (so it sees throttled subclasses and `SemanticSearchMixin`, not
just package classes) and asserts the mixin is present, precedes `APIView` in the
MRO (DRF's `APIView` declares `versioning_class` in its own body — bases in the
wrong order silently hand the host default back), and is re-declared nowhere else.

Generalizable: when an attribute's *correct* value is indistinguishable from its
default **on the mount that ships**, behavioural tests cannot protect it there.
Assert the structure — and when claiming "no test catches this", enumerate the
urlconfs, because coverage can differ per mount within one repo.

## Wagtail contrib integrations: package hooks, host wiring (Wagtail quick wins, PR #624)

The package stays host-agnostic (`test_reusability`) by exposing small hooks;
the host (`apps/forum_host/`) does the Wagtail-contrib wiring behind them.

| Package hook | Host wiring | Wagtail contrib |
|---|---|---|
| `conf.register_override_provider(fn)` / `conf.MISSING` | `forum_settings.provide` reads the `ForumSettings` generic setting | `wagtail.contrib.settings` |
| `SearchView.record_search(request, *, query, page)` (no-op) | `search_hits.record_query_hit` on page 1 | `wagtail.contrib.search_promotions` |
| plain `pre_save`/`post_save` on `Topic`, `page_slug_changed` on `ForumBoard` | `redirects.py` writes/repairs `Redirect` rows (per topic, or in bulk for every live topic on a board rename); `RedirectsAPIViewSet` mounted at `/api/v2/redirects/` | `wagtail.contrib.redirects` |
| nothing — snippets are already indexed | `signals.py` (package) warns on deleting an image a live post shows | `ReferenceIndex` |

### Override provider: process memo + commit-rotated token

`get_setting` consults providers before the `WAGTAILFORUM_*` setting. A
provider runs on hot paths (spam check ×2 per post create, autopublish per
publish, experts per request) whose query counts are pinned, so the host one
must cost no DB query in steady state:

```python
_memo = None  # (token seen at load, {NAME: value})

def _values():
    global _memo
    token = cache.get(CACHE_KEY)          # 1 cache GET per read
    if _memo is None or (token is not None and token != _memo[0]):
        _memo = (token, _load_values())   # 1 SELECT, first read / after a save
    return _memo[1]

def invalidate(**kwargs):                 # post_save / post_delete
    global _memo
    _memo = None                          # this worker: now
    token = uuid.uuid4().hex
    transaction.on_commit(lambda: cache.set(CACHE_KEY, token, TTL))  # others: after commit
```

Three deliberate properties: a *missing* token keeps the memo (so `cache.clear()`
in tests and a Redis restart never turn reads into queries — worst case "stale
until the next save"); the token rotates **after commit** (rotating inside the
admin's atomic block let another worker memoise the uncommitted old row under
the new token, forever); and the TTL is bounded per `docs/rules/caching.md`
without driving correctness. Tests that write the row reset the memo to
`(None, {})` at teardown — the row rolls back, the memo would not.

### Redirect rows: loop- and chain-free by construction

`redirect_topic_path(old, new)` does three things in order: delete **every**
row whose `old_path == new` (a rename-back's own row or a manual reverse row
would loop, and the next step would rewrite the manual one into B→B); re-point
rows whose `redirect_link == old` to `new` (chain collapse); then
`filter(old_path=old, site=None).update(...)` and create only if nothing
matched (Postgres does not enforce `unique_together` on a NULL `site`). Gate
on the topic's **new** `live` state so an auto-hidden topic whose slug a
moderator fixes on the way back to published still redirects its once-public
URL. A **board** slug rename (`page_slug_changed` on `ForumBoard`, sent from
`transaction.on_commit`, so the handler opens its own `atomic()`) fans the same
three steps over every live topic as bulk statements — the query count is
pinned equal at 3 and 1,000 topics (only the INSERT splits past
`REDIRECT_BULK_CREATE_BATCH_SIZE`): `old_path__in` delete, one prefix
`Replace()` update for the chain collapse, delete-then-`bulk_create` for the
rows. The collapse is prefix-wide and runs even with zero live topics, because a
rename BACK must repair the rows an earlier rename left for topics unpublished
in between — and it folds exactly those rows onto themselves, so a
`redirect_link=F("old_path")` delete under the new prefix follows it (review
round 1 caught both). Per-topic paths come from `Topic.get_absolute_url()` on
stub instances (no restated URL shape); only the prefix helper restates the
board half, and a test pins it to the model method (todo 334).

### What Wagtail already does — pin it, don't rebuild it

`register_snippet` registers the model with `ReferenceIndex`, and the
`update_reference_index_on_save` handler runs synchronously under the immediate
django-tasks backend, so the image usage view and delete confirmation list forum
posts with no forum code. The search-terms report and promoted-results editor
need only `Query.get(q).add_hit()` — capped to `MAX_QUERY_STRING_LENGTH`, in a
savepoint, failure-swallowed, never touching cache headers (CDN-served
anonymous repeats go uncounted by design).

### Moderation queue: a `ReportView` over `Report`, gated like the snippet (todo 345)

The queue is Wagtail's report framework, not a bespoke admin view: a
`ReportView` subclass gets the listing, sortable columns, filters, pagination,
CSV/XLSX export and the Reports-menu entry for free, and stays a *listing* —
every row links to the existing `Report` snippet inspect view, so there is one
mutation path. The shape (`wagtail_forum/admin_views.py`, `admin_urls.py`,
`wagtail_hooks.py`):

```python
class ModerationQueueView(ReportView):
    index_url_name = "wagtail_forum_reports:moderation_queue"
    index_results_url_name = "wagtail_forum_reports:moderation_queue_results"
    permission_policy = ModelPermissionPolicy(Report)          # the snippet's gate
    any_permission_required = ["add", "change", "delete", "view"]
    default_ordering = "created_at"                            # oldest first
    columns = [TitleColumn("target_excerpt", get_url=_inspect_url), ...]
    custom_field_preprocess = {"reporter_trust_level": {"csv": label, "xlsx": label}}

    def order_queryset(self, queryset):        # deterministic pages
        ordering = self.ordering
        ordering = (ordering,) if isinstance(ordering, str) else ordering
        return queryset.order_by(*ordering, "pk")

    def get_queryset(self):
        self.queryset = Report.objects.filter(status__in=QUEUE_STATUSES).select_related(...)
            .annotate(reporter_trust_level=F("reporter__wagtail_forum_profile__trust_level"),
                      target_open_reports=Case(When(post__isnull=False, then=Subquery(open_on_post)),
                                               default=Subquery(open_on_message)))
        return super().get_queryset()


@hooks.register("register_admin_urls")
def register_moderation_queue_urls():
    return [path("forum/reports/", include("wagtail_forum.admin_urls"))]   # namespaced module


@hooks.register("register_reports_menu_item")
def register_moderation_queue_menu_item():
    return ModerationQueueMenuItem(_("Forum moderation queue"),
                                   reverse("wagtail_forum_reports:moderation_queue"), ...)
```

Three things the review caught that the framework does not tell you:

- **Gate on the linked model's policy, and grant it to the bootstrapped group.**
  The first cut gated on `change_post`; the "Forum Moderators" group held no
  `*_report` perm, so every row link bounced. `bootstrap.py` now grants
  `view_report` + `change_report`, and `test_moderation_queue.py::_moderator()`
  is a member of that group who GETs each row's inspect URL and expects 200.
- **Keep the query count flat across rows.** `UserColumn` renders an avatar via
  `user.wagtail_userprofile` — one query per row — so the reporter column is a
  plain username `Column`; the trust level is an annotation (LEFT JOIN), the
  sibling-report count a correlated subquery per target shape. Pinned by an
  equal-count assertion for 1 vs 3 rows across post and message reports.
- **Export and empty state have their own seams.** `list_export` sends the raw
  annotation to the sheet (decode with `custom_field_preprocess`); a
  class-attribute `no_results_message` would hide the base class's
  filtered-vs-empty distinction (override the `cached_property` instead).

### Multi-choice polls: one final ballot, one lock, one query (todo 349)

`Poll.max_choices` (default 1) turns the single-choice poll into an N-of-K
ballot without a second model: `PollVote` is unique per `(poll, user,
option)`, so a ballot is N rows and `Poll.results()` stays row-based. The
three shapes that carry it:

```python
# models/polls.py — voters counted from the rows, in the SAME query as the
# option counts; never "sum the counts" (trusts a view invariant)
voters = (PollVote.objects.filter(poll=OuterRef("poll_id")).order_by()
          .values("poll").annotate(n=Count("user", distinct=True)).values("n"))
options = self.options.annotate(vote_count=Count("votes"),
                                voters=Coalesce(Subquery(voters), 0))

# api/polls.py — one submission per voter, enforced by the view, not the DB
existing = _existing_ballot(poll, user)          # fast, unlocked
if existing: raise Conflict(...)
with transaction.atomic():
    Poll.objects.select_for_update().get(pk=poll.pk)
    if _existing_ballot(poll, user): raise Conflict(...)   # locked re-check
    PollVote.objects.bulk_create([...])          # the whole ballot or nothing
```

Decisions worth not re-deciding: a second submission is **409, never
replaced or merged** (results are hidden until you vote, so change-vote
would let a voter peek and re-decide — the todo-283 rule carried over);
`option_ids` is a `_BoundedListField` (raw-length gate before per-item
parsing); the vote response sorts the ballot ids exactly as `get_poll` reads
them back, so the two payloads stay byte-identical once options can be
reordered. Web: checkbox ballot capped in the UI with `aria-disabled`, one
Vote button; composer "Choices per voter" is a `<select>` clamped to the
filled option count. Flutter builds multi-choice from the start in todo 341.

### Mute: a one-way preference filter riding the block helpers (todo 347)

`UserMute(muter, muted)` is `UserBlock`'s one-directional, content-only
sibling. What made it a small change is that every block-aware surface reads
two helpers in `api/views.py`, so both grew a second clause and every surface
became mute-aware at once:

```python
def _annotate_author_blocked(qs, user, *, author_field="author_id"):   # COLLAPSE
    if not _should_filter_blocks(user):          # anonymous + moderators: constant False
        return qs.annotate(author_is_blocked=Value(False, ...), author_is_muted=Value(False, ...))
    return qs.annotate(
        author_is_blocked=Exists(UserBlock.objects.filter(blocker_id=user.pk, blocked_id=OuterRef(author_field))),
        author_is_muted=Exists(UserMute.objects.filter(muter_id=user.pk, muted_id=OuterRef(author_field))),
    )

def _exclude_blocked_authors(qs, user, *, author_field="author_id"):   # HIDE
    ...
    return qs.exclude(**{f"{author_field}__in": Subquery(blocked_ids)}).exclude(
        **{f"{author_field}__in": Subquery(muted_ids)})
```

Per-site decisions (recorded in the todo's Work Log and the package README's
mute-vs-block table): topic list, search, experts rail, notifications
(read-time + fan-out), and — after the review found it had never been
block-aware — the home `topics/recent/` feed are HIDE; post list and topic
detail COLLAPSE via `is_muted`; the public profile flags and empties activity;
DMs and the @mention typeahead are untouched; the muted member's view never
changes; moderators' own mutes are inert. Tests pin each surface AND the
other direction (`test_a_mute_is_one_directional_the_muted_member_notices_nothing`,
the reverse-direction fan-out test in `apps/forum_host/tests/test_signals.py`).

### Badge engine: CMS-curated rules over a closed metric set (todo 348)

`Badge` (a `ClusterableModel` snippet with inline `BadgeRule` rows) +
`UserBadge` (unique per user/badge, `PROTECT` FK) replace the single
hardcoded Botanist badge. The shape worth keeping:

```python
# badges.py
def user_metrics(user_id) -> dict[str, int]: ...        # the closed BadgeMetric set
def award_badges_for_user(user_id) -> list[Badge]:      # idempotent; any rule earns
    candidates = Badge.objects.filter(is_active=True).exclude(awards__user_id=user_id)
    ...UserBadge.objects.get_or_create(...); notify(badge_awarded, ...)
def award_after_commit(user_id): transaction.on_commit(lambda: award_badges_for_user(user_id))
```

Evaluation points: a post's/topic's first publish (`signals.py`, on_commit —
Wagtail publishes inside a transaction so this really defers; under pytest
the callback is rolled back unrun, so endpoint query pins cannot see its
cost), the `solution_marked` receiver (already inside on_commit), and lazily
on `GET me/stats/` (catches up pre-engine holders without a data migration).
The package ships **no badge rows**: `seed_default_badges` (idempotent on
slug AND name, per-row savepoint, wired into `preDeployCommand`) seeds the
defaults including Botanist; once seeded, the Botanist `BadgeRule` is the
single source of truth for the stats progress bar and the `BADGE_BOTANIST_*`
settings only seed/fall back. Reviewer-caught seams: name-collision in the
seed (deploy blocker), two sources of truth for the threshold, CASCADE on the
award FK, and the inline-formset create view needing an actual POST test.
