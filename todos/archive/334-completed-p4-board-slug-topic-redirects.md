---
status: completed
priority: p4
issue_id: "334"
tags: [forum, wagtail, redirects, backend]
dependencies: []
---

# Board slug edits leave topic paths without redirects

## Problem

`Topic.get_absolute_url()` is `/forum/{board.id}-{board.slug}/{id}-{slug}`, so
renaming a `ForumBoard` page's slug in `/cms/` (promote tab) moves every topic
path beneath it. `apps/forum_host/redirects.py` only hooks `Topic` saves, and
Wagtail's own `WAGTAILREDIRECTS_AUTO_CREATE` only covers the Page `url_path`
(`/forum/general/`), never the topic shape — so a board rename writes zero
redirect rows while a single topic-slug edit does.

## Findings

- `backend/apps/forum_host/redirects.py` — receivers on `pre_save`/`post_save`
  of `wagtail_forum.Topic` only; the module docstring now states board slugs
  as a non-goal and points here. Source: bundled `/code-review` on the
  Wagtail quick-wins branch, 2026-09-04 (finding 3 of 8).
- `backend/packages/wagtail_forum/wagtail_forum/models/topics.py:186` —
  the URL shape that embeds `board.slug`.
- `wagtail/contrib/redirects/signal_handlers.py:106-186` — Wagtail's
  auto-create walks child *Pages* only.

## Recommended Action

1. Receive `wagtail.signals.page_slug_changed` (kwargs `instance`,
   `instance_before`) filtered to `isinstance(instance, ForumBoard)`.
2. For each **live** topic under the board, compute the old path from
   `instance_before.slug` and call `redirect_topic_path(old, new)`.
3. Do it as a bulk write, not N×3 statements inside the admin save: collect
   `(old, new)` pairs, one `delete()` for shadowing rows, one chain-collapse
   `update()` per batch, then `bulk_create(ignore_conflicts=True)` mirroring
   Wagtail's `BatchRedirectCreator`. A board with thousands of topics must
   not turn the promote-tab save into a multi-second request; consider a
   Celery task if the count is large.
4. Tests: board rename creates one row per live topic and none for drafts;
   the 301 is served for an old topic path; repeated renames collapse chains.

## Technical Details

- Reach today is limited: the SPA resolves topics by leading id, so these
  rows serve origin hits and `/api/v2/redirects/find/?html_path=` lookups.
  That is why this is p4 rather than a blocker on the quick-wins PR.
- `redirect_topic_path` is already loop- and duplicate-safe for a single
  pair; the batch version must keep both properties.

## Acceptance Criteria

- [x] Renaming a `ForumBoard` slug in the admin creates a permanent redirect
      for every live topic's previous path — `test_board_rename_redirects_every_live_topic_and_no_drafts`,
      `test_board_rename_through_the_admin_publish_path` (save_revision().publish()),
      `test_board_rename_old_topic_path_is_served_as_a_301` (2026-09-04)
- [x] Draft/unpublished topics get no rows — same test plus
      `test_board_rename_with_no_live_topics_writes_nothing` (2026-09-04)
- [x] A board with 1,000 topics completes the admin save in bounded queries
      (pinned with `CaptureQueriesContext`, flat in N) —
      `test_board_rename_query_count_is_flat_in_topic_count`: `(small, big) == (9, 9)`
      at 3 and 1,000 topics, 1,003 rows written (2026-09-04)
- [x] Existing `test_topic_redirects.py` stays green — 24 passed (12 existing +
      12 new); `apps/forum_host` + `packages/wagtail_forum`: 1189 passed (2026-09-04)

## Work Log

### 2026-09-04 - Started by completing-todos skill (run 2026-09-04-0350)

- Picked up by automated workflow, in worktree `feat/forum-board-slug-redirects`.

### 2026-09-04 - Implemented (run 2026-09-04-0350)

- `apps/forum_host/redirects.py`: `page_slug_changed` receiver registered with
  `sender=ForumBoard` (a custom `Signal`, so the sender is the class, not a
  lazy `"app.Model"` string) calling `redirect_board_topics(before, board)`.
  Wagtail sends the signal from `transaction.on_commit`, so the board's own
  save has already committed when the handler runs — the bulk write opens its
  own `atomic()` so a failure leaves the table untouched, never half-moved.
- Same three steps as `redirect_topic_path`, each ONE statement over the whole
  live-topic set: `old_path__in=new_paths` delete (manual rows logged with the
  existing `[ERROR] Removed manual redirect` line), a prefix `Replace()` update
  for the chain collapse (any row aimed under the old board path now aims
  under the new one — also fixes rows aimed at unpublished topics for when they
  republish), then delete-then-`bulk_create(ignore_conflicts=True,
  batch_size=REDIRECT_BULK_CREATE_BATCH_SIZE)` for the per-topic rows, which
  is the bulk form of the per-topic "re-point every NULL-site row, else
  create". Per-topic paths come from `Topic.get_absolute_url()` on stub
  instances (`Topic(board=before, id=…, slug=…)`), so no URL shape is restated
  except the board prefix, which `test_board_prefix_matches_the_topic_url_shape`
  pins to the model method.
- Query count is a constant 9 (SELECT topics, SAVEPOINT, SELECT manual
  shadowing, DELETE, UPDATE, DELETE self-loops, DELETE, INSERT, RELEASE) —
  pinned equal at 3 and 1,000 topics; only the INSERT splits past
  `REDIRECT_BULK_CREATE_BATCH_SIZE`. No Celery task: the 1,000-topic case
  runs in well under a second inside the test.
- Verification:

  ```
  $ pytest apps/forum_host/tests/test_topic_redirects.py -q --reuse-db
  22 passed, 1 warning in 20.67s
  $ PYTHONPATH=…/backend/packages/wagtail_forum pytest apps/forum_host packages/wagtail_forum -q --reuse-db
  1187 passed, 2 warnings in 104.58s (0:01:44)
  $ ruff check apps/forum_host/redirects.py apps/forum_host/constants.py apps/forum_host/tests/test_topic_redirects.py
  All checks passed!
  ```

- Worktree gotcha, recorded for the next run: `wagtail_forum` is installed
  editable from the MAIN checkout, so collecting `packages/wagtail_forum`
  from a worktree raises 71 "import file mismatch" collection errors. The
  `PYTHONPATH=<worktree>/backend/packages/wagtail_forum` prefix above makes
  the worktree's copy win (PathFinder runs before the editable finder).
- Docs: `backend/docs/patterns/domain/forum.md` redirect section + hooks
  table updated; the module docstring's "Scope" paragraph no longer calls
  board renames a non-goal.

### 2026-09-04 - Review round 1 (bundled `/code-review medium`, run 2026-09-04-0350)

Three findings, two CONFIRMED by the reviewer's own probe tests against the
real test DB, one low. Both confirmed ones were in the rename-BACK path when a
topic was unpublished between the two renames:

1. **Self-loop row.** Step 1 shadow-deletes only LIVE topics' new paths, so
   the prefix `Replace()` in step 2 folded an unpublished topic's earlier A→B
   row into A→A; on republish its canonical URL 301'd to itself. The
   reviewer's first suggestion (delete everything under the new prefix) was
   rejected — it would also delete legitimate topic-slug rows (`/A/2-old →
   /A/2-new`) that step 2 has just correctly restored. Applied the second:
   after the collapse, delete `old_path__startswith=new_prefix,
   redirect_link=F("old_path")` (step 2b, +1 query → 9).
   `test_board_rename_back_after_a_topic_was_unpublished_leaves_no_self_loop`.
2. **Early return skipped the repair.** `if not pairs: return` ran before
   steps 1–2, so a board whose topics were all unpublished kept its stale A→B
   row and the docstring's "the collapse still re-points rows aimed at them"
   was false. Steps 1 and 3 are now gated on `pairs`; step 2/2b always run.
   `test_board_rename_back_with_no_live_topics_still_repairs_stale_rows`.
3. **Constant rationale aimed at the wrong statement** (low). The batch size
   bounds the INSERT, while the unbatched `old_path__in` lists are what would
   hit Postgres's 65,535-parameter cap first (~65k topics on one board).
   Comment, docstring and pattern doc reworded honestly; no chunking added —
   prod boards hold single-digit topic counts.

Verification after the fixes:

```
$ pytest apps/forum_host/tests/test_topic_redirects.py -q --reuse-db
24 passed, 1 warning in 19.97s
$ ruff format … → 2 files left unchanged; ruff check on the changed files clean
  (the one E714 ruff reports in apps/forum_host/tasks.py:141 is pre-existing, untouched)
```

### 2026-09-04 - Review round 2 (run 2026-09-04-0350)

The bundled `/code-review` round 2 stalled in the harness after reading the
diff. `code-review-orchestrator` returned only its triage (django-drf,
wagtail, cross-cutting), so those three reviewers were dispatched directly.

- **All three reported one CRITICAL finding — and it was reviewer residue,
  not a defect.** The working tree's step 2b had become
  `pass  # MUTANT A: 2b removed`: a mutation probe left behind by the review
  round that stalled (round 1 had used probe tests and cleaned up; the
  stalled run never got to its revert). The three reviewers each hand-traced
  the two round-1 regression tests against the mutant and concluded both
  would fail, which is the strongest evidence yet that those tests guard the
  fix. Restored the delete verbatim, swept the tree (no untracked probe
  files; no other `MUTANT` residue), re-verified below.
- **MEDIUM (django-drf) — resolved by the same restore.** `BOARD_RENAME_QUERIES
  = 9` was flagged as "one higher than the code produces" — true only of the
  mutant; against the restored code the pin passes at `(9, 9)`.
- **Known issues (LOW, cross-cutting, accepted):** the *pre-existing* topic
  receivers' guards (`if raw or instance.pk is None`, `if raw or created or
  not old_path or not instance.live`) have no `raw=True` fixture-load test,
  and `created` is subsumed by `not old_path`. Pre-dates this todo (quick-wins
  PR #624); `raw` is Django's documented `loaddata` contract and `created` is
  a harmless redundancy. Not changed here — out of this slice's scope.

Final verification, after the restore:

```
$ ruff format --check … → 3 files already formatted; ruff check → All checks passed!
$ pytest apps/forum_host/tests/test_topic_redirects.py -q --reuse-db
24 passed, 1 warning in 5.57s
$ PYTHONPATH=…/backend/packages/wagtail_forum pytest apps/forum_host packages/wagtail_forum -q --reuse-db
1189 passed, 2 warnings in 88.43s (0:01:28)
```

### 2026-09-04 - Completed by completing-todos skill (run 2026-09-04-0350)

- Verification: all 4 acceptance criteria passed (evidence quoted inline above).
- Review: round 1 — 3 findings (2 confirmed bugs repaired + 1 low doc fix);
  round 2 — 3 reviewers, 1 critical (reviewer residue, restored), 1 medium
  (same root cause), 1 low accepted as a known issue. No blocking findings
  remain.
- Shipped as a PR from worktree branch `feat/forum-board-slug-redirects`
  (deviation from the skill's never-commit rail, per the project's
  "a todo slice ships as a merged PR" convention).

### 2026-09-04 - Filed

- Surfaced by code review of the Wagtail quick-wins branch; scoped out of
  that PR (the brief covered topic slug changes only) and documented as a
  non-goal in the module docstring.

## Notes

Related: the quick-wins PR mounted `wagtail.contrib.redirects`' headless API
at `/api/v2/redirects/`; if the web app ever consumes it, this gap becomes
user-visible and the priority should rise.
