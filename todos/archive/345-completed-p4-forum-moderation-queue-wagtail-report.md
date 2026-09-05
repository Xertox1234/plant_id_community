---
status: completed
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

- [x] "Forum moderation queue" appears under the Reports menu for users
      with `wagtail_forum.change_post`, hidden otherwise (test-pinned)
- [x] Queue lists open + auto-hidden reports with the columns above, oldest
      first; empty state renders
- [x] All URLs resolved with `reverse()` (regression test per M1 pattern)
- [x] No duplicate mutation paths — actions link through to the existing
      inspect view

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  "moderator queue UI (moderators currently work in the CMS)"). Uses
  Wagtail's report framework rather than a bespoke admin view, per the
  reusable-package constraint.

### 2026-09-04 - Started by completing-todos skill (run 2026-09-05-0408)

- Picked up by automated workflow.

### 2026-09-05 - Implemented as a Wagtail ReportView (run 2026-09-05-0408)

- Package: `wagtail_forum/admin_views.py` (`ModerationQueueView(ReportView)`,
  `ModerationQueueFilterSet`, `ModerationQueueMenuItem`), `admin_urls.py`
  (namespace `wagtail_forum_reports`), two hooks appended to
  `wagtail_hooks.py` (`register_admin_urls`, `register_reports_menu_item`),
  `Report.target_excerpt` property, README "Moderation queue (admin report)".
- Decisions: queue = `open` + `auto_hidden` (both still need a human),
  oldest first; gate = `ModelPermissionPolicy(Post)` "change"
  (`wagtail_forum.change_post`), NOT `AdminOnlyMenuItem`; every row's title
  links to `reverse(Report.snippet_viewset.get_url_name("inspect"))` — no
  mutation path added; reporter column is a plain username (not
  `UserColumn`, whose avatar cell costs one `wagtail_userprofile` query per
  row); `target_open_reports` is one correlated subquery per target shape.
- AC1 menu gating: `test_menu_item_url_and_visibility_follow_the_moderator_permission`
  (`is_shown` True for access_admin+change_post, False for access_admin only;
  `item.url == reverse("wagtail_forum_reports:moderation_queue")`) and
  `test_staff_without_change_post_is_bounced_from_the_queue` (302 →
  `wagtailadmin_home`).
- AC2 membership/order/empty state:
  `test_queue_lists_open_and_auto_hidden_oldest_first_and_links_to_inspect`
  (actioned/dismissed excluded, `[oldest, hidden, dm]` order, excerpt +
  message_summary + trust label rendered),
  `test_empty_queue_renders_its_empty_state`.
- AC3 reverse(): both tests above assert the resolved URLs, and every row's
  inspect link is asserted present in the HTML.
- AC4 no duplicate mutation paths: the view is a listing (`ReportView`); the
  only links are to the existing snippet inspect view.
- Also pinned: `test_open_reports_on_target_counts_only_queue_statuses_for_the_same_target`,
  `test_queue_filters_by_reason_and_status`,
  `test_queue_exports_csv_with_the_triage_columns`,
  `test_queue_query_count_does_not_grow_with_rows` (equal query count for 1
  vs 3 rows across post + message reports).
- Evidence: `pytest packages/wagtail_forum/wagtail_forum/tests/test_moderation_queue.py …`
  → `10 passed`; full backend suite `2043 passed, 8 skipped in 320.76s`.

### 2026-09-05 - Code review round 1 + repair (run 2026-09-05-0408)

- Reviewers: django-drf, wagtail, cross-cutting (read-only, parallel).
- **HIGH (django-drf + wagtail, same finding) — repaired:** the host's
  bootstrapped "Forum Moderators" group held only topic/post permissions, so
  every queue row's inspect link would have bounced a real moderator to the
  admin home (`InspectView.any_permission_required` is on `Report`).
  Fix: `forum_host/bootstrap.py` now grants `view_report` + `change_report`
  (pinned by `test_moderator_group_can_view_and_change_reports`), and the
  queue's gate moved from `change_post` to the Report model's own policy
  (any of add/change/delete/view — the Report snippet views' gate), so the
  queue and the views it links into open for exactly the same people and
  the DM-excerpt read scope (django-drf INFO finding) is the Report
  snippet's, not wider. AC1 is therefore met by "the moderator group", not
  by `change_post` literally: `change_post` alone is deliberately NOT
  enough (`test_change_post_alone_does_not_open_the_queue`).
- MEDIUM (both) — repaired: the listing test now follows every row's
  inspect link as the bootstrapped moderator and asserts 200.
- MEDIUM (cross-cutting) — repaired: `order_queryset` appends `pk` as a
  deterministic tie-break for the 50-row pagination
  (`test_reports_filed_in_the_same_instant_keep_a_stable_order_across_sorts`).
- LOW (django-drf) — repaired: CSV/XLSX decode `reporter_trust_level` via
  `custom_field_preprocess` (export test asserts "Regular").
- LOW (wagtail) — repaired: `no_results_message` keeps the filtered-vs-empty
  distinction ("No reports match your filters." when a filter is active).
- LOW (cross-cutting) — repaired: `test_target_excerpt_is_just_the_topic_title_when_the_body_has_no_text`.
- Post-repair: `test_moderation_queue.py` + `test_bootstrap.py` +
  `test_admin.py` → `37 passed`. Residue sweep (`rg MUTANT|probe`, untracked
  files) clean.

### 2026-09-04 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: all 4 acceptance criteria passed (12 queue tests, bootstrap test, full suite 2047 passed).
- Review: 7 findings total, 1 blocking (HIGH, reported by two reviewers) — all 7 repaired in round 1.
