---
status: pending
priority: p3
issue_id: "721"
tags: [backend, dependencies, owner]
dependencies: ["711"]
triage: blocked-prod
triaged: 2026-11-22
blocked_on: "The owner makes one real prod call per enabled AI feature, and the next Dependabot pip PR after #1397 runs its install job"
owner_decision: "Owner delegated the live check to a Claude session driving Chrome (2026-11-22); run by hand outside the sweep"
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

### 2026-11-22 - AC1 observation (Claude, owner-delegated 2026-11-22)

- The first Dependabot pip PR after #1397 (merged 2026-11-22T01:50Z) is **#1401** (opened
  01:57Z, backend-minor-patch group, 7 updates). Its "Install dependencies and run Django
  checks" job **failed**, but not on a resolver conflict. It failed the pip-compile drift
  check: Dependabot's `requirements.txt` drops extras markers (`willow[heif]`→`willow`,
  `httpx[http2]`→`httpx`, `pyjwt[crypto]`, `uvicorn[standard]`, `whitenoise[brotli]`,
  `google-api-core[grpc]`, `coverage[toml]`). The backend test suite passed on it. The owner
  decides whether this counts as "installs without a resolver conflict". AC2 (prod AI calls)
  was not run.
