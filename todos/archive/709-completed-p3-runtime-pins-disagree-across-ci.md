---
status: completed
priority: p3
issue_id: "709"
tags: [ci, runtime, python, node, dependencies]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Owner 2026-11-17 allowed a read-only Railway lookup: production runs Postgres 18 (image ghcr.io/railwayapp-templates/postgres-ssl:18) and Redis 8.2.9 (image redis:8.2.9), read 2026-11-18 via Railway MCP service config. CI moves to match: pgvector/pgvector:pg18 and redis:8"
---

# Runtime versions disagree between CI, the image and the version files

## Problem

Python and Node are pinned in several places that do not agree, so some CI
jobs test on a runtime production does not use, and no single file says which
version the project is on.

## Findings

Source: stack audit, 2026-11-15.

- Python 3.12 in three workflows: `firebase-rules-emulator.yml:64`,
  `firebase-rules-drift.yml:81`, `harness-ci.yml:105`. Everything else, and
  production, is 3.13.
- Node 22 in `firebase-rules-emulator.yml:59`; `.nvmrc` and the other
  workflows say 24.
- `.python-version` says `3.13.9`, `backend/.python-version` says `3.13`,
  `backend/Dockerfile:13` is `FROM python:3.13-slim` (floating), and the local
  venv ran 3.13.15 on 2026-11-15.
- Root `package.json` lists `@playwright/test` (lock: 1.56.1) and
  `react-error-boundary` (lock: 6.0.0) as runtime dependencies of the
  Cloudflare Workers deploy tree. `web/package.json` has its own, newer
  copies. Hypothesis, not verified: nothing at the root uses them.
- `.github/dependabot.yml` ignores new Python lines for the Docker image, so
  moving off 3.13 is a decision made here, not a Dependabot PR.
- Not checked: which Postgres and Redis versions production runs.
  `.railway/railway.ts` pins no image; CI uses `pgvector/pgvector:pg16` and
  `redis:7`.

## Recommended Action

1. Move the three Python 3.12 jobs to 3.13 and the Node 22 job to 24. If a job
   needs the older runtime, say why in a comment next to the pin.
2. Make one `.python-version` the source: both files carry the same value, and
   decide whether the Dockerfile pins a patch (`python:3.13.x-slim`) or keeps
   floating. A patch pin lets Dependabot propose patch bumps.
3. Check whether anything at the repo root imports `@playwright/test` or
   `react-error-boundary`; remove the ones nothing uses and regenerate the
   root lock.
4. Owner: read the Postgres and Redis versions off Railway and record them
   here; set CI to the same majors.
5. Owner decision: stay on Python 3.13, or plan the move to a newer line. If
   moving, remove the `python` ignore from `.github/dependabot.yml` in that PR.

## Technical Details

- `.github/workflows/firebase-rules-emulator.yml`, `firebase-rules-drift.yml`,
  `harness-ci.yml`
- `.python-version`, `backend/.python-version`, `.nvmrc`, `backend/Dockerfile`
- `package.json`, `package-lock.json` (repo root)
- `.github/dependabot.yml` (docker entry)

## Acceptance Criteria

- [x] `grep -n "python-version: '3.12'\|node-version: '22'" .github/workflows/*.yml`
      prints nothing, or each remaining line has a comment giving the reason.
- [x] Both `.python-version` files hold the same value.
- [x] Root `package.json` lists only packages the root tree uses; root
      `npm audit --package-lock-only` reports 0 vulnerabilities.
- [x] Production Postgres and Redis versions recorded here with the date read,
      and CI service images match their majors.
- [x] Python line decision recorded here with its date.

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit.

### 2026-11-17 - Implemented by the todo sweep (run 2026-11-17-1802)

- Python line decision (owner, 2026-11-17): stay on 3.13 and pin a patch. `.python-version`, `backend/.python-version` and `backend/Dockerfile` (`python:3.13.18-slim`) now all say 3.13.18, the newest 3.13 that has a `-slim` tag on Docker Hub and an actions/python-versions build for Ubuntu 22.04, 24.04 and 26.04 (both checked 2026-11-17). The floating `3.13-slim` tag already resolved to it, so the deploy does not change Python.
- Drift left on purpose: Dependabot's docker entry bumps only the Dockerfile line, so a patch PR must move both version files too. That is written next to the `FROM` and in `backend/docs/deployment/railway.md`. No guard was added.
- `firebase-rules-emulator.yml`, `firebase-rules-drift.yml` and `harness-ci.yml` move from Python 3.12 to 3.13. The emulator job moves from Node 22 to 24 (firebase-tools 14.19.1 declares `node >=20`). None of them needed the older runtime.
- Root `package.json`: `@playwright/test` and `react-error-boundary` removed. Nothing at the root imports them; both design scripts load Playwright through `web/package.json`. The root lock was regenerated (71 lines gone), and the root `npm audit --package-lock-only` finds 0 vulnerabilities.
- AC4 (production Postgres and Redis versions) is the owner's: read them off Railway and record them here. CI is still on `pgvector/pgvector:pg16` and `redis:7`.

### 2026-11-17 - Review round 1: non-blocking findings (PR #1359, hand-landed)

- **Checked.** The reviewer could not confirm the Python 3.13.18 builds offline. Checked on 2026-11-17: Docker Hub `library/python` tag `3.13.18-slim` answered HTTP 200, and actions/python-versions' `versions-manifest.json` lists `3.13.18` first among 3.13.x. No CI job builds `backend/Dockerfile`, so the Railway deploy after merge is its first build.
- No other findings: no file outside `web/` imports the removed root npm packages (the design scripts resolve `playwright` through `createRequire(web/package.json)`).

### 2026-11-18 - Implemented by the todo sweep (run 2026-11-18-0148)

- Production versions, read 2026-11-18 from the Railway service config (owner-approved read-only lookup): Postgres 18 (image `ghcr.io/railwayapp-templates/postgres-ssl:18`) and Redis 8.2.9 (image `redis:8.2.9`).
- `backend-ci.yml` moves its services to the same majors: `pgvector/pgvector:pg18` (the tag exists on Docker Hub, checked 2026-11-18) and `redis:8`, with the production versions named next to each image. `backend/CLAUDE.md` says PostgreSQL 18 and Redis 8.
- Python line decision stands as recorded on 2026-11-17: stay on 3.13, pinned to the 3.13.18 patch in both `.python-version` files and the Dockerfile.

### 2026-11-18 - Verified by the todo sweep (run 2026-11-18-0148)

- AC 1: `grep -n "python-version: '3.12'\|node-version: '22'" .github/workflows/*.yml || echo 'no matches'` — evidence `.sweep-evidence/g7/709-ac0.txt` (not committed), last lines:

  ```text
  no matches
  ```

- AC 2: `cat .python-version backend/.python-version && cmp .python-version backend/.python-version && echo SAME` — evidence `.sweep-evidence/g7/709-ac1.txt` (not committed), last lines:

  ```text
  3.13.18
  3.13.18
  SAME
  ```

- AC 3: `cat package.json && npm --prefix . audit --package-lock-only` — evidence `.sweep-evidence/g7/709-ac2.txt` (not committed), last lines:

  ```text
      "deploy": "wrangler deploy",
      "preview": "wrangler dev"
    }
  }
  found 0 vulnerabilities
  ```

- AC 4: `grep -n 'Production versions' todos/archive/709-completed-p3-runtime-pins-disagree-across-ci.md && grep -n 'image:' .github/workflows/backend-ci.yml` — evidence `.sweep-evidence/g7/709-ac3.txt` (not committed), last lines:

  ```text
  97:- Production versions, read 2026-11-18 from the Railway service config (owner-approved read-only lookup): Postgres 18 (image `ghcr.io/railwayapp-templates/postgres-ssl:18`) and Redis 8.2.9 (image `redis:8.2.9`).
  177:        image: pgvector/pgvector:pg18
  191:        image: redis:8
  ```

- AC 5: `grep -n 'Python line decision' todos/archive/709-completed-p3-runtime-pins-disagree-across-ci.md` — evidence `.sweep-evidence/g7/709-ac4.txt` (not committed), last lines:

  ```text
  74:- [ ] Python line decision recorded here with its date.
  84:- Python line decision (owner, 2026-11-17): stay on 3.13 and pin a patch. `.python-version`, `backend/.python-version` and `backend/Dockerfile` (`python:3.13.18-slim`) now all say 3.13.18, the newest 3.13 that has a `-slim` tag on Docker Hub and an actions/python-versions build for Ubuntu 22.04, 24.04 and 26.04 (both checked 2026-11-17). The floating `3.13-slim` tag already resolved to it, so the deploy does not change Python.
  99:- Python line decision stands as recorded on 2026-11-17: stay on 3.13, pinned to the 3.13.18 patch in both `.python-version` files and the Dockerfile.
  ```

### 2026-11-18 - Completed by the todo sweep (run 2026-11-18-0148)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
