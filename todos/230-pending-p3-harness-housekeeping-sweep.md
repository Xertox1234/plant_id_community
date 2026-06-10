---
status: pending
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

- [ ] todos/ contains only TEMPLATE.md, README.md, archive/, and live todo files.
- [ ] Forum pattern doc matches code that actually exists.
- [ ] MEMORY.md index has no entries flagged stale.
- [ ] No instruction text is loaded twice (global + project CLAUDE.md overlap
      resolved).

## Work Log

### 2026-06-10 - Created

- Filed from harness audit session (recommendation #8).
