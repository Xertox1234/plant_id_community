# Pre-commit Lint & Prettier Hooks Design

**Date:** 2026-05-07  
**Status:** Approved

## Summary

Add ESLint, Prettier (web), `flutter analyze`, and `dart format` (mobile) as pre-commit hooks. Fix the existing broken `mirrors-eslint` v8 hook, which is incompatible with the project's ESLint v9 flat config.

## Scope

- `web/` — React/TypeScript frontend
- `plant_community_mobile/` — Flutter mobile app

Python checks (Black, Flake8, isort) are already working and are out of scope.

## Approach

Option A: local hooks running project CLI tools directly. No new hook systems (no husky/lint-staged). All hooks live in `.pre-commit-config.yaml` alongside existing checks. Runs on all project files (not just staged), which is acceptable at this codebase size.

## Changes Required

### 1. `web/` — Bootstrap Prettier

- Install `prettier` as a devDependency in `web/package.json`
- Add `web/.prettierrc` with:
  - `printWidth: 100`
  - `singleQuote: true`
  - `semi: true`
  - `tabWidth: 2`
  - `trailingComma: "es5"`
- Add `"format": "prettier --write ."` script to `web/package.json`

### 2. `.pre-commit-config.yaml` — Web hooks

Remove the existing broken `pre-commit/mirrors-eslint` v8 hook.

Add two local hooks under a new `# JavaScript/TypeScript` section:

**ESLint hook**

- `name`: Lint JS/TS with ESLint
- `entry`: `bash -c 'cd web && npm run lint'`
- `language`: system
- `files`: `^web/.*\.(js|jsx|ts|tsx)$`
- `pass_filenames`: false

**Prettier hook**

- `name`: Check JS/TS formatting with Prettier
- `entry`: `bash -c 'cd web && npx prettier --check .'`
- `language`: system
- `files`: `^web/.*\.(js|jsx|ts|tsx)$`
- `pass_filenames`: false

### 3. `.pre-commit-config.yaml` — Flutter hooks

Add two local hooks under a new `# Flutter/Dart` section:

**flutter analyze hook**

- `name`: Analyze Flutter with flutter analyze
- `entry`: `bash -c 'flutter analyze plant_community_mobile/'`
- `language`: system
- `files`: `^plant_community_mobile/.*\.dart$`
- `pass_filenames`: false

**dart format hook**

- `name`: Check Dart formatting with dart format
- `entry`: `bash -c 'dart format --output=none --set-exit-if-changed plant_community_mobile/lib/'`
- `language`: system
- `files`: `^plant_community_mobile/.*\.dart$`
- `pass_filenames`: false

## Developer Workflow

| Problem | Fix command |
|---------|-------------|
| ESLint errors | `cd web && npm run lint -- --fix` |
| Prettier failures | `cd web && npm run format` |
| flutter analyze failures | Fix the reported Dart issues |
| dart format failures | `dart format plant_community_mobile/lib/` |

## Out of Scope

- Adding ESLint/Prettier to GitHub Actions CI (separate task)
- Changing existing Python (Black/Flake8/isort) hooks
- Changing `analysis_options.yaml` lint rules
