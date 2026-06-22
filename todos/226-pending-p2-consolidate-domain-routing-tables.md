---
status: pending
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

- [ ] One file defines all path→domain/agent mappings; both hooks and all three
      markdown consumers reference it.
- [ ] `bash .claude/hooks/test-inject-patterns.sh` and `test-kimi-review.sh` pass.
- [ ] Adding a fake domain entry in routing.json is picked up by both hooks with
      no other edits (manual smoke test documented in work log).

## Work Log

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
