# Security Quick Reference - Issue #1 Prevention

**Purpose:** Quick reference card for developers to avoid Issue #1 type incidents
**Time to read:** 2 minutes
**Related:** PRE_COMMIT_SETUP.md, SECURITY_PATTERNS_CODIFIED.md

## Files You Should NEVER Commit

### 1. CLAUDE.md (BLOCKER)
❌ **Never commit** - This is a local development file only
✅ **Instead:** Use CLAUDE.md.example as template
**Why:** Contains real API keys and sensitive context
**Check:** `git ls-files | grep CLAUDE.md` (should be empty)

### 2. .env Files (BLOCKER)
❌ **Never commit** - .env, .env.local, .env.production
✅ **Instead:** Use .env.example with placeholders
**Why:** Contains production secrets and credentials
**Check:** `grep "^.env$" .gitignore` (should exist)

### 3. config.local.* (WARNING)
❌ **Avoid committing** - Local configuration files
✅ **Instead:** Use config.example.* templates
**Why:** May contain developer-specific credentials

## Placeholders vs Real Values

### ❌ WRONG - Real Values
```bash
# DON'T DO THIS
PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
SECRET_KEY=django-insecure-dev-key-change-in-production-2024
```

### ✅ CORRECT - Placeholders
```bash
# DO THIS
# Plant.id API Key - Get from: https://web.plant.id/
PLANT_ID_API_KEY=your-plant-id-api-key-here

# Django Secret Key - Generate with:
# python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY=your-secret-key-here
```

## Quick Checks Before Committing

```bash
# 1. Check what you're committing
git status

# 2. Verify CLAUDE.md not staged
git diff --cached --name-only | grep CLAUDE.md
# Should be empty

# 3. Verify no .env files staged
git diff --cached --name-only | grep "\.env$" | grep -v "\.env\.example"
# Should be empty

# 4. Scan for API key patterns (manual check)
git diff --cached | grep -E "API_KEY.*=.*[A-Za-z0-9]{20,}"
# Should only show placeholders

# 5. Run pre-commit hooks (if installed)
git commit -m "message"
# Hooks will catch issues automatically
```

## Common Mistakes and Fixes

### Mistake 1: "It's just documentation"
**Problem:** Real API keys in README.md, SETUP.md
**Fix:** Use placeholders with generation instructions
**Example:**
```markdown
❌ export PLANT_ID_API_KEY=W3YvEk2rx...
✅ export PLANT_ID_API_KEY=your-api-key-here
   # Get from: https://web.plant.id/
```

### Mistake 2: "It's just a dev key"
**Problem:** Development keys committed because "not production"
**Fix:** Use environment variables for ALL keys, even dev
**Example:**
```python
❌ SECRET_KEY = 'dev-key-123'
✅ SECRET_KEY = os.environ.get('SECRET_KEY')
```

### Mistake 3: "Template with real value"
**Problem:** .env.example has real key "as example"
**Fix:** Always use obvious placeholders
**Example:**
```bash
❌ PLANT_ID_API_KEY=test_W3YvEk2rx...
✅ PLANT_ID_API_KEY=your-plant-id-api-key-here
```

### Mistake 4: "Local file accidentally added"
**Problem:** CLAUDE.md added with `git add .`
**Fix:** Add to .gitignore immediately
**Example:**
```bash
# Check if CLAUDE.md in .gitignore
grep "^CLAUDE.md$" .gitignore

# If not, add it
echo "CLAUDE.md" >> .gitignore
```

## Emergency: I Committed a Secret

### Step 1: Don't Panic
**If not pushed yet:**
```bash
# Undo last commit, keep changes
git reset --soft HEAD~1

# Remove secret from file
# Edit file, replace secret with placeholder

# Stage changes
git add file.py

# Commit again (correctly)
git commit -m "fix: update configuration"
```

**If already pushed:**
1. **Immediately rotate the secret** (most important!)
2. Report to security team
3. Follow KEY_ROTATION_INSTRUCTIONS.md
4. Consider git history rewrite (coordinate with team)

### Step 2: Rotate the Secret
```bash
# For API keys: Visit provider website, revoke old key, generate new
# For Django SECRET_KEY:
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# For JWT_SECRET_KEY:
python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

### Step 3: Update .env File
```bash
# Update local .env file (NOT committed)
vim backend/.env
# Replace old secret with new secret

# Verify it works
python manage.py runserver
```

## Pre-commit Hooks (5 Minute Setup)

**Prevents Issue #1 automatically:**

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
cd /path/to/project
pre-commit install

# Test
pre-commit run --all-files

# Now hooks run automatically on every commit
```

**What gets blocked:**
- ✅ CLAUDE.md commits
- ✅ .env file commits
- ✅ API key patterns
- ✅ OAuth secrets
- ✅ Django SECRET_KEY patterns

**See:** PRE_COMMIT_SETUP.md for complete guide

## Critical .gitignore Entries

**These MUST be in .gitignore:**

```gitignore
# Environment & Secrets
.env
.env.local
.env.*.local
*.key
*.pem
secrets/

# Local Development
CLAUDE.md

# Configuration
config.local.*
settings.local.py
```

**Verify:**
```bash
# Check critical patterns present
grep -E "^(CLAUDE.md|\.env|\.env\.local)$" .gitignore
```

## What to Do in Code Review

**As Author:**
- [ ] Verify no secrets in diff: `git diff main...HEAD | grep -i "api_key\|secret"`
- [ ] Check .gitignore updated if new secret types added
- [ ] Verify .env.example uses placeholders
- [ ] Run pre-commit hooks: `pre-commit run --all-files`

**As Reviewer:**
- [ ] Scan for API_KEY, SECRET, PASSWORD in changes
- [ ] Verify documentation uses placeholders
- [ ] Check no CLAUDE.md or .env files in PR
- [ ] Ensure new secrets have generation instructions

## Resources

**Quick Setup:**
- PRE_COMMIT_SETUP.md - Install hooks (5 minutes)

**Comprehensive:**
- SECURITY_PATTERNS_CODIFIED.md - Complete analysis
- ISSUE_1_LESSONS_LEARNED_SUMMARY.md - Full summary

**Incident Details:**
- SECURITY_INCIDENT_2025_10_23_API_KEYS.md
- KEY_ROTATION_INSTRUCTIONS.md

**Code Review Agent:**
- /.claude/agents/code-review-specialist.md - Now includes secret detection

## Quick Decision Tree

```
Are you about to commit a file?
│
├─ Is it named CLAUDE.md?
│  └─ YES → ❌ STOP - Add to .gitignore, never commit
│
├─ Does filename match *.env (except .env.example)?
│  └─ YES → ❌ STOP - Add to .gitignore, never commit
│
├─ Does it contain API_KEY=<long string>?
│  ├─ In .env.example → ✅ OK if placeholder
│  └─ In other files → ❌ STOP - Move to .env file
│
├─ Does it contain SECRET_KEY=<long string>?
│  ├─ In .env.example → ✅ OK if placeholder
│  └─ In other files → ❌ STOP - Move to .env file
│
├─ Is it a config.local.* file?
│  └─ YES → ⚠️  WARNING - Consider using .example template
│
└─ Otherwise → ✅ Proceed with commit
```

## Remember

**3 Simple Rules:**
1. **NEVER commit CLAUDE.md** (local file only)
2. **NEVER commit .env files** (use .env.example)
3. **ALWAYS use placeholders** in documentation and examples

**Before Every Commit:**
- Check `git status` for CLAUDE.md, .env
- Verify placeholders in changes
- Let pre-commit hooks run (if installed)

**5 seconds of checking > hours of incident response**

---

**Questions?** See PRE_COMMIT_SETUP.md or SECURITY_PATTERNS_CODIFIED.md
**Emergency?** Rotate secret first, report second, clean up third
