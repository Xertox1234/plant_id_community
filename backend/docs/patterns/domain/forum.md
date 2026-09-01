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
| `SPAM_LLM_TIMEOUT_SECONDS` | 3 | Caller **and** provider deadline. Bounds held-transaction time. |
| `SPAM_LLM_MAX_WORKERS` | 4 | Concurrent screens. Size for peak concurrent moderation. |
| `SPAM_LLM_CACHE_TTL_SECONDS` | 24h | Verdict cache lifetime (duplicate spam is free). |
| `SPAM_LLM_PROMPT_VERSION` | 1 | Bump to invalidate cached verdicts after a prompt change. |

`SPAM_LLM_ATTEMPTS_LIMIT` **must stay above** `SPAM_LLM_BUDGET_LIMIT` (pinned by
`test_attempts_limit_stays_above_the_verdict_limit`). Every definitive verdict is
also an attempt, so inverting them makes the attempts cap trip first under
healthy traffic — converting the intended cost-degrade (publish) into a hold on
legitimate posts.

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
in one transaction (`document_key` is the table's primary key — index-unique
prefixes are what keep `SimilarTopics` and `BlogChunks` rows apart).

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
