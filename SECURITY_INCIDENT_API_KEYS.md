# SECURITY INCIDENT: Exposed API Keys

**Date Discovered**: 2025-10-22
**Severity**: CRITICAL (CVSS 9.1)
**Status**: REQUIRES IMMEDIATE ACTION

---

## Summary

API keys for Plant.id and PlantNet services were inadvertently committed to the git repository in `.env` files. These keys are now exposed in git history and must be rotated immediately.

## Exposed Credentials

**Plant.id API Key**: `W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4`
**PlantNet API Key**: `2b10XCJNMzrPYiojVsddjK0n`

**Affected Files**:
- `/backend/.env`
- `/existing_implementation/backend/.env`

**Git Commits**: Multiple commits contain these credentials in history

---

## IMMEDIATE ACTIONS REQUIRED (Complete Within 24 Hours)

### Step 1: Revoke Exposed API Keys

**Plant.id (Kindwise)**:
1. Log in to https://web.plant.id/
2. Navigate to API Settings
3. Revoke API key: `W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4`
4. Generate new API key
5. Store new key securely (see Step 4)

**PlantNet**:
1. Log in to https://my.plantnet.org/
2. Navigate to API Keys section
3. Revoke API key: `2b10XCJNMzrPYiojVsddjK0n`
4. Generate new API key
5. Store new key securely (see Step 4)

### Step 2: Remove .env Files from Git Tracking

```bash
# Navigate to project root
cd /Users/williamtower/projects/plant_id_community

# Remove .env files from git tracking (keeps local files)
git rm --cached backend/.env
git rm --cached existing_implementation/backend/.env

# Commit the removal
git commit -m "security: remove .env files from git tracking

SECURITY INCIDENT: API keys were exposed in git history.
- Removed backend/.env from tracking
- Removed existing_implementation/backend/.env from tracking
- Keys will be rotated separately
- See SECURITY_INCIDENT_API_KEYS.md for details"
```

### Step 3: Update .gitignore

```bash
# Ensure .env files are ignored
echo "" >> .gitignore
echo "# Environment variables (contains secrets)" >> .gitignore
echo "*.env" >> .gitignore
echo ".env.*" >> .gitignore
echo "!.env.example" >> .gitignore

git add .gitignore
git commit -m "security: update .gitignore to prevent .env exposure"
```

### Step 4: Securely Store New API Keys

**Option A: Environment Variables (Development)**
```bash
# Create .env file (NOT committed to git)
cat > backend/.env << 'EOF'
# Django settings
SECRET_KEY=your-new-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///plant_id.db

# Redis
REDIS_URL=redis://127.0.0.1:6379/1

# Plant Identification APIs (ROTATE THESE KEYS)
PLANT_ID_API_KEY=YOUR_NEW_PLANT_ID_KEY_HERE
PLANTNET_API_KEY=YOUR_NEW_PLANTNET_KEY_HERE

# OAuth (if configured)
GOOGLE_OAUTH2_CLIENT_ID=
GOOGLE_OAUTH2_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
EOF

# Set restrictive permissions
chmod 600 backend/.env
```

**Option B: System Environment Variables (Production)**
```bash
# Set in production environment (Heroku, AWS, etc.)
export PLANT_ID_API_KEY="your_new_key_here"
export PLANTNET_API_KEY="your_new_key_here"
```

**Option C: Secrets Manager (Recommended for Production)**
- AWS Secrets Manager
- HashiCorp Vault
- Google Secret Manager
- Azure Key Vault

### Step 5: Purge Git History (Optional but Recommended)

⚠️ **WARNING**: This rewrites git history and requires force push. Coordinate with team.

```bash
# Install BFG Repo-Cleaner
brew install bfg  # macOS
# OR download from https://rtyley.github.io/bfg-repo-cleaner/

# Backup repository first
cd /Users/williamtower/projects/plant_id_community
git clone --mirror . ../plant_id_community_backup.git

# Remove .env files from all history
bfg --delete-files '*.env' --no-blob-protection

# Clean up and force push
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (⚠️ coordinate with team first)
git push --force --all
```

---

## VERIFICATION STEPS

After completing the above steps, verify:

### 1. Old Keys No Longer Work
```bash
# Test old Plant.id key (should fail)
curl -X POST "https://plant.id/api/v3/identification" \
  -H "Api-Key: W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4" \
  -H "Content-Type: application/json"
# Expected: 401 Unauthorized or API key invalid

# Test old PlantNet key (should fail)
curl "https://my-api.plantnet.org/v2/identify/all?api-key=2b10XCJNMzrPYiojVsddjK0n"
# Expected: 401 Unauthorized or invalid API key
```

### 2. New Keys Work
```bash
# Test new Plant.id key
curl -X POST "https://plant.id/api/v3/identification" \
  -H "Api-Key: YOUR_NEW_KEY" \
  -H "Content-Type: application/json"
# Expected: 200 OK or valid API response

# Test new PlantNet key
curl "https://my-api.plantnet.org/v2/identify/all?api-key=YOUR_NEW_KEY"
# Expected: 200 OK or valid API response
```

### 3. .env Files Not in Git
```bash
git status
# Should NOT show .env files as tracked

git log --all --full-history -- "*/.env"
# Should show removal commit, not the actual .env content
```

---

## PREVENTION MEASURES

### 1. Pre-commit Hook

Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Prevent committing .env files

if git diff --cached --name-only | grep -E '\.env$|\.env\..*$'; then
  echo "ERROR: Attempting to commit .env file(s)!"
  echo "These files contain secrets and should never be committed."
  echo ""
  echo "To fix:"
  echo "  git reset HEAD <file>"
  echo "  Add file to .gitignore"
  exit 1
fi
```

```bash
chmod +x .git/hooks/pre-commit
```

### 2. .env.example Template

Create `backend/.env.example` (safe to commit):
```bash
# Django settings
SECRET_KEY=change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///plant_id.db

# Redis
REDIS_URL=redis://127.0.0.1:6379/1

# Plant Identification APIs
PLANT_ID_API_KEY=get-from-https-plant-id
PLANTNET_API_KEY=get-from-https-my-plantnet-org

# OAuth
GOOGLE_OAUTH2_CLIENT_ID=your-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

### 3. Environment Variable Validation

Add to Django settings startup:
```python
# backend/settings.py or simple_server.py
import sys

REQUIRED_ENV_VARS = [
    'SECRET_KEY',
    'PLANT_ID_API_KEY',
    'PLANTNET_API_KEY',
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
    print(f"Copy backend/.env.example to backend/.env and configure")
    sys.exit(1)
```

### 4. Secrets Scanning (CI/CD)

Add to `.github/workflows/security.yml`:
```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: TruffleHog Secrets Scan
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
```

---

## INCIDENT TIMELINE

- **2025-10-22 14:00**: Codebase security scan identified exposed API keys
- **2025-10-22 14:30**: SECURITY_INCIDENT_API_KEYS.md created
- **[PENDING]**: API keys revoked and rotated
- **[PENDING]**: .env files removed from git tracking
- **[PENDING]**: Git history purged (optional)
- **[PENDING]**: Pre-commit hooks installed

---

## IMPACT ASSESSMENT

**Exposure Duration**: Unknown (likely since initial commit)
**Potential Impact**:
- Unauthorized API usage (billing impact)
- Rate limit exhaustion
- Data access via compromised keys
- Service disruption if keys are revoked

**Actual Impact**:
- [TO BE ASSESSED after reviewing API provider usage logs]

---

## LESSONS LEARNED

1. **Never commit .env files** - Always use .env.example templates
2. **Use secrets managers** - For production environments
3. **Implement pre-commit hooks** - Prevent accidental commits
4. **Regular security audits** - Automated scanning in CI/CD
5. **Principle of least privilege** - Use separate keys for dev/staging/prod

---

## RESPONSIBLE DISCLOSURE

This incident was discovered during internal security audit. No external disclosure required unless unauthorized API usage is detected.

---

**Next Steps**: Complete Steps 1-5 above within 24 hours, then update this document with completion timestamps.
