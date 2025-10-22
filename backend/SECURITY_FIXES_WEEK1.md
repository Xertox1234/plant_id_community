# Week 1 Security Fixes - Implementation Guide

## ⚠️ CRITICAL: API Keys Exposed - Immediate Action Required

### Current Status
The following API keys were found hardcoded in the repository:
- **Plant.id API Key**: `W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4` (REVOKE IMMEDIATELY)
- **PlantNet API Key**: `2b10XCJNMzrPYiojVsddjK0n` (REVOKE IMMEDIATELY)

These keys were exposed in:
- `simple_server.py` (lines 47-48)
- `.env` file (lines 25, 30)
- Multiple documentation files (CLAUDE.md, README.md, etc.)

---

## Fix #1: Revoke and Regenerate API Keys (DO THIS FIRST)

### Step 1: Revoke Exposed Keys

**Plant.id (Kindwise)**:
1. Go to: https://plant.id/
2. Log in to your account
3. Navigate to API Keys section
4. Click "Revoke" on the exposed key
5. Generate a new API key
6. Save the new key securely

**PlantNet**:
1. Go to: https://my.plantnet.org/
2. Log in to your account
3. Navigate to API Keys section
4. Delete the exposed key
5. Generate a new API key
6. Save the new key securely

### Step 2: Update .env File

```bash
cd existing_implementation/backend

# Copy template
cp .env.template .env.local

# Edit .env file with new keys
nano .env
```

Update these lines:
```bash
PLANT_ID_API_KEY=YOUR_NEW_PLANT_ID_KEY_HERE
PLANTNET_API_KEY=YOUR_NEW_PLANTNET_KEY_HERE
SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
```

### Step 3: Update .gitignore

Ensure `.env` is in `.gitignore`:
```bash
# Add to .gitignore if not already present
echo ".env" >> .gitignore
echo "*.env" >> .gitignore
echo "!.env.template" >> .gitignore
```

### Step 4: Purge Git History (CRITICAL)

Use BFG Repo-Cleaner to remove exposed secrets from git history:

```bash
# Install BFG (Mac)
brew install bfg

# Clone a fresh copy
git clone --mirror https://github.com/youruser/plant_id_community.git

# Create passwords.txt with exposed keys
cat > passwords.txt <<EOF
W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
2b10XCJNMzrPYiojVsddjK0n
EOF

# Run BFG to purge secrets
cd plant_id_community.git
bfg --replace-text ../passwords.txt

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (DANGER: coordinate with team)
git push --force

# Delete passwords.txt securely
cd ..
shred -u passwords.txt  # Linux
# OR
rm -P passwords.txt  # Mac
```

**⚠️ WARNING**: Force pushing rewrites history. Coordinate with all team members first.

---

## Fix #2: Secure simple_server.py

### Changes Made
✅ **Removed hardcoded API keys**
✅ **Added environment variable loading with python-dotenv**
✅ **Added SECRET_KEY validation**
✅ **Fixed CORS_ALLOW_ALL_ORIGINS security issue**
✅ **Added security headers**
✅ **Added proper error messages if keys missing**

### Files Modified
- `/existing_implementation/backend/simple_server.py`

### Test the Fix
```bash
cd existing_implementation/backend

# Ensure python-dotenv is installed
pip install python-dotenv

# Run server (should fail if .env missing)
python simple_server.py

# Expected output:
# ValueError: PLANT_ID_API_KEY not found in environment variables
```

---

## Fix #3: Add Transaction Boundaries

### Changes Made
✅ **Added `@transaction.atomic` to identify_plant endpoint**
✅ **Added rate limiting (10 requests/hour per IP)**
✅ **Imported django.db.transaction**
✅ **Added django-ratelimit decorator**

### Files Modified
- `/existing_implementation/backend/apps/plant_identification/api/simple_views.py`

### Install Required Package
```bash
pip install django-ratelimit
```

### Test the Fix
```bash
# Test transaction rollback
python manage.py shell

from apps.plant_identification.api.simple_views import identify_plant
# Transactions will now rollback automatically on errors
```

---

## Fix #4: Fix Unsafe UUID Migration

### Problem
Migration `0003_plantidentificationresult_uuid_and_more.py` adds UUID fields with `unique=True` constraint immediately. This will FAIL if the table has existing data because:
1. Django generates UUIDs during migration
2. Multiple rows may get the same UUID
3. Unique constraint fails

### Solution: Split into 3 Migrations

**Migration 0003a: Add Nullable UUID Fields**
```python
# File: migrations/0003a_add_uuid_fields.py

operations = [
    migrations.AddField(
        model_name='plantidentificationresult',
        name='uuid',
        field=models.UUIDField(
            default=uuid.uuid4,
            editable=False,
            null=True,  # ← NULLABLE FIRST
            blank=True,
            help_text='Unique identifier for secure references'
        ),
    ),
    # ... repeat for plantspecies, userplant
]
```

**Migration 0003b: Populate UUIDs**
```python
# File: migrations/0003b_populate_uuids.py

def populate_uuids(apps, schema_editor):
    PlantIdentificationResult = apps.get_model('plant_identification', 'PlantIdentificationResult')
    PlantSpecies = apps.get_model('plant_identification', 'PlantSpecies')
    UserPlant = apps.get_model('plant_identification', 'UserPlant')

    # Generate unique UUIDs for each row
    for model in [PlantIdentificationResult, PlantSpecies, UserPlant]:
        for obj in model.objects.filter(uuid__isnull=True):
            obj.uuid = uuid.uuid4()
            obj.save(update_fields=['uuid'])

operations = [
    migrations.RunPython(
        populate_uuids,
        reverse_code=migrations.RunPython.noop
    ),
]
```

**Migration 0003c: Add Unique Constraint**
```python
# File: migrations/0003c_make_uuid_unique.py

operations = [
    migrations.AlterField(
        model_name='plantidentificationresult',
        name='uuid',
        field=models.UUIDField(
            default=uuid.uuid4,
            editable=False,
            unique=True,  # ← NOW ADD UNIQUE
            help_text='Unique identifier for secure references'
        ),
    ),
    # ... repeat for plantspecies, userplant
]
```

### How to Apply

```bash
cd existing_implementation/backend

# Option 1: Delete existing migration and recreate
python manage.py migrate plant_identification 0002  # Rollback to before 0003
rm apps/plant_identification/migrations/0003_*.py
python manage.py makemigrations plant_identification  # Will create new 0003

# Option 2: Keep existing, create new migrations
# Edit 0003 migration to remove unique=True
# Create new migrations 0004, 0005 to add constraint

# Test on copy of database first!
cp db.sqlite3 db.sqlite3.backup
python manage.py migrate
```

---

## Fix #5: Update Documentation

### Remove API Keys from Documentation

**Files to Update**:
```bash
# Remove keys from these files:
- CLAUDE.md (lines 272-273)
- README.md (lines 141-142)
- existing_implementation/CLAUDE.md
- Any other docs with hardcoded keys
```

**Replace with**:
```markdown
# Plant Identification APIs

## Plant.id (Kindwise)
Get your API key at: https://plant.id/
Set in `.env`: `PLANT_ID_API_KEY=your_key_here`

## PlantNet
Get your API key at: https://my.plantnet.org/
Set in `.env`: `PLANTNET_API_KEY=your_key_here`
```

---

## Verification Checklist

### Security
- [ ] Old API keys revoked from provider dashboards
- [ ] New API keys generated and stored in `.env`
- [ ] `.env` added to `.gitignore`
- [ ] Git history purged with BFG Repo-Cleaner
- [ ] `simple_server.py` loads keys from environment
- [ ] SECRET_KEY is cryptographically secure (not 'dev-secret-key')
- [ ] CORS_ALLOW_ALL_ORIGINS removed (specific origins only)
- [ ] Security headers added (X-Frame-Options, XSS, etc.)

### Transactions & Rate Limiting
- [ ] `@transaction.atomic` added to identify_plant endpoint
- [ ] `django-ratelimit` installed
- [ ] Rate limiting tested (10 requests/hour per IP)
- [ ] Transaction rollback tested with forced errors

### Migrations
- [ ] UUID migration split into 3 parts (nullable → populate → unique)
- [ ] Tested on database copy first
- [ ] No IntegrityError when running migrations
- [ ] All existing rows have UUIDs after migration

### Documentation
- [ ] All hardcoded API keys removed from docs
- [ ] `.env.template` created with instructions
- [ ] SECURITY_FIXES_WEEK1.md created
- [ ] README updated with security setup instructions

---

## Testing the Fixes

### Test 1: Environment Variables
```bash
cd existing_implementation/backend

# Should fail without .env
python simple_server.py
# Expected: ValueError: PLANT_ID_API_KEY not found

# Create .env with new keys
cp .env.template .env
nano .env  # Add real keys

# Should start successfully
python simple_server.py
# Expected: Server starts on port 8000
```

### Test 2: Rate Limiting
```bash
# Make 11 requests rapidly
for i in {1..11}; do
  curl -X POST http://localhost:8000/api/plant-identification/identify/ \
    -F "image=@test_plant.jpg"
done

# Expected: First 10 succeed, 11th returns 429 Too Many Requests
```

### Test 3: Transaction Rollback
```bash
python manage.py shell

from django.db import transaction
from apps.plant_identification.api.simple_views import identify_plant

# Transactions automatically rollback on errors
# No partial data left in database
```

### Test 4: Migrations
```bash
# Test on copy first!
cp db.sqlite3 db.sqlite3.test
python manage.py migrate --database=test

# Check UUID fields populated
python manage.py shell
from apps.plant_identification.models import PlantIdentificationResult
print(PlantIdentificationResult.objects.filter(uuid__isnull=True).count())
# Expected: 0
```

---

## Deployment Notes

### Before Deploying to Production

1. **Generate Production SECRET_KEY**:
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

2. **Set Environment Variables**:
```bash
export DEBUG=False
export SECRET_KEY='production-secret-key-here'
export ALLOWED_HOSTS='yourdomain.com,www.yourdomain.com'
export CORS_ALLOWED_ORIGINS='https://yourdomain.com'
```

3. **Enable HTTPS**:
```python
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

4. **Change AllowAny to IsAuthenticated**:
```python
# In simple_views.py
@permission_classes([IsAuthenticated])  # No more AllowAny
```

---

## Summary

**Time Required**: 4-6 hours
**Risk Level**: Medium (requires force push for git history cleanup)
**Impact**: HIGH - Eliminates 5 critical security vulnerabilities

**What Was Fixed**:
1. ✅ Exposed API keys revoked and removed from code
2. ✅ Environment variables properly configured
3. ✅ CORS security hardened
4. ✅ Transaction boundaries added
5. ✅ Rate limiting implemented
6. ✅ UUID migration made safe
7. ✅ Security headers added

**Next Steps** (Week 2):
- Implement parallel API processing for performance
- Add database indexes
- Implement Redis caching
- Frontend optimizations
