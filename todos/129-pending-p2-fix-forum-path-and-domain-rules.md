---
name: fix-forum-path-and-domain-rules
status: pending
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

- [ ] `CLAUDE.md` forum row points to `backend/apps/forum_integration/`.
- [ ] Decide (and document) whether `apps/forum/` decoy should be deleted/git-ignored.
- [ ] Decide whether forum/garden/auth warrant a `docs/rules/<domain>.md` file;
      if yes, add the highest-value binding rules (cite the existing pattern docs).
- [ ] If a forum domain is added, wire it into `inject-patterns.sh` and
      `kimi-review.sh` path→domain maps (these are self-mod-blocked — handoff edit).

## Notes

Confirm the CLAUDE.md table has no other stale app paths while here.
