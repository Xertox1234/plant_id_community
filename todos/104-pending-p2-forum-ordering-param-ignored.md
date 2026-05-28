---
status: pending
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

- [ ] Sort dropdown in ThreadListPage changes the result order visibly.
- [ ] Unknown/unsupported ordering values fall back to `-last_post_on`.
- [ ] No raw query param passed to `.order_by()` (allowlist enforced).

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
