---
status: pending
priority: p3
issue_id: "711"
tags: [backend, dependencies, dependabot, upgrade, ai]
dependencies: ["708"]
triage: blocked-prod
triaged: 2026-11-17
blocked_on: "Todo 708 (requirements.in + pip-compile) must land first; the last AC needs the owner to make a real production AI call per enabled feature."
owner_decision: "Owner: wait for todo 708 (requirements.in + lock) to land first (2026-11-17)"
---

# Backend majors, wave 2: openai 3, any-llm-sdk 1.x, mypy 2

## Problem

The OpenAI SDK, the any-llm SDK and mypy are each a major behind. The two AI
SDKs are tied together through wagtail-ai, so they cannot be bumped one at a
time the way Dependabot will propose them.

## Findings

Source: `pip list --outdated` and `pip show` in `backend/venv`, 2026-11-15.

| Package | Pinned | Latest |
|---|---|---|
| openai | 2.34.0 | 3.51.0 |
| any-llm-sdk | 0.20.3 | 1.50.0 |
| llm | 0.31.1 | 0.37.2 |
| anthropic | 2.3.0 | 2.8.0 |
| mypy | 1.20.2 | 2.4.1 |

- Dependency chain: `wagtail-ai` 3.1.1 requires `django-ai-core` and `llm`;
  `django-ai-core` 0.1.5 requires `any-llm-sdk`; `any-llm-sdk` and `llm` both
  require `openai`. The version ranges were not read: whether openai 3 or
  any-llm 1.x is installable today is not known.
- Hardcoded model names in backend code (grep, tests excluded): `gpt-4o-mini`
  x5, `text-embedding-3-small` x2, `claude-sonnet-5-5` x2,
  `gpt-4o-vision-preview` x1. The last looks like a retired preview name;
  whether its code path is live was not checked.
- mypy gates every backend app (`[tool.mypy] files` in
  `backend/pyproject.toml`); `django-stubs` 6.0.3 -> 6.1.2 moves with it.

## Recommended Action

1. After todo 708, ask the resolver: add `openai>=3` to `requirements.in` and
   compile. If it fails, the blocker is named in the error; decline the
   openai PR with `@dependabot ignore this major version` and record which
   parent caps it.
2. If it resolves, bump `openai`, `any-llm-sdk`, `llm`, `django-ai-core` and
   `wagtail-ai` together in one PR. Read the openai 3 migration notes for the
   calls this code makes (chat completions, embeddings).
3. Find the `gpt-4o-vision-preview` reference; delete the code if dead,
   otherwise replace the model name.
4. mypy 2 with django-stubs in its own PR: fix or annotate what it newly
   reports, no blanket ignores.

## Technical Details

- `backend/requirements.in` / `requirements.txt` (after todo 708)
- `backend/pyproject.toml` (`[tool.mypy]`)
- `backend/apps/forum_host/` (spam backend, compose assist, RAG),
  `backend/apps/blog/` (wagtail-ai)
- `backend/docs/patterns/domain/blog.md`

## Acceptance Criteria

- [ ] openai and any-llm-sdk are each bumped in a merged PR, or declined on
      their Dependabot PRs with the capping parent named in the Work Log.
- [ ] `grep -rn "gpt-4o-vision-preview" backend --include=*.py` prints nothing.
- [ ] mypy 2 is bumped with a clean run over the gated file list, or declined
      with the reason recorded.
- [ ] Full backend suite passes repo-wide on each PR.
- [ ] The first Dependabot pip PR after todo 708 merges installs without a
      resolver conflict (record the PR number and date here; moved from 708
      on 2026-11-17).
- [ ] The first Railway deploy after todo 708 merges builds the backend Docker
      image (record the deployment id and date here; moved from 708 on
      2026-11-18).
- [ ] After an AI SDK bump: one real call per enabled feature succeeds in
      production (date and observation recorded here).

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit. Wave 2 of the backend majors.

### 2026-11-15 - Four Dependabot holds point here (#1326)

- `.github/dependabot.yml` ignores `django-ai-core` >=0.1.6 (needs
  any-llm-sdk >=1.23), `llm` >=0.32 (needs sqlite-utils 4; >=0.33 needs
  openai >3) and `sqlite-migrate` >=0.2 (needs sqlite-utils 4). Remove
  those entries in the PR that takes the AI SDK majors.
- django-stubs 6.0.3 -> 6.1.2 landed in #1333 with four type fixes. mypy
  itself is still 1.x.
