---
status: completed
priority: p3
issue_id: "097"
tags: [forum, backend, security]
dependencies: []
source_review: "docs/superpowers/plans/2026-05-25-forum-phase2-security.md"
source_finding: "M1"
---

# Forum: replace `str(e)` error responses with generic messages

## Problem

Four forum endpoints return `str(e)` in JSON 500 responses, leaking internal exception details (stack frames, file paths, ORM error strings) to clients in production.

## Findings

From security-reviewer audit 2026-05-26:

- `api_views.py:121` — `all_topics_list` except block
- `api_views.py:327` — `forum_ai_assist` except block
- `api_views.py:561` — `PostReactionView` except block
- `api_views.py:1102` — `user_trust_level` except block

## Recommended Action

Replace `str(e)` in each Response payload with a generic `"An error occurred."` string. Log the real exception server-side with `logger.exception(...)` before returning. No behavior change to callers.

## Acceptance Criteria

- [x] All four locations return a generic error message (not `str(e)`) to clients.
- [x] Each replaced location logs the real exception via `logger.exception`.
- [x] `python manage.py test apps.forum_integration --noinput` still green.

## Work Log

### 2026-05-26 - Created

- Surfaced by security-reviewer during Phase 2 audit (MEDIUM — out of scope for Phase 2).

### 2026-05-26 - Implemented by completing-todos skill (run 2026-05-26-1959)

- Added `import logging` and `logger = logging.getLogger(__name__)` to `api_views.py`.
- Fixed 5 `str(e)` leaks (todo listed 4; a 5th in the image-upload loop at line 838 was also fixed — same vulnerability, same one-line pattern):
  - `all_topics_list` except block → `logger.exception("[ERROR] all_topics_list failed")` + `"An error occurred."`
  - `forum_ai_assist` except block → `logger.exception("[ERROR] forum_ai_assist failed")` + `"An error occurred."`
  - `PostReactionView.post` except block → `logger.exception("[ERROR] PostReactionView.post failed")` + `"An error occurred."`
  - Image upload loop → `logger.exception("[ERROR] image upload failed for %s", uploaded_file.name)` + `"upload error"` (filename retained since it is user-supplied, not exception data)
  - `user_trust_level` except block → `logger.exception("[ERROR] user_trust_level failed")` + `"An error occurred."`
- Verification: `grep -n "str(e)" api_views.py` → zero results.
- Tests: `python manage.py test apps.forum_integration --noinput` → Ran 38 tests in 7.450s — OK (skipped=3).
- Code review: 1 finding repaired — `except Exception as e:` → `except Exception:` at 5 sites (F841 unused variable; `logger.exception()` reads traceback from sys.exc_info() automatically).
- Known issues (out of scope): `setup_forums.py:81,83` has two `str(e)` in management command stdout output — not an HTTP response leak; tracked separately.

### 2026-05-26 - Completed by completing-todos skill (run 2026-05-26-1959)

- Verification: all 3 acceptance criteria passed.
- Review: 1 finding total, 1 repaired (F841 unused `e` variable) — no accepted blockers.
