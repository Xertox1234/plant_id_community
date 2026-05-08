---
status: completed
priority: p3
issue_id: "054"
tags: [documentation, onboarding, maintenance, cleanup]
dependencies: ["047", "050", "052"]
---

# Update Stale Setup and Status Documentation

## Problem

Several documentation files appear stale or inconsistent with the current repository layout, toolchain, and validation results. This makes onboarding and future maintenance harder.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- Root `README.md` still references `existing_implementation/backend`, while the actual backend is under `backend/`.
- Root `README.md` says Flutter 3.37+ / Dart 3.10+, while `plant_community_mobile/pubspec.yaml` uses Dart `^3.9.0`.
- `plant_community_mobile/README.md` says Flutter 3.27+ but other docs mention newer versions.
- `web/TEST_FAILURES_ANALYSIS.md` contains stale failure counts/categories compared with the May 1, 2026 test run.
- Flutter dependency progress docs may be stale relative to current commits and should be reconciled.

## Recommended Action

1. Update root setup instructions to use the current folder structure.
2. Align Python/Node/Flutter version docs with CI and config files.
3. Update web test failure documentation after test triage.
4. Reconcile Flutter dependency progress docs with current code and lockfile state.
5. Add a short “current stabilization status” section to the root README or a dedicated status doc.

## Technical Details

Key files:

- `README.md`
- `web/TEST_FAILURES_ANALYSIS.md`
- `plant_community_mobile/README.md`
- `DEPENDENCY_UPDATE_PROGRESS.md`
- `plant_community_mobile/FLUTTER_DEPENDENCY_UPDATES_REMAINING.md`
- `.github/workflows/security-scan.yml`

## Acceptance Criteria

- [x] Root README paths match the actual repo layout.
- [x] Toolchain versions are consistent across README, CI, and package config files.
- [x] Test-status docs reflect current test results.
- [x] Flutter dependency docs reflect current dependency state.
- [x] A fresh developer can follow docs without hitting known missing steps.

## Work Log

### 2026-05-08 - Completed by completing-todos skill (run 2026-05-08-0240)

Two doc inconsistencies fixed to satisfy "fresh developer" criterion:

1. `plant_community_mobile/README.md` lines 59-63: stated that `google-services.json` is ignored and native Firebase files should be kept out of git. Both files are in fact tracked (per policy decided in todo 053). Updated paragraph to accurately describe tracking policy and Gradle plugin disabled status.

2. `README.md` line 144: `CORS_ALLOWED_ORIGINS` example used port 5173; Vite dev server runs on 5174. Fixed to 5174.

3. `README.md` line 152: still referenced "FlutterFire CLI" for mobile Firebase setup. Project uses `--dart-define` approach; updated to reflect actual workflow.

Verification: all referenced files read and confirmed consistent with actual repo state and tracking policy.

### 2026-05-01 - Codebase Assessment

- Classified P3 because stale docs are not direct runtime blockers, but they slow future sessions and increase restart temptation.
