---
status: pending
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
