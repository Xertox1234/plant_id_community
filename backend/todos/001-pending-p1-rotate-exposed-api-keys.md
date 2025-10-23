---
status: pending
priority: p1
issue_id: "001"
tags: [security, api-keys, critical]
dependencies: []
---

# Rotate Exposed API Keys (CRITICAL)

## Problem Statement

API keys are hardcoded in `/backend/.env` file and may have been committed to git history, exposing:
- `PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4`
- `PLANTNET_API_KEY=2b10XCJNMzrPYiojVsddjK0n`
- `SECRET_KEY=django-insecure-dev-key-change-in-production-2024`
- `JWT_SECRET_KEY=jwt-dev-secret-change-in-production-2024`

**Impact:**
- If .env is in git history, anyone with repo access can exhaust API quota
- Potential financial impact if paid API tiers are used
- JWT tokens can be forged, bypassing authentication entirely

## Findings

- Discovered during security audit by security-sentinel agent
- Location: `/backend/.env` (multiple lines)
- Risk: If repository is public or credentials leaked, API quota can be exhausted

## Proposed Solutions

### Option 1: Immediate Key Rotation (RECOMMENDED)
- **Pros**: Invalidates compromised keys immediately
- **Cons**: Requires updating production environment variables
- **Effort**: Small (30 minutes)
- **Risk**: Low (standard security practice)

**Steps:**
1. Generate new API keys:
   - Plant.id: https://plant.id/account
   - PlantNet: Contact PlantNet team
   - Django SECRET_KEY: `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`
   - JWT_SECRET_KEY: `python -c 'import secrets; print(secrets.token_urlsafe(64))'`

2. Update production environment variables (do NOT commit to git)

3. Verify .env is in .gitignore:
   ```bash
   grep "^\.env$" .gitignore
   ```

4. Check if .env was ever committed to git:
   ```bash
   git log --all --full-history -- .env
   ```

5. If found in git history, remove with git-filter-repo:
   ```bash
   pip install git-filter-repo
   git filter-repo --path .env --invert-paths --force
   ```

6. Update .env.example with placeholders (already done)

### Option 2: Use Secrets Manager (Long-term)
- **Pros**: Industry best practice, audit logging
- **Cons**: Additional infrastructure complexity
- **Effort**: Medium (4 hours for AWS Secrets Manager integration)
- **Risk**: Medium (requires AWS setup)

## Recommended Action

**IMMEDIATE:** Rotate all API keys (Option 1)
**LONG-TERM:** Migrate to AWS Secrets Manager or similar (Option 2)

## Technical Details

- **Affected Files**:
  - `/backend/.env` (contains exposed keys)
  - `/backend/.env.example` (template for developers)
  - Potentially git history (needs verification)

- **Related Components**:
  - Plant.id API integration
  - PlantNet API integration
  - Django authentication
  - JWT token generation

- **Database Changes**: No

## Resources

- Security audit report: `/backend/docs/development/SECURITY_AUDIT_REPORT.md`
- Agent report: security-sentinel (Finding #1)
- Git history check: `git log --all --full-history -- .env`

## Acceptance Criteria

- [ ] New Plant.id API key generated and tested
- [ ] New PlantNet API key generated and tested
- [ ] New Django SECRET_KEY generated (50+ characters)
- [ ] New JWT_SECRET_KEY generated (64+ characters)
- [ ] Production environment variables updated
- [ ] .env verified in .gitignore
- [ ] Git history checked for .env commits
- [ ] If found in history, .env removed with git-filter-repo
- [ ] Tests pass with new API keys

## Work Log

### 2025-10-22 - Code Review Discovery
**By:** security-sentinel agent
**Actions:**
- Discovered hardcoded API keys during comprehensive security audit
- Analyzed impact of credential exposure
- Categorized as CRITICAL priority

**Learnings:**
- Never commit .env files to version control
- Use .env.example with placeholders
- Implement secrets rotation policy (quarterly)
- Consider secrets manager for production

## Notes

**Urgency:** CRITICAL - Fix within 24 hours
**Deployment:** Requires production environment variable updates
**Testing:** Verify all API integrations work with new keys before deployment
