---
status: completed
priority: p4
issue_id: "249"
tags: [security, ci, github-actions, review]
dependencies: ["239"]
---

# Add a fail-on-severity gate to the PR Security Review (true merge-block)

## Problem

Todo 239 decided to keep `.github/workflows/security-review.yml` **advisory**,
because the upstream `anthropics/claude-code-security-review` action **never exits
non-zero on findings** — it counts `findings_count`, posts PR comments, and exits
`success` regardless. Consequence: promoting the check to a *required* branch-
protection check would only enforce "the job ran", not block a merge on an actual
security finding. The only way to get a real merge-gate is a **workflow change**
that fails the job when findings cross a severity threshold. This todo captures
that future option so it isn't lost.

## Findings

- Upstream `action.yml` (pinned commit `0c6a49f1…` in our workflow) has no
  `exit 1` on findings; the only non-zero exit is a missing API key, which our
  `check-key` step already guards. Verified during todo 239.
- The action exposes two outputs usable by a downstream gate step:
  - `findings-count` — total number of findings (post false-positive filtering).
  - `results-file` — path to `claudecode-results.json`; the action also copies
    `findings.json` and `claudecode-results.json` to `${{ github.workspace }}`.
- Observed signal to date (todo 239): 0 findings / 0 false positives across
  ~17 real PRs since #398. No demonstrated catch yet — so there is currently no
  evidence-based pressure to gate. This todo is appetite-driven, not bug-driven.

## Proposed Solutions

### Option 1: Severity-filtered gate (Recommended)

- **Implementation:** add a step after "Run Claude Code security review" that
  reads `${{ github.workspace }}/claudecode-results.json`, counts findings whose
  severity is at/above a chosen threshold (e.g. `HIGH`/`CRITICAL`), and
  `exit 1` if any exist. Guard it with
  `if: steps.check-key.outputs.enabled == 'true'` so fork PRs (scan skipped)
  are never blocked. Then promote to a required check in branch protection.
- **Pros:** real merge-block on high-severity findings; low-severity findings
  stay advisory (comments only); fork-safe.
- **Cons:** only as trustworthy as the false-positive rate — a noisy gate that
  blocks merges on bad findings is worse than no gate. Needs FP tuning first.
- **Effort:** ~1–2 hours (step + a dry-run period before flipping to required).
- **Risk:** medium — a false positive at/above threshold blocks a legitimate
  merge until dismissed. Mitigate with a tuning/observation window.

### Option 2: Count-based gate (any finding fails)

- **Implementation:** `if: steps.review.outputs.findings-count != '0'` → fail.
- **Pros:** trivial.
- **Cons:** too aggressive — every finding, including low-impact/FP-prone ones,
  blocks the merge. Rejected unless the FP rate is proven ~0 over a long window.

### Option 3: Do nothing (status quo)

- Keep advisory indefinitely; rely on the `kimi-review` commit gate +
  `code-review-orchestrator` + CodeQL (`github-advanced-security[bot]`) for
  actual blocking signal. Valid until a real finding shows the advisory comment
  was missed.

## Recommended Action

1. Tune first: set `false-positive-filtering-instructions` (and, if useful,
   `custom-security-scan-instructions`) on the action step and observe a few PRs.
2. Add the severity-filtered gate step (Option 1), guarded on
   `enabled == 'true'`, parsing `claudecode-results.json` for severity.
3. Run it **non-blocking first** (e.g. `continue-on-error: true` or log-only) for
   a 2–3 PR window to confirm it only trips on real high-severity findings.
4. Remove the soft-fail, then promote "Claude Code Security Review" to a required
   status check in branch protection.
5. Re-confirm fork-PR semantics: the gate step must be skipped (not failed) when
   the scan is skipped, so a fork PR's job still concludes `success`.

## Technical Details

- Workflow: `.github/workflows/security-review.yml`. Today: `check-key` →
  `Checkout PR head` (if enabled) → `Run Claude Code security review` (if enabled).
  The gate step inserts after the review step, same `if` guard.
- Results JSON shape: `{"findings": [{"severity": "...", ...}], ...}` (confirm
  exact severity field/enum from a run artifact — the workflow already uploads
  `security-review-results` for 7 days when `upload-results` is on, or read the
  copied `${{ github.workspace }}/claudecode-results.json`).
- Promotion itself is a repo-settings change (branch protection), mirroring how
  the Cloudflare Workers check is treated (project_cloudflare_workers_check).
- Parent decision + full evidence: `todos/archive/239-completed-p3-promote-security-review-required-check.md`.

## Acceptance Criteria

- [x] Gate step added, guarded on `enabled == 'true'`, parsing severity from the
      results JSON (not just a raw count).
- [x] Soft-fail observation window completed: the gate tripped only on genuine
      at/above-threshold findings (or there were none) across ≥2 PRs.
      **Met 2026-07-13 — the gate ran clean on ≥2 PRs (#455/#456/#457, all 0
      findings, never tripped); satisfies the criterion's own "or there were
      none across ≥2 PRs" wording. The true-trip path (HIGH → exit 1) stays
      unobserved in prod (no HIGH finding has ever occurred) but was verified
      locally against synthetic HIGH fixtures during the #454 groundwork —
      acceptable for an advisory observer. See Work Log.**
- [x] Gate made blocking and "Claude Code Security Review" added to
      branch-protection required checks.
      **Done 2026-07-14 — user reversed the 2026-07-13 advisory decision
      with full knowledge of the unobserved-FP-rate tradeoff. PR #459
      dropped `continue-on-error` and fixed a fail-closed consistency gap;
      "Claude Code Security Review" added to branch-protection required
      checks via the narrow contexts endpoint, verified `enforce_admins`
      and the other 5 existing required checks were untouched. See Work
      Log.**
- [x] Fork-PR semantics re-confirmed: a skipped-scan job still concludes
      `success` (gate step skipped, not failed).
      **Satisfied by construction, 2026-07-14 — not empirically observed
      (no real fork PR exists to test against; same limitation todo 239's
      own analogous AC accepted). The blocking gate step's `if:` guard is
      unchanged by this promotion (`steps.check-key.outputs.enabled ==
      'true'`, identical to the pre-existing "Run Claude Code security
      review" step it already relies on): when the API-key secret is
      absent (fork PR), `enabled` is `false`, both steps are skipped
      outright, and a skipped step cannot fail a job — so the job still
      concludes `success` regardless of severity-gate promotion. See Work
      Log.**

## Work Log

### 2026-06-27 - Created

- Filed from todo 239's "documented future option". 239 kept the check advisory
  because the action can't block on findings; this todo tracks the workflow
  change that would make a real merge-gate possible, if/when there's appetite.

### 2026-07-13 - Started by completing-todos skill (run 2026-07-13-0237)

- Picked up by automated workflow.

### 2026-07-13 - Groundwork laid, then skipped by completing-todos skill (run 2026-07-13-0237)

- Read the acceptance criteria before touching anything: only #1 (add the
  gate step) is achievable in a single local session. #2 needs a real ≥2-PR
  observation window over time, #3 needs a GitHub branch-protection
  settings change (shared-infra, hard-to-reverse, outside this session's
  scope per my own operating constraints on CI/CD changes), #4 needs a real
  fork-PR run to observe. Presented this to the user before writing any
  code; user chose "lay groundwork only": implement #1 in non-blocking
  form, verify locally, leave #2-4 explicitly deferred as a group.
- Primary-source research before implementing, instead of guessing at the
  results-JSON shape the todo's own Technical Details flagged as unconfirmed:
  read `anthropics/claude-code-security-review`'s source at the exact pinned
  SHA (`0c6a49f1fa56a1d472575da86a94dbc1edb78eda`) already vendored into our
  workflow (via `gh api repos/.../contents/<path>?ref=<sha>`).
  - `action.yml`'s "Run ClaudeCode scan" step:
    `python -u claudecode/github_action_audit.py > claudecode/claudecode-results.json 2>claudecode/claudecode-error.log || CLAUDECODE_EXIT_CODE=$?`
    — confirms the todo's premise: the script's own exit code is captured
    into a variable and only ever surfaced as `::warning::`, never
    re-raised. "The action never exits non-zero on findings" (239/249's
    stated premise) holds.
  - `claudecode/github_action_audit.py:636-637` — the script *does*
    internally compute `high_severity_count` and would
    `sys.exit(EXIT_GENERAL_ERROR)` on a HIGH finding, but per the point
    above, that exit code is exactly the one being discarded upstream.
  - `action.yml` also confirmed (unconditionally, "regardless of the
    outcome"): `cp claudecode/claudecode-results.json ${{ github.workspace }}/claudecode-results.json`
    — the Technical Details' `${{ github.workspace }}/claudecode-results.json`
    fallback guess is correct, and is what the new step reads. The
    `results-file` *output* itself is a footgun — it's hardcoded to the
    literal string `claudecode/claudecode-results.json` near the top of the
    step and never updated, so it's relative to the action's own working
    directory, not a downstream step's `github.workspace` cwd. Deliberately
    not used.
  - `claudecode/prompts.py`'s REQUIRED OUTPUT FORMAT + SEVERITY GUIDELINES —
    confirms the severity enum is `HIGH|MEDIUM|LOW` only; **no `CRITICAL`
    value is ever emitted**, correcting the todo's own Option 1 text
    ("HIGH/CRITICAL"). Matched `CRITICAL` defensively anyway in the new
    step (costs nothing, future-proofs if upstream's prompt changes).
- Implemented: added an "Evaluate severity gate (soft-fail observation, todo
  249)" step to `.github/workflows/security-review.yml`, immediately after
  "Run Claude Code security review", guarded on the same
  `steps.check-key.outputs.enabled == 'true'` condition as the existing
  steps, with `continue-on-error: true` (Recommended Action step 3's
  soft-fail). Reads `${{ github.workspace }}/claudecode-results.json`,
  counts findings whose `severity` (case-insensitive) is `HIGH` or
  `CRITICAL` via jq, `exit 1` with a `::error::` annotation if any exist,
  else `exit 0`. Handles a missing results file and an `{"error": ...}`
  response shape (no `findings` key) gracefully — both `exit 0` with a
  `::warning::`, never a crash.
- Verification:
  - Non-vacuous logic check: extracted the exact jq filter + shell logic
    into a standalone script (`gate.sh`), ran it against 6 synthetic
    fixtures built to match the confirmed real schema: zero findings,
    medium-only, one HIGH mixed with one low, an `{"error": ...}` shape, a
    lowercase `"high"` value, and a missing file. All 6 produced the
    expected result — 0/no-trip for the first two and the error/missing
    cases, 1/trip for the two HIGH-containing fixtures (mixed-severity and
    lowercase) — full output captured in this session's tool transcript.
  - Actions-syntax validation: `actionlint .github/workflows/security-review.yml`
    → exit code 0, zero findings. actionlint type-checks GitHub Actions
    expressions and shellchecks embedded `run:` blocks — stronger than a
    bare YAML parse.
  - Negative control on the linter itself: copied the file, replaced
    `steps.check-key.outputs.enabled` with a bogus step reference in all
    three guarded steps, reran actionlint → correctly failed with 3
    findings, one pointing at the new step's own `if:` line (line 86) —
    confirms the earlier clean pass was a genuine check of this file
    including the new step, not a no-op.
- Acceptance criteria: only #1 flipped, backed by the verification above.
  #2-4 are explicitly NOT flipped — see each criterion's inline note above
  for the specific reason. Not a `--force-complete`; mirrors todo 265's
  precedent of surfacing an honest partial state rather than forcing a box.
- On criterion #4 specifically: the new step reuses the *identical*
  `if: steps.check-key.outputs.enabled == 'true'` guard as the pre-existing
  "Run Claude Code security review" step, whose fork-skip behavior is
  already this workflow's documented, currently-relied-upon default. A step
  gated by a falsy `if:` is unconditionally "skipped" and can never fail a
  job regardless of `continue-on-error` — so there is no code path by which
  a fork PR (where `enabled` is `false`) can reach this step's `exit 1`.
  Logically airtight by construction, and actionlint-confirmed (its
  expression type-checker validated the guard resolves to a real, existing
  step output) — but that's an argument from construction, not an empirical
  observation of a real fork-PR run, which is what "re-confirmed" asks for.
  Left unchecked per the user's "defer 2-4 as a group" framing, flagged
  here as the cheapest of the three to close later (one observed fork-PR
  run, no code change needed).
- Left in `in_progress` state (filename unchanged) per the skill's
  skip-todo protocol; NOT moved to `todos/archive/`.

### 2026-07-13 - Observation window evidenced; advisory decision (keep soft-fail)

- Resumed the todo and pulled live CI evidence instead of guessing at
  whether the observation window (#2) had accrued any data since the
  groundwork merged: `ANTHROPIC_API_KEY` is confirmed set (the review
  genuinely runs, not self-skipping), and the "Evaluate severity gate" step
  has now executed on 3 distinct downstream PRs, all clean:
  - #455 `docs/codify-todo-sweep` — run `29273550920` —
    `CLAUDECODE_FINDINGS: 0`, "gate would not have tripped"
  - #456 `security/pillow-12.3.0-cve-bump` — run `29277712678` — `0`, did
    not trip
  - #457 `ci/security-scan-advisory-on-pr` — run `29278109826` — `0`, did
    not trip
  This also confirms in production the one assumption the #454 groundwork
  couldn't verify live: the `${{ github.workspace }}/claudecode-results.json`
  read resolves and parses correctly (`HIGH_COUNT=0` computed from a real
  results file, not the missing-file fallback path).
- Presented two options to the user: keep advisory (close the loop as
  documentation only) vs. make it blocking now (drop `continue-on-error`,
  add fail-closed-on-missing-file behavior, then add "Claude Code Security
  Review" to branch-protection required checks). User chose **keep
  advisory**.
- Reasoning for advisory, and a correction to an analogy I initially reached
  for: PR #457 (merged same day) moved the *sibling* `security-scan.yml`
  workflow to advisory-on-`pull_request` too, and I first read that as
  supporting precedent here. On inspection that analogy is weak and I'm not
  relying on it — #457's actual failure mode was *global CVE contagion*
  (one upstream CVE red-failing every unrelated open PR, regardless of
  whether that PR's diff touched the affected dependency). `security-review`
  is diff-scoped: a HIGH finding is about that PR's own code, so #457's
  failure mode doesn't exist here. The real, sufficient reason to stay
  advisory is independent of #457: the gate has **never fired once** across
  ~20 PRs since #454, so its false-positive rate on a genuine finding is
  completely unobserved. Flipping a never-fired gate to merge-blocking is
  premature regardless of what the sibling workflow did. This matches the
  todo's own pre-existing Notes, which already named the revisit trigger
  ("bump to p3 if a real high-severity finding is ever posted and slips
  through as a mere comment") as the steady state — this session confirms
  that state rather than overriding it.
- No workflow file touched this session — `.github/workflows/security-review.yml`
  is byte-for-byte unchanged; the gate remains `continue-on-error: true`.
  This is a documentation-only update to this todo file.
- Todo fate: left `in_progress` (not archived). Its headline deliverable —
  a true merge-block (criterion #3) — is exactly what's being deliberately
  deferred, so archiving as "done" would misrepresent state. #1/#2 done,
  #4 moot while advisory, #3 a parked future option with a concrete revisit
  trigger.

### 2026-07-14 - Promoted to blocking, branch protection updated, archived (user directive)

- User asked whether making the gate blocking would stop unrelated failure
  emails they'd been getting. Investigated before answering: those emails
  traced to `security-scan.yml` (pip-audit/npm-audit dependency scanning,
  a different workflow) hard-failing every open PR on a new upstream CVE
  regardless of diff relevance — already fixed by PR #457. Confirmed
  `security-review.yml` (this workflow) has never failed a single run in
  its history, so it could not have been the source. After that
  correction, user explicitly instructed: "make it blocking and complete
  this todo" — a direct reversal of the 2026-07-13 advisory decision
  above, made with full knowledge of the tradeoff (a never-fired gate has
  an unobserved false-positive rate). Treated as explicit authorization
  for the full scope of criterion #3 (gate blocking + branch-protection
  required check), not re-litigated.
- Pre-flight sanity check: zero open PRs at the time of the change, and
  zero HIGH/CRITICAL findings across the entire observed run history — so
  nothing was retroactively blocked by the promotion.
- PR #459 (`ci/security-review-blocking-gate-todo-249`, merged 2026-07-14):
  removed `continue-on-error: true` from the severity-gate step. Also
  fixed a fail-closed inconsistency identified during execution planning:
  the missing-results-file path already exited 1, but a results file
  lacking a `findings` key (e.g. an `{"error": ...}` shape from an errored
  scan) fell through `.findings // []` to an empty array and passed
  silently — coherent for a soft-fail observer, incoherent for a blocking
  gate. Added an explicit `jq -e 'has("findings")'` check so both "no
  file" and "file present but unverifiable" fail closed. Renamed the step
  to "Enforce severity gate (blocking, todo 249)" and updated its comment
  block plus the workflow-level header comment, both of which described
  the now-superseded advisory/soft-fail state.
  - Verified: `actionlint` clean (exit 0). Re-extracted the shell gate
    logic to a standalone script and re-ran the 6 synthetic fixtures from
    the original #454 groundwork, with updated expectations for the two
    changed paths — missing file and the `{"error": ...}` shape both now
    exit 1 (previously 0) — all 6 passed.
- Branch-protection change (applied directly via `gh api`, not through a
  PR — GitHub repo settings aren't file-based): added "Claude Code
  Security Review" to `required_status_checks.contexts` via the narrow
  `POST .../protection/required_status_checks/contexts` endpoint (body
  `["Claude Code Security Review"]`), deliberately avoiding a full `PATCH
  .../protection`, which would silently clobber unspecified fields.
  Verified via GET immediately after: all 6 contexts present (5
  pre-existing + the new one), `enforce_admins.enabled` still `true`,
  `required_pull_request_reviews`/`allow_force_pushes`/`allow_deletions`
  all unchanged from their pre-change values.
  - Noted for the record: `enforce_admins: true` means this check is
    unbypassable by anyone, admins included, from the moment it was added.
    The consequence is bounded per-PR (a tripped/false-positive gate
    blocks only that PR's merge, not all of main) and reversible with a
    single protection-settings edit if the false-positive rate turns out
    to be a problem.
- Criterion #3 flipped to done. Criterion #4 resolved "satisfied by
  construction" — the same standard todo 239's own analogous AC accepted,
  since no real fork PR exists this session to empirically test against;
  not claiming empirical proof that doesn't exist.
- Archiving now per "complete this todo" — the 2026-07-13 "keep
  in_progress" call was explicitly contingent on staying advisory; that
  contingency no longer holds now that the headline deliverable (a true
  merge-block) is actually in place.

## Notes

- **2026-07-14 promoted to blocking (supersedes the note below):** gate is
  now blocking and fail-closed (including the `{"error": ...}` shape, not
  just the missing-file case the note below flagged), and "Claude Code
  Security Review" is a required branch-protection check. See the
  2026-07-14 Work Log entry for full detail. The "priority p4,
  appetite-driven" framing below no longer applies — the todo is complete.
- **Priority p4 (deferred, appetite-driven):** there is no demonstrated need —
  0 findings over ~17 real PRs, and three other layers already provide blocking
  signal (kimi-review, code-review-orchestrator, CodeQL). Bump to p3 if a real
  high-severity finding is ever posted and slips through as a mere comment.
- Depends on 239 only for lineage (239 is already complete/archived).
- **2026-07-13 groundwork:** the severity-gate step (Option 1) is now in
  `.github/workflows/security-review.yml`, soft-failing only
  (`continue-on-error: true`). Starting the observation window (criterion
  #2) needs no further code — just open ≥2 real PRs and watch the
  "Evaluate severity gate" step's log/annotations, then revisit criteria
  #3-4.
- **2026-07-13 evidenced + advisory decision:** criterion #2 is now met
  (3 clean PRs observed — see Work Log). Criterion #3 (blocking promotion)
  is deliberately still open, staying advisory per the revisit trigger
  above (bump to p3 only if a real HIGH finding is ever posted and slips
  through as a mere comment). If #3 is ever pursued, also make the gate
  **fail-closed** on a missing results file — it currently `exit 0`s when
  `claudecode-results.json` is absent, which is correct fail-open behavior
  for an observer but wrong for a blocker (a missing file should not
  silently pass a merge gate).
