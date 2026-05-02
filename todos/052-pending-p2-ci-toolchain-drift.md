---
status: blocked
priority: p2
issue_id: "052"
tags: [ci, github-actions, flutter, node, python, dependencies, stabilization]
dependencies: ["047", "050"]
---

# Align CI Toolchains With Project Requirements

## Problem

CI configuration appears to use toolchain versions that are not aligned with project requirements. This can cause false failures or false confidence.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- `plant_community_mobile/pubspec.yaml` requires Dart `^3.9.0`.
- Historical finding: `.github/workflows/security-scan.yml` installed Flutter `3.27.x`, which was not aligned with Dart 3.9-era Flutter releases.
- Historical finding: backend docs/README mentioned Python 3.10+, while local environment was Python 3.12.1 and backend `pyproject.toml` set mypy `python_version = "3.13"`.
- Historical finding: web dependencies were installed with local Node `v24.14.0`, while CI used Node 20.
- The current GitHub cloud workspace has Python 3.12.1 and Node v24.14.0, but no Flutter/Dart SDK.

## Recommended Action

1. Decide and document supported toolchain versions:
   - Python version
   - Node version
   - Flutter/Dart version
2. Update GitHub Actions to use those versions.
3. Add local version files if helpful:
   - `.nvmrc`
   - `.python-version`
   - FVM config for Flutter, if using FVM
4. Run CI-equivalent commands locally or in GitHub Actions.

## Technical Details

Key files:

- `.github/workflows/security-scan.yml`
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `web/package.json`
- `plant_community_mobile/pubspec.yaml`
- `README.md`

## Acceptance Criteria

- [x] Supported Python/Node/Flutter versions are documented in the root README or setup docs.
- [x] CI uses the documented versions.
- [ ] Flutter CI can run `flutter pub get` successfully.
- [x] Web CI can run install/build/audit successfully.
- [ ] Backend CI can install dependencies and run checks successfully.

## Work Log

### 2026-05-01 - Codebase Assessment

- Classified P2 because mismatched toolchains can make CI unreliable even when code is correct.

### 2026-05-01 - Toolchain Alignment In Progress

- Aligned GitHub Actions security scan to Python 3.12, Node 24, and Flutter 3.35.x.
- Updated backend Safety scans to audit `backend/requirements.txt` directly.
- Updated backend mypy target to Python 3.12.
- Added `.python-version` and `.nvmrc` for local version discovery.
- Updated root README prerequisites and backend path references.
- Runtime validation remains deferred to CI/a Flutter-capable environment because this GitHub cloud workspace does not include Flutter/Dart.

### 2026-05-02 - Web CI Validation

- Ran web install/audit/build/test commands under the local Node 24 toolchain.
- Verified `npm audit --audit-level=moderate` reports 0 vulnerabilities.
- Verified `npm run build` passes, including TypeScript type-check.
- Verified `npm run test -- --run` passes: 24 files, 663 tests passed.
