---
status: pending
priority: p4
issue_id: "345"
tags: [forum, moderation, wagtail, package]
dependencies: []
---

# Moderation queue as a Wagtail admin report view

## Problem

Moderators triage reports today through generic snippet listing
(`Report` `ModelViewSet` filters). It works, but the "queue" (open reports
ordered by severity/age, one-click action/dismiss) is a workflow Wagtail's
snippet list wasn't shaped for — no zero-state, no bulk triage tuned to
reporting statuses, no prominence in the admin nav. Discourse's review
queue is a first-class surface; ours is a filtered table.

## Findings

- Current surface: snippet viewsets for `Topic`/`Post`/`ForumProfile`/
  `Report` with filters, search, CSV/XLSX export, inspect, bulk unpublish
  (`wagtail_forum/wagtail_hooks.py:1-332`).
- `Report` statuses: `open`, `auto_hidden`, `actioned`, `dismissed`;
  auto-unpublish at `REPORT_AUTO_HIDE_THRESHOLD` (3)
  (`wagtail_forum/models/reports.py:1-236`, `conf.py:49`).
- Wagtail's native extension point for exactly this is a **custom report
  view** (context7 `/wagtail/wagtail`, `docs/extending/adding_reports.md`):
  `ReportView` + `register_reports_menu_item` hook:

  ```python
  class CustomModelReport(ReportView):
      def get_queryset(self):
          return MySnippetModel.objects.all()

  # wagtail_hooks.py
  @hooks.register("register_reports_menu_item")
  def register_menu_item():
      return AdminOnlyMenuItem("...", reverse("..."), icon_name=..., order=700)
  ```

## Recommended Action

1. **Package (`wagtail_forum`):** add
   `wagtail_forum/admin_views.py` with a `ModerationQueueReportView(ReportView)`:
   queryset = `Report.objects.filter(status=OPEN)` (plus `auto_hidden`
   section), `select_related` the target post/message and reporter; columns:
   reason, reporter trust level, target excerpt, age, open-report count on
   target. Permission: reuse `wagtail_forum.change_post` moderator perm
   (not superuser-only) via a `dispatch` guard per the report docs
   precedent.
2. Register via `register_reports_menu_item` with `MenuItem` gated on the
   moderator permission, not `AdminOnlyMenuItem` — the package's trust
   system grants moderation below superuser.
3. Row actions resolve by linking to the existing `Report` inspect URLs
   (`snippet_viewset.get_url_name("inspect")` — **use `reverse()`, never a
   hardcoded mount**, per the M1 finding in
   `docs/audits/2026-07-17-forum-wagtail.md`).
4. Keep it read-mostly: action/dismiss stay in the inspect view's existing
   form rather than re-implementing bulk mutations in the report view
   (Wagtail reports are listings, not mutation surfaces).
5. **Web moderator queue** stays out of scope — CMS is the mod surface by
   design; revisit only if non-CMS-savvy moderators are onboarded.

## Technical Details

- Wagtail docs: `docs/extending/adding_reports.md` (ReportView,
  `list_export`, `register_reports_menu_item`).
- Sibling precedence in the same file for menu/search registration:
  `wagtail_forum/wagtail_hooks.py` (SearchArea, menu items).
- Tests: `wagtail_forum/tests/` pattern — render the report, assert only
  open reports and moderator-permission gating, pin resolved URLs.

## Acceptance Criteria

- [ ] "Forum moderation queue" appears under the Reports menu for users
      with `wagtail_forum.change_post`, hidden otherwise (test-pinned)
- [ ] Queue lists open + auto-hidden reports with the columns above, oldest
      first; empty state renders
- [ ] All URLs resolved with `reverse()` (regression test per M1 pattern)
- [ ] No duplicate mutation paths — actions link through to the existing
      inspect view

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  "moderator queue UI (moderators currently work in the CMS)"). Uses
  Wagtail's report framework rather than a bespoke admin view, per the
  reusable-package constraint.
