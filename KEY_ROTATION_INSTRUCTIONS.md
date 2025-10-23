# API Key Rotation Instructions

**Status:** CRITICAL - Complete within 24 hours
**Issue:** #1 - Rotate exposed API keys and remove from git history

## Overview

This PR removes exposed API keys from the repository, but you **MUST** rotate the keys on the external services to prevent unauthorized use.

## Required Actions

### 1. Rotate Plant.id API Key (5 minutes)

1. Visit https://web.plant.id/account (or https://my.kindwise.com/)
2. Log in to your account
3. Navigate to: **API Keys** or **Developer Settings**
4. **Revoke the old key:** `W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4`
5. **Generate new key** (copy immediately - shown only once)
6. Update your environment variables (see step 5 below)

### 2. Rotate PlantNet API Key (5 minutes)

1. Visit https://my.plantnet.org/
2. Log in to your account
3. Navigate to: **API Keys** or **Account Settings**
4. **Revoke the old key:** `2b10XCJNMzrPYiojVsddjK0n`
5. **Generate new key** (copy immediately)
6. Update your environment variables (see step 5 below)

### 3. Generate New Django SECRET_KEY (1 minute)

```bash
cd backend
source venv/bin/activate

# Generate new SECRET_KEY
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Copy the output (50+ characters)
```

### 4. Generate New JWT_SECRET_KEY (1 minute)

```bash
# Generate new JWT_SECRET_KEY
python -c 'import secrets; print(secrets.token_urlsafe(64))'

# Copy the output (64+ characters)
```

### 5. Update Environment Variables (5 minutes)

#### Local Development (.env file)

```bash
cd backend

# Create .env from template if it doesn't exist
cp .env.example .env

# Edit .env and update these lines:
# PLANT_ID_API_KEY=<paste_new_plant_id_key>
# PLANTNET_API_KEY=<paste_new_plantnet_key>
# SECRET_KEY=<paste_new_django_secret_key>
# JWT_SECRET_KEY=<paste_new_jwt_secret_key>
```

**IMPORTANT:** Never commit `.env` file - it's in `.gitignore`

#### Production Environment (Heroku example)

```bash
# Update production environment variables
heroku config:set PLANT_ID_API_KEY="new_plant_id_key_here"
heroku config:set PLANTNET_API_KEY="new_plantnet_key_here"
heroku config:set SECRET_KEY="new_django_secret_key_here"
heroku config:set JWT_SECRET_KEY="new_jwt_secret_key_here"

# Verify
heroku config:get PLANT_ID_API_KEY
```

#### Production Environment (AWS/other)

Update environment variables through your hosting provider's dashboard or CLI.

### 6. Verify Keys Work (5 minutes)

```bash
cd backend
source venv/bin/activate

# Start Redis (required for caching)
brew services start redis  # macOS
# OR: sudo systemctl start redis  # Linux

# Start development server
python manage.py runserver

# In another terminal, test health endpoint
curl http://localhost:8000/api/plant-identification/identify/health/

# Expected response:
# {
#   "status": "healthy",
#   "plant_id_available": true,
#   "plantnet_available": true
# }
```

### 7. Test Plant Identification (Optional - 5 minutes)

```bash
# Test with a sample plant image
cd backend
curl -X POST http://localhost:8000/api/plant-identification/identify/ \
  -F "image=@/path/to/plant_photo.jpg"

# Should return plant identification results
```

## What Changed in This PR

1. ✅ Removed `CLAUDE.md` from repository (local development only)
2. ✅ Added `CLAUDE.md` to `.gitignore`
3. ✅ Updated `backend/.env.example` with key generation instructions
4. ✅ Verified `.env` and `CLAUDE.md` not tracked in git
5. ✅ Documented security incident

## Why This Matters

### Current Risk
- **Plant.id key:** 100 IDs/month limit - can be exhausted quickly
- **PlantNet key:** 500 IDs/day limit - can be exhausted rapidly
- **Django SECRET_KEY:** Session hijacking, CSRF bypass
- **JWT_SECRET_KEY:** Complete authentication bypass

### Impact if Not Rotated
- Legitimate users unable to identify plants (quota exhausted)
- Service disruption for development and production
- Potential unauthorized access to user sessions
- Security breach requiring emergency response

## Timeline

**Immediate (Today):**
- [ ] Rotate Plant.id API key
- [ ] Rotate PlantNet API key
- [ ] Generate new Django SECRET_KEY
- [ ] Generate new JWT_SECRET_KEY
- [ ] Update local `.env` file
- [ ] Update production environment variables
- [ ] Verify health endpoint works

**Within 24 Hours:**
- [ ] Test plant identification with new keys
- [ ] Monitor API usage for next 7 days
- [ ] Report completion on GitHub Issue #1

**Within 7 Days:**
- [ ] Decide on git history cleanup with team
- [ ] Implement GitHub secret scanning
- [ ] Add pre-commit hooks for secret detection

## Git History Cleanup (Optional)

**WARNING:** This is optional and requires team coordination!

The exposed keys exist in git history (5 commits). Options:

### Option 1: Do Nothing (Recommended if low risk)
- Keys are rotated, so old keys are useless
- No disruption to team workflow
- Simpler approach

### Option 2: Rewrite Git History (High coordination required)
- Removes keys from all commits
- **Requires all team members to delete and re-clone repo**
- See `SECURITY_INCIDENT_2025_10_23_API_KEYS.md` for detailed instructions

**Recommendation:** Choose Option 1 if this is a small team or low-risk project.

## Support

**Questions?** Comment on GitHub Issue #1

**Need Help?**
- Plant.id support: https://web.plant.id/
- PlantNet support: https://my.plantnet.org/contact
- Django SECRET_KEY docs: https://docs.djangoproject.com/en/5.2/ref/settings/#secret-key

## Completion Checklist

After rotating all keys, update Issue #1 with:

```markdown
## Key Rotation Completed

- [x] Plant.id API key rotated
- [x] PlantNet API key rotated
- [x] Django SECRET_KEY regenerated
- [x] JWT_SECRET_KEY regenerated
- [x] Local .env updated
- [x] Production environment updated
- [x] Health endpoint verified
- [x] Plant identification tested

All keys rotated successfully on YYYY-MM-DD.
```

---

**Total Time Required:** ~20-30 minutes
**Priority:** CRITICAL
**Deadline:** 24 hours from PR merge
