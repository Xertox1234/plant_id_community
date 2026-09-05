---
status: pending
priority: p2
issue_id: "352"
tags: [blog, web, forum, api, moderation]
dependencies: []
---

# Blog post comments: wire existing BlogComment to frontend + forum anti-spam services

## Problem

Blog posts allow no reader participation — no way to comment, reply, or
discuss an article. Discussion is a proven engagement/retention driver
(Discourse's core premise, and the reason forum todos 339-350 exist).
The research finding: **`BlogComment` already exists end-to-end in the
backend but the frontend was never wired up**, and it lacks the forum's
spam/trust/rate-limit protections, so enabling the UI as-is would expose
an unprotected comment surface.

This was scoped as "a new Wagtail package reusing forum tech"; research
(summarized below) found that a new package is unnecessary — direct
`Topic`/`Post` reuse is architecturally wrong, third-party packages
(`django-comments-xtd` et al.) would create a parallel system with no
trust-level or auth integration, and the backend model/API/admin
moderation already exist. The work is: frontend UI + wiring forum
anti-abuse services into the existing comment flow.

## Findings

**Existing backend (all in `backend/apps/blog/`):**

- `BlogComment` model — threaded (`parent` self-FK for replies),
  `is_approved`/`is_flagged`/`flag_count`, indexes on
  `(post, created_at)`, `(author, created_at)`, `(is_approved, created_at)`.
  `backend/apps/blog/models.py:893-957`.
- DRF API: `BlogPostPageViewSet.add_comment` (auth-required, respects
  `allow_comments`) + `BlogCommentViewSet` CRUD incl. `flag`;
  non-staff see only approved comments. `backend/apps/blog/views.py:48-225`,
  `366-402`; serializer `backend/apps/blog/serializers.py:159-188`.
- Admin moderation: staff-only approve/reject routes + Wagtail
  homepage "Comments Pending Approval" widget.
  `backend/apps/blog/admin_urls.py:14-25`,
  `backend/apps/blog/admin_views.py:63-141`,
  `backend/apps/blog/wagtail_hooks.py:48-246`.
- `BlogPostPage.allow_comments` (default `True`) published in Wagtail
  API v2 `api_fields`; `comment_count` already computed in both the
  Wagtail API v2 serializer (`api/serializers.py:375-391`) and queryset
  annotations (`api/viewsets.py:191-196, 230-235`) — but the web
  frontend type ignores them.

**Missing today:**

- **No frontend at all.** `web/src/types/blog.ts:218-244` has no
  comment fields; `blogService.ts` only calls Wagtail API v2 (no comment
  endpoints); `BlogDetailPage.tsx` renders no comment section.
  Note: the comment endpoints are on the **DRF v1** API
  (`/api/v1/blog/…`), which the current `blogService` doesn't use —
  service will either add v1 calls or the endpoint surface needs
  deriving from v2 conventions.
- **No anti-abuse protection.** `add_comment` and `flag` have no rate
  limiting, no spam screening, no trust gating — every authenticated
  user's comment auto-approves (`is_approved` default `True`).
- Serializer caps replies at one level deep (`if obj.is_reply: return []`)
  — decide and document the intended thread depth.

**Forum components reusable for blog comments** (service-level, NOT
model-level — `Topic`/`Post` are hard-wired to `ForumBoard` and carry
forum-only semantics; reusing them directly would pollute forum
counters/search/notifications):

- Spam screening: `wagtail_forum/spam/base.py` `SpamBackend.check_text()`
  - host LLM backend `apps/forum_host/spam.py`. Screen flattened
  comment text before deciding `is_approved`.
- Trust gating: `ForumProfile.for_user(user).trust_level` — e.g.
  NEW/BASIC held for moderation, MEMBER+ auto-approved (threshold
  configurable).
- Rate-limit wrapper pattern: `apps/forum_host/api.py`
  `django-ratelimit` decorators — mirror on comment/flag endpoints.
- `UserBlock` — already content-agnostic; suppress replies/notifications
  from blocked authors.
- UI patterns for the frontend: `web/src/pages/forum/ThreadDetailPage.tsx`
  (composer, per-target draft persistence, moderation-pending banner,
  reports) and `web/src/utils/sanitize.ts` (DOMPurify MINIMAL preset).

**Ecosystem check (2026):** Wagtail's built-in `Comment` model is
editorial-only. Only maintained third-party visitor-comment package is
`django-comments-xtd`, which would be a parallel system with its own
moderation UI and no trust/auth integration — rejected in favor of the
existing `BlogComment`.

## Recommended Action

1. **Backend — protect the existing endpoints:**
   - On comment create, call `get_spam_backend()` (forum host wiring,
     heuristic fallback in package) on the comment text; spammy AND/OR
     below trust threshold → create with `is_approved=False`
     ("pending moderation") and surface that state in the API response,
     like the forum's moderation-pending notices.
   - Auto-approve above a trust threshold (`ForumProfile.trust_level >=
     MEMBER`); make the threshold a Django setting.
   - Apply `django-ratelimit` wrappers to `add_comment` and `flag`
     (mirror `apps/forum_host/api.py`); keep gotcha #4 in mind —
     the custom exception handler must map `Ratelimited` → 429.
   - Optionally fire notification events (reply-to-comment, flag) via a
     host-side helper — don't touch `wagtail_forum` internals for this.
2. **Frontend — build the comment section:**
   - Extend `BlogPost` type + `blogService.ts` with `comment_count`,
     `allow_comments`, comment list/create endpoints.
   - New `BlogCommentSection` component under `BlogDetailPage`:
     composer, reply, flag, moderation-pending banner — modeled on
     `ThreadDetailPage` patterns; render with DOMPurify MINIMAL.
   - Honor `allow_comments: false` → no composer.
3. **Tests:**
   - Backend: spam → held; low trust → held; high trust → approved;
     rate limit returns 429; `allow_comments=false` → 403 (exists).
   - Frontend: Vitest for section states (pending banner, disabled
     comments, empty state); Playwright happy path (post + reply).

## Technical Details

- Follow `django-ratelimit` 429-not-403 gotcha:
  `backend/docs/patterns/architecture/rate-limiting.md` (rule 4 in
  root CLAUDE.md).
- Comments are plain `TextField` today — keep plain text (escapes the
  whole rich-text sanitization question); rich-text comments are a
  possible follow-up using `wagtail_forum/api/sanitize.py`.
- Frontend draft persistence/composer patterns:
  `web/src/pages/forum/ThreadDetailPage.tsx`;
  React Router import from `react-router-dom` only (gotcha #2).
- Debounce/submit-timer handling via `useRef`, not `useState` (gotcha #5).
- If a migration is added, test DB rebuild: `python manage.py test
  apps.blog --noinput` (gotcha #6).
- Follow-ups explicitly OUT of scope: notification fan-out for every
  reply thread, comment editing/versioning, converting `BlogComment`
  to a Wagtail snippet + workflow (bigger migration), extracting a
  shared `wagtail_moderation` package (revisit only if a third
  commentable surface appears).

## Acceptance Criteria

- [ ] Signed-in user can comment on a blog post from the web UI; reply
      to a comment (documented depth cap)
- [ ] New/low-trust users' comments show "pending moderation" and are
      not publicly visible until approved via existing admin queue
- [ ] Spam backend screens comment text before auto-approval
- [ ] Rate limiting on comment create + flag returns 429 (not 403)
- [ ] `allow_comments: false` hides/disables the composer
- [ ] `comment_count` renders in the UI (list and/or detail page)
- [ ] Backend tests: spam/trust gating, rate limit 429, visibility
      (non-staff see approved only)
- [ ] Frontend tests: Vitest section states + Playwright post/reply
      happy path

## Work Log

### 2026-09-04 - Filed

- Research session: "extending forum functionality into blog comments".
  Key discovery: `BlogComment` model + DRF API + admin moderation queue
  predated the question; frontend was never wired and endpoints are
  unprotected. Rejected alternatives: (a) reusing `Topic`/`Post`
  directly (forum-shaped models, would corrupt forum semantics), (b) a
  new `wagtail_comments` package (over-engineering for two surfaces),
  (c) `django-comments-xtd` (parallel system, no trust/auth integration).
