---
status: in_progress
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

- [x] miniflare's current sharp requirement recorded in the Work Log
- [x] Override deleted, widened, or explicitly re-dated based on that fact
- [x] If the lockfile was regenerated: `grep -c '"libc"' package-lock.json`
      returns **16**, and no package lost a field versus the previous lockfile
- [x] `npm audit --package-lock-only` at the repo root reports 0 vulnerabilities
- [x] `npx wrangler --version` still runs

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

### 2026-09-13 - Removal condition MET; override deleted (PR pending review)

**miniflare moved.** Measured against the registry, not inferred:

| wrangler | miniflare | its `dependencies.sharp` |
| --- | --- | --- |
| 4.129.0 (ours, before) | 5.20260903.0-alpha | `0.35.2` |
| 4.130.0 | 5.20260908.0-alpha | `0.35.2` |
| **4.131.1 (ours, now)** | **5.20260911.0-alpha** | **`0.35.4`** |

That is Recommended Action 2, and it needs the wrangler bump to come with it:
our own wrangler 4.129.0 still drags in the miniflare that pins `0.35.2`, so
deleting the override alone would have silently walked sharp **back** to the
vulnerable version. Bump and delete are one change, not two.

Removed from the root `package.json`: the `overrides` block and its
`"//sharp-override"` note. `wrangler` `^4.129.0` -> `^4.131.1`.

**Lockfile regenerated with npm 12.0.2** (`npx --yes npm@12.0.2 install`); the
local npm is 11.19.0, which is exactly the version the trigger warns silently
strips `libc`.

Verification:

| Check | Result |
| --- | --- |
| `grep -c '"libc"' package-lock.json` | **16** (unchanged) |
| packages present in both lockfiles that lost any field | **0** |
| field census delta across all 99 packages | **empty** |
| packages added / removed | 0 / 0 |
| `npm ls --package-lock-only sharp` | `wrangler@4.131.1 -> miniflare@5.20260911.0-alpha -> sharp@0.35.4` |
| `"overrides"` in `package-lock.json` | **0 occurrences** |
| `npm audit --package-lock-only --json` | `{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}` |
| `npx wrangler --version` | `4.131.1` |

sharp resolves to the patched `0.35.4` **because miniflare now asks for it**,
not because we still cap it — `npm ls` is run against the override-free tree.

**One residual worth knowing:** miniflare pins sharp at *exactly* `0.35.4`, not
a range. If a future advisory lands on `0.35.4`, we are pinned to a vulnerable
transitive again by the same mechanism, and the same override will be the only
fix. The watcher for that is Dependabot, which is what raised alert #125 in the
first place -- no new machinery needed here, but the shape will recur.

`docs/rules/triggers.json:1682` (the npm>=12 lockfile trigger) fired on this
edit as designed and needs no change; it is about regenerating lockfiles
generally, not about this override.
