---
status: completed
priority: p4
issue_id: "678"
tags: [forum, forum-categories, backend, web]
dependencies: ["666"]
triage: ready
triaged: 2026-10-30
owner_decision: "Template is plain text: each line becomes a paragraph, no formatting. (owner, 2026-10-30)"
---

# Forum categories slice 12: topic template per forum

## Problem

Discourse prefills the new-topic composer with a per-category template (e.g. a plant-problem checklist).

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (Discourse topic_template).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Field `topic_template` (plain text/markdown in the composer's input format), admin *Posting* tab, exposed in the forum API; web `NewThreadPage.tsx` prefills when the body is empty.

## Technical Details

- `NewThreadPage.tsx`, forum serializer.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: API exposes the template.
- [x] Web Vitest: composer prefills only when empty and never overwrites a draft.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Template is plain text: each line becomes a paragraph, no formatting.

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-1108)

- `Forum.topic_template` (plain text) on the forum form's *Posting* tab, exposed as `topic_template` on the forum rows of `GET /forum/categories/`. Not on `/forum/boards/`, whose keys are pinned as the Flutter contract.
- Web: `fetchForumTopicTemplate` plus `templateToDoc` (each line a paragraph, no formatting, owner decision); `NewThreadPage` prefills only an empty composer, never over a stored draft or typed text, and the template alone is never saved as a draft.
- Tests: `tests/api/test_forum_topic_template.py`; Vitest cases in `NewThreadPage.test.tsx` and `forumService.test.ts`.

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-1108)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_forum_topic_template.py --create-db` — evidence `.sweep-evidence/g1/678-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 3 warnings in 19.80s ========================
  ```

- AC 2: `cd web && ./node_modules/.bin/vitest run src/pages/forum/NewThreadPage.test.tsx -t 'topic template'` — evidence `.sweep-evidence/g1/678-ac1.txt` (not committed), last lines:

  ```text
     Duration  1.10s (transform 115ms, setup 101ms, import 308ms, tests 194ms, environment 424ms)

  (!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
    - `__dirname` (vitest.config.ts:62:25). Use `import.meta.dirname` instead
  Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-1108)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-30 - Repaired by the todo sweep (run 2026-10-30-1108)

- Round-1 review: `Forum.topic_template` (added by 0047) now has `db_default=""` in the model and the migration, so the previous release can insert forums while this one migrates.
- No behaviour change to the template itself; every criterion was re-run.

### 2026-10-30 - Review round 1: non-blocking findings (hand fixes)

- No non-blocking finding was raised against this todo in round 1.

### 2026-10-30 - Review round 2: non-blocking findings (hand fixes)

- Declined (low): the composer refetches the categories index for each category change and can open for a locked forum. One extra GET per change, and since round 2 a locked row's template is blank, so nothing locked is prefilled. P4.
