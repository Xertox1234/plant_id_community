---
status: in_progress
priority: p3
issue_id: "241"
tags: [security, deployment, railway, secrets, nixpacks]
dependencies: []
---

# Move build-time secrets out of Railway image layers

## Problem

Railway/Nixpacks exposes all service variables at **build** time by default, so
production secrets get baked into the built image's layers (and persist in image
history). The original deploy session flagged this as `SecretsUsedInArgOrEnv`
warnings for `SECRET_KEY`, `JWT_SECRET_KEY`, `PLANT_ID_API_KEY`,
`PLANTNET_API_KEY` (see todo 216 Findings → "Build bakes secrets into image
layers", Recommended Action #6).

It was never an acceptance criterion of 216 (which closed legitimately on its 7
ACs), so it stayed open. **Todo 216's 2026-06-24 work then expanded the surface**:
five more secrets — `TREFLE_API_KEY`, `PLANT_HEALTH_API_KEY`, `OPENAI_API_KEY`,
`GOOGLE_OAUTH2_CLIENT_ID`, `GOOGLE_OAUTH2_CLIENT_SECRET` — were added to Railway
and are now also build-time-exposed.

Practical blast radius is bounded (the image lives in Railway's private registry,
not a public one), which is why this is p3 rather than a p1. But secrets in image
layers are still a real hygiene problem, especially before external testers.

## Recommended Action

1. Identify which secrets are genuinely needed at **build** time (likely none —
   `collectstatic`/`migrate` run in the **start** command, not the build) vs
   **runtime** only.
2. Configure Railway so runtime-only secrets are NOT injected into the build
   (Railway build-time variable controls / runtime-only / sealed variables,
   per current Railway docs — verify the exact mechanism, it has changed over
   time). Goal: the `SecretsUsedInArgOrEnv` warning no longer lists app secrets.
3. Consider rotating the most sensitive baked secrets after they're moved
   runtime-only (`SECRET_KEY`, `JWT_SECRET_KEY`, `GOOGLE_OAUTH2_CLIENT_SECRET`)
   so old image layers no longer hold live values. (No users yet → low cost.)
4. Re-deploy and confirm the build log no longer warns about app secrets.

## Technical Details

- Build config: `backend/railway.json` (`builder: NIXPACKS`; start command runs
  migrate + seed + collectstatic + gunicorn — none of which need secrets at
  *build* time).
- Affected vars: all app secrets currently set on the Railway `plant_id_community`
  service (`SECRET_KEY`, `JWT_SECRET_KEY`, the two plant-API keys, and the five
  integration keys migrated in todo 216).
- Reference: Railway docs on build vs runtime variables; Nixpacks secret handling.

## Acceptance Criteria

- [ ] App secrets are no longer exposed at build time (Railway build log shows no
      `SecretsUsedInArgOrEnv` for app secrets), OR the exposure is explicitly
      accepted with a documented rationale if Railway offers no clean mechanism.
- [ ] Decision recorded on whether to rotate the previously-baked sensitive
      secrets (and rotated if chosen).

## Notes

Split from **todo 216** (live-deployment hardening). Surfaced/expanded by 216's
integration-key migration on 2026-06-24; tracked here so it isn't dropped.

## Work Log

### 2026-06-28 - Started by completing-todos skill (run 2026-06-28-1330)

- Picked up by automated workflow.

**Orientation findings (evidence-grounded):**

- Builder confirmed `NIXPACKS` v1.41.0 in `backend/railway.json`; start command runs
  migrate + seed + collectstatic + gunicorn — none need secrets at *build* time.
- Live build log (`railway logs --build`) shows Nixpacks generates **both**
  `ARG "<NAME>"` (line 11) and `ENV "<NAME>=..."` (line 12) per secret-named var.
  The `ENV` form persists in final image layers. BuildKit lint
  `SecretsUsedInArgOrEnv` fires for 9 app secrets:
  `SECRET_KEY`, `JWT_SECRET_KEY`, `PLANT_ID_API_KEY`, `PLANTNET_API_KEY`,
  `TREFLE_API_KEY`, `PLANT_HEALTH_API_KEY`, `OPENAI_API_KEY`,
  `GOOGLE_OAUTH2_CLIENT_SECRET`, and **`EMAIL_HOST_PASSWORD`** (not in original
  todo list — newly found; folded into scope). `GOOGLE_OAUTH2_CLIENT_ID` is set
  but NOT flagged (lint only matches secret-named keys).
- Railway docs (Context7 `/railwayapp/docs`): for the **Nixpacks** builder, all
  service variables are exposed at build + runtime, and even **sealed variables**
  are still "injected into builds" — so sealing does NOT close AC1.
  `RAILPACK` is now Railway's **default** builder (valid `builder` values:
  `RAILPACK` | `DOCKERFILE`); it uses BuildKit secret mounts rather than baking
  `ENV` layers — the documented fix for this exact warning.
- Only one environment exists (`production`); no staging. RAILPACK test relies on
  Railway's safety net (a failed build leaves the live Nixpacks deploy untouched).

**Decisions (user-approved 2026-06-28):**

- **AC1:** switch `NIXPACKS` → `RAILPACK`, redeploy, verify build log no longer
  warns. Fall back to AC1 OR-clause (accept + document) only if RAILPACK fails.
- **AC2:** rotate the 2 self-rotatable Django secrets (`SECRET_KEY`,
  `JWT_SECRET_KEY`) *after* the build fix; document accept-risk for the 7
  externally-issued keys (private registry + no users yet → low blast radius).

### 2026-06-28 - RAILPACK failed; pivoting to a Dockerfile builder

- **RAILPACK switch (PR #421) merged but its build FAILED.** Root cause (build
  log): RAILPACK copies only `requirements.txt`+`pyproject.toml` before
  `pip install`, so the editable local dep `-e ./packages/wagtail_forum`
  (`requirements.txt:228`) errors — *"not a valid editable requirement"* — the
  package dir isn't copied yet. NIXPACKS copied the whole context first, so it
  never hit this. Prod stayed healthy on the prior NIXPACKS image (failed build
  never swapped in).
- The clean one-line RAILPACK fix is therefore dead for our editable-package
  layout. Discriminator brought to user; **user chose to fix it properly via a
  DOCKERFILE builder** (not accept+document). Rotation stays downstream:
  Dockerfile (non-baking) → rotate.
- **Recovery:** reverted `main` to NIXPACKS (PR #422) to restore a deployable
  state while the Dockerfile is developed/validated.
- **Dockerfile approach** (`backend/Dockerfile` + `backend/.dockerignore`,
  `railway.json` builder → `DOCKERFILE`): `COPY . .` *then* `pip install` (the
  editable package resolves), and **no secret `ARG`/`ENV`** (DOCKERFILE builder
  only exposes build vars you explicitly `ARG`) → nothing baked into layers.
  `.dockerignore` excludes the 652M local `venv/` + `media/` + `.env`. Validating
  via `railway up` (prod-safe: a failed build leaves the NIXPACKS deploy
  untouched) before merging to `main`. Docker daemon is down locally, so no local
  `docker build`.

### 2026-06-28 - Dockerfile built + closed AC1, but RUNTIME 502'd → reverted

- `railway up --ci` was blocked by the auto-mode classifier (direct prod deploy),
  so the Dockerfile went through the normal PR flow (**PR #423**, merged).
- **Build succeeded and AC1 was MET**: the DOCKERFILE build log had **0**
  `SecretsUsedInArgOrEnv` (was 18 lines under NIXPACKS); `COPY . .` → `pip install`
  ran, the editable `wagtail_forum` installed, deploy reached SUCCESS.
- **BUT the running container 502s.** Deploy log shows the start chain **hangs
  right after `migrate`**: one `Starting Container`, no crash-loop, and **zero**
  output for `seed_default_forum`/`collectstatic`/`gunicorn`, no traceback —
  ~1h40m stuck. `seed_default_forum` is pure DB ops (can't hang; would
  error+restart, not silently stall), so the hang is environmental to the
  Dockerfile runtime (PID-1/signals? a non-daemon thread blocking process exit
  after migrate? collectstatic?). **Root cause NOT identified** — needs
  in-container inspection.
- Could not diagnose: `railway ssh` blocked by the classifier; local Docker
  daemon down (no `docker run` repro).
- **Recovery: reverted the Dockerfile merge (PR #424, `git revert 6a0b279`)** —
  restores NIXPACKS and **deletes `backend/Dockerfile`** (Railway prefers a
  Dockerfile if present). Prod confirmed healthy again (root HTTP 302,
  `main` builder = NIXPACKS). Dockerfile preserved in history at commit `6a0b279`.
- **Lesson:** a Railway deploy reporting SUCCESS only means the container
  *started* (no healthcheck configured) — NOT that it serves. Any retry must (a)
  reproduce/serve-test off-prod first (local `docker run` or a healthcheck that
  fails a bad deploy instead of silently 502ing), and (b) likely move
  migrate/seed/collectstatic to a `preDeployCommand` so a startup failure surfaces
  as a failed deploy, not a hung container.
- **OPEN DECISION (for user):** get a repro to fix the Dockerfile (start local
  Docker, or approve a scoped SSH read) vs. close this p3 on NIXPACKS + documented
  accept-risk (no rotation — futile under NIXPACKS baking).
