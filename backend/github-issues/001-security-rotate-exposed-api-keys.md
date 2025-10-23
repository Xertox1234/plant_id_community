# security: Rotate exposed API keys and remove from git history

## Overview

🔴 **CRITICAL** - API keys for Plant.id, PlantNet, Django SECRET_KEY, and JWT_SECRET_KEY are hardcoded in `.env` file and may exist in git repository history, exposing them to anyone with repository access.

**Severity:** CRITICAL (CVSS 7.5 - HIGH)
**Category:** Security / CWE-798 (Hard-coded Credentials)
**Impact:** API quota exhaustion, authentication bypass, potential financial loss
**Timeline:** Fix within 24-48 hours (CISA BOD 19-02)

## Problem Statement / Motivation

**Current State:**
The `.env` file contains production API keys in plaintext:
```bash
PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
PLANTNET_API_KEY=2b10XCJNMzrPYiojVsddjK0n
SECRET_KEY=django-insecure-dev-key-change-in-production-2024
JWT_SECRET_KEY=jwt-dev-secret-change-in-production-2024
```

**Risk Scenario:**
1. If `.env` was ever committed to git, keys are in repository history
2. Repository is **PUBLIC** (github.com/Xertox1234/plant_id_community)
3. Anyone with access can:
   - Exhaust Plant.id API quota (100 requests/month free tier)
   - Exhaust PlantNet API quota (500 requests/day)
   - Forge Django session cookies (authentication bypass)
   - Generate valid JWT tokens (complete authentication bypass)

**Why This Matters:**
- Plant.id free tier: 100 identifications/month (can be exhausted in hours)
- PlantNet free tier: 500 identifications/day (can be exhausted in minutes)
- Django SECRET_KEY compromise: Complete authentication bypass, session hijacking
- Public repository means keys are accessible to anyone

## Proposed Solution

**Immediate Actions (User Required - 30 minutes):**

### Step 1: Generate New API Keys

```bash
# 1. Plant.id API Key
# Visit: https://plant.id/account
# Navigate to: API Keys → Generate New Key
# Save the new key (will only be shown once)

# 2. PlantNet API Key
# Contact PlantNet team or use existing key rotation process
# If unavailable, proceed with other keys and schedule PlantNet rotation

# 3. Django SECRET_KEY (50+ characters, cryptographically secure)
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# 4. JWT_SECRET_KEY (64+ characters, cryptographically secure)
python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

### Step 2: Update Production Environment Variables

```bash
# DO NOT commit these to git!
# Update production environment (Heroku/AWS/etc.)
export PLANT_ID_API_KEY="new_key_here"
export PLANTNET_API_KEY="new_key_here"
export SECRET_KEY="new_django_secret_key_here"
export JWT_SECRET_KEY="new_jwt_secret_key_here"
```

### Step 3: Verify Keys Work

```bash
cd backend
source venv/bin/activate

# Test Plant.id API with new key
curl -X POST https://plant.id/api/v3/health_assessment \
  -H "Api-Key: NEW_PLANT_ID_KEY" \
  -d '{"images": ["data:image/jpeg;base64,..."]}'

# Test Django with new SECRET_KEY
python manage.py check --deploy

# Start development server and verify authentication works
python manage.py runserver
```

### Step 4: Check Git History for Exposed Keys

```bash
# Check if .env was ever committed
git log --all --full-history -- .env
git log --all --full-history -- backend/.env

# Search for API keys in entire git history
git log --all -p | grep -E "PLANT_ID_API_KEY|PLANTNET_API_KEY|SECRET_KEY" | head -20
```

### Step 5: Remove Keys from Git History (If Found)

⚠️ **WARNING:** This rewrites git history - coordinate with team first!

```bash
# Install git-filter-repo (preferred over git filter-branch)
pip install git-filter-repo

# Backup repository first!
cd ..
cp -r plant_id_community plant_id_community.backup

cd plant_id_community

# Remove .env file from entire history
git filter-repo --path backend/.env --invert-paths --force

# Remove .env from root if it existed there too
git filter-repo --path .env --invert-paths --force

# Force push to origin (ALL team members must re-clone)
git push origin --force --all
git push origin --force --tags
```

### Step 6: Update .env.example

```bash
# File: backend/.env.example
PLANT_ID_API_KEY=your_plant_id_api_key_here
PLANTNET_API_KEY=your_plantnet_api_key_here
SECRET_KEY=generate_with_django_get_random_secret_key
JWT_SECRET_KEY=generate_with_secrets_token_urlsafe_64

# Add generation instructions
echo "# Generate SECRET_KEY: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'" >> backend/.env.example
echo "# Generate JWT_SECRET_KEY: python -c 'import secrets; print(secrets.token_urlsafe(64))'" >> backend/.env.example
```

### Step 7: Verify .gitignore

```bash
# Ensure .env is in .gitignore
grep "^\.env$" backend/.gitignore || echo ".env" >> backend/.gitignore
grep "^\.env\.local$" backend/.gitignore || echo ".env.local" >> backend/.gitignore

# Verify .env is not tracked
git ls-files | grep "\.env$"
# Should return nothing (empty output)
```

## Technical Considerations

**Security:**
- Rotating keys invalidates all existing API clients using old keys
- Django SECRET_KEY rotation requires users to re-authenticate (sessions invalidated)
- JWT_SECRET_KEY rotation invalidates all existing JWT tokens

**Backwards Compatibility:**
- Django 4.1+ supports `SECRET_KEY_FALLBACKS` for zero-downtime rotation:
  ```python
  # settings.py
  SECRET_KEY = config('SECRET_KEY')
  SECRET_KEY_FALLBACKS = [config('OLD_SECRET_KEY')] if config('OLD_SECRET_KEY', default=None) else []
  ```
- Remove fallback after all users re-authenticated (24-48 hours)

**Git History Cleanup:**
- `git filter-repo` rewrites commit SHAs - all team members must `git clone` fresh copy
- Alternative: GitHub Security Advisories for private disclosure (repo must be private first)
- Consider rotating to private repository for sensitive projects

## Acceptance Criteria

**Critical (Must Complete):**
- [ ] New Plant.id API key generated and tested
- [ ] New PlantNet API key generated and tested (or scheduled if unavailable)
- [ ] New Django SECRET_KEY generated (50+ characters)
- [ ] New JWT_SECRET_KEY generated (64+ characters)
- [ ] Production environment variables updated with new keys
- [ ] All API integrations tested with new keys (Plant.id, PlantNet)
- [ ] Django authentication tested (login, session management)
- [ ] JWT token generation/validation tested

**Git History Cleanup:**
- [ ] Git history checked for `.env` commits: `git log --all --full-history -- .env`
- [ ] If found: `.env` removed from git history with `git filter-repo`
- [ ] If found: Force push completed, team notified to re-clone
- [ ] `.env` verified in `.gitignore`
- [ ] `git ls-files` confirms `.env` not tracked

**Documentation:**
- [ ] `.env.example` updated with placeholders and generation instructions
- [ ] Security incident documented in `/backend/docs/development/SECURITY_INCIDENTS.md`
- [ ] Key rotation procedure documented for future reference
- [ ] Team notified of key rotation and re-authentication requirements

## Success Metrics

**Immediate (Within 24 hours):**
- ✅ No hardcoded API keys in repository (code or history)
- ✅ All API integrations work with new keys
- ✅ Zero authentication errors in production logs

**Long-term (Within 30 days):**
- 📋 Implement secrets management (AWS Secrets Manager, HashiCorp Vault)
- 📋 Quarterly key rotation policy established
- 📋 Monitoring for unusual API usage patterns (quota exhaustion detection)

## Dependencies & Risks

**Dependencies:**
- Access to Plant.id account for key generation
- Access to PlantNet account for key generation
- Production environment access for updating variables
- Team coordination for git history rewrite (if needed)

**Risks:**
- **High:** If keys already leaked, malicious actors may have copied them
  - **Mitigation:** Monitor API usage logs for suspicious activity
  - **Mitigation:** Enable rate limiting (already implemented in Quick Win #1)

- **Medium:** Git history rewrite requires team re-clone
  - **Mitigation:** Schedule during low-activity period
  - **Mitigation:** Notify team 24 hours in advance
  - **Mitigation:** Create backup before rewrite

- **Low:** Temporary downtime during key rotation
  - **Mitigation:** Use `SECRET_KEY_FALLBACKS` for zero-downtime rotation
  - **Mitigation:** Test in staging environment first

## References & Research

### Internal References
- **Code Review Finding:** security-sentinel agent (Finding #1)
- **Security Audit:** `/backend/docs/development/SECURITY_AUDIT_REPORT.md`
- **Week 3 Quick Wins:** `/backend/docs/quick-wins/authentication.md`
- **Environment Config:** `/backend/plant_community_backend/settings.py:34`
- **`.env` file:** `/backend/.env` (DO NOT COMMIT)

### External References
- **Django SECRET_KEY Security:** https://docs.djangoproject.com/en/5.2/ref/settings/#secret-key
- **Django Key Rotation:** https://adamj.eu/tech/2023/06/12/django-secret-key-rotation/
- **OWASP Hard-coded Credentials:** https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password
- **CISA BOD 19-02:** https://www.cisa.gov/news-events/directives/bod-19-02
- **CWE-798:** https://cwe.mitre.org/data/definitions/798.html
- **git-filter-repo:** https://github.com/newren/git-filter-repo

### Related Work
- **Git commit:** b4819df (Week 3 Quick Wins implementation)
- **Security incident:** SECURITY_INCIDENT_API_KEYS.md (Week 1 documented previous exposure)

---

**Created:** 2025-10-22
**Priority:** 🔴 CRITICAL
**Assignee:** @williamtower
**Labels:** `priority: critical`, `type: security`, `area: backend`, `week-3`, `code-review`
**Estimated Effort:** 30 minutes (user actions) + 2 hours (if git history cleanup needed)
