---
status: in_progress
priority: p3
issue_id: "230"
tags: [harness, docs, housekeeping, memory]
dependencies: []
---

# Harness housekeeping: todos/ reference docs, stale pattern doc, memory pruning, CLAUDE.md trim

## Problem

Accumulated clutter across the harness: static reference docs mixed into the
working todos/ directory, a stale forum pattern doc describing deleted code,
May-era memory files whose lessons are already absorbed, and CLAUDE.md prose that
duplicates enforcement that now lives in triggers/hooks.

## Findings

- `todos/` holds ~204KB of static reference docs alongside 7 working todos:
  GITHUB_ISSUE_BEST_PRACTICES.md, GITHUB_ISSUE_CREATION_GUIDE.md,
  GITHUB_RESEARCH_SUMMARY.md, IMPLEMENTATION_CHECKLIST.md,
  QUICK_REFERENCE_ISSUE_CONVERSION.md, RESEARCH_SUMMARY.md.
- `backend/docs/patterns/domain/forum.md` describes the deleted
  forum_integration system (TrustLevelService, SpamDetectionService,
  warm_moderation_cache — none exist in the codebase post-machina-retirement).
  `docs/rules/forum.md` was rewritten 2026-06-10; the long-form doc was not.
  New wagtail_forum rules should be derived from
  `backend/packages/wagtail_forum/` (it has its own spam/ + moderation modules).
- Memory dir (~/.claude/projects/...plant-id-community/memory/): May-era
  feedback files + resolved project notes (~15-20K) are candidates for pruning;
  `project_forum_app_path.md` is self-flagged stale.
- CLAUDE.md: Critical Gotchas #1 and #3 are already enforced as triggers in
  `docs/rules/triggers.json`; the prose can shrink to one-line pointers.
  Kimi delegation rules appear in BOTH `~/.claude/CLAUDE.md` and project
  CLAUDE.md — loaded twice in this repo.
- Discovery source: 2026-06-10 harness audit.

## Recommended Action

1. `git mv` the six reference docs from `todos/` to `docs/archive/todos-reference/`.
2. Rewrite `backend/docs/patterns/domain/forum.md` for the wagtail_forum package
   (or archive it and start a new doc from the package README + code).
3. Prune/merge stale memory files; update MEMORY.md index (delete
   project_forum_app_path.md — superseded by repo docs fixed 2026-06-10).
4. Trim CLAUDE.md: gotchas already trigger-enforced become pointers; dedupe the
   delegation section against ~/.claude/CLAUDE.md (keep the project copy, slim
   the global one to a pointer, or vice versa).

## Technical Details

- todos/README.md may reference the moved files — update links.
- CLAUDE.md edits can hit the auto-mode self-mod classifier; have Auto Mode
  disabled for that step.

## Acceptance Criteria

- [x] todos/ contains only TEMPLATE.md, README.md, archive/, and live todo files.
      (done 2026-06-21 — `git mv`'d the 6 reference docs to
      `docs/archive/todos-reference/`; README had no links to update.)
- [x] Forum pattern doc matches code that actually exists. (done 2026-06-21 —
      archived the stale 979-line doc to
      `docs/archive/forum-patterns-trust-spam-pre-wagtail.md`; wrote a concise
      replacement pointing to the real `wagtail_forum` package (spam/, models/
      moderation.py, api/sanitize.py), `forum_host`, README, and docs/rules/forum.md
      — verified those paths exist; the only mentions of deleted code are in the
      archive notice.)
- [x] MEMORY.md index has no entries flagged stale. (done 2026-06-21 — deleted
      `project_forum_app_path.md` (self-flagged STALE, superseded by the
      wagtail-forum-rebuild memory) and its index line; 0 STALE markers remain.)
- [ ] No instruction text is loaded twice (global + project CLAUDE.md overlap
      resolved). (DEFERRED 2026-06-21 — the Kimi delegation guidance is in BOTH
      `~/.claude/CLAUDE.md` (global, all projects) and project `CLAUDE.md:250+`.
      Resolving it edits the user's GLOBAL cross-project config and requires a
      judgment call on which copy to keep — not done unilaterally at a sweep tail.
      This todo stays in_progress until that's decided.)

## Work Log

### 2026-06-21 - Parts 1–3 done, part 4 deferred (run 2026-06-21-1412)

- **Part 1 (todos/ cleanup):** moved the 6 reference docs (GITHUB_*, IMPLEMENTATION_
  CHECKLIST, QUICK_REFERENCE_*, RESEARCH_SUMMARY) to `docs/archive/todos-reference/`
  via `git mv`. todos/ now holds only TEMPLATE.md, README.md, archive/, live todos.
- **Part 2 (forum pattern doc):** the 979-line doc described the retired
  `forum_integration` (TrustLevelService/SpamDetectionService/warm_moderation_cache).
  Archived it; wrote a concise accurate replacement pointing to the live package
  (chose "archive + new doc" over a full rewrite, per the todo's Recommended Action).
- **Part 3 (memory prune):** deleted the self-flagged-stale `project_forum_app_path.md`
  - its MEMORY.md line.
- **Part 4 (CLAUDE.md dedup): DEFERRED.** The delegation guidance lives in both the
  user's GLOBAL `~/.claude/CLAUDE.md` and project `CLAUDE.md`. Deduping means editing
  the global cross-project file and deciding which copy is canonical — a call for the
  user, not a unilateral sweep-tail edit. (The gotcha→pointer trim in Recommended
  Action #4 is also optional judgment and was left as-is; the gotchas are useful prose.)
  **Follow-up:** decide global-vs-project canonical delegation copy, then this closes.

### 2026-06-10 - Created

- Filed from harness audit session (recommendation #8).
