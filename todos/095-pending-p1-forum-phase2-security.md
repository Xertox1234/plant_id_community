---
status: pending
priority: p1
issue_id: "095"
tags: [forum, backend, security]
dependencies: ["094"]
---

# Forum Phase 2 — harden the forum API ("won't get hacked")

## Problem

The forum API is not safe to expose publicly. It has **no rate limiting** on any
endpoint, **unbounded pagination** (memory DoS), **spoofable image uploads**, and
**no server-side HTML sanitization** of stored post content. These must be closed
before the forum goes online.

## Findings

Verified by direct read of `backend/apps/forum_integration/api_views.py` +
`serializers.py`:

- **No rate limiting** anywhere (incl. `forum_ai_assist` — a real-money cost vector).
- **Unbounded `page_size`** in `all_topics_list` (`api_views.py:74`) + `TopicDetailView`.
- **Image upload** validates only size + client `content_type` (`api_views.py:689–709`).
- **No server-side sanitization** of `Post.content`; `content_format` is an
  unconstrained `CharField` (`serializers.py:334,417`).
- **Already correct (do not "fix"):** attachment trust enforcement uses machina
  `PermissionHandler.can_attach_files()` (`api_views.py:645`); ownership checks on
  edit/delete; search wildcard escaping. (Corrected from earlier recon, which
  mis-read the `is_staff` fallback at `api_views.py:1096`.)

## Recommended Action

Execute the Phase 2 plan task-by-task in a fresh session:
**`docs/superpowers/plans/2026-05-25-forum-phase2-security.md`**

Audit-first (`security-reviewer` agent), then harden using existing repo patterns:
`django-ratelimit` decorators (limits in a new `apps/forum_integration/constants.py`),
pagination caps, the 4-layer image-upload validation, `nh3` server-side
sanitization + `content_format` `ChoiceField` + a one-time backfill command,
forum-level authz verification, dead-code removal, and a security regression suite.

## Technical Details

- Plan: `docs/superpowers/plans/2026-05-25-forum-phase2-security.md`
- Spec: `docs/superpowers/specs/2026-05-25-forum-modernization-hardening-design.md`
- Patterns: rate-limit (`apps/users/views.py:88`, `apps/plant_identification/constants.py`),
  file-upload (`docs/patterns/security/file-upload.md`), 429 handler (`apps/core/exceptions.py`).
- **Ordering:** the content backfill command ships in the **same release** as
  sanitize-on-write (no unsanitized window).
- **Precondition (verify before launch, not built here):** confirm email
  verification is enforced on signup (registration is already IP-rate-limited).

## Acceptance Criteria

- [ ] `security-reviewer` CRITICAL/HIGH findings resolved or converted to todos.
- [ ] Rate limiting on all write/AI/search endpoints (429 via `apps/core` handler);
      `page_size` capped; 4-layer image validation; server-side sanitization +
      `content_format` choices + backfill run.
- [ ] `python manage.py test apps.forum_integration --noinput` green, incl. the new
      `test_security.py` (xss, rate-limit, upload, pagination, authz).
- [ ] Dead permission-bypass code removed (`views.py`, `*_simple.html`, `apps/forum`).

## Acceptance note

No DB migration required (sanitization/limits are serializer/view-level;
`content_format` constrained at the serializer).

## Work Log

### 2026-05-25 - Created

- Spec + Phase 2 plan written and committed on `feat/forum-web-modernization`.
  Spec corrected re: trust-level enforcement already wired. Todo created.

## Notes

Depends on [todo 094] (a working forum to verify against; backend hardening itself
is largely independent of the Phase-1 frontend). This is the user's headline
priority ("stable and won't get hacked the minute I put it online"). New features
(notifications, mentions, etc.) remain deferred.
