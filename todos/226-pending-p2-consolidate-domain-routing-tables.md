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
