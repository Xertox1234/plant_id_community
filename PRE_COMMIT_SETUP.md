# Pre-commit Hooks Setup Guide

**Purpose:** Prevent security incidents like Issue #1 (API keys exposed in git)
**Status:** Recommended for all developers
**Time to setup:** 5-10 minutes

## What are Pre-commit Hooks?

Pre-commit hooks are automated checks that run **before** you commit code to git. They catch issues like:
- Exposed API keys and secrets (Issue #1 prevention)
- CLAUDE.md being committed (local file only)
- .env files being committed
- Code formatting issues
- Syntax errors
- Large files

**Key benefit:** Issues are caught locally BEFORE they enter the git repository.

## Quick Setup (5 minutes)

### Step 1: Install pre-commit

```bash
# Using pip (recommended)
pip install pre-commit

# OR using Homebrew (macOS)
brew install pre-commit

# OR using conda
conda install -c conda-forge pre-commit

# Verify installation
pre-commit --version
```

### Step 2: Install the hooks

```bash
# Navigate to project root
cd /path/to/plant_id_community

# Install hooks (creates .git/hooks/pre-commit)
pre-commit install

# Expected output:
# pre-commit installed at .git/hooks/pre-commit
```

### Step 3: Generate secrets baseline

```bash
# Create baseline file (tells detect-secrets what secrets are known)
detect-secrets scan > .secrets.baseline

# Audit the baseline (mark false positives)
detect-secrets audit .secrets.baseline

# This file is committed to git to track known secrets
git add .secrets.baseline
```

### Step 4: Test the hooks

```bash
# Run hooks on all files to verify setup
pre-commit run --all-files

# Expected: Some hooks may modify files (formatting, whitespace)
# If any CRITICAL checks fail, fix the issues before committing
```

## What Gets Checked?

### Critical Security Checks (Issue #1 Prevention)

1. **detect-secrets** - Industry-standard secret scanner
   - Detects API keys, passwords, tokens, private keys
   - Uses entropy analysis and pattern matching
   - Configurable with `.secrets.baseline`

2. **block-claude-md** - CLAUDE.md prevention
   - Blocks commits containing CLAUDE.md
   - This file is for local development only
   - Caused Issue #1 when committed

3. **block-env-files** - .env file prevention
   - Blocks commits containing .env, .env.local, etc.
   - Only .env.example allowed
   - Environment files contain real secrets

4. **scan-api-keys** - API key pattern detection
   - Scans for patterns like: `PLANT_ID_API_KEY=W3YvEk2rx...`
   - Warns if potential real credential detected
   - Verifies .env.example uses placeholders

5. **scan-django-secrets** - Django SECRET_KEY detection
   - Scans for Django SECRET_KEY patterns
   - Warns if looks like real secret (40+ chars)
   - Ensures secrets are in .env file

6. **verify-gitignore** - Security pattern verification
   - Ensures CLAUDE.md in .gitignore
   - Ensures .env patterns in .gitignore
   - Fails commit if critical patterns missing

### Code Quality Checks

7. **black** - Python code formatter
8. **flake8** - Python linter
9. **isort** - Python import sorter
10. **eslint** - JavaScript/React linter
11. **markdownlint** - Markdown formatter

### Git Hygiene Checks

12. **check-added-large-files** - Prevents files > 10MB
13. **check-merge-conflict** - Detects merge conflict markers
14. **no-commit-to-branch** - Prevents direct commits to main/master
15. **trailing-whitespace** - Removes trailing whitespace
16. **end-of-file-fixer** - Ensures files end with newline
17. **detect-private-key** - Detects private key files

## How to Use

### Normal Workflow

```bash
# Make your changes
vim backend/apps/plant_identification/services/my_service.py

# Stage changes
git add backend/apps/plant_identification/services/my_service.py

# Commit (hooks run automatically)
git commit -m "feat: add new plant identification service"

# Hooks will:
# 1. Check for secrets (CRITICAL - blocks if found)
# 2. Check for CLAUDE.md (CRITICAL - blocks if found)
# 3. Check for .env files (CRITICAL - blocks if found)
# 4. Format code with black, isort
# 5. Lint code with flake8, eslint
# 6. Check file hygiene

# If hooks pass:
✅ All checks passed! Commit successful.

# If hooks fail:
❌ Secret detected in file.py:45
❌ CLAUDE.md must not be committed
❌ flake8 found 3 linting errors

# Fix the issues and try again
```

### Bypassing Hooks (NOT RECOMMENDED)

```bash
# Skip all hooks (DANGEROUS - only for emergencies)
git commit --no-verify -m "emergency fix"

# WARNING: This skips ALL security checks
# Only use if:
# - Emergency hotfix needed immediately
# - You understand the security implications
# - You will fix issues in next commit
```

### Updating Hooks

```bash
# Update to latest hook versions (monthly recommended)
pre-commit autoupdate

# Review changes
git diff .pre-commit-config.yaml

# Commit updates
git add .pre-commit-config.yaml
git commit -m "chore: update pre-commit hooks"
```

## Handling False Positives

### detect-secrets False Positives

Sometimes detect-secrets flags legitimate code as secrets. To mark false positives:

```bash
# Run audit tool
detect-secrets audit .secrets.baseline

# For each flagged item:
# - Press 'y' if it's a real secret (should not be in code)
# - Press 'n' if it's a false positive (safe to ignore)
# - Press 's' to skip for now

# Save updated baseline
git add .secrets.baseline
git commit -m "chore: update secrets baseline"
```

### API Key Pattern False Positives

If you have a placeholder that looks like a real key:

```bash
# Example: This triggers warning
PLANT_ID_API_KEY=test_key_with_20_characters_exactly

# Fix: Make it obviously a placeholder
PLANT_ID_API_KEY=your-plant-id-api-key-here

# OR: Add generation instructions
# Get from: https://web.plant.id/
PLANT_ID_API_KEY=your-api-key-here
```

## Troubleshooting

### Issue: Hooks not running

```bash
# Verify hooks are installed
ls -la .git/hooks/pre-commit

# If missing, reinstall
pre-commit install

# Verify configuration exists
ls -la .pre-commit-config.yaml
```

### Issue: detect-secrets not found

```bash
# Install detect-secrets
pip install detect-secrets

# Verify installation
detect-secrets --version

# Regenerate baseline
detect-secrets scan > .secrets.baseline
```

### Issue: Hooks too slow

```bash
# Run only changed files (default behavior)
git commit -m "message"

# Skip specific hooks temporarily
SKIP=eslint git commit -m "message"

# Disable hooks for single commit (NOT RECOMMENDED)
git commit --no-verify -m "message"
```

### Issue: Black/flake8 conflicts

```bash
# Black and flake8 may disagree on formatting
# Solution: Configure flake8 to be Black-compatible

# Already configured in .pre-commit-config.yaml:
# flake8:
#   args:
#     - '--max-line-length=120'
#     - '--extend-ignore=E203,W503'  # Black compatibility
```

## Issue #1 Prevention in Action

### Scenario 1: Developer tries to commit CLAUDE.md

```bash
$ git add CLAUDE.md
$ git commit -m "docs: update local config"

Running block-claude-md hook...
ERROR: CLAUDE.md must NEVER be committed (local file only). See Issue #1.
❌ Hook failed
```

**Result:** Commit blocked, security incident prevented.

### Scenario 2: Developer accidentally adds .env file

```bash
$ git add backend/.env
$ git commit -m "fix: update configuration"

Running block-env-files hook...
ERROR: .env files must NOT be committed. Use .env.example for templates.
❌ Hook failed
```

**Result:** Commit blocked, credentials protected.

### Scenario 3: Documentation has real API key

```bash
$ git add README.md
$ git commit -m "docs: add setup instructions"

Running scan-api-keys hook...
WARNING: Potential API key detected in README.md:45
Pattern: PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
⚠️  Hook passed with warnings
```

**Result:** Commit succeeds with warning, developer alerted to verify.

### Scenario 4: OAuth secret in code

```bash
$ git add backend/settings.py
$ git commit -m "feat: add Google OAuth"

Running detect-secrets hook...
❌ Potential secret detected:
  File: backend/settings.py
  Line: 67
  Type: Secret Keyword
  Secret: GOOGLE_OAUTH2_CLIENT_SECRET = "abc123xyz..."

❌ Hook failed
```

**Result:** Commit blocked, secret must be moved to .env file.

## Integration with CI/CD

Pre-commit hooks run locally, but you should also run them in CI:

```yaml
# .github/workflows/pre-commit.yml
name: Pre-commit Checks

on: [push, pull_request]

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install pre-commit
        run: pip install pre-commit
      - name: Run pre-commit
        run: pre-commit run --all-files
```

This ensures:
- Hooks can't be bypassed with `--no-verify`
- All commits are validated before merge
- Team-wide enforcement of security standards

## Best Practices

### DO:
✅ Run `pre-commit run --all-files` before creating PR
✅ Update hooks monthly: `pre-commit autoupdate`
✅ Mark false positives in `.secrets.baseline`
✅ Use obvious placeholders in documentation
✅ Keep .env.example updated with placeholders
✅ Fix hook failures immediately, don't skip

### DON'T:
❌ Use `--no-verify` except for emergencies
❌ Commit CLAUDE.md or .env files
❌ Ignore secret detection warnings
❌ Use real API keys in .env.example
❌ Disable hooks permanently
❌ Skip security checks to "save time"

## Performance Optimization

### Speed up hook execution:

```bash
# Only run hooks on changed files (default)
git commit -m "message"

# Run hooks in parallel (faster)
# Already configured in .pre-commit-config.yaml

# Cache hook environments (pre-commit does this automatically)
# Speeds up subsequent runs significantly
```

### Typical execution times:

- **First run:** 30-60 seconds (installs hook environments)
- **Subsequent runs:** 5-15 seconds (cached environments)
- **Small commits:** 1-3 seconds (only changed files)

## Reference

### Complete Hook List

| Hook | Type | Blocks Commit? | Purpose |
|------|------|----------------|---------|
| detect-secrets | Security | ✅ Yes | Detect secrets in code |
| block-claude-md | Security | ✅ Yes | Prevent CLAUDE.md commit (Issue #1) |
| block-env-files | Security | ✅ Yes | Prevent .env commit |
| scan-api-keys | Security | ⚠️  Warns | Detect API key patterns |
| scan-django-secrets | Security | ⚠️  Warns | Detect Django secrets |
| verify-gitignore | Security | ✅ Yes | Verify .gitignore patterns |
| black | Quality | 🔧 Fixes | Format Python code |
| flake8 | Quality | ✅ Yes | Lint Python code |
| isort | Quality | 🔧 Fixes | Sort Python imports |
| eslint | Quality | ✅ Yes | Lint JavaScript/React |
| markdownlint | Quality | 🔧 Fixes | Format Markdown |
| check-added-large-files | Git | ✅ Yes | Prevent large files |
| check-merge-conflict | Git | ✅ Yes | Detect conflicts |
| no-commit-to-branch | Git | ✅ Yes | Protect main/master |
| trailing-whitespace | Git | 🔧 Fixes | Remove whitespace |
| end-of-file-fixer | Git | 🔧 Fixes | Add final newline |
| detect-private-key | Security | ✅ Yes | Detect private keys |

### Configuration Files

- `.pre-commit-config.yaml` - Hook configuration
- `.secrets.baseline` - Known secrets (false positives)
- `.gitignore` - Files to exclude from git

### Resources

- **Pre-commit docs:** https://pre-commit.com/
- **detect-secrets:** https://github.com/Yelp/detect-secrets
- **Issue #1 analysis:** `backend/docs/development/SECURITY_PATTERNS_CODIFIED.md`
- **Security incident:** `backend/docs/development/SECURITY_INCIDENT_2025_10_23_API_KEYS.md`

## Support

**Questions?** Ask in team chat or create GitHub issue.

**Found a bug in hooks?** Update `.pre-commit-config.yaml` and submit PR.

**Need to bypass for emergency?** Discuss with team lead first.

---

**Remember:** These hooks exist to prevent Issue #1 from happening again. Taking 5 seconds to let hooks run is better than spending hours fixing a security incident.

**Setup Status:** After completing this guide, add to team documentation that pre-commit hooks are REQUIRED for all developers.
