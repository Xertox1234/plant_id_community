---
status: pending
priority: p3
issue_id: "381"
tags: [dependencies, security, npm, cloudflare]
dependencies: []
---

# Remove the root `sharp` override once miniflare stops pinning 0.35.2

## Problem

PR #718 added `overrides: {"sharp": "^0.35.4"}` to the root `package.json` to
clear Dependabot alert #125. An override is a **standing instruction with no
expiry** — the exact shape `.github/security-suppressions.yml` exists to prevent
("the Twisted entry said 'Remove when Twisted >=26.4.0 stable releases'. It did.
Nothing was watching."). This todo is the thing that has to exist so someone is
watching.

## Findings

Raised as a `low` finding by the bundled `/code-review` pass on PR #718, and
independently by the pre-merge investigation.

- `package.json:9-11` — the override carries no removal condition, and nothing
  else in the tree explains why it exists.
- The pin exists **only** because every miniflare alpha pins sharp at exactly
  `0.35.2` while the libheif patch is `0.35.4`:

  | wrangler | miniflare | sharp |
  | --- | --- | --- |
  | 4.128.0 | 5.20260831.0-alpha | 0.35.2 |
  | 4.129.0 (ours) | 5.20260903.0-alpha | 0.35.2 |
  | 4.129.1 | 5.20260907.0-alpha | 0.35.2 |
  | 4.130.0 | 5.20260908.0-alpha | 0.35.2 |

- **The rot scenario is concrete.** `^0.35.4` resolves `>=0.35.4 <0.36.0`. If
  miniflare later moves to sharp `0.36.x`, the override silently caps the tree
  *below* what miniflare declares, and Dependabot's update job starts failing
  again — this time caused by our own override rather than miniflare's pin, with
  nothing pointing at the cause. npm applies an override silently; there is no
  conflict error to notice.
- Today the cap is inert: `npm view sharp version` is `0.35.4`, so nothing is
  being held back. The risk is entirely future.

## Recommended Action

1. Check whether miniflare still pins sharp below `0.35.4`:

   ```
   npm view wrangler dependencies.miniflare
   npm view miniflare@<that version> dependencies.sharp
   ```

2. **If miniflare now requests `>=0.35.4`:** delete the `overrides` block and the
   `"//sharp-override"` note from the root `package.json`, regenerate the
   lockfile **with npm >= 12** (see AC below), and confirm
   `npm ls sharp` still resolves `>=0.35.4` without the override.
3. **If miniflare has moved to `0.36.x` or later:** the override is now actively
   harmful — widen or delete it in the same commit that bumps wrangler. Do not
   leave `^0.35.4` in place against a `0.36.x` request.
4. **If miniflare still pins `0.35.2`:** nothing to do; re-date this todo.

## Technical Details

- The override lives in the **root** `package.json` (the Cloudflare Workers
  manifest), not `web/`. `sharp` appears in exactly one lockfile in the repo.
- `sharp` is a devDependency transitive (`wrangler` → `miniflare` → `sharp`),
  used for local `wrangler dev` preview. It never ships, and the alert's scope
  is `development`.
- **Regenerate the lockfile with npm >= 12.** npm 11.6.0 silently strips the 16
  `libc` fields from `@img/sharp-linux-*` / `@img/sharp-linuxmusl-*`, which is a
  runtime "cannot load shared library" on Alpine and is invisible to `npm audit`,
  to CI, and to a normal diff read. PR #718 reproduced that regression and had to
  repair it; `docs/LEARNINGS.md` (2026-09-06) records the original.
- Verify a lockfile change at the **field** level, not the version level:
  `libc` hides inside "non-version field changes".

## Acceptance Criteria

- [ ] miniflare's current sharp requirement recorded in the Work Log
- [ ] Override deleted, widened, or explicitly re-dated based on that fact
- [ ] If the lockfile was regenerated: `grep -c '"libc"' package-lock.json`
      returns **16**, and no package lost a field versus the previous lockfile
- [ ] `npm audit --package-lock-only` at the repo root reports 0 vulnerabilities
- [ ] `npx wrangler --version` still runs

## Notes

p3: the override is correct and inert today, and the failure mode needs an
upstream change to trigger. Not p4 because the failure is silent — npm applies
an override with no warning, so the first symptom would be a confusing Dependabot
failure pointing at miniflare rather than at us.

Related: `todos/366` (the same "who is watching this pin?" problem for pip-audit
suppressions), `.github/security-suppressions.yml` header for the rationale.

## Work Log

### 2026-09-09 - Filed

- Filed from the `/code-review` low finding on PR #718, during the GitHub cleanup
  that closed Dependabot #125.
- Confirmed the cap is inert today: latest published sharp is `0.35.4`.
