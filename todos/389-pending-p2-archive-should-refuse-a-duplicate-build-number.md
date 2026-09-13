---
status: pending
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

- [ ] `run_archive.sh` queries App Store Connect before building and exits
      non-zero on a build number that already exists, naming the next free one
- [ ] A missing/unreachable credential produces an explicit `SKIPPED` warning,
      never a silent pass
- [ ] Verified against the real account: a known-taken number (e.g. 9) is
      refused, and the next free number is accepted
- [ ] `docs/LEARNINGS.md` records that expiring a build does not free its number

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
