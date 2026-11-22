---
status: completed
priority: p3
issue_id: "711"
tags: [backend, dependencies, dependabot, upgrade, ai]
dependencies: ["708"]
triage: ready
triaged: 2026-11-20
owner_decision: "Owner: the mypy criterion is met (mypy 2.4.0 in the dev lock); attempt openai 3 and any-llm-sdk 1.x; if they will not resolve, keep 711 open (2026-11-20)"
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

- [x] openai and any-llm-sdk are each bumped in a merged PR, or declined on
      their Dependabot PRs with the capping parent named in the Work Log.
- [x] `grep -rn "gpt-4o-vision-preview" backend --include=*.py` prints nothing.
- [x] mypy 2 is bumped with a clean run over the gated file list, or declined
      with the reason recorded.
- [x] Full backend suite passes repo-wide on each PR.
- [ ] The first Dependabot pip PR after todo 708 merges installs without a
      resolver conflict (record the PR number and date here; moved from 708
      on 2026-11-17). → todo 721 (re-pointed 2026-11-21)
- [x] The first Railway deploy after todo 708 merges builds the backend Docker
      image (record the deployment id and date here; moved from 708 on
      2026-11-18).
- [ ] After an AI SDK bump: one real call per enabled feature succeeds in
      production (date and observation recorded here). → todo 721 (re-pointed 2026-11-21)

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

### 2026-11-21 - Implemented by the todo sweep (run 2026-11-20-2202)

- openai 3 and any-llm-sdk 1.x resolve: nothing caps them. `bash bin/compile-requirements.sh --upgrade-package ...` moved openai 2.34.0 -> 3.57.0, any-llm-sdk 0.20.3 -> 1.53.1, django-ai-core 0.1.5 -> 0.1.7, llm 0.31.1 -> 0.38 and sqlite-utils 3.38 -> 4.2.1 in both locks; wagtail-ai stays 3.1.1 (latest). sqlite-migrate, distro and tqdm drop out (no first-party import).
- llm needed its own `--upgrade-package llm --upgrade-package condense-json` pass: pip-tools kept 0.31.1 on the first one, though `llm>=0.32` resolves to 0.38 with no cap.
- No code change was needed for the SDKs: `LLMService.completion` (with `timeout`), `AnyLLM.create(..., timeout=)`, `_embedding`, `OpenAI().images.generate` / `chat.completions.create` and the openai exception classes all exist in the installed versions (probed). mypy 2.4.0 is clean over the gated list.
- Deleted the commented-out `gpt-4o-vision-preview` WAGTAIL_AI provider in `backend/plant_community_backend/settings.py`: it was dead (a comment), never a live path.
- Removed the `django-ai-core`, `llm` and `sqlite-migrate` holds from `.github/dependabot.yml`.

### 2026-11-21 - Verified by the todo sweep (run 2026-11-20-2202)

- AC 1: `grep -nE '^(openai|any-llm-sdk|llm|django-ai-core|wagtail-ai)==' backend/requirements.txt backend/requirements-dev.txt` — evidence `.sweep-evidence/g4/711-ac0.txt` (not committed), last lines:

  ```text
  backend/requirements-dev.txt:33:any-llm-sdk==1.53.1
  backend/requirements-dev.txt:198:django-ai-core==0.1.7
  backend/requirements-dev.txt:457:llm==0.38
  backend/requirements-dev.txt:491:openai==3.57.0
  backend/requirements-dev.txt:820:wagtail-ai==3.1.1
  ```

- AC 2: `grep -rn "gpt-4o-vision-preview" backend --include=*.py` — evidence `.sweep-evidence/g4/711-ac1.txt` (not committed), last lines:

  ```text

  ```

- AC 3: `cd backend && venv/bin/python -m mypy --cache-dir "$TMPDIR/mypy-cache"` — evidence `.sweep-evidence/g4/711-ac2.txt` (not committed), last lines:

  ```text
  ============================================================
  ⚠️  Redis not configured - caching will use in-memory fallback (not recommended)
  ============================================================

  Success: no issues found in 862 source files
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g4/711-ac3.txt` (not committed), last lines:

  ```text
  = 7065 passed, 8 skipped, 14 warnings, 298 subtests passed in 573.88s (0:09:33) =
  …
      self.callHandlers(record)
    File "backend/venv/lib/python3.13/site-packages/sentry_sdk/integrations/logging.py", line 171, in sentry_patched_callhandlers
      return old_callhandlers(self, record)
  Message: '[SHUTDOWN] ThreadPoolExecutor cleanup complete'
  Arguments: ()
  ```

### 2026-11-21 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-20-2202)

- AC 6: confirmed by the owner on 2026-11-21: "Owner chose 'Confirm (b)': the first Railway deploy after todo 708 merged (#1375, 2026-11-19T04:20:53Z) is GitHub deployment 7903998279 for commit 2f64d344, status success at 2026-11-19T04:25:35Z (read by Claude from the GitHub deployments API, 2026-11-21)" (`state.py confirm`; no command or evidence)

### 2026-11-21 - Completed by the todo sweep (run 2026-11-20-2202)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-21 - Review round 1: non-blocking findings (PR #1397)

Round 1 was clean (5 reviewers, nothing blocking). The lows:

- **Fixed:** the pip block's header comment in `.github/dependabot.yml` still said the first Dependabot PR
  check was todo 711 and that the holds below were 711 decisions. It now points the check at todo 721 and
  says the one hold left (django-treebeard) is a Wagtail resolver cap.
- **Declined:** a reviewer asked that the Wagtail AI, forum RAG and spam paths be run on this lockfile before
  merge. The full backend suite ran on it (7065 passed, `--create-db`), the blog AI and forum spam tests
  included, and no first-party code needed a change. Real calls in production are todo 721, after deploy.
