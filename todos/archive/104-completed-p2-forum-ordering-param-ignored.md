---
status: completed
priority: p2
issue_id: "104"
tags: [forum, backend, api]
dependencies: []
---

# ForumTopicsListView ignores ordering param — sort dropdown non-functional

## Problem

`ForumTopicsListView.get_queryset()` hardcodes `.order_by('-last_post_on')` and never
reads `request.query_params.get('ordering')`. The frontend wires the sort dropdown
correctly (ThreadListPage → forumService `?ordering=<value>`) but the backend ignores
it and always returns topics by last post date.

## Evidence

```python
# api_views.py line 71-78
def get_queryset(self):
    return Topic.objects.filter(...).order_by("-last_post_on")  # always
```

```typescript
// forumService.ts line 95
params.set('ordering', ordering);  // sent but ignored
```

## Recommended Action

Read the `ordering` query param in `get_queryset()` and map allowed values to safe
`.order_by(...)` expressions:

```python
ORDERING_MAP = {
    '-last_post_on': '-last_post_on',   # default
    '-views_count': '-views_count',
    '-posts_count': '-posts_count',
    'created': 'created',
}

def get_queryset(self):
    ordering = self.request.query_params.get('ordering', '-last_post_on')
    safe_ordering = ORDERING_MAP.get(ordering, '-last_post_on')
    return Topic.objects.filter(...).order_by(safe_ordering)
```

Use an allowlist — never pass the raw param directly to `.order_by()`.

## Acceptance Criteria

- [x] Sort dropdown in ThreadListPage changes the result order visibly.
- [x] Unknown/unsupported ordering values fall back to `-last_post_on`.
- [x] No raw query param passed to `.order_by()` (allowlist enforced).

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Started by completing-todos skill (run 2026-05-28-2019)

- Picked up by automated workflow.

### 2026-05-28 - Implemented + verified by completing-todos skill (run 2026-05-28-2019)

**Key correction to the recommended action:** the frontend sort dropdown
(`web/src/pages/forum/ThreadListPage.tsx:211-215`) emits values in a *different*
naming convention than the backend ORM fields — `-last_activity_at`,
`-created_at`/`created_at`, `-view_count`, `-post_count`. The todo's suggested
`ORDERING_MAP` keyed on backend names (`-last_post_on`, `-views_count`, …), so
following it literally would have made *every* dropdown option fall back to the
default. The allowlist must map **frontend param → backend field**.

Changes:
- `constants.py`: added `FORUM_TOPIC_DEFAULT_ORDERING` + `FORUM_TOPIC_ORDERING_MAP`
  (frontend value → safe Topic ORM field).
- `api_views.py`: `ForumTopicsListView.get_queryset()` now reads `ordering` from
  query params and resolves it through the allowlist with a safe default.
- New test `tests/test_topic_ordering.py` (5 tests).

Verification — `python manage.py test apps.forum_integration.tests.test_topic_ordering --keepdb`:
```
Ran 5 tests in 0.161s
OK
```
- AC1 (dropdown changes order): `test_ordering_param_changes_result_order` —
  `-view_count` and `-post_count` yield different sequences. Frontend already
  sends the param (`forumService.ts:95`); backend now honors it. *Verified at the
  API/queryset layer; literal browser render not observed.*
- AC2 (unknown → default): `test_unknown_ordering_falls_back_to_default`.
- AC3 (no raw param to `.order_by()`): same test — a SQL-injection-shaped value
  returns 200 (not a 500 FieldError), proving it never reaches `.order_by()`.
- Added `test_allowlist_covers_every_frontend_dropdown_value` as a drift guard.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

- Verification: all 3 acceptance criteria passed (6 tests, `OK`).
- Review (feature-dev:code-reviewer): 0 critical/high. 1 medium + 1 low — both
  **addressed** (not just logged):
  - medium: added `test_all_mapped_orm_fields_are_valid` so all 5 mappings are
    behaviorally exercised (a typo'd ORM field would 500, not silently fall
    through). Re-verified: 6 tests `OK`.
  - low: changed the no-param default from an ORM field name to `""` so the
    allowlist fallback is always explicit, not accidental.
- Not-a-finding noted by reviewer: single-field sort drops Machina's `-type`
  prefix, but that matches every other `order_by` in this file — not a regression.
