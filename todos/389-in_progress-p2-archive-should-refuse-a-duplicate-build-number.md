---
status: in_progress
priority: p2
issue_id: "389"
tags: [mobile, ios, release, tooling]
dependencies: []
---

# run_archive.sh should refuse a duplicate build number before building

## Problem

The iOS build number lives as a hand-maintained integer in `pubspec.yaml`, and
nothing checks it against reality. It has now been wrong **twice in two days**,
both times discovered by a human rather than by a tool:

| Date | pubspec said | Reality | Caught by |
| --- | --- | --- | --- |
| 2026-09-12 | `1.0.0+2` | builds 1-5 existed | code review |
| 2026-09-13 | `1.0.0+6` | builds 1-9 existed | **the owner noticing build 9 on their phone** |

The second case is the instructive one. PR #741 set `+6` using todo 383 as the
source of truth, which records builds 1-5. Builds 6-9 were uploaded
2026-09-12/13 and never written back to that todo. Build 6 went up at
2026-09-12T21:26:07 — *before #741 was opened* — so `+6` was already a duplicate
when it merged. **A todo is not a source of truth for remote state.**

## Why it fails late and expensively

- `ios/ExportOptions.plist` sets `manageAppVersionAndBuildNumber = false`, so
  Xcode does **not** renumber at export. The pubspec value is used literally.
- `run_archive.sh:62` derives `EFFECTIVE_BUILD` from the pubspec `+` suffix when
  `BUILD_NUMBER` is unset.
- So a duplicate builds cleanly, passes the in-script IPA config gate, and is
  rejected by `altool` at the very end — after roughly five minutes of work.
- **Expiring a build does not free its number.** All of builds 1-8 are expired
  and all eight numbers remain permanently taken. This surprises people and is
  why "I expired the old ones" does not help.

## Recommended Action

Make `run_archive.sh` ask App Store Connect for the highest existing build
number **before** it starts building, and refuse to proceed on a duplicate.

The credentials already exist and are already used by `run_upload.sh`:
`ASC_KEY_ID` / `ASC_ISSUER_ID` from the gitignored `.env.appstore`, plus
`~/.appstoreconnect/private_keys/AuthKey_<ASC_KEY_ID>.p8`. The query is a signed
ES256 JWT (`aud: appstoreconnect-v1`) against:

```
GET /v1/apps?limit=50                      -> match bundleId com.plantcommunity.plantCommunityMobile
GET /v1/builds?filter[app]=<id>&limit=200  -> attributes.version is the build number
```

Behaviour:

- Refuse, loudly, if `EFFECTIVE_BUILD` <= the highest existing build, naming
  both numbers and the next free one.
- Offer `--next` (or `BUILD_NUMBER=next`) to select `highest + 1` automatically,
  so the pubspec integer stops being load-bearing.
- Degrade gracefully when ASC is unreachable or credentials are absent: warn
  clearly that the check was **skipped**, and do not silently pass. A check that
  cannot run must not look like a check that passed.

## Acceptance Criteria

- [x] `run_archive.sh` queries App Store Connect before building and exits
      non-zero on a build number that already exists, naming the next free one
- [x] A missing/unreachable credential produces an explicit `SKIPPED` warning,
      never a silent pass
- [x] Verified against the real account: a known-taken number (e.g. 9) is
      refused, and the next free number is accepted
- [x] `docs/LEARNINGS.md` records that expiring a build does not free its number

## Notes

p2, not p3: this wastes a full build cycle every time it fires, it has fired
twice in two days, and the only thing that caught it the second time was the
owner happening to look at their phone. The fix is ~30 lines against
credentials the repo already has.

## Work Log

### 2026-09-13 - Filed

- Filed while correcting `1.0.0+6` to `1.0.0+10`. The corrected value was taken
  from the ASC API directly (9 builds exist; build 9 is the only non-expired
  one), not from a todo — but `+10` is itself only correct until someone
  uploads again, which is precisely the reason this todo exists.

### 2026-09-13 - Implemented (PR pending review)

`plant_community_mobile/scripts/asc_build_numbers.py` (new) mints an ES256 App
Store Connect JWT and reports the highest build number the app holds.

**Stdlib only, deliberately.** PyJWT + `cryptography` exist in `backend/venv` and
nowhere else, so a release script importing them would silently stop working
outside that venv. The signature is made by `openssl dgst -sha256 -sign` and the
DER output converted to JOSE's raw `r||s` in ~20 lines.

Exit codes are three-valued so "could not check" cannot read as "checked and
fine": `0` queried, `3` SKIPPED (no credentials / unreachable), `1` hard error.

`run_archive.sh` consumes it before building:

- refuses `EFFECTIVE_BUILD <= highest`, naming both numbers and the next free one
- `--next` (or `BUILD_NUMBER=next`) selects `highest + 1`; refuses outright if the
  query did not run, rather than guessing
- exit 3 prints a loud `!! SKIPPED … UNVERIFIED` banner and continues
- `SKIP_ASC_CHECK=1` opts out explicitly and says so
- skipped entirely under `SKIP_BUILD=1`, which is the verify-only path
  `run_upload.sh` reuses — the number of an already-built IPA is not a decision
- `flutter build ipa` now receives `--build-number="$EFFECTIVE_BUILD"` explicitly,
  so `--next` takes effect and the built number cannot drift from the checked one

**Verified against the real account** (app `6811429591`, builds 1-9 exist):

| Case | Result |
| --- | --- |
| `BUILD_NUMBER=9` (taken) | refused, named 10 as next free |
| `BUILD_NUMBER=10` (free), `flutter` stubbed on PATH | passed the gate, `--build-number=10` reached the build |
| `--next` | selected 10 |
| no `.p8` (HOME redirected) | `SKIPPED … UNVERIFIED`, build continued |
| `--next` with no `.p8` | refused |
| `SKIP_ASC_CHECK=1` | announced the skip |
| `--bogus` | rejected |

The `BUILD_NUMBER=10` case is the positive control: refusing 9 says nothing about
whether a free number still builds.

Also confirms this branch's own `1.0.0+10` is genuinely free.
