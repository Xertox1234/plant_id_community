---
status: pending
priority: p4
issue_id: "430"
tags: [forum, backend, testing]
dependencies: []
---

# `test_spam.py` fails 8 tests when run on its own

## Problem

`pytest packages/wagtail_forum/wagtail_forum/tests/test_spam.py` run as a
lone file fails 8 of its 9 tests with `RuntimeError: Database access not
allowed`. The tests aren't marked `django_db`, but `HeuristicSpamBackend`
calls `get_setting`, which reaches the host's override provider
(`apps/forum_host/forum_settings.provide` → `_values` → `_load_values`, one
SELECT) whenever the process-level `_memo` is cold.

Inside the full suite an earlier DB test warms the memo, so the file passes.
The result depends on run order, and a developer iterating on spam code
gets a wall of false failures.

## Findings

- Found while implementing todo 426 (2026-09-24), on clean `main`.
- Traceback: `spam/heuristic.py:21` → `conf.py:223` →
  `forum_settings.py:105/94/72` → `transaction.atomic()`.

## Recommended Action

Either mark the module `pytestmark = pytest.mark.django_db`, or give
`wagtail_forum` tests an autouse fixture that primes or stubs the override
provider. Prefer the one that also covers other package test files with the
same shape (grep for `get_setting` use in tests without `django_db`).

## Acceptance Criteria

- [ ] `test_spam.py` passes when run as a lone file, and in the full suite.

## Work Log

### 2026-09-24 - Filed from todo 426
