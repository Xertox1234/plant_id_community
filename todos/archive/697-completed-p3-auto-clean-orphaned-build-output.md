---
status: completed
priority: p3
issue_id: "697"
tags: [tooling, worktrees, mobile, flutter, u34bolt, disk]
dependencies: []
triage: ready
triaged: 2026-11-05
owner_decision: "Delete automatically: the completing-todos cleanup runs the script with --apply (orphans older than 2 days, none a live worktree uses) (2026-11-05)"
---

# Clean up orphaned build output automatically

## Problem

Native build output for a worktree is redirected to the external SSD by hand
(`plant_community_mobile/build` → `/Volumes/U34Bolt/plant_id_community/build/<name>`),
and nothing removes it when the worktree goes away. `git worktree remove` deletes
only the symlink, so every finished worktree or one-off build leaves gigabytes
behind on U34Bolt until someone notices.

## Findings

- 2026-11-05, removing the `scan2-c` worktree after PR #1251 merged: the
  untracked symlink `plant_community_mobile/build -> /Volumes/U34Bolt/plant_id_community/build/scan2-c`
  had to be deleted first (`git worktree remove` refuses an untracked file), and
  its 1.8 GB target stayed on U34Bolt.
- The same folder also holds `build/testflight-18` (528 MB, last written
  2026-11-04), from the TestFlight build 18 archive. No worktree uses it.
- The symlink is untracked, not ignored: `.gitignore:27` and
  `plant_community_mobile/.gitignore:67` say `build/` and `/build/`, and a
  trailing slash matches directories only, so a symlink named `build` shows as
  `?? plant_community_mobile/build` in `git status`.
- Nothing in the repo creates these links or knows about
  `U34Bolt/plant_id_community/build/` (grep of `scripts/`, `.claude/hooks/`,
  `.claude/skills/` and `plant_community_mobile/CLAUDE.md` finds no reference). The
  `/Volumes/U34Bolt/README.md` entry for `plant_id_community/` lists only
  `tmp/`, and says the project "has no `build/` folder here", which is now false.
- `/Volumes/U34Bolt/plant_id_community/tmp/` (67 MB on 2026-11-05) also
  accumulates: SwiftPM `.lock` files that name long-gone worktrees
  (`…worktrees_flutter-3-47-9_…`), `TemporaryDirectory.*` folders, and
  one-off logs and APKs.
- Worktrees are removed in several places: the `completing-todos` engine's
  cleanup step (`git worktree remove $WT` + `git worktree prune`), and by hand.
  A cleanup tied to one of them would miss the others.
- Discovery: owner request 2026-11-05 ("create a todo that would allow build
  output to be cleaned up automatically").

## Proposed Solutions

### Option 1: A sweep script keyed on live worktrees (recommended)

- **Implementation:** `scripts/clean_build_output.py`. List
  `/Volumes/U34Bolt/plant_id_community/build/*`, compare each entry against
  `git worktree list --porcelain` (resolve every live worktree's
  `plant_community_mobile/build` symlink), and report each entry no live
  worktree points at, with its size and last-modified time. Dry run by
  default; `--apply` deletes orphans older than `--min-age` (default 2 days).
  Exit cleanly, doing nothing, when U34Bolt is not mounted (the README's
  `df -P` check, never `[ -d … ]`). Call it from the `completing-todos`
  cleanup step and document it next to the U34Bolt notes in
  `plant_community_mobile/CLAUDE.md`.
- **Pros:** catches orphans however the worktree was removed, including the
  ones already there; nothing is deleted while a worktree still points at it;
  easy to test against a temp directory.
- **Cons:** runs only when something calls it.
- **Effort:** 2–3 hours, including tests.
- **Risk:** low, provided deletion is limited to children of that one
  directory, it never follows symlinks out of it, and `--apply` is explicit.

### Option 2: A scheduled launchd agent

- **Implementation:** the same script run weekly by a `~/Library/LaunchAgents`
  plist with `--apply`.
- **Pros:** fully automatic.
- **Cons:** a laptop-wide agent outside the repo, so it isn't versioned with the
  code it serves; deletes on a schedule nobody is watching. Better as a later
  step on top of Option 1, if the owner wants it.
- **Effort:** 1 hour on top of Option 1.
- **Risk:** medium: unattended deletion.

## Recommended Action

1. Write `scripts/clean_build_output.py` per Option 1 (dry run by default,
   `--apply`, `--min-age DAYS`, `--root` override for tests).
2. Also report, but do not delete, entries in `plant_id_community/tmp/` older
   than 14 days (SwiftPM locks naming a missing worktree, `TemporaryDirectory.*`),
   under a separate `--tmp` flag; logs and APKs there are often kept on purpose.
3. Tests in `scripts/tests/` against a temp root with a fake worktree list:
   orphan reported, live target kept, a symlink inside an orphan is not
   followed, an unmounted drive is a no-op, nothing deleted without `--apply`.
4. Add the call to the `completing-todos` cleanup step (after
   `git worktree prune`), dry run first, then `--apply`.
5. Document it in `plant_community_mobile/CLAUDE.md` → "Build caches on the
   external drive", including the symlink convention and the
   `git worktree remove` gotcha (delete the `build` link first). Ask the owner to
   update the `plant_id_community/` entry in `/Volumes/U34Bolt/README.md`, which
   is outside the repo.
6. Optionally ignore the link itself: add `plant_community_mobile/build` (no
   trailing slash) to `plant_community_mobile/.gitignore`, so it stops showing
   as untracked and can't be committed by `git add -A`.

## Technical Details

- Live worktree targets: `git worktree list --porcelain` → for each `worktree
  <path>`, `os.path.realpath(<path>/plant_community_mobile/build)`.
- Deletion must check that each target's `realpath` is a direct child of the
  build root before calling `shutil.rmtree`, and pass the path itself, not a
  resolved symlink.
- Related memory: the U34Bolt rules in `/Volumes/U34Bolt/README.md`; the
  "Build caches on the external drive (U34Bolt)" section of
  `plant_community_mobile/CLAUDE.md`.

## Acceptance Criteria

- [x] `python3 scripts/clean_build_output.py` (no flags) lists orphaned
      entries under `/Volumes/U34Bolt/plant_id_community/build/` with sizes and
      deletes nothing.
- [x] `--apply` deletes only orphans older than `--min-age`; an entry a live
      worktree's `build` link points at is never deleted (covered by a test).
- [x] With U34Bolt unmounted (or `--root` pointing at a missing path) the script
      exits 0 and changes nothing (covered by a test).
- [x] A symlink inside an orphan is removed as a link, never followed
      (covered by a test).
- [x] The `completing-todos` cleanup step runs the script after
      `git worktree prune`.
- [x] `plant_community_mobile/CLAUDE.md` documents the build symlink
      convention, the script, and deleting the link before `git worktree remove`.

## Work Log

### 2026-11-05 - Filed

- Filed at the owner's request after removing the `scan2-c` worktree left
  `U34Bolt/plant_id_community/build/scan2-c` (1.8 GB) behind. The owner deletes
  that folder by hand (Claude's `rm -rf` was permission-denied); `testflight-18`
  (528 MB) is the other orphan found.

### 2026-11-05 - Implemented by the todo sweep (run 2026-11-05-2004)

- Added `scripts/clean_build_output.py`: lists every entry of
  `/Volumes/U34Bolt/plant_id_community/build/` with size and newest mtime, marks
  each one no live worktree's `plant_community_mobile/build` link resolves to, into
  or above as an orphan; dry run by default, `--apply` deletes orphans older than
  `--min-age` (2 days), `--tmp` reports old `tmp/` entries without deleting. Exits 0
  when the drive is unmounted (`df -P`) or the root is missing; deletes nothing if
  `git worktree list` fails; never follows a symlink.
- 20 tests in `scripts/test_clean_build_output.py` (temp root, fake worktrees),
  wired into `.github/workflows/harness-ci.yml`. Mutation-checked: dropping the
  live-target filter fails 5 tests, following links inside an orphan fails the
  symlink test.
- `completing-todos` cleanup now runs the script (dry run, then `--apply`, sandbox
  off) after `git worktree prune`, per the owner decision to delete automatically.
- `plant_community_mobile/.gitignore` ignores the `build` link (`/build`), and
  `plant_community_mobile/CLAUDE.md` documents the link convention, the script and
  deleting the link before `git worktree remove`.
- Owner action outside the repo: update the `plant_id_community/` entry in
  `/Volumes/U34Bolt/README.md` (it says the project has no `build/` folder there).

### 2026-11-05 - Verified by the todo sweep (run 2026-11-05-2004)

- AC 2: `python3 scripts/test_clean_build_output.py` — evidence `.sweep-evidence/g2/697-ac1.txt` (not committed), last lines:

  ```text

  ----------------------------------------------------------------------
  Ran 20 tests in 0.037s

  OK
  ```

- AC 3: `python3 scripts/test_clean_build_output.py` — evidence `.sweep-evidence/g2/697-ac2.txt` (not committed), last lines:

  ```text

  ----------------------------------------------------------------------
  Ran 20 tests in 0.032s

  OK
  ```

- AC 4: `python3 scripts/test_clean_build_output.py` — evidence `.sweep-evidence/g2/697-ac3.txt` (not committed), last lines:

  ```text

  ----------------------------------------------------------------------
  Ran 20 tests in 0.033s

  OK
  ```

- AC 5: `grep -n -B2 -A6 clean_build_output .claude/skills/completing-todos/SKILL.md` — evidence `.sweep-evidence/g2/697-ac4.txt` (not committed), last lines:

  ```text
  366-at, and exits 0 doing nothing when U34Bolt is not mounted. Report what it deleted in the wrap-up.
  367-
  368-**A wedged CI job** (todo 512) can hold an armed PR open indefinitely. On PR #906 a Web CI run stayed
  369-`in_progress` for over 80 minutes, and `gh run cancel`, the API's `force-cancel` and `gh run rerun` each
  370-refused it. When a required check has shown `in_progress` far past its usual time and those refuse, start a fresh run
  ```

- AC 6: `grep -n -E 'clean_build_output|link first|worktree remove|plant_id_community/build|/build\b' plant_community_mobile/CLAUDE.md` — evidence `.sweep-evidence/g2/697-ac5.txt` (not committed), last lines:

  ```text
  43:  `plant_community_mobile/build -> /Volumes/U34Bolt/plant_id_community/build/<name>`.
  44:  `plant_community_mobile/.gitignore` ignores the link (`/build`, no trailing slash).
  45:  On a branch cut before that ignore, `git worktree remove` refuses the worktree because the
  47:  `build` link first** (`rm plant_community_mobile/build`, no `-r`), then remove the
  49:  `python3 scripts/clean_build_output.py` sweeps it (todo 697): a dry run by default lists
  ```

### 2026-11-05 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-05-2004)

- AC 1: confirmed by the owner on 2026-11-05: "Owner confirmed 2026-11-05 after a live dry run on U34Bolt with a 1 MB probe folder zz-orphan-probe dated 2026-11-01: output 'orphan 1.0 MB 2026-11-01 00:00 zz-orphan-probe', 'Orphans: 1, 1.0 MB.', 'Dry run: nothing deleted.', exit 0, probe still present afterwards (then removed by hand)" (`state.py confirm`; no command or evidence)

### 2026-11-05 - Completed by the todo sweep (run 2026-11-05-2004)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

P3: costs disk space, not correctness. The orphans found today are about
2.3 GB in total.
