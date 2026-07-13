---
status: in_progress
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
- [ ] Soft-fail observation window completed: the gate tripped only on genuine
      at/above-threshold findings (or there were none) across ≥2 PRs.
      **Deferred — requires real PRs merging over time; not achievable in a
      single local session. See Work Log.**
- [ ] Gate made blocking and "Claude Code Security Review" added to
      branch-protection required checks.
      **Deferred — a GitHub repo-settings change (branch protection),
      hard-to-reverse and affecting shared state; also gated on the
      observation window above. See Work Log.**
- [ ] Fork-PR semantics re-confirmed: a skipped-scan job still concludes
      `success` (gate step skipped, not failed).
      **Deferred — logically guaranteed by construction (identical `if:`
      guard as the pre-existing steps) and actionlint-confirmed, but not
      empirically observed on a real fork PR. See Work Log.**

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

## Notes

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
