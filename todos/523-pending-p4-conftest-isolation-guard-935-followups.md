---
status: pending
priority: p4
issue_id: "523"
tags: [forum, backend, testing]
dependencies: []
triage: ready
triaged: 2026-10-02
owner_decision: "Finding 5: widen the regex to also flag quoted 'apps.' strings, sharing HOST_IMPORT with test_reusability.py; no ast parse (2026-10-02)"
---

# Conftest isolation guard: non-blocking findings from PR #935 (todo 511)

## Problem

PR #935 (todo 511) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_conftest_isolation.py:36`** (low, round 1). The guard test skips when no provider was captured. If the host stops registering its provider at ready(), the test skips instead of failing, so the deleted-fixture regression it exists to catch goes silent.
   Suggested: Assert the host provider is present (it registers at ready()), or fail rather than skip when the list is empty.

2. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_conftest_isolation.py:38`** (low, round 1, round 2). The guard skips when the provider list is empty at module setup. If a test that runs earlier unregisters the host's `provide` and never restores it, this test skips quietly, and a deleted conftest fixture would go unnoticed in that run.
   Suggested: Make the skip conditional on the host app being absent, e.g. `if not apps.is_installed('apps.forum_host')`, rather than on the list being empty. That way an emptied list fails as a real failure instead of a skip.
   Also reported: The test skips when no host provider is registered. If the host stops registering at ready(), the guard goes silently inert and the suite stays green, which is the gap this test exists to close.
   Also reported: The guard skips when the captured provider list is empty, so it does not fail. If the host stops registering at ready() or an earlier test unregisters it without restoring, the regression guard turns into a quiet skip. In this repo the host always registers forum\_settings.provide, so the skip branch is unreachable.
   Also reported: The test skips when no host provider is registered. If the host's ready() registration is ever removed, the guard silently becomes a skip and the deleted-fixture regression goes unnoticed (green by skip).

3. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_conftest_isolation.py:39`** (low, round 2). The guard skips when the host has no provider registered at collection time. If host registration ever moves off ready() (lazy, or registered by an earlier DB test), the test skips instead of failing, and the cold-memo hazard from todo 501 comes back unflagged.
   Suggested: In this repo, assert that apps.forum\_host's provide is registered (host-side test), or fail rather than skip when forum\_host is in INSTALLED\_APPS. Keep the skip only for hosts that don't install forum\_host.

4. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_conftest_isolation.py:42`** (low, round 1). The per-provider `not in` loop adds nothing after `assert conf._override_providers == []`. If the equality passes, the loop cannot fail; if it fails, the loop never runs.
   Suggested: Drop the loop. The equality assert already reports the leftover provider in its diff.

5. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_conftest_isolation.py:49`** (low, round 1). The host-import check only matches lines that start with `from apps` or `import apps`. It misses other ways of pulling in the host: `pytest_plugins = ['apps...']`, `importlib.import_module('apps...')`, and comma imports such as `import x, apps.y`. The guard is narrower than its name says.
   Suggested: Also flag the string pattern `['"]apps\.` in the conftest, or parse it with `ast` and check every Import/ImportFrom node and every string constant that starts with `apps.`.
   Also reported: The host-import regex is copied verbatim from test\_reusability.HOST\_IMPORT (line 6). The two copies can drift, so a pattern tightened in one place would not tighten the conftest check.

6. **`todos/archive/511-completed-p4-forum-package-test-isolation-913-followups.md:50`** (low, round 2). The Verified entry embeds an absolute /Users/williamtower/... venv path, which is the same defect finding 2 asked to remove from 501. The recorded grep guard only covers the 501 file, not this one.
   Suggested: Use repo-relative `venv/bin/python` as the 501 entry now does.

7. **`todos/archive/511-completed-p4-forum-package-test-isolation-913-followups.md:54`** (low, round 2). The Verified work-log entry embeds an absolute /Users/williamtower/... venv path. This is the same defect that finding 2 of this todo fixed in the 501 archive. The entry's own grep guard only checks the 501 file.
   Suggested: Write the command with the repo-relative `venv/bin/python` and a note that the venv is the main checkout's, as the 501 entry does.

8. **`todos/archive/511-completed-p4-forum-package-test-isolation-913-followups.md:55`** (low, round 1). The Verified entry embeds an absolute /Users/williamtower/... venv path. This is the same defect finding 2 asked to remove from the 501 Work Log. The grep guard only checks the 501 file, so it does not catch this.
   Suggested: Write the command as venv/bin/python, as the 501 entry does, and note that the venv is the main checkout's.

9. **`todos/archive/511-completed-p4-forum-package-test-isolation-913-followups.md:56`** (low, round 1, round 2). The new Verified AC command embeds an absolute home path (/Users/williamtower/.../backend/venv/bin/python). Finding 2 removed exactly this kind of path from the 501 Work Log, and this PR adds one back in 511's own log. Its grep check only scans the 501 file, so it misses this.
   Suggested: Write the interpreter as repo-relative, e.g. `venv/bin/python` (the main checkout's venv), as the 501 entry now does. Or widen the `! grep '/Users/'` check to cover both archive files.
   Also reported: 511's own Verified entry adds back an absolute /Users/williamtower/... venv path. That is the same pattern finding 2 removed from the 501 Work Log, so it shows up again one file over.
   Also reported: The Verified entry embeds the absolute /Users/williamtower/... venv path. That is the same machine-path leak finding 2 fixed in todo 501.
   Also reported: The 511 Verified AC command embeds an absolute /Users/williamtower/... venv path. Finding 2 of this same todo removed exactly that kind of path from the 501 Work Log, so the new archive repeats it.
   Also reported: The new Verified entry puts the machine's absolute home path (/Users/williamtower/projects/.../backend/venv/bin/python) back into the public repo. That is the same local-path and username leak that Finding 2 of this todo removed from the 501 Work Log.
   Also reported: The new Verified AC line embeds /Users/williamtower/... absolute venv paths. Finding 2 of this same todo flagged exactly this in 501's Work Log, and the AC's grep only checks 501's file.

10. **`todos/archive/511-completed-p4-forum-package-test-isolation-913-followups.md:57`** (low, round 1). The new Verified entry embeds /Users/williamtower/projects/plant\_id\_community/backend/venv/bin/python, an absolute home path with the local username, in a public repo. This is the same kind of leak that finding 2 of this todo removed from the 501 Work Log.
   Suggested: Replace the absolute interpreter path with the repo-relative form used in the 501 entry (`venv/bin/python`, noting the venv is the main checkout's), so the AC command has no /Users/ path.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #935 review rounds 1-2.
