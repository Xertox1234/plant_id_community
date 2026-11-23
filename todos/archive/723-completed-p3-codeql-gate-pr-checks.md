---
status: completed
priority: p3
issue_id: "723"
tags: [ci, security, owner]
dependencies: ["718"]
triage: ready
triaged: 2026-11-22
owner_decision: "Owner OK: a worker may open throwaway PRs against main, incl. one with a deliberate critical CodeQL alert and auto-merge armed; each is closed and its branch deleted (owner 2026-11-22)"
---

# CodeQL merge gate: prove it with real PRs (from todo 718)

## Problem

Branch-protection ruleset 9138781 already has a `code_scanning` rule (CodeQL, security_alerts_threshold `critical`; read 2026-11-21). These checks prove it blocks what it should and nothing else.

## Findings

- Requiring the Analyze checks directly deadlocked Dependabot PRs in 2026-09 (docs/LEARNINGS.md); the ruleset rule does not.
- Todo 718 renames `RATELIMIT_CLIENT_IP_META_KEY` to stop a `py/clear-text-logging-sensitive-data` false positive.

## Recommended Action

Open a throwaway PR with a known critical alert and confirm it cannot merge; cite a Dart-only and a docs-only PR merged under the rule; open a PR that logs through `log_safe_ip` after 718 merges.

## Technical Details

- Ruleset: `gh api repos/<owner>/<repo>/rulesets/9138781`.
- Close and delete the throwaway PR's branch afterwards.

## Acceptance Criteria

- [x] A test PR that adds a known CodeQL alert at or above the threshold cannot be merged, and
      auto-merge does not merge it (record the PR number; moved from 718 on 2026-11-21).
- [x] A Dart-only PR and a docs-only PR can still merge without waiting on a CodeQL result that
      never arrives (record both PR numbers; moved from 718 on 2026-11-21).
- [x] A PR that logs a client IP through `log_safe_ip` is not blocked by
      `py/clear-text-logging-sensitive-data` (moved from 718 on 2026-11-21).

## Work Log

### 2026-11-21 - Filed

- Filed from sweep run 2026-11-20-2202 on the owner's decision of 2026-11-21: these criteria were
  re-pointed here because they can only be checked after the parent's PR merges, or need the owner.

### 2026-11-22 - Implemented by the todo sweep (run 2026-11-22-1957)

- Read ruleset 9138781 from the public API: `enforcement: active`, `code_scanning` CodeQL with
  `security_alerts_threshold: critical`, last updated 2026-09-06, so it applied to every PR cited below.
- Dart-only PR #1390 (three `plant_community_mobile/` `.dart` files) merged 2026-11-20 and docs-only PR
  #1405 (one todo `.md`) merged 2026-11-22. On both, the `CodeQL` results check and the three
  `Analyze (…)` jobs completed `success` within about a minute, so neither waited on a missing result.
- The other two criteria need new throwaway PRs (one with a deliberate critical alert and auto-merge
  armed, one adding a `log_safe_ip(` call). No merged PR since #1396 (todo 718) adds a `log_safe_ip(`
  call. The worker cannot push, run `gh`, arm auto-merge or delete a branch, so both are left open for
  the main session.

### 2026-11-22 - Throwaway PRs opened by the main session (owner OK 2026-11-22)

- **Criterion 1: PR #1411** added `backend/apps/core/codeql_canary.py`, a view that passes a
  query parameter to `subprocess.call(..., shell=True)`. Nothing imports it and no URLconf includes
  it. CodeQL raised alert 170, `py/command-line-injection`, severity **critical**, at
  `backend/apps/core/codeql_canary.py:16` ("New alerts in code changed by this pull request:
  1 critical"). Auto-merge (squash) was armed at 2026-11-22T21:35:15Z. At 21:54:47Z every other
  check had finished `SUCCESS` (backend pytest, Django checks, web, security scans, the three
  Analyze jobs) and only `CodeQL` was `FAILURE`, yet the PR was still `OPEN`,
  `mergeStateStatus: BLOCKED`, auto-merge still enabled. It was closed unmerged (`merged=never`)
  and branch `test/723-codeql-canary-critical` was deleted.
- **Criterion 3: PR #1412** added `backend/apps/core/codeql_canary_log.py`, which logs
  `log_safe_ip(request.META.get("REMOTE_ADDR"))` at warning level. At 2026-11-22T21:55:36Z
  `CodeQL=SUCCESS` and the three Analyze jobs were `SUCCESS`, with 0 code-scanning alerts on the
  PR and `mergeStateStatus: CLEAN`, so `py/clear-text-logging-sensitive-data` did not fire and the
  merge rule did not block it. It was closed unmerged and branch
  `test/723-codeql-canary-log-safe-ip` was deleted.

### 2026-11-23 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 2: `python3 -c 'import json,urllib.request as u A="https://api.github.com/repos/Xertox1234/plant_id_community" g=lambda p: json.load(u.urlopen(A+p)) r=g("/rulesets/9138781"); print("ruleset", r["id"], r["enforcement"], "updated_at", r["updated_at"], [x for x in r["rules"] if x["type"]=="code_scanning"]) for n in (1390,1405):   p=g("/pulls/%d"%n); fs=[f["filename"] for f in g("/pulls/%d/files"%n)]   cr=g("/commits/%s/check-runs?per_page=100"%p["head"]["sha"])["check_runs"]   print("PR", n, "merged", p["merged"], p["merged_at"], "files", fs)   print("  codeql checks", [(c["name"],c["status"],c["conclusion"],c["completed_at"]) for c in cr if c["name"]=="CodeQL" or c["name"].startswith("Analyze")])'` — evidence `.sweep-evidence/g5/723-ac1.txt` (not committed), last lines:

  ```text
  ruleset 9138781 active updated_at 2026-09-06T00:47:20.503Z [{'type': 'code_scanning', 'parameters': {'code_scanning_tools': [{'tool': 'CodeQL', 'security_alerts_threshold': 'critical', 'alerts_threshold': 'none'}]}}]
  PR 1390 merged True 2026-11-20T01:26:42Z files ['plant_community_mobile/lib/features/forum/widgets/home/forum_season_card.dart', 'plant_community_mobile/test/features/forum/forum_home_social_test.dart', 'plant_community_mobile/test/features/forum/widgets/home/forum_season_card_test.dart']
    codeql checks [('CodeQL', 'completed', 'success', '2026-11-20T01:07:08Z'), ('Analyze (actions)', 'completed', 'success', '2026-11-20T01:07:09Z'), ('Analyze (javascript-typescript)', 'completed', 'success', '2026-11-20T01:07:43Z'), ('Analyze (python)', 'completed', 'success', '2026-11-20T01:07:43Z')]
  PR 1405 merged True 2026-11-22T08:24:34Z files ['todos/731-pending-p2-blog-comment-authors-expose-legal-names.md']
    codeql checks [('CodeQL', 'completed', 'success', '2026-11-22T08:06:39Z'), ('Analyze (python)', 'completed', 'success', '2026-11-22T08:07:10Z'), ('Analyze (javascript-typescript)', 'completed', 'success', '2026-11-22T08:07:04Z'), ('Analyze (actions)', 'completed', 'success', '2026-11-22T08:06:46Z')]
  ```

### 2026-11-23 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-22-1957)

- AC 1: confirmed by the owner on 2026-11-22: "Owner OK 2026-11-22 to open throwaway PRs ("Yes, I open them now"); observed: #1411 critical alert 170, auto-merge armed, still BLOCKED with every other check green, closed unmerged" (`state.py confirm`; no command or evidence)
- AC 3: confirmed by the owner on 2026-11-22: "Owner OK 2026-11-22 to open throwaway PRs ("Yes, I open them now"); observed: #1412 log_safe_ip canary, CodeQL success, 0 alerts, CLEAN, closed unmerged" (`state.py confirm`; no command or evidence)

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-23 - Review round 1: non-blocking findings

- **Declined: the "AC 2" entry cites evidence file `723-ac1.txt` (low).** The engine numbers
  evidence files from 0, so `723-ac1.txt` is the second criterion's file. The quoted output is the
  right one (PRs #1390 and #1405), and the file is not committed. Renaming a recorded evidence
  path after the fact would falsify the record, so it stays as run.

### 2026-11-23 - Review round 2: non-blocking findings

- **Recorded, not fixed: the AC 3 canary does not exercise the renamed setting (low).** PR #1412
  logs `request.META["REMOTE_ADDR"]` through `log_safe_ip`. It never reads the renamed
  `RATELIMIT_CLIENT_IP_HEADER` flow that raised the original false positive, and that query sits
  below the gate's critical threshold, so #1412 would have passed without todo 718's rename. What
  the canary does show is the criterion as written: a `log_safe_ip` PR is not blocked. Read on
  2026-11-23 through the code-scanning API: `main` has 0 open CodeQL alerts; on
  `backend/apps/core/ratelimit.py` the two `py/clear-text-logging-sensitive-data` alerts are #106
  (fixed 2026-09-06) and #126 (dismissed 2026-09-06). Neither changed after #1396, so the rename's
  own effect on that query was not observed here.
