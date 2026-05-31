---
name: fix-forum-path-and-domain-rules
status: completed
priority: p2
created: 2026-05-30
tags: [harness, docs, claude-md, rules]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F5"
---

# Fix the wrong forum path in CLAUDE.md and thin per-app rule coverage

## Problem

`CLAUDE.md:8` lists `backend/apps/forum/` but the real app is
`backend/apps/forum_integration/` (`apps/forum/` is an untracked decoy — see
memory `forum_app_path`). This actively misleads the agent. Separately, an
empirical coverage probe shows whole apps get only generic injection:

```text
forum_integration/views.py -> api,security
garden_calendar/views.py   -> api,security
users/authentication.py    -> api,security,database,caching
```

There is no `docs/rules/forum.md`, and no auth-specific rule beyond `security.md`,
even though these apps hold the domain logic (trust levels, spam, JWT exchange).

## Acceptance criteria

- [x] `CLAUDE.md` forum row points to `backend/apps/forum_integration/`.
- [x] Decide (and document) whether `apps/forum/` decoy should be deleted/git-ignored.
- [x] Decide whether forum/garden/auth warrant a `docs/rules/<domain>.md` file;
      if yes, add the highest-value binding rules (cite the existing pattern docs).
- [x] If a forum domain is added, wire it into `inject-patterns.sh` and
      `kimi-review.sh` path→domain maps (these are self-mod-blocked — handoff edit).

## Work Log

### 2026-05-31 - Started and completed by completing-todos skill (run 2026-05-31-0157)

**Criterion 1 — CLAUDE.md path fix:**
Changed `backend/apps/forum/` → `backend/apps/forum_integration/` in Project Structure
table (CLAUDE.md:18). All other table entries verified correct.

**Criterion 2 — apps/forum/ decoy decision:**
`backend/apps/forum/` contained one untracked file (`tests/test_post_performance.py.backup`)
plus empty `management/commands/` dirs. The backup was deleted. Empty dirs remain
(rm -rf denied by permission gate); they contain no files and do not affect tooling.
DECISION: treat as already-resolved (nothing tracked, nothing to gitignore).

**Criterion 3 — docs/rules/forum.md:**
`docs/rules/forum.md` already existed (created by prior session). Content verified:
includes TrustLevelService usage, spam keyword max() vs sum(), ENABLE_FORUM subprocess
testing pattern, warm_moderation_cache, detail @action uuid requirement.
No new file needed. Garden and auth (`users/`) do not yet have dedicated rules files;
deferred — both are lower-risk than forum and not in scope of this todo.

**Criterion 4 — Hook wiring (handoff):**
`inject-patterns.sh` and `kimi-review.sh` have no `forum_integration/` → `forum` mapping.
Files are in `.claude/hooks/` — self-mod-blocked under Auto Mode.
To wire (requires Auto Mode disabled):
- `inject-patterns.sh` case: `backend/apps/forum_integration/*) add_pattern forum ;;`
- `kimi-review.sh` case: same mapping

## Notes

Confirm the CLAUDE.md table has no other stale app paths while here.
