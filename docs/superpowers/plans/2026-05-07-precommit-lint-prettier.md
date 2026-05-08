# Pre-commit Lint & Prettier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ESLint, Prettier (web), `flutter analyze`, and `dart format` (mobile) as pre-commit hooks, replacing the broken ESLint v8 mirror hook.

**Architecture:** Three-task sequence — bootstrap Prettier in `web/` first (so existing files are formatted before the check hook goes live), then replace the broken ESLint mirror with two local hooks (ESLint + Prettier), then add two Flutter hooks. Each task ends with a commit.

**Tech Stack:** pre-commit (Python), ESLint v10 (flat config), Prettier 3, Flutter SDK

---

## File Map

| Action | File |
|--------|------|
| Modify | `web/package.json` — add `prettier` devDep, add `format` script |
| Create | `web/.prettierrc` — Prettier config |
| Modify | `.pre-commit-config.yaml` — replace mirrors-eslint, add 4 local hooks |

---

### Task 1: Bootstrap Prettier in web/

**Files:**

- Create: `web/.prettierrc`
- Modify: `web/package.json`

- [ ] **Step 1: Create `web/.prettierrc`**

```json
{
  "printWidth": 100,
  "singleQuote": true,
  "semi": true,
  "tabWidth": 2,
  "trailingComma": "es5"
}
```

- [ ] **Step 2: Add `prettier` devDependency and `format` script to `web/package.json`**

In the `"scripts"` object, add after `"lint"`:

```json
"format": "prettier --write .",
```

In `"devDependencies"`, add (alphabetically after `"postcss"`):

```json
"prettier": "^3.4.0",
```

- [ ] **Step 3: Install the new dependency**

```bash
cd web && npm install
```

Expected: `package-lock.json` updated, no errors.

- [ ] **Step 4: Format all existing files**

This must happen before the Prettier check hook goes live, otherwise the hook fails on the first commit.

```bash
cd web && npm run format
```

Expected: Prettier rewrites any files that don't match the config. Review the diff — this is cosmetic whitespace/quote changes only.

- [ ] **Step 5: Verify Prettier passes on the formatted files**

```bash
cd web && npx prettier --check .
```

Expected: `All matched files use Prettier code style!`

- [ ] **Step 6: Commit**

```bash
git add web/package.json web/package-lock.json web/.prettierrc
git add -u web/
git commit -m "chore(web): install Prettier, format existing files"
```

(`git add -u web/` stages only already-tracked files modified by Prettier — `.gitignore` keeps `node_modules/` out.)

---

### Task 2: Replace broken ESLint mirror hook with local ESLint + Prettier hooks

**Files:**

- Modify: `.pre-commit-config.yaml`

The existing `mirrors-eslint` block (lines ~155–168) uses ESLint v8 with `.eslintrc` config style. The project has ESLint v10 with flat config (`web/eslint.config.js`), so the mirror hook silently fails. Replace the entire block.

- [ ] **Step 1: Replace the `mirrors-eslint` section in `.pre-commit-config.yaml`**

Find and replace this block:

```yaml
  # ===================================
  # JavaScript/TypeScript Code Quality
  # ===================================
  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.56.0
    hooks:
      - id: eslint
        name: Lint JavaScript/React with ESLint
        files: ^web/src/.*\.(js|jsx|ts|tsx)$
        types: [file]
        additional_dependencies:
          - eslint@8.56.0
          - eslint-plugin-react@7.33.2
          - eslint-plugin-react-hooks@4.6.0
```

Replace with:

```yaml
  # ===================================
  # JavaScript/TypeScript Code Quality
  # ===================================
  - repo: local
    hooks:
      - id: eslint-web
        name: Lint JS/TS with ESLint
        entry: bash -c 'cd web && npm run lint'
        language: system
        files: ^web/.*\.(js|jsx|ts|tsx)$
        pass_filenames: false

      - id: prettier-web
        name: Check JS/TS formatting with Prettier
        entry: bash -c 'cd web && npx prettier --check .'
        language: system
        files: ^web/.*\.(js|jsx|ts|tsx)$
        pass_filenames: false
```

- [ ] **Step 2: Verify ESLint hook passes**

```bash
pre-commit run eslint-web --all-files
```

Expected: `Lint JS/TS with ESLint..........Passed`

If it fails: run `cd web && npm run lint` directly to see the ESLint errors, fix them, re-run.

- [ ] **Step 3: Verify Prettier hook passes**

```bash
pre-commit run prettier-web --all-files
```

Expected: `Check JS/TS formatting with Prettier..........Passed`

If it fails: run `cd web && npm run format` to auto-fix, then re-run the check.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: replace broken mirrors-eslint hook with local ESLint + Prettier hooks"
```

---

### Task 3: Add Flutter analyze and dart format hooks

**Files:**

- Modify: `.pre-commit-config.yaml`

**Prerequisites:** `flutter` and `dart` must be in your `PATH`. Verify with `flutter --version` before starting.

- [ ] **Step 1: Add Flutter hooks to `.pre-commit-config.yaml`**

Find the Markdown Linting section header:

```yaml
  # ===================================
  # Markdown Linting
  # ===================================
```

Insert a new block immediately before it:

```yaml
  # ===================================
  # Flutter/Dart Code Quality
  # ===================================
  - repo: local
    hooks:
      - id: flutter-analyze
        name: Analyze Flutter with flutter analyze
        entry: bash -c 'flutter analyze plant_community_mobile/'
        language: system
        files: ^plant_community_mobile/.*\.dart$
        pass_filenames: false

      - id: dart-format
        name: Check Dart formatting with dart format
        entry: bash -c 'dart format --output=none --set-exit-if-changed plant_community_mobile/lib/'
        language: system
        files: ^plant_community_mobile/.*\.dart$
        pass_filenames: false

```

- [ ] **Step 2: Verify `flutter analyze` hook passes**

```bash
pre-commit run flutter-analyze --all-files
```

Expected: `Analyze Flutter with flutter analyze..........Passed`

If it fails: run `flutter analyze plant_community_mobile/` directly, fix reported issues, re-run.

- [ ] **Step 3: Check if existing Dart files need formatting**

```bash
dart format --output=none --set-exit-if-changed plant_community_mobile/lib/
```

If it exits non-zero, files need formatting:

```bash
dart format plant_community_mobile/lib/
```

Then verify the hook passes:

```bash
pre-commit run dart-format --all-files
```

Expected: `Check Dart formatting with dart format..........Passed`

- [ ] **Step 4: If Dart files were reformatted, commit them first**

```bash
git add plant_community_mobile/lib/
git commit -m "chore(mobile): format Dart files with dart format"
```

- [ ] **Step 5: Commit the hook config**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add flutter analyze and dart format pre-commit hooks"
```

---

## Developer Cheat Sheet

| Hook fails | Fix command |
|------------|-------------|
| `eslint-web` | `cd web && npm run lint -- --fix` |
| `prettier-web` | `cd web && npm run format` |
| `flutter-analyze` | Fix the reported Dart issue |
| `dart-format` | `dart format plant_community_mobile/lib/` |
