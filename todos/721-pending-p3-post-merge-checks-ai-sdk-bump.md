---
status: pending
priority: p3
issue_id: "721"
tags: [backend, dependencies, owner]
dependencies: ["711"]
triage: blocked-prod
triaged: 2026-11-21
blocked_on: "Todo 711 must merge and deploy first; then a Dependabot pip PR and owner-run prod AI calls"
---

# Post-merge checks for the AI SDK bump (todo 711)

## Problem

Todo 711 bumps openai to 3 and any-llm-sdk to 1.x. Two of its criteria can only be checked after that PR merges and deploys.

## Findings

- The first Dependabot pip PR after todo 708 merged (#1378, 2026-11-19) failed the lock-drift check in "Install dependencies and run Django checks". Dependabot edited `requirements.txt` without re-running pip-compile. That is not a resolver conflict, so it did not settle the criterion either way.
- The prod AI features need one real call each after the new SDKs deploy.

## Recommended Action

After 711 merges: watch the next Dependabot pip PR's install job, then make one real call per enabled AI feature in production.

## Technical Details

- Lock files: `backend/requirements.in` → `backend/requirements.txt` via `scripts/compile-requirements.sh`.
- AI features: blog AI content (wagtail-ai / django-ai-core), forum spam LLM backend, and any other enabled flag in `docs/` and CLAUDE.md's env table.

## Acceptance Criteria

- [ ] The first Dependabot pip PR after todo 711 merges installs without a resolver conflict
      (record the PR number and date here; moved from 711 on 2026-11-21).
- [ ] After the 711 deploy: one real call per enabled AI feature succeeds in production (date
      and observation recorded here; moved from 711 on 2026-11-21).

## Work Log

### 2026-11-21 - Filed

- Filed from sweep run 2026-11-20-2202 on the owner's decision of 2026-11-21: these criteria were
  re-pointed here because they can only be checked after the parent's PR merges, or need the owner.
