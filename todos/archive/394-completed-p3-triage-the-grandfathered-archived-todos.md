---
status: completed
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

- `todos/archive/020-superseded-p2-post-search-gin-index.md` — the only one whose
  grep came back **empty** (no `GinIndex` / `gin_trgm` / `SearchVector` in the
  forum migrations). Most likely genuinely unfinished. Start here.
- `todos/archive/009-superseded-p2-dead-code-services.md` — genuinely
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

**Renaming a file means updating its path in
`todos/archive-status-allowlist.yml` too** — entries are keyed by path, and a
path that no longer exists fails the check as a stale entry. If the rename came
with a real fix, delete the entry instead. This bites immediately, because step
2 above renames files.

**Renaming an archived todo also makes its `.secrets.baseline` entries stale** — the
baseline is keyed by filename, and `detect-secrets` will block the commit. Fix
it with a filename-only edit to `.secrets.baseline`. **Never regenerate it**: a
regeneration adds ~28 entries including the file that held the leaked Plant.id
key.

**Run `git commit` as `/usr/bin/git commit`.** The rtk wrapper swallowed a
`detect-secrets` failure and reported exit 0 with no commit made, three times in
a row, while doing exactly this work.

## Acceptance Criteria

- [x] `allow:` in `todos/archive-status-allowlist.yml` is empty, and every file
      it listed carries its verdict + evidence in its own Work Log (completed
      2026-09-27)
- [x] Any of the 13 found **not** done is either marked `superseded` with a
      pointer to what did the work, or re-filed as a live todo — never marked
      `completed` (completed 2026-09-27: 10 superseded, open ACs re-filed as
      todos 464–467)
- [x] `todos/archive/020-superseded-p2-post-search-gin-index.md` is settled
      against the actual migrations, since it is the one negative grep result
      (completed 2026-09-27: the grep was a false negative, see the Work Log)
- [x] `python3 scripts/check_archived_todo_status.py --fail-over 0` still exits 0
      with no stale entries (completed 2026-09-27)

## Notes

**Priority p3.** The tripwire already binds — nothing new can be archived on
vibes, which was the point. This is historical cleanup, and the 16 already
resolved covered the ones that were cheap to settle.

Related: todo 390 (the tripwire), `scripts/check_archived_todo_status.py`,
`todos/archive-status-allowlist.yml`.

## Work Log

### 2026-09-24 - Owner: cleared for a sweep

Not blocked — research work. The owner cleared it for the next sweep. Mind the
three traps in Recommended Action (allowlist paths, `.secrets.baseline`
filename edits — never regenerate it — and `/usr/bin/git commit`).

### 2026-09-27 - All 13 settled; `allow` is empty

Each file was checked AC by AC against the current code and `git log`, by two
read-only investigators. Their load-bearing claims were then spot-checked:
the GIN migration in a81416c4, `apps/forum`'s deletion in a7b61b7c (#271, 56
files), and `ai_care_service.py` having no code references. Each file's
verdict and evidence is in its own Work Log.

| File | Verdict |
|------|---------|
| 001 plantnet circuit breaker | partial → `superseded`; test AC → todo 464 |
| 002 cascade disease result | `completed` (admin AC has nothing to update) |
| 002 views type hints | partial → `superseded`; mypy gate → todo 466 |
| 004 reaction toggle race | `superseded` (#271; live equivalent in `wagtail_forum`); concurrency test → 464, tap guard → 465 |
| 004 vote race | `superseded` (F() fix e48bb8c9, routes removed in #800); `diagnosis_count` → 467 |
| 005 attachment soft delete | `superseded` (landed #122, deleted #271, `ImageBlock` design) |
| 008 image magic number | `completed` (rebuilt in `wagtail_forum` #406, with tests) |
| 009 dead code services | `superseded`: 1 of 13 deleted, 8 now live; `ai_care_service.py` → 467, `plant_care_reminder_service.py` → todo 410 slice B |
| 009 upload rate limiting | `completed` (rebuilt in `forum_host`, with tests) |
| 015 TipTap memory leak | partial → `superseded`; destroy test → 464 |
| 016 moderation dashboard | `superseded` (#271) |
| 020 post search GIN index | `superseded`; **the empty grep was a false negative** |
| 031 API documentation | partial → `superseded`; `--fail-on-warn` and request examples → 466 |

On 020: a81416c4 added `apps/forum/migrations/0008_add_post_search_gin_indexes.py`
(tsvector and trigram GIN on `content_raw`). The grep only searched
`wagtail_forum`. That app was then deleted in #271. Forum search today goes
through `modelsearch`'s Postgres backend, and its GIN indexes live on
`wagtailsearch_indexentry`.

Ten files were renamed `-completed-` → `-superseded-` to match their
status (the tripwire's filename check). Their paths were updated in the
allowlist's `grandfathered_unchecked_acs`. None is keyed in
`.secrets.baseline`. `docs/archive/2025-11/SECURITY_AUDIT_COMPLETION_REPORT.md`
still names the old filenames and was left alone as a historical record.
`grandfathered_unchecked_acs` still lists 62 files; per this todo, it
shrinks opportunistically.

Four of the thirteen hints pointed at the wrong code (002-views, 004-vote,
004-reaction, 008), and 031's hint was simply wrong. That confirms the
allowlist's warning: a hint is a starting point, never a verdict.

### 2026-09-27 - PR #859 review round 1; archived

The review confirmed the tripwire exits 0, the allowlist YAML is valid, the
paths resolve, and every spot-checked evidence claim held. One blocking
finding: 031 was `completed` with an open AC (request examples) that was
neither done nor re-pointed, against this todo's own rule. 031 is now
`superseded` (renamed; allowlist path updated), with the residue re-pointed
to todo 466. Non-blocking: the rebuilt upload throttle lost its
window-reset test, now added to todo 464.
