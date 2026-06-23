---
status: completed
priority: p2
issue_id: "226"
tags: [harness, hooks, maintainability]
dependencies: []
---

# Consolidate the five hardcoded domain-routing tables into one source of truth

## Problem

The domain→rules/agents routing logic is duplicated in five places. Adding or
renaming a domain requires five synchronized edits, and misses cause silent rot —
this is exactly how the forum rules kept injecting machina-era guidance after the
machina retirement (fixed in the 2026-06-10 harness audit, but the structural
cause remains).

## Findings

- `.claude/hooks/inject-patterns.sh` (~18 independent path→domain if-blocks)
- `.claude/hooks/kimi-review.sh` (case-statement mirror of the same mapping, lines ~47-80)
- `.claude/skills/codify/SKILL.md` (Step 1 domain routing table)
- `.claude/agents/code-review-orchestrator.md` (Phase 1 routing table)
- `.claude/agents/full-review-orchestrator.md` (Phase 1 routing + hardcoded exclusions)
- Discovery source: 2026-06-10 harness audit (Explore agent + manual verification).

## Recommended Action

1. Create `docs/rules/routing.json`: path-glob → `{domains: [...], agents: [...]}`
   entries, plus a shared exclusion list (`existing_implementation/`, `docs/archive/`,
   `**/migrations/` exclusions used by full-review-orchestrator).
2. Add a small reader (`scripts/inject/route_domains.py` or pure-bash glob loop)
   used by both hooks; keep the hooks' fail-open behavior (missing/unparseable
   routing.json → exit 0 silently).
3. Update the codify skill and both orchestrator agents to instruct reading
   `docs/rules/routing.json` instead of carrying inline tables.
4. Update hook tests (`test-inject-patterns.sh`, `test-kimi-review.sh`) to cover
   the new lookup path, including the missing-file fail-open case.

## Technical Details

- Hooks are PreToolUse with 10s/180s timeouts — the lookup must stay cheap
  (single jq/python3 invocation, no network).
- `inject-patterns.sh` domains are additive (multiple matches allowed);
  `kimi-review.sh` is first-match-wins per file. The JSON schema needs an
  ordered list + a `mode` note, or both consumers normalize to additive.
- Note: `.claude/hooks/*` edits are blocked by the auto-mode classifier — user
  must disable Auto Mode for the implementation session.

## Acceptance Criteria

- [x] **(Option A — domains only)** One file (`docs/rules/routing.json`) defines all
      path→**domain** mappings; both hooks (`inject-patterns.sh`, `kimi-review.sh`)
      and the codify Step-1 markdown consumer reference it. **Scope amendment:**
      path→**agent** mappings (Type B: `code-review-orchestrator.md`,
      `full-review-orchestrator.md` + its exclusion list) and finding-domain→agent
      (Type C: codify Step 4) are deferred to **todo 229**, which owns the fleet and
      will extend `routing.json` with an `agents`/`exclusions` block.
- [x] `bash .claude/hooks/test-inject-patterns.sh` and `test-kimi-review.sh` pass.
- [x] Adding a fake domain entry in routing.json is picked up by both hooks with
      no other edits (manual smoke test documented in work log).

## Work Log

### 2026-06-23 - Completed by completing-todos skill (run 2026-06-23-0033)

- Verification: all 3 acceptance criteria passed (Option-A scope). Tests green:
  route_domains 10/10, inject 22/22 (incl. firebase regression), kimi 20/20;
  fake-domain smoke test confirmed both hooks pick up a new routing.json entry.
- Review: code-review-orchestrator → 0 blocking (0 critical/high/medium/low),
  2 INFO — #1 (extra web-spec-ts divergence) recorded in routing.json; #2 (test
  fixture drift) accepted, guarded by subprocess tests.
- Type B (orchestrator agent routing) + Type C (codify Step 4) remain for todo 229.

### 2026-06-23 - Started by completing-todos skill (run 2026-06-23-0033)

- Picked up by automated workflow. Scope confirmed by user: **Option A — domains-only**
  (Type A); agents/orchestrators (Type B) + codify Step 4 (Type C) deferred to todo 229.
  Auto Mode off. Branch `chore/226-consolidate-routing-tables` off `origin/main`.
- **Design correction (within Option A):** the 2026-06-22 "no primary matched → apply
  fallback (single post-pass)" wording is subtly wrong. `inject-patterns.sh` evaluates
  the `backend/*.py` fallback (block 9) *before* the firebase/dart/web/testing blocks
  (10–13), so `backend/apps/garden/firebase_config.py` today gets
  `api,security,database` (fallback) **+** `firebase,security` (stacked) =
  `{api,security,database,firebase}`. A post-pass model would drop `api,database`.
  Verified 6 real backend `*.py` firebase files exist (garden/firebase_config.py,
  users/firebase_auth_views.py, garden/services/firebase_*.py, …). **Fix:** model rules
  as an *ordered* list where `fallback` rules fire only if the domain set is empty
  *at their position* — reproduces inject exactly. Advisor independently re-traced
  and confirmed. Added a regression test (`firebase_config.py` ⇒ both `database` +
  `firebase`) that discriminates the ordered model from the buggy post-pass.
- **Blessed reconciliations** (two diverged tables → one): forum gains `security`
  (matches kimi); `*/api/*.py` ⇒ `api,security` explicit (matches kimi; inject side-effect:
  `backend/apps/*/api/*non-view*.py` loses `database` vs old fallback); `*.dart` any path
  (matches inject); `backend/*.py` fallback ⇒ `api,security,database` (drops kimi's
  `+caching`); blog ⇒ `wagtail,api,security` (codify gains `api`+`security`).
  kimi normalized first-match-wins → additive; for backend-firebase files kimi now
  gains `firebase` and loses `caching`. kimi gains a `python3` dependency (guarded,
  fail-open to unscoped review).

**Implemented (Type A only):**

- New `docs/rules/routing.json` (ordered `rules`; `additive`/`fallback` modes;
  load-bearing-order comment) — single source of truth.
- New `scripts/inject/route_domains.py` — the one shared matcher (stdin paths →
  comma-joined deduped domains; fail-open on missing/unparseable routing).
- New `scripts/inject/test_route_domains.py` — 10 unit + subprocess tests
  (ordered firebase stacking, fallback suppression, per-path union, fail-open).
- `inject-patterns.sh`: ~57 lines of if-blocks → one guarded matcher call.
- `kimi-review.sh`: `add_pattern` fn + per-file `case` loop → one guarded matcher
  call (+ added `PROJECT_ROOT`).
- `test-inject-patterns.sh`: added the firebase ordered-fallback regression
  (database **and** firebase must both appear).
- `test-kimi-review.sh`: fixed a **pre-existing latent test bug** surfaced by this
  run — `SKIP_KIMI_REVIEW=1 echo … | bash "$HOOK"` bound the env var to `echo`, not
  the hook; only passed on a clean tree (exits at the no-staged-files gate). Proven
  pre-existing: `git show HEAD:.claude/hooks/kimi-review.sh` fails identically with
  anything staged. Fixed to `echo … | SKIP_KIMI_REVIEW=1 bash "$HOOK"`.
- `codify/SKILL.md` Step 1: divergent inline table → `git diff … --name-only |
  python3 scripts/inject/route_domains.py` (codify now uses the same matcher).
- NOT touched (deferred to 229): both orchestrators, codify Step 4, exclusions.

**Verification (Acceptance Criteria):**

- AC2 — `python3 scripts/inject/test_route_domains.py` → `Ran 10 tests … OK`;
  `bash .claude/hooks/test-inject-patterns.sh` → `Results: 22 passed, 0 failed`
  (incl. both firebase regression checks); `bash .claude/hooks/test-kimi-review.sh`
  → `Results: 20 passed, 0 failed`.
- AC1/AC3 — matcher spot-checks match the pre-change hooks exactly, e.g.
  `firebase_config.py` → `api,security,database,firebase`. Fake-domain smoke test:
  added one `*.smoketestext` rule to routing.json → `inject-patterns.sh` emitted
  `RULES — smoketest` and `kimi-review.sh`'s matcher returned `smoketest` with **no
  other edits**; routing.json restored byte-identically (no residue, valid JSON).

**Code review (code-review-orchestrator):** 0 critical / 0 high / 0 medium / 0 low;
2 INFO (doc-only). Reviewer independently audited injection-safety (hostile
`file_path` like `$(touch …)`, backticks, `;rm -rf /` → rc 0, no execution, valid
JSON out), fail-open (missing python3 / corrupt JSON / non-dict JSON all → empty +
rc 0), and behavior-preservation (~45 paths through old inject/kimi/codify tables
vs new matcher; all divergences are ordering-only or blessed).

- INFO #1 (addressed): one more divergence — web non-`.tsx` test files
  (`web/src/App.spec.ts`) now resolve to `testing` only, not `typescript,testing`.
  Matches old inject exactly; fail-safe (drops a checklist hint, never blocks).
  **Recorded** as a blessed reconciliation in `routing.json`'s comment (not left
  silent). Verified: `web/src/App.spec.ts` → `testing`.
- INFO #2 (accepted): `test_route_domains.py`'s inline `RULES` fixture is a
  hand-copy of routing.json that could drift. Mitigated by the two subprocess tests
  that drive the REAL routing.json end-to-end (firebase regression + union) — those
  are the drift guard. Intentional unit/integration split; left as-is.

### 2026-06-22 - Re-scoped during sweep run 2026-06-22-0205; DEFERRED again (Type-A design ready)

Read all five consumers this session. **The scope is bigger than the 2026-06-21
note captured** — consolidation spans THREE mapping types across six tables, not
just the two hooks:

- **Type A — path → rule-domains** (picks `docs/rules/<domain>.md`):
  `inject-patterns.sh`, `kimi-review.sh`, AND `codify/SKILL.md` Step 1. codify
  diverges *further* than the two hooks: `blog → wagtail,api` (NO security),
  `backend other .py → security` only, and no forum rule at all.
- **Type B — path → review-agents**: `code-review-orchestrator.md` (Phase 1) and
  `full-review-orchestrator.md` (562 lines; primary/secondary precedence,
  missing-root reviewer-skipping, the shared exclusion list). **This overlaps
  todo 229** ("rationalize the 17-agent fleet"), which *depends on* 226.
- **Type C — finding-domain → agent**: `codify/SKILL.md` Step 4.

**Decision (user, this session):** DEFER. Recommended path when resumed is
**Option A — domains-only now, agents to 229**. That fixes the actual hook-rot
cause (Type A) and leaves Type B for 229, which owns the fleet and will extend
`routing.json` with agent mappings as it decides which agents survive.
**Option A requires amending Acceptance Criterion 1** to scope it to domains
(note that 229 adds the agent mappings) — do not silently narrow it.

**Type-A reconciliation design (DONE — ready to implement):**

- Schema: ordered `rules` list, each `{globs, domains, tier: "primary"|"fallback"}`,
  plus a shared `exclusions` list. One matcher in `scripts/inject/route_domains.py`:
  collect domains from ALL matching `primary` rules (additive, deduped,
  order-preserving); if NO primary matched, apply matching `fallback` rules. Both
  hooks call it.
- This normalizes `kimi-review.sh` from first-match-wins → additive (strictly more
  thorough for the commit gate). Verified: no kimi test asserts routing, so none
  break; every existing `test-inject-patterns.sh` case still passes under this
  model (traced by hand).
- `fallback` tier = `backend/*.py` and `*.ts`/`*.tsx` (disjoint globs, so the two
  old "only-if-empty" checks collapse into one fallback pass).
- Canonical choices for the divergences: forum → `forum,wagtail,security`
  (+security); `*/api/*.py` → `api,security` (explicit rule); `*.dart` → `flutter`
  (any path, not just `plant_community_mobile/`); `backend/*.py` fallback →
  `api,security,database` (drop kimi's `+caching`); blog → `wagtail,api,security`
  (codify gains security — a behavior change to bless in tests, not silent).
- **Verify before writing:** `grep` whether any real backend `.py` matches
  `*firebase*` but no tier-1 rule (the firebase edge case where the normalized
  matcher resolves differently than inject's two-point emptiness check). If none
  exists, it's moot; if one does, document the resolution.
- Keep `INJECT_PATTERNS_DISABLE=1` / `SKIP_KIMI_REVIEW=1` kill switches active
  while editing the live hooks. Gate on `test-inject-patterns.sh` +
  `test-kimi-review.sh` + the fake-domain smoke test.

(File was briefly flipped to `in_progress` during scoping, then reverted to
`pending` on the defer decision — no implementation was written.)

### 2026-06-21 - Scoped during a sweep; DEFERRED to a focused session (head-start findings)

Read both hooks during run 2026-06-21-1412. Key discovery: this is a
**reconciliation of two DIVERGED tables**, not a mechanical extraction — the
divergence is the rot, so consolidation requires deciding the canonical mapping
for each difference. User chose to defer (too risky to rush at a sweep tail; one
fires on every Edit/Write, one gates every commit). Differences found
(`inject-patterns.sh` vs `kimi-review.sh`):

- forum dirs → inject: `forum,wagtail`; kimi: `forum,wagtail,security` (+security).
- `*/api/*.py` → inject: no rule; kimi: `api,security`.
- `*.dart` → inject: any `*.dart` → flutter; kimi: only `plant_community_mobile/*.dart`.
- backend `*.py` fallback → inject: `api,security,database`; kimi: `+caching`.
- match mode → inject: additive if-blocks + TWO "only-if-DOMAINS-empty" fallbacks
  (`backend/*.py`, then `*.ts/*.tsx → typescript`); kimi: `case` (first-match-wins)
  for the dir/role block + an additive `case` for the testing classification.

Implications for the design: the JSON schema must carry an ordered list + a per-
consumer `mode` (additive vs first-match) OR both consumers normalize to additive
(a behavior change the hook tests would need to bless). The two "only-if-empty"
fallbacks in inject must be modeled as a lower-priority tier, not a plain entry.
Markdown consumers to update: `.claude/skills/codify/SKILL.md`,
`.claude/agents/code-review-orchestrator.md`,
`.claude/agents/full-review-orchestrator.md` (+ its exclusion list). Gate on
`test-inject-patterns.sh` + `test-kimi-review.sh`; use the `INJECT_PATTERNS_DISABLE=1`
kill switch while editing the live hook. **229 depends on this — defer it too.**

### 2026-06-10 - Created

- Filed from harness audit session (finding #2 of the environment audit).
