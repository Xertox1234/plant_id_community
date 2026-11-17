---
status: pending
priority: p3
issue_id: "709"
tags: [ci, runtime, python, node, dependencies]
dependencies: []
triage: ready
triaged: 2026-11-17
owner_decision: "Python line: stay on 3.13, pin the Dockerfile to a patch (python:3.13.x-slim). Prod Postgres/Redis versions (AC4) are owner-only, not read by the agent (2026-11-17)"
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

- [ ] `grep -n "python-version: '3.12'\|node-version: '22'" .github/workflows/*.yml`
      prints nothing, or each remaining line has a comment giving the reason.
- [ ] Both `.python-version` files hold the same value.
- [ ] Root `package.json` lists only packages the root tree uses; root
      `npm audit --package-lock-only` reports 0 vulnerabilities.
- [ ] Production Postgres and Redis versions recorded here with the date read,
      and CI service images match their majors.
- [ ] Python line decision recorded here with its date.

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit.
