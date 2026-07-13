# Audit: Forum Modernization (maturity + Wagtail integration + AI opportunities)

> **Date:** 2026-07-11
> **Trigger:** User-invoked `/audit` — after the write-path correctness review cluster
> (todos 250–255, all fixed), take the forum from "basic but correct" to a modern,
> professional-grade forum. Focus: UX, social interactions, Wagtail integration
> (highest importance), Wagtail AI for premium members. Must follow Wagtail
> package/addon best practices per Wagtail documentation.
> **Nature:** Maturity/gap audit — findings are best-practice violations and
> feature/capability gaps benchmarked against Wagtail docs and the professional-forum
> baseline (Discourse/Flarum/NodeBB-class). Severity = product impact for a plant
> community. Most findings are expected to become prioritized roadmap todos rather
> than same-day fixes.
> **Domains:** wagtail (primary), django-drf, react-typescript, product-ux, ai-integration
> **Branch at audit:** `main` (worktree `.worktrees/audit-2026-07-11`)
> **Stack versions:** Wagtail 7.4.2, Django 6.0.7, wagtail-ai 3.1.0, django-ai-core 0.1.5, DRF 3.17.1, React 19
> **Baseline:** Backend: `manage.py check` clean (0 issues), full test suite green
> (exit 0; per-run count summary lost to pipe buffering — exact count recorded
> at Phase 5 close re-run, below). Web: vitest suite green (exit 0; duplicate-key React
> warnings noted as a discovery lead), `tsc --noEmit` clean, eslint 0 errors /
> 1 warning (coverage artifact `block-navigation.js`, not source). Redis up.
> **Close baseline (post-fix, incl. Phase 6 repairs):** Backend full suite
> **906 passed, 8 skipped** (exit 0; file-redirected — no pipe buffering this
> time; was 901 before the 5 Phase-6 regression tests). Web vitest
> **588 passed / 43 files** (duplicate-key warnings now 0 — M21), `tsc` clean,
> eslint exit 0. `manage.py check` + `spectacular` clean.

## Prior-work dedupe context

Already fixed — not re-reportable (verified complete before discovery):

- 2026-06-10 forum audit (37 findings, 34 fixed): rate limiting + 429/Retry-After,
  counter/trust reconciliation incl. demotion on spam removal, idempotency contract,
  visibility/`.public()` + PageViewRestriction, title spam screening, bootstrap perms.
- Write-path trial review 2026-07-02 (13 findings → todos 250–255, all completed):
  edit-moderation failure cluster (workflow wedge, NULL author, fake-pending, missing
  edit signal), DELETE/locked-topic/post.locked guards, 409 message, can_edit/can_delete
  affordance parity, 401/locked test gaps, 429 OpenAPI documentation, write-path
  duplication cluster.
- `ed1674b` (2026-07-10): view_count increment, tombstone sync, FCM push notifications.
- `a8ec7b1`: drf-spectacular schema warnings cleared.

## Findings

Each finding has a lifecycle: `open` → `fixing` → `verified` or `deferred` or `false-positive`.

**Status key:**

- `open` — Found but not yet addressed
- `fixing` — Work in progress
- `verified` — Fix applied AND confirmed by test/grep/type-check
- `deferred` — Intentionally postponed (must link to todo)
- `false-positive` — Agent was wrong or issue was already fixed

**Research key** (Phase 2.5 verdict, recorded in the `Research` column):

- `confirmed` — current documentation agrees the finding is valid
- `better-fix` — finding is real, but current docs show a cleaner fix (described in the `Verification` column for Phase 3 to use)
- `contradicted ⚠` — current docs say the flagged pattern is fine; may be a false positive — decide at triage
- `—` — research not applicable, or finding predates Phase 2.5

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `H` = `backend/apps/forum_host`, `web` = `web/src`.

Verification note: feature-gap findings spot-verified in code by the lead auditor
(9/9 checks exact: C1, C2, H1, H5, H7, H8, H9, L1 + mobile stub read directly);
remaining absence claims rest on the agent's cited greps, which have a 100% hit rate
on spot-checks.

### Critical

| ID  | Finding       | Domain | Agent                 | File(s)     | Research | Status | Verification |
| --- | ------------- | ------ | --------------------- | ----------- | -------- | ------ | ------------ |
| C1  | No user-facing report/flag mechanism: `flags_received` has no writer anywhere, no report endpoint/model, no report UI — post-publish abuse invisible to mods outside admin browsing | product-ux | feature-gap inventory + wagtail-reviewer (independent convergence) | `W/models/profiles.py:40`, `W/api/urls.py`, `web/components/forum/PostCard.tsx:103` | — | deferred → todo 254 | grep `flags_received` → field+comment only ✓ |
| C2  | No in-app notifications and no working delivery channel at all: no Notification model/endpoints/bell UI; FCM push server-side only — no web or mobile client ever registers a token (`fcm_token` never populated), so `send_forum_push` always no-ops; ask→answered loop absent | product-ux | feature-gap inventory | `H/tasks.py:52-57`, `W/models/profiles.py:34`, `web` layout (no bell) | — | deferred → todo 253 | grep FCM/getToken in mobile lib → 0 ✓ |

### High

| ID  | Finding       | Domain | Agent                 | File(s)     | Research | Status | Verification |
| --- | ------------- | ------ | --------------------- | ----------- | -------- | ------ | ------------ |
| H1  | Forum email notifications fully orphaned: `send_forum_reply/mention/digest` exist with `EmailType.FORUM_*` + user pref `forum_notifications`, zero callers — the user-visible toggle gates nothing | product-ux | feature-gap inventory | `apps/core/services/notification_service.py:287,407,472`, `H/signals.py` | — | deferred → todo 253 | grep callers → definitions only ✓ |
| H2  | Push event coverage minimal by design: `reply_added` notifies topic author only (not participants), `topic_created` log-only, nothing for mentions/reactions | product-ux | feature-gap inventory | `H/notifications.py:26-72` | — | deferred → todo 253 | agent-read ✓ |
| H3  | No topic/board subscriptions or watching model — users can't follow a board or thread | product-ux | feature-gap inventory | `W/api/urls.py` (anchor), new model | — | deferred → todo 253 | agent grep `subscri\|watch\|follow` → 0 ✓ |
| H4  | No @mentions: no write-side parsing, no composer autocomplete, no linkification | product-ux | feature-gap inventory | `W/api/sanitize.py`, `web` TipTapEditor | — | deferred → todo 253 | agent grep → 0 ✓ |
| H5  | Pinned topics don't pin: `TopicListView` orders `-last_post_at,-id`, overriding model Meta `-is_pinned` — pin badge renders but pinned topics sink | product-ux | feature-gap inventory | `W/api/views.py:161-165`, `W/models/topics.py:83` | — | verified | FIXED: root cause was `TopicCursorPagination.ordering` (paginator overrides the view's order_by) → `(-is_pinned,-last_post_at,-id)` + view order_by synced with comment; 2 new tests (pinned floats above fresh activity; cursor traversal 26/26 unique, pinned heads page 1) + existing exact query pin still green (3 passed); kimi-review clean |
| H6  | No solved/accepted-answer marking — highest-value missing content feature for a plant-ID Q&A forum | product-ux | feature-gap inventory | `W/models/topics.py` (anchor), `web/components/forum/PostCard.tsx` | — | deferred → todo 256 | agent grep `solved\|accepted` → 0 ✓ |
| H7  | No public user identity: no public profile endpoint/page; `PostAuthorSerializer` never joins ForumProfile (display_name from `get_full_name()`, `trust_level` hardcoded None); `avatar` field exists but absent from MeProfileSerializer so it can't even be set; profile fields are write-only vanity | product-ux | feature-gap inventory | `W/api/serializers.py:212-222,341-350`, `W/models/profiles.py:22-28` | — | deferred → todo 257 | read both serializers ✓ |
| H8  | Search undiscoverable + decorative filters: nothing links to `/forum/search`; ThreadListPage renders a working-looking search form, sort select, and "Searching for: X" chip while `fetchThreads` destructures only `{board, cursor}` — same unfiltered list every time (worse than missing: actively misleading); SearchPage filters dropped by service; backend 50-cap with no pagination/sort, default DB backend (no `WAGTAILSEARCH_BACKENDS`); tests mock fetchThreads and assert only chip UI, so nothing catches it | product-ux | feature-gap inventory + react-ts-reviewer + wagtail-reviewer (3-way convergence) | `web/pages/forum/ThreadListPage.tsx:28-30,187-241`, `web/services/forumService.ts:115-134,259-262`, `W/api/views.py:623-659` | — | deferred → todo 256 | read both web files ✓ |
| H9  | Zero SEO surface: no per-route `document.title`/meta/OG anywhere in the SPA (static `<title>web</title>` in index.html:7, no meta description), no sitemap, no RSS — link unfurlers and non-JS crawlers get an empty `<div id="root">`; every forum tab shares one generic title | product-ux | feature-gap inventory + react-ts-reviewer (convergence) | `web/index.html:7`, `plant_community_backend/urls.py` (anchor) | — | deferred → todo 256 | grep helmet/og:/document.title → 0 ✓ |
| H10 | No unread/new-content indicators and no freshness mechanism (no read-state model, no polling/live updates; `websocket_urlpatterns = []`) | product-ux | feature-gap inventory | backend `routing.py`, `web` forum pages | — | deferred → todo 253 | agent grep `unread` → 0 ✓ |
| H11 | Mobile forum is a hardcoded 3-post visual stub (empty `onPressed`, "Live posting coming soon") — 0% parity on the project's primary platform; backend `/sync/` + tombstones + push pipeline have no consumer | product-ux (mobile) | feature-gap inventory | `plant_community_mobile/lib/features/forum/forum_screen.dart:11-71` | — | deferred → todo 260 | read stub directly ✓ |
| H12 | No premium/entitlement primitive exists anywhere (no plan/tier/Stripe/entitlement code; `is_staff` is the only tier proxy in `AIRateLimiter`) — hard prerequisite for every premium AI feature; belongs host-side in `apps/users/` + `forum_host` decorators, never in the package | ai-integration | docs-researcher (AI) | `apps/users/` (grep 0), `apps/blog/services/ai_rate_limiter.py` | — | deferred → todo 255 | grep premium/stripe/entitlement → 0 ✓ |
| H13 | LLM spam/moderation pre-screen not implemented despite a first-class extension point built for it: `WAGTAILFORUM_SPAM_BACKEND` swaps in one setting; host-side `LLMSpamBackend` can reuse `generate_ai_text()` + Redis cache; design cost = synchronous publish-path call needs timeout + heuristic fallback. Premium-agnostic quality win — ranks first of the AI items | ai-integration | docs-researcher (AI) | `W/conf.py:6`, `W/spam/base.py`, `apps/blog/wagtail_ai_v3_integration.py:73` | confirmed | deferred → todo 255 | read conf.py + generate_ai_text ✓; substrate citations at installed-source level |
| H14 | AI thread summarization (premium perk) absent — 100% host-side reuse of existing substrate (`generate_ai_text`, Celery task pattern from `send_forum_push`, `AICacheService` content-hash caching); needs H12 first | ai-integration | docs-researcher (AI) | `H/tasks.py` (pattern), `H/api.py` (anchor) | confirmed | deferred → todo 255 | substrate verified ✓ |
| H15 | Semantic "similar topics" on compose absent — `django_ai_core.contrib.index` (pgvector storage, `rebuild_indexes` cmd) already ships in the dependency tree via wagtail-ai 3.x and is dormant; `ModelSource` verified to work on plain models (Topic/Post are non-Page); one-time infra: INSTALLED_APPS + pgvector extension (Railway support UNVERIFIED — check first) + index definition. Product call: arguably free-for-all, not premium-gated (dedupe helps community health) | ai-integration | docs-researcher (AI) | settings (anchor), `W/models/topics.py:9-16` | confirmed | deferred → todo 255 | cross-checked by Wagtail researcher: wagtail-ai 3.1.0 METADATA requires django-ai-core; imports verified at installed-version level; wagtail-vector-index staleness verified on PyPI (v0.10.0, June 2024, Wagtail 5 classifier only) — the django-ai-core path is right |
| H16 | No effective human moderation queue in Wagtail admin — 3 compounding gaps: (a) `SpamCheckTask` never overrides `get_task_states_user_can_moderate()` (base returns `TaskState.objects.none()`) so "Awaiting my review" can STRUCTURALLY never show forum content to anyone; (b) no `list_filter` on any of the 3 SnippetViewSets — Post/Topic listings have no filter UI, not even live/draft; (c) no `construct_homepage_panels` "N awaiting moderation" count (blog does exactly this in-repo). Mod's only path to rejected content = paginating an unfiltered listing | wagtail | wagtail-reviewer | `W/models/moderation.py:6-38`, `W/wagtail_hooks.py:7-52`, contrast `apps/blog/wagtail_hooks.py:44,161` | confirmed | deferred → todo 254 | greps ✓; docs: override is the standard mechanism (custom_tasks.md, GroupApprovalTask precedent). Research refinement: spam check resolves synchronously, so (a) bites on the FAILURE path — create-path `workflow.start` (workflow.py:61) is unwrapped (edit path IS wrapped), so a spam-backend exception orphans an IN_PROGRESS TaskState nobody can see — frame the fix there |
| H17 | `ForumIndex`/`ForumBoard` are live-routable Pages with no template and no `serve()` override, package ships no `templates/`; host mounts `wagtail.urls` catch-all → published board served directly (admin "View live", sitemap, crawler) raises `TemplateDoesNotExist` → 500. No documented headless contract excuses it (blog pages in-repo have templates) | wagtail | wagtail-reviewer | `W/models/boards.py:7-26`, `plant_community_backend/urls.py:168` | confirmed | verified | FIXED: minimal fallback templates (`templates/wagtail_forum/forum_index.html` + `forum_board.html`, host-overridable) + `get_context` (index lists live+public child boards; board lists live topics, pinned-first, capped `SERVED_TOPICS_LIMIT=50`); 2 serve()-level tests incl. live-only filtering; kimi clean |
| H18 | No retry affordance on any forum error state — all 4 pages render a static error box; only recovery is a full browser reload | web-ux | react-ts-reviewer | `web/pages/forum/*` (CategoryList:49, ThreadList:143, ThreadDetail:258, NewThread:105) | — | deferred → todo 259 | agent-read ✓ |
| H19 | Composer toolbar buttons have no accessible name: glyph text ("B","•","1.") becomes the accessible name and `title` is ignored — screen readers announce "B, button" across the entire primary write path; tests query `getByTitle` so they can't catch it | web-ux | react-ts-reviewer | `web/components/forum/TipTapEditor.tsx:220-234,108-185` | confirmed | verified | FIXED: `aria-label={title}` on ToolbarButton + spec-citing comment; new getByRole(name) test proving the a11y-tree exposure (getByTitle alone can't); kimi clean |
| H20 | Edit/Delete invisible-but-focusable for desktop keyboard users: `md:opacity-0 md:group-hover:opacity-100` with no focus-visible fallback — WCAG 2.4.7 failure on tab-reachable controls | web-ux | react-ts-reviewer | `web/components/forum/PostCard.tsx:104` | confirmed | verified | FIXED: `md:group-focus-within:opacity-100` added alongside the hover reveal + WCAG-citing comment; class-contract test pin; kimi clean |
| H21 | Tombstone pruning never scheduled: `prune_forum_tombstones` documents "run daily via beat/cron" and is unit-tested, but no `CELERY_BEAT_SCHEDULE` exists anywhere (`send_forum_push` is the backend's only Celery task, `.delay()`-only) and railway.json never invokes it — `TopicDeletedLog` grows unbounded; the 30-day retention contract is silently unenforced | celery/ops | cross-cutting | `W/management/commands/prune_forum_tombstones.py:1-8`, `plant_community_backend/` (grep 0), `backend/railway.json` | — | deferred → todo 261 | grep BEAT_SCHEDULE → 0 ✓ |
| H22 | ~~Live `/search/` has no index behind it~~ CONTRADICTED by empirical research: with `django.contrib.postgres` installed, the default backend resolves to `PostgresSearchBackend` (verified by executing `get_search_backend()` in the live env) with real FTS, `ts_rank` ranking, and applied GIN-index migrations (`wagtailsearch 0004`) — the "unindexed linear scan" only applies to SQLite/unknown vendors. The package README's own caveat overstates the risk. Valid residue (already tracked in H8/M40): 50-cap silent truncation, no `has_more`, client synthesizes `has_next: false` | performance | cross-cutting → docs-researcher (Wagtail) | `W/api/views.py:623-659`, `backend/packages/wagtail_forum/README.md:9-16` | contradicted ⚠ | false-positive | empirical: backend = PostgresSearchBackend, GIN migrations applied; closed false-positive at triage 2026-07-11 (user approved recommended triage); truncation residue tracked in H8/M40; README caveat correction folded into M18 |
| H23 | PATCH on a moderated (untrusted-author) edit returns the STALE pre-edit body with `status: "live"` while only `moderation_status: "pending"` hints otherwise — no response field carries the submitted content or flags staleness, so a client renders the user's edit "reverting" before their eyes. Zero untrusted-author coverage on the endpoint (tests use member/moderator only, both autopublish) | django-drf | django-drf-reviewer (empirically proven via throwaway pytest) | `W/api/views.py:444-475`, `W/workflow.py:135-212` | — | verified | FIXED: when `moderation_status='pending'` the PATCH response serializes the SUBMITTED revision (`latest_revision.as_object()`) instead of the reverted live row; `@extend_schema` description documents the semantics (GET keeps serving the live body); new untrusted-author flagged-edit test asserts submitted-body echo + unchanged live read; 223 forum tests green; kimi clean |
| H24 | SearchView post-hits reintroduce the already-fixed image N+1: `p.body.render_as_block()` iterates the resolved StreamValue — the exact pattern `serializers.py:177-191` documents as dangerous and raw_data serialization was built to avoid; measured +1 query per image-bearing post; endpoint has no query-count test and is public/unauthenticated | django-drf/performance | django-drf-reviewer (empirical: 1 post=4q, 5 posts=8q) | `W/api/views.py:656` | — | verified | FIXED: `_plain_text_excerpt` iterates `raw_data` (plain text — also kills M40's dangling-tag slice), `MAX_EXCERPT_CHARS=200`; regression test pins equal query counts for 1 vs 5 image-bearing hits + asserts no `<` in excerpt; 13 search/sync tests green; kimi clean |
| H25 | `FORUM_BODY_SCHEMA` — the OpenAPI type for every post `body` — omits the `value` property entirely (declares only `type`+`id`), so any codegen client type lacks the one field carrying actual content; contrast the complete AUTHOR/BOARD/CAPABILITIES schemas in the same file | django-drf | django-drf-reviewer | `W/api/serializers.py:47-56,208,261` | — | verified | FIXED: `value` property added (`oneOf` string/object + content-shape comment); `manage.py spectacular` clean; kimi clean |
| H26 | `author` is a bare username string on Topic resources but a rich object on Post resources (`last_post_author` string-only too) — same concept, two incompatible shapes in one API; blocks any generic author renderer. Fix merges naturally with H7 profile enrichment | django-drf | django-drf-reviewer | `W/api/serializers.py:74-77,96-99` vs `:226,251-259` | — | deferred → todo 257 | read :74 ✓ CharField |

### Medium

| ID  | Finding       | Domain | Agent                 | File(s)     | Research | Status | Verification |
| --- | ------------- | ------ | --------------------- | ----------- | -------- | ------ | ------------ |
| M1  | No quote-reply: BlockQuoteBlock exists in schema + renderer, but composer can't produce it (nh3 flattens; toolbar omits) and no Quote button | product-ux | feature-gap inventory | `W/blocks.py:25`, `web` TipTapEditor:124-127, PostCard | — | deferred → todo 256 | agent-read ✓ |
| M2  | No bookmarks/saves | product-ux | feature-gap inventory | `W` (anchor: new model) | — | deferred → todo 263 | agent grep → 0 ✓ |
| M3  | No drafts/autosave — composer state is in-memory only, no `beforeunload` guard; refresh/back-nav/crash loses the post unrecoverably (failed-submit preservation DOES work) | product-ux | feature-gap inventory + react-ts-reviewer | `web/pages/forum/NewThreadPage.tsx:30`, `ThreadDetailPage.tsx:70` | — | deferred → todo 263 | agent-read ✓ ×2 |
| M4  | Edit history stored (RevisionMixin) but no endpoint/viewer — "Edited" stamp with nothing behind it | product-ux | feature-gap inventory | `W/models/posts.py:54-60`, `web` PostCard:87-96 | — | deferred → todo 263 | agent-read ✓ |
| M5  | No tags/taxonomy beyond boards (species/genus/symptom tags are the natural discovery axis) | product-ux | feature-gap inventory | `W/models/topics.py` (anchor) | — | deferred → todo 256 | agent grep → 0 ✓ |
| M6  | Zero linkage to the app's own plant domain: can't attach a plant-ID result/species to a question — the app's differentiator is absent from its forum | product-ux | feature-gap inventory | `W/blocks.py:13-30` (anchor: new block) | — | deferred → todo 263 | agent grep → 0 ✓ |
| M7  | Image authoring below par for a photo-centric community: alt-text authoring absent END-TO-END (composer inserts display-only alt, write path intentionally drops it, backend re-derives alt=filename, renderer falls back to `''`) — an a11y gap, not just polish; plus no paste/drag-drop upload, no lightbox | product-ux | feature-gap inventory + react-ts-reviewer (chain verified end-to-end) | `W/api/serializers.py:147`, `W/api/views.py:549`, `web/utils/forumBody.ts:17-22`, `forumImageNode.ts:1-23`, `StreamFieldRenderer.tsx:94-100` | — | deferred → todo 263 | agent-read ✓ ×2 |
| M8  | No polls | product-ux | feature-gap inventory | `W/blocks.py` (anchor) | — | deferred → todo 263 | agent grep → 0 ✓ |
| M9  | No block/mute users | product-ux | feature-gap inventory | `W` (anchor: new model) | — | deferred → todo 263 | agent grep → 0 ✓ |
| M10 | No private messaging (M9 is a trust&safety prerequisite) | product-ux | feature-gap inventory | new surface | — | deferred → todo 263 | agent grep → 0 ✓ |
| M11 | No per-post permalinks/share: DOM anchors exist but no copy-link control; async fetch means native hash-scroll silently no-ops before the target renders; posts beyond page 1 aren't in the DOM at all — replies are not reliably linkable; no oEmbed/link previews. (react-ts-reviewer rates this High — triage call) | product-ux | feature-gap inventory + react-ts-reviewer | `web/pages/forum/ThreadDetailPage.tsx:82-117,366`, `PostCard.tsx` | — | deferred → todo 256 | agent-read ✓ ×2 |
| M12 | Semantic search upgrade (premium) — marginal add once H15 infra exists (`VectorIndex.search_sources()` generic). Baseline correction per H22 research: the current backend is already Postgres FTS with ranking (not the naive fallback), so the semantic upgrade's value-add is synonym/meaning matching, not "any ranking at all" | ai-integration | docs-researcher (AI) | settings (anchor) | confirmed | deferred → todo 255 | substrate verified; baseline corrected via H22 empirical result |
| M13 | RAG plant-care answers grounded in site's plant-ID + blog data — highest differentiation, long-horizon big bet; strict superset of H15 infra; needs citation UX + hallucination guardrails (plant-care advice has real-world consequences). Do not start before H15 | ai-integration | docs-researcher (AI) | (feasibility) | — | deferred → todo 255 | feasibility-only |
| M14 | AI-assisted composer (draft improvement) — wagtail-ai's admin editor machinery does NOT transfer to the end-user TipTap composer (verified: panels are `/cms/`-only); only the backend `generate_ai_text` substrate applies → bespoke host endpoint + TipTap toolbar action; least favorable cost profile (interactive, uncacheable) | ai-integration | docs-researcher (AI) | `H/api.py` (anchor), `web` TipTapEditor | confirmed | deferred → todo 255 | wagtail-ai surface verified admin-only at code level ✓ |
| M15 | Every API-driven publish/unpublish logs actor `user=None` ("system") — Wagtail `LogContext` only activates in admin auth flow, never in DRF path — so even moderator PATCH/DELETE actions are unattributable in snippet History | wagtail | wagtail-reviewer | `W/workflow.py:52,61,107`, `W/api/views.py:512` | confirmed | verified | FIXED: trusted-path publish, topic publish, and DELETE unpublish (direct `UnpublishAction` — the mixin can't skip perm checks) now carry the acting user + `skip_permission_checks=True`; `workflow.start` stays `None` — load-bearing, Wagtail's completion hook publishes permission-checked as requested_by (empirically hit, documented in docstring); 2 new API attribution tests (ModelLogEntry.user); query pins 32→33/68→69 explained (+1 `auth_user` existence check per attributed log write); full forum+host suite 214 passed; kimi clean |
| M16 | No preview support: neither `HeadlessPreviewMixin` (used by blog in-repo) nor `PreviewableMixin` on Topic/Post/Board — mods can't preview a NEEDS_CHANGES post's rendered body; SPA can't offer pre-moderation preview; SnippetViewSet would auto-detect the mixin | wagtail | wagtail-reviewer | `W/models/topics.py:9-16`, `W/models/posts.py:19-26`, contrast `apps/blog/models.py:30,597` | confirmed | deferred → todo 254 | agent-read ✓; docs: auto-detect verified (snippets.py:624); note model must also implement get_preview_template/serve_preview — registration alone doesn't render |
| M17 | Zero i18n: no `gettext_lazy` on any user/admin-facing string (menu labels, all API error messages), no `TranslatableMixin` on Topic/Post (wagtail-localize has no path to forum content) | wagtail | wagtail-reviewer | `W/wagtail_hooks.py:10-51`, `W/api/views.py:97-119`, `W/api/sanitize.py:62-136` | — | deferred → todo 262 | agent-read ✓ |
| M18 | README (24 lines) documents almost nothing a reuser needs: silent on ALL 13 `WAGTAILFORUM_*` settings, the 3 public signals, the pluggable `SpamBackend` interface, and install/bootstrap steps (workflow bootstrap, Forum Moderators group pattern). Package IS pip-installable (pyproject.toml exists) — gap is docs only | wagtail | wagtail-reviewer + cross-cutting (independent convergence, 13 settings counted) | `W/../README.md`, `W/conf.py:5-34`, `W/signals.py:18-20` | — | deferred → todo 262 | pyproject verified present ✓ |
| M19 | No per-board moderation/permission granularity: single global `wagtail_forum.change_post` perm + one flat "Forum Moderators" group — "moderator of one board only" impossible. REFRAMED by research: the reviewer's proposed mechanism doesn't apply — `GroupPagePermission` is hard-FK'd to Page and Topic/Post are snippets with no tree position; no GroupSnippetPermission analog exists — a custom board-scoped permission check (group↔board mapping consulted via `post.topic.board_id`) is the required shape | wagtail | wagtail-reviewer + docs-researcher | `W/models/posts.py:107-143`, `H/bootstrap.py:20-46` | better-fix | deferred → todo 254 | agent-read ✓; mechanism reframe verified against pages.py:2139 + permission_policies/pages.py:89 |
| M20 | Admin polish cluster: no `register_admin_search_area` (forum invisible in global admin search — blog registers one in-repo), `search_fields` missing on Post/Profile viewsets (no search box), no bulk actions for spam-wave cleanup | wagtail | wagtail-reviewer | `W/wagtail_hooks.py:12,21-45` | confirmed | deferred → todo 254 | agent-read ✓; hooks current per docs/reference/hooks.md |
| M21 | Test-fixture bug: `Array(20).fill(createMockPost())` fills 20 slots with ONE object (default id `post-1`) → 19 duplicate-key React warnings per run, copy-pasted at 4 sites — CI noise that masks real warnings; fix = `Array.from({length:20},(_,i)=>createMockPost({id:\`post-${i}\`}))` | testing | react-ts-reviewer | `web/tests/forumUtils.ts:94`, `ThreadDetailPage.test.tsx:530`, `ThreadListPage.test.tsx:274,293,322` | — | verified | FIXED: `Array.from` with per-index ids at all 4 sites + explanatory comment; 38 tests pass with 0 duplicate-key warnings (was 19/run); kimi clean |
| M22 | Data-fetch effects lack unmount/race guards (no AbortController/cancelled flag, 3 pages) — fast navigation can render thread A's content under thread B's URL | web-ux | react-ts-reviewer | `web/pages/forum/ThreadListPage.tsx:36-75`, `ThreadDetailPage.tsx:82-117`, `NewThreadPage.tsx:36-60` | confirmed | deferred → todo 259 | agent grep ✓; react.dev prescribes the `ignore` cleanup flag as PRIMARY (AbortController alone documented insufficient) |
| M23 | Reaction "reacted" state discarded: backend already returns `ReactionToggleResult.reacted`, `handleReact` drops it, `Post` type can't hold it, buttons have no pressed state or `aria-pressed` — users can't tell what they've already reacted to | web-ux | react-ts-reviewer | `web/types/forum.ts:239`, `ThreadDetailPage.tsx:180-194`, `PostCard.tsx:136-146` | — | deferred → todo 257 | read handleReact ✓ discards `reacted` |
| M24 | Native blocking dialogs used inconsistently: `alert()` for pending-moderation on new thread while the identical outcome uses a styled banner for replies; `confirm()` for delete; `prompt()` for link URL with no validation | web-ux | react-ts-reviewer | `NewThreadPage.tsx:80`, `ThreadDetailPage.tsx:197`, `TipTapEditor.tsx:161` | — | deferred → todo 259 | agent-read ✓ |
| M25 | Focus drops after posting a reply: remount-via-key clears cleanly but the fresh editor is never autofocused and no success announcement fires | web-ux | react-ts-reviewer | `ThreadDetailPage.tsx:156-157`, `TipTapEditor.tsx:31-59` | — | deferred → todo 259 | agent-read ✓ |
| M26 | Write-path error/notice banners have no `role="alert"`/aria-live (4 sites) — screen readers never hear a failed post or a moderation notice. SCOPE BROADENED by research: all 8 existing `role="alert"` sites app-wide (incl. TipTapEditor's, Input.tsx:81, LoginPage:161, …) use the conditional-mount-with-content anti-pattern that MDN documents as generally NOT announced — the "done right" example isn't actually effective either | web-ux | react-ts-reviewer + docs-researcher | `ThreadDetailPage.tsx:334-338`, `NewThreadPage.tsx:161-165`, `ThreadListPage.tsx:146-149`, `CategoryListPage.tsx:52-55`, app-wide role=alert sites | better-fix | deferred → todo 259 | agent-read ✓; fix = persistent live-region container, swap text content (MDN alert role) |
| M27 | Clicking Edit on a second post silently discards unsaved edits on the first (single `editingPostId`/`editBody` state, no dirty check) | web-ux | react-ts-reviewer | `ThreadDetailPage.tsx:75-76,212-215` | — | deferred → todo 259 | agent-read ✓ |
| M28 | `as unknown as ForumAuthor` ×4 suppresses a real structural mismatch (`id: ''` string vs required `User.id: number`); plus 6 dead exported legacy types (FetchThreadsOptions, CreateThreadInput, Reaction, …) | react-typescript | react-ts-reviewer | `web/services/forumMappers.ts:88-109`, `web/types/forum.ts:113-207` | — | deferred → todo 258 | read mappers ✓ id:'' ×4 |
| M29 | No client-side file size/type pre-check before image upload — no max-size hint; slow connections wait through a full failed upload to learn the file was too big | web-ux | react-ts-reviewer | `TipTapEditor.tsx:65-88,186-193` | — | deferred → todo 259 | agent-read ✓ |
| M30 | Pagination: no jump-to-page/jump-to-latest in long threads; the two Load More buttons are inconsistent (detail shows "(N remaining)", list shows bare "Load More" because `meta.count` is hardcoded 0 in the service) | web-ux | react-ts-reviewer | `ThreadListPage.tsx:261-274`, `forumService.ts:132` | — | deferred → todo 259 | agent-read ✓ |
| M31 | No scroll-to-top on forum navigation — deep-scrolled list → thread renders mid-page; `useHandlePageChange` hook exists and is already used by Search/Blog pages, just not wired here | web-ux | react-ts-reviewer | `web/layouts/RootLayout.tsx`, `web/hooks/useHandlePageChange.ts` | — | deferred → todo 259 | agent-read ✓ |
| M32 | `quote` block sanitize contract mismatch: package doc says plain-text blocks are consumer-escaped; web renderer instead treats any `<`-containing quote as HTML (`includes('<')` heuristic) and DOMPurifies with the broad STREAMFIELD preset (h1-h6/pre/img/div ≫ forum nh3 allowlist); reachable via direct API POST (composer never emits quote). No live bypass constructed — contract mismatch + ZERO tests either side for script/onerror in quote/heading/code blocks | security | cross-cutting | `W/api/sanitize.py:1-12,144-150`, `web/components/StreamFieldRenderer.tsx:31-37,110`, `web/utils/sanitize.ts:114-139` | confirmed | verified | FIXED (test gap — the verified actual gap): backend contract test pins paragraph=nh3-cleaned vs quote/heading/code=verbatim through the real API round-trip; web tests pin the renderer neutralizing script/onerror in string-shaped quotes + React-escaping heading/code. The heuristic/preset tightening itself deferred to the web-UX epic (behavior change, riskier); kimi clean |
| M33 | `send_forum_push` retries permanent FCM failures: bare `except Exception` → `self.retry()` ×3 fixed interval, no `autoretry_for`, no backoff — contra the project's celery pattern doc; the retry branch has zero test coverage (tests cover skip-conditions only, never a raising `fcm.send`) | celery | cross-cutting | `H/tasks.py:16,74`, `H/tests/test_tasks.py` | — | verified | FIXED: `_is_permanent_fcm_error` (UnregisteredError/SenderIdMismatch/ThirdPartyAuth/InvalidArgument — lazy-import safe) → log-and-return; transient path keeps `self.retry` with exponential backoff 30/60/120s; tests: 4 parametrized permanent classes (single attempt) + eager `apply()` transient test proving initial+3 retries then FAILURE; kimi clean (its 2 WARNINGs addressed: classes parametrized; ForumPage deletion separately verified) |
| M34 | Forum write path has no E2E coverage: golden-path spec is unauthenticated-browse-only by its own comment (written before Spec 2 landed); create/reply/edit/delete/react/upload exist only as mocked component tests — real network/CSRF/cookie path unexercised | testing | cross-cutting | `web/e2e/forum-golden-path.spec.ts:3-4` | — | deferred → todo 261 | agent-read ✓ |
| M35 | PATCH `/posts/{id}/` lacks Idempotency-Key support unlike all sibling writes; a retried edit re-runs `submit_edit_for_moderation` → duplicate revision row + duplicate `moderation_decided` signal → traced to an unconditional duplicate FCM push (no dedup at any layer) | django-drf | django-drf-reviewer | `W/api/views.py:444-475`, `W/workflow.py:174,211`, `H/notifications.py:51-65`, `H/tasks.py:68-70` | — | deferred → todo 258 | agent-traced end-to-end ✓ |
| M36 | POST `/forum/images/` lacks Idempotency-Key — a retried multipart upload (most retry-prone request shape; the docstring's own mobile use case) creates duplicate Image rows + stored files; `docs/rules/api.md:31-35` names the package's own `idempotency.py` as the reference contract | django-drf | django-drf-reviewer | `W/api/views.py:516-557` | — | deferred → todo 258 | agent-read ✓ |
| M37 | OpenAPI response-code gaps: topic/reply create declare 201/409/422 but not the provable 400; ReactionToggle omits 409/422 despite running the same idempotency contract; list GETs document 404 in prose only (board-lookup 409 documented on POST only); plus zero `examples=` anywhere | django-drf | django-drf-reviewer | `W/api/views.py:140-146,167-177,302-308,345-353,564-571` | — | deferred → todo 258 | agent-read ✓ |
| M38 | `MeProfileView` has zero `@extend_schema` (no description, no 400 for bio/fcm_token length failures) — thinnest docs of any endpoint. History: trial todo 254 fixed the related capabilities `@extend_schema_field` but this view-level gap persists | django-drf | django-drf-reviewer | `W/api/views.py:611-620` | — | deferred → todo 258 | agent-read ✓ |
| M39 | The consistent error envelope is HOST-owned (`apps/core/exceptions.py` via the project-level `EXCEPTION_HANDLER`) — the reusable package neither ships nor documents that dependency; another host gets bare DRF `{"detail"}` responses (silently different contract); the one envelope test accepts either shape so pins neither | django-drf (reusability) | django-drf-reviewer | `apps/core/exceptions.py:57-224`, `settings.py:448`, `W/tests/api/test_topic_create.py:318` | — | deferred → todo 258 | agent grep: 0 refs in package ✓ |
| M40 | Four different list envelope shapes in one API (cursor `{results,next,previous}` / flat `{results}` / search `{topics,posts}` / sync custom); search per-item fields are a poorer subset of the list serializers (drop reply_count/view_count/is_pinned/last_post_at) and the search excerpt is raw HTML from a different render path, char-truncated → can emit dangling/unclosed tags | django-drf | django-drf-reviewer | `W/api/views.py:643,656,659,726-734`, `W/api/serializers.py:81-92` | — | deferred → todo 258 | read :656 ✓ `[:200]` slice |
| M41 | Deleted-author representation inconsistent: `null` on topics vs `{"username":"[deleted]",…}` sentinel on posts — two absent-value conventions for the same condition | django-drf | django-drf-reviewer | `W/api/serializers.py:74` vs `:252-258` | — | deferred → todo 257 | agent-read ✓ |
| M42 | No HTTP-layer caching/conditional requests (Cache-Control/ETag/Last-Modified) on hot public reads — DISTINCT from the documented no-Redis-app-cache decision (which covers only the application cache); board/topic lists are public + read-heavy and the deploy already sits behind Cloudflare; caveat: post-list `can_edit`/`can_delete` is per-user so caching must be anon-scoped/varied | django-drf/performance | django-drf-reviewer | `W/api/*.py` (grep 0), `backend/docs/patterns/architecture/caching.md:186-198` | — | deferred → todo 261 | agent grep ✓ |
| M43 | `WAGTAILADMIN_BASE_URL = "http://localhost:8000"` hardcoded (neighbors `FRONTEND_BASE_URL`/`HEADLESS_PREVIEW_CLIENT_URLS` correctly use `config()`) — no env var can override it, so every production absolute URL Wagtail generates (workflow/moderation notification email links, user bar, preview links, sitemap) points at localhost | wagtail/ops | docs-researcher (Wagtail) — incidental find | `backend/plant_community_backend/settings.py:411` | confirmed | verified | FIXED: `config("WAGTAILADMIN_BASE_URL", default="http://localhost:8000")` + intent comment; `manage.py check` clean; kimi-review clean. Railway env var to set at deploy |

### Low

| ID  | Finding       | Domain | Agent                 | File(s)     | Research | Status | Verification |
| --- | ------------- | ------ | --------------------- | ----------- | -------- | ------ | ------------ |
| L1  | Reaction counts invisible to logged-out readers (row renders only when `onReact` passed = authed) — social proof lost | product-ux | feature-gap inventory | `web/components/forum/PostCard.tsx:133`, `ThreadDetailPage.tsx:371` | — | deferred → todo 257 | read PostCard:133 ✓ |
| L2  | Onboarding/empty-community surface bare: one-liner empty states; `ForumIndex.intro` CMS field never serialized so welcome copy can't reach UI; no guidelines surface; board list lacks last-activity info | product-ux | feature-gap inventory | `W/models/boards.py:10`, `W/api/serializers.py:67-70`, `web` CategoryListPage:70-74 | — | deferred → todo 259 | agent-read ✓ |
| L3  | `locked` missing from topic-list payload; web approximates with `is_closed` — lock badge wrong in lists. (django-drf-reviewer independently converged and rates Medium: write-eligibility is unpredictable from list data since the guard is `is_closed OR locked` — treat as Medium at triage) | product-ux | feature-gap inventory + django-drf-reviewer | `W/api/serializers.py:79-92,102-121`, `web/services/forumMappers.ts:141` | — | verified | FIXED: `locked` BooleanField added to TopicListSerializer (mirrors detail) + web `BackendTopicListItem.locked` + mapper `is_closed \|\| locked` + backend payload test + web mapper/service fixture tests; backend 4 passed, web 33 passed, tsc clean; kimi-review clean |
| L4  | No markdown input path; effective formatting minimal after nh3 allowlist; NewThreadPage requires `?category=` — no board picker in composer | product-ux | feature-gap inventory | `web` TipTapEditor:124-127, `NewThreadPage.tsx:38-40` | — | deferred → todo 259 | agent-read ✓ |
| L5  | No badges/gamification; trust levels exist as machinery but are invisible (with H7) so no progression incentive | product-ux | feature-gap inventory | `W/models/profiles.py:6-11` (anchor) | — | deferred → todo 257 | agent grep → 0 ✓ |
| L6  | Doc drift: `blog.md` "Rate Limiting by User Tier" documents a `TIER_LIMITS`/premium API that does not exist in `ai_rate_limiter.py` (copied from an archived aspirational pattern) — overstates premium infra | ai-integration | docs-researcher (AI) | `backend/docs/patterns/domain/blog.md:381-450` | — | deferred → todo 255 | read blog.md:381 ✓ |
| L7  | `OPENAI_API_KEY` defaults to `""` — whether production AI endpoints actually work depends on a deployed secret unverifiable from the repo; ops check before shipping any AI feature | ai-integration | docs-researcher (AI) | `backend/plant_community_backend/settings.py:771` | — | deferred → todo 255 | agent-read ✓ |
| L8  | `index.AutocompleteField("title")` declared on Topic but nothing calls `backend.autocomplete()` — dead index cost; wire a typeahead or drop it | wagtail | wagtail-reviewer | `W/models/topics.py:67` | confirmed | deferred → todo 256 | agent-read ✓; `.autocomplete()` API verified current (modelsearch/backends/base.py:825) — a typeahead endpoint is cheap to add |
| L9  | `ForumPage.tsx` is dead/orphaned code showing stale "Forum coming soon" — unreachable from any route; real board list is `CategoryListPage` | web-ux | react-ts-reviewer | `web/pages/ForumPage.tsx:1-21`, `App.tsx:61` | — | verified | FIXED: deleted (re-verified 0 refs in worktree first); tsc + eslint clean; kimi clean |
| L10 | Composer toolbar buttons ~32px tall — under the project's own 44px tap-target rule, which the same feature applies correctly elsewhere | web-ux | react-ts-reviewer | `TipTapEditor.tsx:220-234` vs `web/docs/patterns/tailwind.md:21-26` | confirmed | deferred → todo 259 | agent-read ✓; cite WCAG 2.5.5 (AAA 44px) not 2.5.8 (AA 24px) — project rule is a voluntary AAA bar |
| L11 | `Button` never sets `aria-busy` while loading and the label doesn't change during submit — no busy signal on primary write actions | web-ux | react-ts-reviewer | `web/components/ui/Button.tsx:65-72` | confirmed | deferred → todo 259 | agent-read ✓; research: label-swap ("Posting…") is the reliable primary signal, aria-busy supplementary (MDN/ARIA 1.2) |
| L12 | Absolute timestamps hover-only (`title` attr) — inaccessible on touch and to screen readers | web-ux | react-ts-reviewer | `PostCard.tsx:85`, `ThreadCard.tsx:103-112` | confirmed | deferred → todo 259 | agent-read ✓; fix = `<time datetime>` + aria-label pattern (MDN title a11y concerns) |
| L13 | Composer/upload tests tautological ("provides onChange" asserts the mock is defined; loading-state test passes either way); `handleImageSelect` success/failure paths uncovered | testing | react-ts-reviewer | `TipTapEditor.test.tsx:67-79,137-156` | — | deferred → todo 259 | agent-read ✓ |
| L14 | Identity/polish cluster: `trust_level` renders as raw unstyled text (always null today per H7), decorative emoji not `aria-hidden`, reactions row missing `flex-wrap` | web-ux | react-ts-reviewer | `PostCard.tsx:71-75,134`, `ThreadDetailPage.tsx:311-328` | — | deferred → todo 257 | agent-read ✓ |
| L15 | Dead `password="x"` kwarg across ~25 forum test files (all use `force_login`/`force_authenticate`, none call `client.login()`) — violates the binding testing rule verbatim; bulk-removable | testing | cross-cutting | `W/tests/test_admin.py:9,18,29` + 24 more files | — | verified | FIXED: one deterministic perl sweep removed all 101 `, password="x"` sites across 25 files (grep re-verified 0 remaining); full forum+host suite 223 passed; kimi clean |
| L16 | Reaction types hand-duplicated: web `REACTION_TYPES` literal mirrors backend `Reaction.REACTION_CHOICES` with no schema link — a backend change silently desyncs the UI | api-contract | cross-cutting | `web/components/forum/PostCard.tsx:14`, `W/models/reactions.py:8-16` | — | deferred → todo 258 | agent-read ✓ |
| L17 | No `makemigrations --check` gate in CI (project-wide; verified currently clean for forum apps) — preventive gap given 11 forum migrations and schema churn history | testing | cross-cutting | `.github/workflows/backend-ci.yml` | — | deferred → todo 261 | agent ran --check: clean ✓ |
| L18 | PATCH costs 68 pinned SQL queries, DELETE 32 (exact test pins — good hygiene); likely inherent to Wagtail's revision/workflow/signal cascade, but 68 round-trips per edit is a real latency line-item on hosted Postgres — profiling pass warranted | performance | django-drf-reviewer | `W/tests/api/test_post_edit_delete.py:475,497` | — | deferred → todo 258 | agent-read ✓ |
| L19 | No `Location` header on any 201 response (topic/reply/image create) | django-drf | django-drf-reviewer | `W/api/views.py:210,401,556-557` | — | deferred → todo 258 | agent-read ✓ |
| L20 | `versioning_class = None` rationale commented on only 1 of 12 view classes (no functional risk — `request.version` unused) | django-drf | django-drf-reviewer | `W/api/views.py:128-130` | — | deferred → todo 258 | agent-read ✓ |
| L21 | Product/privacy note: cross-user image reuse is by-design (collection-scoped, sequential integer PKs — any member can embed another member's uploaded image in their own post); deliberate per the docstring — flagged for roadmap-owner review, not a defect | product-ux | django-drf-reviewer | `W/api/sanitize.py:122-137`, `W/api/views.py:517-521` | — | deferred → todo 254 | agent-read ✓ docstring |

## Strengths (context — do not re-litigate)

Per the Wagtail reviewer's depth pass: Topic/Post are textbook "FullFeaturedSnippets"
(WorkflowMixin/DraftStateMixin/LockableMixin/RevisionMixin/index.Indexed with correct
GenericRelation overrides) buying History/lock/unpublish/workflow admin views for free;
the moderation workflow is admin-reconfigurable (get_or_create defaults pattern);
signal handling is isinstance-correct with a first-publish guard; the custom DRF API
is justified (API v2 can't do moderation filtering/delta sync/idempotency);
`raw_data` StreamField serialization dodges the chooser N+1; search field declarations
are Elasticsearch-ready; `WAGTAILFORUM_*` follows core naming convention; images reuse
Wagtail's Collection/rendition system; reusability is test-enforced. The package is
pip-installable (pyproject.toml).

Per the cross-cutting pass: the absence of a forum read-cache layer is a documented
decision, not a gap (`caching.md:186-198` — denormalized counters instead of a cache
service, updated 2026-07-04); hot-path indexes match the cursor querysets
(`(board, -last_post_at)`, `(topic, created_at)`) and are adequate at current scale;
`makemigrations --check` verified clean for both forum apps.

Per the API reviewer: throttling coverage is comprehensive AND drift-guarded (three
structural tests fail on any new unthrottled endpoint); list/detail reads carry exact
query-count pins; 401/403 coverage is broad across every write endpoint; the
affordance-parity tests (can_edit/can_delete driven off the same fixture as the write
outcomes) are a model pattern; 4-layer upload validation + nh3 XSS round-trips are
thorough; the compound sync cursor + tombstones are solid. `BoardListView` being
unpaginated is intentional (admin-curated set).

## Deferred Items

Items marked `deferred` must have a linked todo and rationale. Per the user's
Phase 2.5 triage decision, deferral is epic-shaped: one todo per epic, each
listing its member finding IDs (76 findings → 11 todos, none dropped).

| Findings | Todo | Rationale |
| --- | ---- | --------- |
| C2, H1, H2, H3, H4, H10 | `todos/253-pending-p1-forum-notifications-engagement.md` | Notification/engagement loop is feature work (new model + API + clients), not a same-day fix; p1 theme selected by user |
| C1, H16, M16, M19, M20, L21 | `todos/254-pending-p1-forum-moderation-safety-admin.md` | Report mechanism + admin moderation surface is a coherent feature cluster; p1 theme selected by user |
| H12, H13, H14, H15, M12, M13, M14, L6, L7 | `todos/255-pending-p1-forum-ai-premium.md` | Every AI feature gates on the missing entitlement primitive (H12 first); pgvector-on-Railway precheck required; p1 theme selected by user |
| H6, H8, H9, M1, M5, M11, L8 | `todos/256-pending-p1-forum-qa-discovery-seo.md` | Solved-marking/search wiring/SEO are product features spanning both stacks; p1 theme selected by user |
| H7, H26, M23, M41, L1, L5, L14 | `todos/257-pending-p2-forum-identity-profiles.md` | Author-contract unification is API-breaking — needs its own coordinated pass |
| M28, M35, M36, M37, M38, M39, M40, L16, L18, L19, L20 | `todos/258-pending-p2-forum-api-contract-hardening.md` | Idempotency parity + envelope normalization are contract changes best batched; M35/M36 should precede the mobile write path |
| H18, M22, M24, M25, M26, M27, M29, M30, M31, L2, L4, L10, L11, L12, L13 | `todos/259-pending-p2-forum-web-ux-hardening.md` | Large but batchable UX/a11y cluster; M26's fix is app-wide (live-region infra), beyond audit scope; carries M32 renderer residue |
| H11 | `todos/260-pending-p2-forum-mobile-client.md` | Full Flutter client build — largest single work item; should consume stabilized p1 contracts |
| H21, M34, M42, L17 | `todos/261-pending-p2-forum-ops-infra.md` | Requires prod Celery-topology investigation (also gates push delivery) + CI/E2E infra decisions |
| M17, M18 | `todos/262-pending-p3-forum-package-polish.md` | Docs/i18n polish — valuable for reuse, no user-facing urgency; M18 carries the H22 README correction |
| M2, M3, M4, M6, M7, M8, M9, M10 | `todos/263-pending-p3-forum-content-features-later.md` | Below the p1/p2 cut; parked with promotion guidance (M7 a11y + M6 differentiator first; M9 hard-gates M10) |

## Summary

| Severity  | Found | Verified | Deferred | False-positive | Open  |
| --------- | ----- | -------- | -------- | -------------- | ----- |
| Critical  | 2     | 0        | 2        | 0              | 0     |
| High      | 26    | 7        | 18       | 1              | 0     |
| Medium    | 43    | 5        | 38       | 0              | 0     |
| Low       | 21    | 3        | 18       | 0              | 0     |
| **Total** | 92    | 15       | 76       | 1              | **0** |

(Phase-4-complete snapshot 2026-07-11. Research verdicts: 24 confirmed, 3
better-fix, 1 contradicted → false-positive (H22), remainder `—`
internal-code/benchmark findings with no external-doc hinge. All 76 open
findings deferred to epic todos 253–263 — none dropped; see Deferred Items
and Finding Status.)

## Triage decisions (user, 2026-07-11)

1. **Fix now:** the full quick-win list — ALL 15 COMPLETED AND VERIFIED:
   H5, H17, H19, H20, H23, H24, H25 / M15, M21, M32, M33, M43 / L3, L9, L15.
   Every fix: targeted tests + kimi-review clean. Final state: full forum+host
   backend suite 223 passed; full web vitest + tsc + eslint green;
   `manage.py check` + `spectacular` clean.
2. **H22** closed false-positive (empirically contradicted).
3. **Phase 4 shape:** ONE TODO PER EPIC (~11 todos), each listing member
   finding IDs with `source_review` frontmatter pointing at this manifest.
4. **P1 themes (all four selected):** social/engagement, moderation & Wagtail
   admin, AI & premium, Q&A + discovery + SEO.

### Phase 4 epic grouping (FINAL — todos created 2026-07-11)

| Todo | Epic (todo slug) | Priority | Member findings |
| --- | --- | --- | --- |
| 253 | forum-notifications-engagement | p1 | C2, H1, H2, H3, H4, H10 |
| 254 | forum-moderation-safety-admin | p1 | C1, H16, M16, M19, M20, L21 |
| 255 | forum-ai-premium | p1 | H12, H13, H14, H15, M12, M13, M14, L6, L7 |
| 256 | forum-qa-discovery-seo | p1 | H6, H8, H9, M1, M5, M11, L8 |
| 257 | forum-identity-profiles | p2 | H7, H26, M23, M41, L1, L5, L14 |
| 258 | forum-api-contract-hardening | p2 | M28, M35, M36, M37, M38, M39, M40, L16, L18, L19, L20 |
| 259 | forum-web-ux-hardening | p2 | H18, M22, M24, M25, M26, M27, M29, M30, M31, L2, L4, L10, L11, L12, L13 |
| 260 | forum-mobile-client | p2 | H11 |
| 261 | forum-ops-infra | p2 | H21, M34, M42, L17 |
| 262 | forum-package-polish | p3 | M17, M18 |
| 263 | forum-content-features-later | p3 | M2, M3, M4, M6, M7, M8, M9, M10 |

Finalization delta from the draft: **L4** (markdown path / composer board
picker) was unassigned in the draft grouping — added to forum-web-ux-hardening
(todo 259), bringing membership to 76/76 open findings.

Notes for Phase 4 execution: M26's fix scope is app-wide (persistent live-region
container — all 8 existing role=alert sites use the ineffective conditional-mount
shape); M32's residual heuristic/preset tightening rides in web-ux-hardening;
M18 must also correct the README's overstated search-backend caveat (H22 outcome);
H15/M12 carry the "pgvector on Railway unverified" precheck; H12 (entitlement
primitive) is a hard prerequisite inside forum-ai-premium — sequence it first.

## Finding Status

Deferred findings converted to todos (Review Doc Tracking convention — the
`completing-todos` skill checks these off on archive). The 15 `verified` and
1 `false-positive` findings were closed in this audit and have no todo.

- [x] #C1 report-flag-mechanism → todo 254 (completed 2026-07-13)
- [ ] #C2 notifications-delivery-channel → todo 253
- [ ] #H1 orphaned-email-notifications → todo 253
- [ ] #H2 push-event-coverage → todo 253
- [ ] #H3 subscriptions-watching → todo 253
- [ ] #H4 mentions → todo 253
- [ ] #H6 solved-accepted-answer → todo 256
- [ ] #H7 public-user-identity → todo 257
- [ ] #H8 search-discoverability-filters → todo 256
- [ ] #H9 seo-surface → todo 256
- [ ] #H10 unread-indicators → todo 253
- [ ] #H11 mobile-forum-client → todo 260
- [ ] #H12 entitlement-primitive → todo 255
- [ ] #H13 llm-spam-prescreen → todo 255
- [ ] #H14 ai-thread-summarization → todo 255
- [ ] #H15 semantic-similar-topics → todo 255
- [x] #H16 admin-moderation-queue → todo 254 (completed 2026-07-13)
- [ ] #H18 error-retry-affordance → todo 259
- [ ] #H21 tombstone-prune-scheduling → todo 261
- [ ] #H26 author-shape-inconsistency → todo 257
- [ ] #M1 quote-reply → todo 256
- [ ] #M2 bookmarks → todo 263
- [ ] #M3 drafts-autosave → todo 263
- [ ] #M4 edit-history-viewer → todo 263
- [ ] #M5 tags-taxonomy → todo 256
- [ ] #M6 plant-domain-linkage → todo 263
- [ ] #M7 image-authoring-alt-text → todo 263
- [ ] #M8 polls → todo 263
- [ ] #M9 block-mute → todo 263
- [ ] #M10 private-messaging → todo 263
- [ ] #M11 post-permalinks → todo 256
- [ ] #M12 semantic-search-upgrade → todo 255
- [ ] #M13 rag-plant-care → todo 255
- [ ] #M14 ai-composer-assist → todo 255
- [x] #M16 preview-support → todo 254 (completed 2026-07-13)
- [ ] #M17 i18n → todo 262
- [ ] #M18 package-readme → todo 262
- [x] #M19 per-board-moderation → todo 254 (completed 2026-07-13)
- [x] #M20 admin-polish-cluster → todo 254 (completed 2026-07-13)
- [ ] #M22 fetch-race-guards → todo 259
- [ ] #M23 reacted-state → todo 257
- [ ] #M24 native-dialogs → todo 259
- [ ] #M25 reply-focus-drop → todo 259
- [ ] #M26 live-region-announcements → todo 259
- [ ] #M27 unsaved-edit-discard → todo 259
- [ ] #M28 author-type-casts → todo 258
- [ ] #M29 upload-precheck → todo 259
- [ ] #M30 thread-pagination-ux → todo 259
- [ ] #M31 scroll-to-top → todo 259
- [ ] #M34 write-path-e2e → todo 261
- [ ] #M35 patch-idempotency → todo 258
- [ ] #M36 image-upload-idempotency → todo 258
- [ ] #M37 openapi-response-codes → todo 258
- [ ] #M38 meprofile-schema → todo 258
- [ ] #M39 error-envelope-ownership → todo 258
- [ ] #M40 envelope-shapes → todo 258
- [ ] #M41 deleted-author-convention → todo 257
- [ ] #M42 http-caching → todo 261
- [ ] #L1 anon-reaction-counts → todo 257
- [ ] #L2 onboarding-empty-states → todo 259
- [ ] #L4 markdown-board-picker → todo 259
- [ ] #L5 badges-gamification → todo 257
- [ ] #L6 blog-md-doc-drift → todo 255
- [ ] #L7 openai-key-ops-check → todo 255
- [ ] #L8 autocomplete-typeahead → todo 256
- [ ] #L10 toolbar-tap-targets → todo 259
- [ ] #L11 button-busy-state → todo 259
- [ ] #L12 timestamp-accessibility → todo 259
- [ ] #L13 tautological-composer-tests → todo 259
- [ ] #L14 identity-polish → todo 257
- [ ] #L16 reaction-types-duplication → todo 258
- [ ] #L17 migrations-check-ci → todo 261
- [ ] #L18 write-path-query-profiling → todo 258
- [ ] #L19 location-header-201 → todo 258
- [ ] #L20 versioning-comment → todo 258
- [x] #L21 image-reuse-privacy-decision → todo 254 (completed 2026-07-13)

## Phase 6 code review (2026-07-11)

Four domain reviewers dispatched over the uncommitted fix diff (routing by
`code-review-orchestrator`): celery-async, wagtail, react-typescript,
cross-cutting. Verdicts: cross-cutting **clean** (independently verified M15
against Wagtail 7.4.2 source and the L15 sweep against every touched auth
setup; 1 info already tracked in todos 259/260); react-typescript clean but 1
LOW; celery 1 MEDIUM + 2 LOW; wagtail 1 MEDIUM + 1 info + one out-of-scope
flag that **escalated to HIGH on empirical verification**. All repairs below
are kimi-review clean (no findings, exit 0).

| # | Severity | Finding (reviewer) | Resolution |
| --- | --- | --- | --- |
| R1 | HIGH (pre-existing, escalated from the wagtail reviewer's out-of-scope flag) | Forum generics views inherited the host's global `OrderingFilter`: any client `?ordering=` **replaced the cursor ordering** — silently defeating H5's pinned-first guarantee (`?ordering=-title` reproduced) — and `?ordering=author__get_username` (dotted serializer source, not a column) raised FieldError → **unauthenticated 500** on a public endpoint (reproduced) | FIXED: `filter_backends = []` on all 5 generics views (BoardList, TopicList, TopicDetail, PostList, MeProfile) — list order is a package contract and a reusable package must not inherit host filter backends; regression tests pin ordering-param inertness + no-500 on topics and posts lists; schema check: 0 forum paths advertise `ordering` (32 legitimate uses remain app-wide) |
| R2 | MEDIUM (celery) | Backoff countdown values structurally untestable via `.apply()` — eager retries re-execute immediately without honoring `countdown`, so the 30/60/120 formula could regress green | FIXED: parametrized `push_request(retries=N)` + mocked `retry` test pins countdown 30/60/120 |
| R3 | MEDIUM (wagtail) | `FORUM_BODY_SCHEMA.value` omitted `nullable` — `serialize_forum_body` legitimately emits `value=None` for image blocks whose Image was deleted post-publish (sibling `id` already declares nullable) | FIXED: `"nullable": True` on `value` + comment; spectacular clean |
| R4 | LOW (celery) | New FCM failure logs lacked the task ID for correlation | FIXED: `task_id=%s` on both failure log lines |
| R5 | LOW (react-ts) | H20 class-contract test pinned the child variant but not the ancestor `group` class it depends on | FIXED: `closest('.group')` assertion added |
| R6 | LOW (celery) | Backoff has no jitter — correlated FCM outage retries in lockstep | DEFERRED: noted in todo 261 (ops epic) — fine at current scale |

Reviewer info-level notes, no action: `WAGTAILADMIN_BASE_URL` not in
`validate_environment()` fail-fast (matches the `FRONTEND_BASE_URL`
convention); verbatim quote/heading/code sanitize contract (pinned by M32
tests; forward-pointer for non-web consumers lives in todos 259/260).

## Fix Commits

| Commit | Description |
| ------ | ----------- |
| branch `chore/forum-modernization-audit-2026-07-11` | All 15 Phase-3 fixes + 6 Phase-6 review repairs + manifest/changelog + epic todos 253–263, committed together (single audit commit; SHA recorded in the PR) |

## Codification (Phase 8)

Completed after fixes are committed. Each row links to the docs change.

| Finding | Destination | Note |
| ------- | ----------- | ---- |
| M15 (+ the workflow.start regression it surfaced) | `docs/rules/wagtail.md` (2 bullets), `backend/docs/patterns/domain/wagtail.md` §Attributing API-Driven Publish/Unpublish, trigger `wagtail-workflow-start-user-none` | `workflow.start(obj, None)` load-bearing; UnpublishAction for attributed unpublish; +1 `auth_user` query per attributed log write |
| Phase 6 R1 (?ordering override + 500) | `docs/rules/api.md`, `backend/docs/patterns/architecture/viewsets.md` §Reusable-Package Views Must Pin `filter_backends`, `docs/LEARNINGS.md`, `django-drf-reviewer` checklist, trigger `drf-package-views-pin-filter-backends` | full fan-out — rule + pattern + incident + review check + write-time trigger |
| M33 + Phase 6 R2 (retry testing) | `docs/rules/celery.md`, `backend/docs/patterns/domain/celery.md` §Testing Retry Backoff | `.apply()` ignores `countdown`; `push_request(retries=N)` + mocked `retry` pins values |
| M21 (fixture trap) | `docs/rules/react.md`, trigger `js-array-fill-shared-reference` | `.fill()` evaluates its argument once |
| H24 (raw_data N+1 recurrence) | trigger `wagtail-streamvalue-render-n-plus-one` | the prose rule already existed (`docs/rules/wagtail.md`) and was violated anyway — now fires at write time on `render_as_block(` |
| Session mechanics (worktree pytest) | `docs/LEARNINGS.md` | `PYTHONPATH=packages/wagtail_forum` beats the editable-install `.pth` pointing at the main checkout |
