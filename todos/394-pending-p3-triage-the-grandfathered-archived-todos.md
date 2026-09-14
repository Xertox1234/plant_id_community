---
status: pending
priority: p3
issue_id: "394"
tags: [todo-hygiene, tech-debt, verification]
dependencies: []
source_review: "todos/archive/390-completed-p3-plant-id-key-rotation-unverified.md"
---

# Shrink the two grandfather lists in todos/archive-status-allowlist.yml

## Problem

`scripts/check_archived_todo_status.py` (todo 390) starts green only because two
lists excuse what predates it:

- **`allow` — 13 archived todos whose frontmatter still says the work is open.**
  Nobody has confirmed any of them landed.
- **`grandfathered_unchecked_acs` — 62 archived todos carrying 462 bare unchecked
  acceptance criteria.**

Neither list can grow: a new violation fails CI, and a *stale* entry fails too,
so the only way to remove one is to establish what actually happened. But
nothing makes them shrink either, and an allowlist that never shrinks is the
state todo 390 was filed to end.

## Findings

Measured 2026-09-13, on the day the checker landed. 29 violations existed; 16
were resolved that day with evidence recorded in each file's own Work Log, which
is why only 13 remain in `allow`.

**The discriminator that made those 16 cheap: "would this have left an
artifact?"** A setting, an index, a decorator, a validator — all answerable with
one grep in under a minute (`CSRF_COOKIE_HTTPONLY = True` at settings.py:1307;
`blog_view_trending_idx` in two migrations; `@csrf_protect` on `def register`;
`ACCESS_TOKEN_LIFETIME` defaulting to 15 minutes). The residue is the work whose
deliverable left nothing to grep for, which is the same category as the incident
that started all of this.

Each `allow` entry carries a `hint` recording what a grep turned up. **A hint is
a starting point, never a verdict** — writing `status: completed` on the strength
of one is the exact falsification the checker exists to prevent.

Two entries are worth naming:

- `todos/archive/020-completed-p2-post-search-gin-index.md` — the only one whose
  grep came back **empty** (no `GinIndex` / `gin_trgm` / `SearchVector` in the
  forum migrations). Most likely genuinely unfinished. Start here.
- `todos/archive/009-completed-p2-dead-code-services.md` — genuinely
  artifact-less. The deliverable was *deleting* 4,500 lines across 13 services;
  a successful deletion and never starting look identical in the tree. Only
  `git log` can answer it.

## Recommended Action

1. Work `allow` first — 13 files, each with a hint, and the list is meant to
   reach zero.
2. For each: confirm the work landed, then fix the frontmatter and record the
   evidence in that file's Work Log. If it did **not** land, do not mark it
   `completed` — either `superseded` with a pointer to whatever did the work, or
   re-file it as a live todo.
3. `grandfathered_unchecked_acs` is a fixed historical snapshot, not a backlog.
   Shrink it opportunistically: when you touch an archived todo for another
   reason, check off or re-point its criteria and drop the entry.

**Renaming an archived todo makes its `.secrets.baseline` entries stale** — the
baseline is keyed by filename, and `detect-secrets` will block the commit. Fix
it with a filename-only edit to `.secrets.baseline`. **Never regenerate it**: a
regeneration adds ~28 entries including the file that held the leaked Plant.id
key.

**Run `git commit` as `/usr/bin/git commit`.** The rtk wrapper swallowed a
`detect-secrets` failure and reported exit 0 with no commit made, three times in
a row, while doing exactly this work.

## Acceptance Criteria

- [ ] `allow:` in `todos/archive-status-allowlist.yml` is empty, and every file
      it listed carries its verdict + evidence in its own Work Log
- [ ] Any of the 13 found **not** done is either marked `superseded` with a
      pointer to what did the work, or re-filed as a live todo — never marked
      `completed`
- [ ] `todos/archive/020-completed-p2-post-search-gin-index.md` is settled
      against the actual migrations, since it is the one negative grep result
- [ ] `python3 scripts/check_archived_todo_status.py --fail-over 0` still exits 0
      with no stale entries

## Notes

**Priority p3.** The tripwire already binds — nothing new can be archived on
vibes, which was the point. This is historical cleanup, and the 16 already
resolved covered the ones that were cheap to settle.

Related: todo 390 (the tripwire), `scripts/check_archived_todo_status.py`,
`todos/archive-status-allowlist.yml`.
