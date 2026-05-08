---
status: completed
priority: p4
issue_id: "062"
tags: [backend, blog, tests, middleware]
dependencies: []
---

# Verify blog/middleware.py transaction.on_commit Patch Path

## Problem

`backend/apps/blog/tests/test_analytics.py` patches `apps.blog.middleware.transaction.on_commit`. This patch path is only correct if `middleware.py` imports `transaction` as `from django.db import transaction`. If it uses `import django.db.transaction`, the patch path would differ and the patch would silently miss.

## Findings

- `backend/apps/blog/tests/test_analytics.py` — patch target `apps.blog.middleware.transaction.on_commit`.
- Source: 2026-05-06 code review (Finding 20, INFO).

## Recommended Action

1. Open `backend/apps/blog/middleware.py` and confirm the import style.
2. If `from django.db import transaction` — patch path is correct, no change needed; mark complete.
3. If `import django.db` or `import django.db.transaction` — update the patch string in the test to match the actual import path.

## Technical Details

- Middleware file: `backend/apps/blog/middleware.py`
- Test file: `backend/apps/blog/tests/test_analytics.py`

## Acceptance Criteria

- [ ] `backend/apps/blog/middleware.py` import style confirmed.
- [ ] Patch path in test matches actual import style.
- [ ] `python manage.py test apps.blog.tests.test_analytics --noinput` passes.

## Work Log

### 2026-05-08 - Created from 2026-05-06 review Finding 20

- Source: `docs/todos/2026-05-06-review.md`, Finding 20 (INFO).
