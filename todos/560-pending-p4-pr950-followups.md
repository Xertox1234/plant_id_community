---
status: pending
priority: p4
issue_id: "560"
tags: [todo-sweep, follow-ups, backend]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Narrow the HOST_IMPORT comment and pin \"# see 'apps.py'\" as a known false positive; do not widen the regex (2026-10-11)"
---

# Follow-ups from PR #950 (todo 523), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #950; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #950 (todo 523)

1. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py:30`** (medium, defect). No HOST\_IMPORT specimen pins re.MULTILINE; dropping the flag leaves every test green. All five positive specimens (lines 30-34) are one-line strings that match at position 0 or through the quoted branch. With re.MULTILINE removed, all ten parametrized pins stay green, but the pattern then sees only a file's first line: a module with 'import os' before 'from apps.forum\_host import x' is no longer flagged. The package scan (line 22) and test\_conftest\_isolation's conftest check share HOST\_IMPORT, so both guards would silently go first-line-only.
   Suggested: Add a multi-line positive specimen shaped like a module header, e.g. 'import pytest\\n\\nfrom apps.forum\_host import x\\n', then mutation-check: drop re.MULTILINE, expect red, restore.
   Seen on main: test\_reusability.py:13 HOST\_IMPORT = re.compile(..., re.MULTILINE); :30-34 the five flag specimens are all single-line. In-memory probe of main's pattern: without MULTILINE all 10 pins still pass; 'import os\\nfrom apps.forum\_host import x\\n' matches with the flag (True) and not without it (False).

2. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_conftest_isolation.py:44`** (low, defect). Todo 523's fail-instead-of-skip arm has no committed test, and its comment overstates when the guard skips. The assert at lines 47-51 runs only when providers\_before\_fixture is empty while apps.forum\_host is installed. A healthy run never produces that (the host registers at ready()), so reverting line 44 to 'if not providers\_before\_fixture: skip', or dropping either 'and' operand, stays green; the only proof is the uncommitted plugin mutation in the 523 Work Log. The line-43 comment 'Skip only for a host that registers no provider at all' overstates: for any host other than apps.forum\_host, a lost or test-removed registration still skips, since an empty list cannot tell 'registers none' from 'lost'.
   Suggested: Extract the verdict into a helper taking (providers, host\_installed) and unit-test its skip, fail and pass arms with synthetic inputs, citing todo 523 in the assert message. Reword line 43 to say the strict check covers only apps.forum\_host and other hosts still skip on an empty list.
   Seen on main: test\_conftest\_isolation.py:44 if not providers\_before\_fixture and not apps.is\_installed("apps.forum\_host"): pytest.skip(...); :47 assert providers\_before\_fixture, (...); :43 comment 'Skip only for a host that registers no provider at all.' No committed test feeds the guard an empty list.

3. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py:13`** (low, polish). HOST\_IMPORT comment, failure message and ignore-pins do not match the pattern's real edges. Verified on main: (a) the comment (lines 7-9) says \_\_import\_\_ is covered, but \_\_import\_\_('apps', fromlist=['forum\_host']) and importlib.import\_module('.forum\_host', 'apps') do not match; (b) quoted prose does match, e.g. # see 'apps.py' or a docstring opening with "apps.forum\_host, and the scan then fails as 'package imports host' naming only the file (line 24). Also: the negatives (44-48) kill neither mutant that drops the statement branch's boundary group or the quoted branch's dot; line 10 names only comma imports as unmatched, yet 'import os; import apps.x' and one-line 'if X: from apps.y import z' slip too (pre-commit isort/flake8 cover backend/, CI runs neither).
   Suggested: All regex/pin-level with no ast, so the owner decision holds: narrow the comment to quoted dotted paths and to 'any import not at line start' (or widen the quoted branch to also accept a closing quote after apps); collect path:line per hit with finditer and say a quoted host path counts; add negatives 'from appstore import x' and 'x = "apps"', and pin "# see 'apps.py'" as a known false positive.
   Seen on main: test\_reusability.py:13 second alternative is quote + apps + literal dot; :24 f"package imports host 'apps.\*': {offenders}" lists file names only. Probes: \_\_import\_\_('apps', fromlist=['forum\_host']) no match; "# see 'apps.py'" match; 'import os; import apps.x' no match; dropping the boundary group or the quoted dot still passes all 10 pins.

## Acceptance Criteria

- [ ] Each of its 3 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).
