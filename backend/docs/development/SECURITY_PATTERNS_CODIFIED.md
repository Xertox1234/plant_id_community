# Security Patterns Codified from Issue #1 Incident

**Date:** 2025-10-23
**Source:** Security Incident - API Keys Exposed in Git History (Issue #1, PR #8)
**Status:** Patterns extracted and codified for automated detection
**Related:** `SECURITY_INCIDENT_2025_10_23_API_KEYS.md`, `KEY_ROTATION_INSTRUCTIONS.md`

## Executive Summary

This document codifies security patterns, anti-patterns, and detection rules learned from a critical security incident where API keys and secrets were inadvertently committed to the public GitHub repository. These patterns have been integrated into the `code-review-specialist` agent to prevent similar incidents in the future.

## Incident Overview

**What Happened:**
- `CLAUDE.md` file (intended for local development only) was committed to public repository
- File contained real API keys: Plant.id, PlantNet, Django SECRET_KEY, JWT_SECRET_KEY
- 12+ documentation files also contained these exposed keys
- Keys existed in git history across 5 commits since initial commit
- Repository is PUBLIC on GitHub

**Root Causes:**
1. **Local development file treated as repository file** - `CLAUDE.md` was meant to be local-only
2. **Documentation treated as "safe"** - Assumed documentation files couldn't contain secrets
3. **No secret detection** - No pre-commit hooks or automated scanning
4. **Template vs actual confusion** - Real keys used in what should have been template examples
5. **Missing .gitignore entry** - `CLAUDE.md` not excluded from version control

## Pattern Analysis: Types of Exposed Secrets

### 1. API Keys (External Services)

**Pattern Detected:**
```bash
# Plant.id API Key (50 character alphanumeric)
PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4

# PlantNet API Key (24 character alphanumeric)
PLANTNET_API_KEY=2b10XCJNMzrPYiojVsddjK0n
```

**Risk Level:** CRITICAL
- 100 requests/month limit (Plant.id) - easily exhausted
- 500 requests/day limit (PlantNet) - can be abused rapidly
- Service disruption for legitimate users
- Financial impact if free tier exceeded

**Detection Regex:**
```regex
# Plant.id pattern
PLANT_ID_API_KEY\s*=\s*[A-Za-z0-9]{40,60}

# PlantNet pattern
PLANTNET_API_KEY\s*=\s*[A-Za-z0-9]{20,30}

# Generic API key patterns
[A-Z_]+_API_KEY\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
```

### 2. Django SECRET_KEY

**Pattern Detected:**
```bash
# Development key with obvious insecure marking
SECRET_KEY=django-insecure-dev-key-change-in-production-2024
```

**Risk Level:** HIGH
- Session hijacking via forged session cookies
- CSRF token bypass (predictable token generation)
- Password reset token forgery
- Authentication bypass scenarios

**Detection Regex:**
```regex
# Django SECRET_KEY pattern (50+ chars, mixed characters)
SECRET_KEY\s*=\s*['"][A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]{40,}['"]

# Insecure development keys
SECRET_KEY\s*=\s*['"].*\b(dev|test|insecure|change|sample|example)\b.*['"]
```

### 3. JWT Secret Keys

**Pattern Detected:**
```bash
# JWT signing key
JWT_SECRET_KEY=jwt-dev-secret-key-change-in-production-2024
```

**Risk Level:** CRITICAL
- Complete authentication bypass via forged JWT tokens
- User impersonation by generating valid tokens
- Privilege escalation attacks

**Detection Regex:**
```regex
# JWT secret patterns
JWT_SECRET_KEY\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
JWT_SECRET\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
```

### 4. OAuth Credentials

**Pattern Detected (from .env.example):**
```bash
GOOGLE_OAUTH2_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_OAUTH2_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

**Risk Level:** CRITICAL
- OAuth flow bypass
- User account takeover via forged OAuth responses
- Unauthorized access to user data

**Detection Regex:**
```regex
# OAuth client secrets
[A-Z_]*CLIENT_SECRET\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
[A-Z_]*OAUTH.*SECRET\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
```

## File Type Analysis: Where Secrets Were Found

### High-Risk Files (NEVER commit these)

1. **CLAUDE.md** - Local development context file
   - Contains environment setup instructions
   - Often includes example commands with real credentials
   - **Solution:** Always in `.gitignore`, use `CLAUDE.md.example` template

2. **.env files** - Environment variables
   - `.env`, `.env.local`, `.env.production`, `.env.*.local`
   - **Solution:** MUST be in `.gitignore`, use `.env.example` as template

3. **Documentation with code examples**
   - `SETUP_COMPLETE.md`, `BACKEND_ENV_TEMPLATE.md`, `QUICK_START.md`
   - Risk: Copy-paste from actual working setup without sanitizing
   - **Solution:** Always use placeholder values, never real credentials

4. **Configuration files** - May contain embedded secrets
   - `config.json`, `settings.local.py`, `secrets.yaml`
   - **Solution:** Use environment variables, never hardcode

### Medium-Risk Files (Review carefully)

1. **Test files** - May contain test API keys
   - Risk: Test keys might be real keys "for quick testing"
   - **Solution:** Use mocked services, if real test keys needed, load from environment

2. **Migration files** - May contain database credentials
   - Risk: Development database passwords in migrations
   - **Solution:** Use environment variables in migrations

3. **Docker files** - May contain build-time secrets
   - `Dockerfile`, `docker-compose.yml`
   - Risk: ARG values with real credentials
   - **Solution:** Use secrets management, never ARG for sensitive data

## Anti-Patterns and Warning Signs

### Pattern 1: "It's just documentation"

**Anti-pattern:**
```markdown
# Quick Start Guide

Set up your environment:
```bash
export PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
export SECRET_KEY=django-insecure-dev-key-change-in-production-2024
```
```

**Why it's dangerous:**
- Documentation files ARE code files
- Search engines index public repos
- Secrets scanners find them easily
- Copy-paste culture spreads them

**Correct pattern:**
```markdown
# Quick Start Guide

Set up your environment:
```bash
export PLANT_ID_API_KEY=your-plant-id-api-key-here
export SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
```
```

### Pattern 2: Development keys are "safe"

**Anti-pattern:**
```python
# It's just a dev key, doesn't matter
SECRET_KEY = 'django-insecure-dev-key-change-in-production-2024'
JWT_SECRET_KEY = 'jwt-dev-secret-key-change-in-production-2024'
```

**Why it's dangerous:**
- Dev keys end up in production
- Demonstrates poor security practices
- Creates false sense of security
- Training developers to commit secrets

**Correct pattern:**
```python
# settings.py
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY environment variable required')

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ImproperlyConfigured('JWT_SECRET_KEY environment variable required')
```

### Pattern 3: Local-only files in repository

**Anti-pattern:**
- `CLAUDE.md` committed to repository (meant for local use only)
- Local configuration files tracked in git
- Developer-specific setup files shared

**Why it's dangerous:**
- Local files often contain real credentials from working setups
- Each developer's local config might expose different secrets
- Files meant for personal use aren't reviewed carefully

**Correct pattern:**
```gitignore
# .gitignore

# ===================================
# Development / Reference Materials
# ===================================
# Claude Code configuration and tools
.claude/

# CLAUDE.md contains project-specific context and may include sensitive info
# Use CLAUDE.md.example as template
CLAUDE.md

# Local configuration
*.local
.env.local
config.local.*
```

### Pattern 4: Template files with real values

**Anti-pattern:**
```bash
# .env.example (WRONG - contains real key!)
PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
```

**Why it's dangerous:**
- Templates get copied directly
- Real keys accidentally committed as "examples"
- Users don't realize they need to replace values

**Correct pattern:**
```bash
# .env.example (CORRECT - clear placeholders)
# Plant.id (Kindwise) - Primary identification service (100 IDs/month free)
# Get from: https://web.plant.id/
PLANT_ID_API_KEY=your-plant-id-api-key-here

# Generate with:
# python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY=your-secret-key-here
```

## Detection Rules for Automated Code Review

### Rule 1: Never commit CLAUDE.md

**Check:**
```bash
# Verify CLAUDE.md is in .gitignore
grep -q "^CLAUDE.md$" .gitignore

# Verify CLAUDE.md is not tracked in git
! git ls-files | grep -q "^CLAUDE.md$"
```

**Blocker if:**
- `CLAUDE.md` exists in git repository
- `CLAUDE.md` not listed in `.gitignore`

**Message:**
```
BLOCKER: CLAUDE.md must NEVER be committed to repository
- This file is for local development context only
- Often contains sensitive configuration and credentials
- Add to .gitignore: echo "CLAUDE.md" >> .gitignore
- Create template: CLAUDE.md.example (with placeholders only)
```

### Rule 2: Verify .env files excluded

**Check:**
```bash
# All .env patterns must be in .gitignore
grep -E "^\.env$|^\.env\.local$|^\.env\.\*\.local$" .gitignore

# No .env files should be tracked
! git ls-files | grep -E "\.env$|\.env\.local$|\.env\.production$"
```

**Blocker if:**
- Any `.env` file tracked in git (except `.env.example`)
- `.env` patterns missing from `.gitignore`

**Message:**
```
BLOCKER: .env files MUST NOT be committed to repository
- Found tracked .env file(s): {files}
- Remove from git: git rm --cached {file}
- Verify .gitignore contains: .env, .env.local, .env.*.local
```

### Rule 3: Scan for API key patterns in committed files

**Check:**
```bash
# Scan all modified files for API key patterns
git diff --cached --name-only | while read file; do
    if [[ -f "$file" ]]; then
        # Check for common API key patterns
        grep -E "[A-Z_]+_API_KEY\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]" "$file" && echo "WARN: $file"
        grep -E "SECRET_KEY\s*=\s*['\"][A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]{40,}['\"]" "$file" && echo "WARN: $file"
        grep -E "JWT_SECRET.*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]" "$file" && echo "WARN: $file"
    fi
done
```

**Warning if:**
- File contains pattern matching real API keys
- File is not `.env.example` or similar template

**Message:**
```
WARNING: Possible API key or secret detected in: {file}:{line}
- Pattern: {pattern_matched}
- Verify this is a placeholder value, not a real credential
- Real credentials MUST be in .env file (excluded from git)
- Template files MUST use obvious placeholders: "your-api-key-here"
```

### Rule 4: Verify .env.example uses placeholders

**Check:**
```bash
# .env.example should have placeholder patterns
grep -E "your-.*-key-here|your-.*-secret-here|<.*>|TODO|CHANGE|REPLACE" backend/.env.example

# Should have generation instructions
grep -E "Generate with:|Get from:|https://" backend/.env.example
```

**Warning if:**
- `.env.example` contains what looks like real keys (20+ alphanumeric chars)
- Missing generation instructions for SECRET_KEY, JWT_SECRET_KEY

**Message:**
```
WARNING: .env.example may contain real credentials
- Use clear placeholders: "your-plant-id-api-key-here"
- Add generation instructions:
  # Generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
  SECRET_KEY=your-secret-key-here
```

### Rule 5: Check documentation files for secrets

**Check:**
```bash
# Scan markdown files for potential secrets in code blocks
find . -name "*.md" -type f ! -path "./.git/*" | while read file; do
    # Extract bash/shell code blocks and scan for patterns
    awk '/```bash/,/```/ {print}' "$file" | \
        grep -E "(API_KEY|SECRET_KEY|PASSWORD|TOKEN)\s*=\s*[A-Za-z0-9]{20,}" && \
        echo "WARN: Potential secret in $file"
done
```

**Warning if:**
- Documentation contains code examples with long alphanumeric values
- Setup guides show export commands with real-looking credentials

**Message:**
```
WARNING: Documentation file contains potential secrets: {file}
- Code examples must use placeholders, not real credentials
- Replace: PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8...
- With: PLANT_ID_API_KEY=your-plant-id-api-key-here
- Add comment: "# Get from: https://web.plant.id/"
```

### Rule 6: OAuth credentials pattern detection

**Check:**
```bash
# Look for OAuth client secrets
grep -rE "CLIENT_SECRET\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]" \
    --include="*.py" --include="*.js" --include="*.ts" --include="*.md" .
```

**Blocker if:**
- OAuth client secret found in any committed file
- Pattern doesn't look like obvious placeholder

**Message:**
```
BLOCKER: OAuth client secret detected in: {file}:{line}
- OAuth credentials MUST be environment variables only
- Remove from code: git rm --cached {file}
- Move to .env file (not committed to git)
- Use: os.environ.get('GOOGLE_OAUTH2_CLIENT_SECRET')
```

## Prevention Measures

### Immediate Actions (Completed in PR #8)

- [x] Add `CLAUDE.md` to `.gitignore`
- [x] Remove `CLAUDE.md` from repository
- [x] Update `.env.example` with clear placeholders
- [x] Add key generation instructions to `.env.example`
- [x] Verify no `.env` files tracked in git
- [x] Document security incident
- [x] Create key rotation instructions for users

### Short-term (Within 1 Week)

- [ ] **Pre-commit hook for secret detection**
  - Install: `pip install pre-commit detect-secrets`
  - Configure: `.pre-commit-config.yaml`
  - Scan: All files before commit

- [ ] **GitHub secret scanning**
  - Enable: Repository Settings > Security > Secret Scanning
  - Alert: Immediate notification on secret detection
  - Free: For public repositories

- [ ] **Update code-review-specialist agent**
  - Add: Secret detection patterns (completed in this PR)
  - Test: Verify agent catches secrets in test commits

- [ ] **CI/CD secret validation**
  - Add step: Scan for secrets in CI pipeline
  - Fail build: If secrets detected
  - Tools: `trufflehog`, `gitleaks`, `detect-secrets`

### Long-term (Within 1 Month)

- [ ] **Secrets management system**
  - Implement: AWS Secrets Manager, HashiCorp Vault, or Doppler
  - Rotate: Keys quarterly
  - Audit: Track secret access

- [ ] **Developer education**
  - Training: Secure coding practices
  - Checklists: Pre-commit security review
  - Documentation: Security best practices guide

- [ ] **Quarterly key rotation policy**
  - Schedule: Rotate all API keys quarterly
  - Document: Rotation procedures
  - Automate: Where possible

## Testing the Detection Rules

### Test Case 1: Detect CLAUDE.md in commit

```bash
# Test: Should be blocked
echo "PLANT_ID_API_KEY=W3YvEk2rx..." > CLAUDE.md
git add CLAUDE.md
git commit -m "test"  # Should fail with BLOCKER

# Expected: BLOCKER - CLAUDE.md must not be committed
```

### Test Case 2: Detect .env file in commit

```bash
# Test: Should be blocked
echo "SECRET_KEY=real-secret-key-here" > backend/.env
git add backend/.env
git commit -m "test"  # Should fail with BLOCKER

# Expected: BLOCKER - .env files must not be committed
```

### Test Case 3: Detect API keys in documentation

```bash
# Test: Should warn
echo "export PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa..." > README.md
git add README.md
git commit -m "test"  # Should warn

# Expected: WARNING - Possible API key detected in README.md
```

### Test Case 4: Allow placeholder values

```bash
# Test: Should pass
echo "PLANT_ID_API_KEY=your-plant-id-api-key-here" > .env.example
git add .env.example
git commit -m "test"  # Should pass

# Expected: ✅ APPROVED - Placeholder detected
```

## Implementation in code-review-specialist Agent

The following patterns have been added to the `code-review-specialist` agent configuration:

### New Section: "Secret Detection and .gitignore Verification"

1. **Check for CLAUDE.md in commits** (BLOCKER)
2. **Check for .env files in commits** (BLOCKER)
3. **Scan for API key patterns** (WARNING/BLOCKER)
4. **Verify .env.example uses placeholders** (WARNING)
5. **Check documentation for secrets** (WARNING)
6. **OAuth credentials detection** (BLOCKER)

See updated `/.claude/agents/code-review-specialist.md` for complete implementation.

## Key Lessons Learned

### 1. Documentation files ARE code files
- Treat markdown files with same security rigor as source code
- Code examples in docs often contain copy-pasted real credentials
- Search engines and scrapers index documentation

### 2. Local-only files need explicit exclusion
- `CLAUDE.md` meant for local use must be in `.gitignore`
- Create template versions (`.example`) for sharing
- Local files often contain working credentials

### 3. "Development" doesn't mean "insecure"
- Development keys set precedent for production practices
- Train developers to never commit secrets, even in dev
- Use environment variables from day one

### 4. Templates need obvious placeholders
- "your-api-key-here" is better than "test-key-123"
- Include URLs for where to get real keys
- Add generation commands for secret keys

### 5. Automation is critical
- Pre-commit hooks catch secrets before they enter git
- Manual review is not sufficient
- GitHub secret scanning provides additional safety net

### 6. .gitignore is a security control
- Regularly review .gitignore for completeness
- Add high-risk file patterns proactively
- Include comments explaining why files are excluded

## References

- **This Incident:** Issue #1, PR #8
- **Related Docs:**
  - `SECURITY_INCIDENT_2025_10_23_API_KEYS.md` - Incident details
  - `KEY_ROTATION_INSTRUCTIONS.md` - User remediation steps
- **OWASP:** [Hard-coded Credentials (CWE-798)](https://cwe.mitre.org/data/definitions/798.html)
- **NIST:** [SP 800-53 IA-5: Authenticator Management](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
- **Tools:**
  - [pre-commit](https://pre-commit.com/) - Git hook framework
  - [detect-secrets](https://github.com/Yelp/detect-secrets) - Secret scanning
  - [gitleaks](https://github.com/gitleaks/gitleaks) - Git secret scanner
  - [trufflehog](https://github.com/trufflesecurity/trufflehog) - Secret discovery

## Appendix: Complete Secret Patterns

```regex
# API Keys (generic)
[A-Z_]+_API_KEY\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
[A-Z_]+_API_TOKEN\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]

# Plant.id specific
PLANT_ID_API_KEY\s*=\s*[A-Za-z0-9]{40,60}

# PlantNet specific
PLANTNET_API_KEY\s*=\s*[A-Za-z0-9]{20,30}

# Django SECRET_KEY
SECRET_KEY\s*=\s*['"][A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]{40,}['"]

# JWT secrets
JWT_SECRET(_KEY)?\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]

# OAuth
[A-Z_]*CLIENT_SECRET\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
[A-Z_]*OAUTH.*SECRET\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]

# AWS
AWS_SECRET_ACCESS_KEY\s*=\s*['"][A-Za-z0-9+/]{40}['"]

# Database URLs with passwords
DATABASE_URL\s*=\s*['"].*://[^:]+:([^@]{8,})@.*['"]

# Private keys
-----BEGIN (RSA |EC )?PRIVATE KEY-----
```

---

**Document Status:** Complete
**Last Updated:** 2025-10-23
**Next Review:** When new secret types are identified or detection rules need updating
