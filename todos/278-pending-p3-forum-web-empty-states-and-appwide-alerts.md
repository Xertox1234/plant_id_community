---
status: pending
priority: p3
issue_id: "278"
tags: [forum, web, react, wagtail, a11y]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "L2"
---

# Forum web: empty/onboarding states + app-wide role="alert" migration

## Problem

Deferred from todo 259 (forum web UX & a11y hardening) at implementation time.
Todo 259 satisfied all 7 of its acceptance criteria (the transient a11y
announcer, fetch race-guards, styled dialogs, composer hardening, sanitizer
tightening, scroll-to-top). Two pieces were explicitly held back because they
fall outside 259's AC and/or drag in backend work:

## Findings

- **L2** — Onboarding/empty states are bare. The `ForumIndex.intro` CMS field is
  never serialized so welcome copy can't reach the UI; the board list lacks a
  last-activity indicator. Full-stack: needs a Wagtail serializer change on the
  forum index page (backend) plus web rendering (CategoryListPage / CategoryCard).
- **M26 residue (app-wide)** — Todo 259 built the persistent live-region
  `AnnouncerContext` and migrated the forum write-path banners + the forum
  composer's upload error. The audit's M26 scope is app-wide: the remaining
  conditional-mount `role="alert"` sites outside forum flows still use the
  MDN-documented not-announced anti-pattern — `components/ui/Input.tsx:81`,
  `pages/auth/LoginPage.tsx`, and the other sites the audit enumerated. Migrate
  them to the persistent announcer / persistent-container pattern.

## Recommended Action

1. Serialize `ForumIndex.intro` in the forum index API and render it as welcome
   copy on CategoryListPage; add richer empty-state copy; surface last-activity
   on board cards (needs a `last_post_at` per board from the API).
2. Sweep the non-forum `role="alert"` conditional-mount sites and migrate them
   to `useAnnounce` (AnnouncerContext) or a persistent live-region container.

## Acceptance Criteria

- [ ] `ForumIndex.intro` reaches the UI and renders as welcome copy
- [ ] Board cards show a last-activity indicator
- [ ] Non-forum `role="alert"` sites (Input, LoginPage, …) announce via the
      persistent-container pattern, verified by a content-swap test

## Notes

p3. Split out from todo 259 (see its Work Log, 2026-07-24). The AnnouncerContext
primitive and the pattern to copy already exist on main.
