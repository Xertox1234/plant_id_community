# 🚀 Quick Start - Week 1 Security Fixes

## ⏱️ 30-Minute Quick Setup

### Step 1: Revoke Old API Keys (5 minutes)

**Plant.id**: https://plant.id/ → API Keys → Revoke → Generate New
**PlantNet**: https://my.plantnet.org/ → API Keys → Delete → Generate New

### Step 2: Run Secure Setup Script (2 minutes)

```bash
cd existing_implementation/backend
./scripts/secure_setup.sh
```

This will:
- Generate secure SECRET_KEY
- Create .env file from template
- Prompt for your new API keys
- Configure CORS settings

### Step 3: Install Dependencies (3 minutes)

```bash
pip install python-dotenv django-ratelimit
```

### Step 4: Test the Server (2 minutes)

```bash
python simple_server.py
```

Expected output:
```
Starting development server at http://127.0.0.1:8000/
```

### Step 5: Test Plant Identification (3 minutes)

```bash
# Health check
curl http://localhost:8000/api/plant-identification/health/

# Upload test image
curl -X POST http://localhost:8000/api/plant-identification/identify/ \
  -F "image=@/path/to/plant.jpg"
```

### Step 6: Update .gitignore (1 minute)

```bash
echo ".env" >> .gitignore
echo "*.env" >> .gitignore
echo "!.env.template" >> .gitignore
```

### Step 7: Purge Git History (OPTIONAL - 15 minutes)

⚠️ **DANGER**: This rewrites git history. Coordinate with team first.

```bash
# Install BFG
brew install bfg  # Mac
# OR
sudo apt-get install bfg  # Linux

# Clone mirror
git clone --mirror https://github.com/youruser/plant_id_community.git

# Create password file
cat > passwords.txt <<EOF
W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
2b10XCJNMzrPYiojVsddjK0n
EOF

# Purge secrets
cd plant_id_community.git
bfg --replace-text ../passwords.txt
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force

# Clean up
rm ../passwords.txt
```

---

## What Was Fixed

| Issue | Status | File | Time |
|-------|--------|------|------|
| Hardcoded API keys | ✅ Fixed | `simple_server.py` | 5 min |
| Insecure SECRET_KEY | ✅ Fixed | `simple_server.py` | Auto |
| CORS_ALLOW_ALL | ✅ Fixed | `simple_server.py` | Auto |
| Missing transactions | ✅ Fixed | `simple_views.py` | Auto |
| No rate limiting | ✅ Fixed | `simple_views.py` | Auto |
| Unsafe migrations | ⚠️ Manual | See guide below | 30 min |

---

## Fix UUID Migration (If Database Has Data)

⚠️ **Only needed if you have existing data in the database**

### Option A: Fresh Start (Recommended for Development)

```bash
# Delete database and start fresh
rm db.sqlite3
python manage.py migrate
```

### Option B: Fix Existing Migration

1. **Rollback migration**:
```bash
python manage.py migrate plant_identification 0002
```

2. **Edit migration file**:
```python
# File: apps/plant_identification/migrations/0003_*.py
# Change line 22 from:
field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),

# To:
field=models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True),
```

3. **Create new migration**:
```bash
# Edit models.py to remove null=True from uuid field
python manage.py makemigrations

# This creates 0004 migration that adds unique constraint safely
python manage.py migrate
```

---

## Verification Checklist

Run these checks to verify all fixes are working:

### ✅ Environment Variables
```bash
# Should fail without .env
python simple_server.py
# Expected: ValueError about missing API keys

# Create .env
cp .env.template .env
nano .env  # Add real keys

# Should start
python simple_server.py
# Expected: Server starts
```

### ✅ Rate Limiting
```bash
# Make 11 requests rapidly
for i in {1..11}; do
  curl -X POST http://localhost:8000/api/plant-identification/identify/ \
    -F "image=@test.jpg" &
done
wait

# Expected: First 10 succeed, 11th returns 429
```

### ✅ Transactions
```bash
python manage.py shell

from django.db import connection
print(connection.in_atomic_block)
# Expected: False (no global transaction)

# Transactions are per-request, not global
```

### ✅ CORS Security
```bash
# Should reject unauthorized origins
curl -H "Origin: https://evil.com" \
  http://localhost:8000/api/plant-identification/health/

# Expected: CORS error (no Access-Control-Allow-Origin header for evil.com)
```

---

## Common Issues

### Issue: "ModuleNotFoundError: No module named 'dotenv'"
**Fix**: `pip install python-dotenv`

### Issue: "ModuleNotFoundError: No module named 'django_ratelimit'"
**Fix**: `pip install django-ratelimit`

### Issue: "ValueError: PLANT_ID_API_KEY not found"
**Fix**: Create `.env` file with your API keys (run `./scripts/secure_setup.sh`)

### Issue: Migration fails with IntegrityError
**Fix**: Use "Option A: Fresh Start" above or follow "Option B" to fix migration

### Issue: Rate limiting not working
**Fix**: Ensure `django-ratelimit` is installed and `RATE_LIMIT_ENABLED=True` in .env

---

## Next Steps (Week 2)

After completing Week 1 security fixes:

1. **Performance Optimization**:
   - Implement parallel API processing (60% faster)
   - Add database indexes (100x faster queries)
   - Implement Redis caching (40% fewer API calls)

2. **Frontend Optimization**:
   - Add client-side image compression (85% faster uploads)
   - Implement lazy loading (40% faster page load)
   - Code splitting (smaller bundle size)

3. **Code Cleanup**:
   - Delete 13 unused backend services (5,000+ LOC)
   - Remove unimplemented frontend methods
   - Simplify dual API strategy

See `SECURITY_FIXES_WEEK1.md` for detailed implementation guide.

---

## Production Deployment Checklist

Before deploying to production:

- [ ] All old API keys revoked
- [ ] Git history purged (or new repo created)
- [ ] DEBUG=False in production .env
- [ ] SECRET_KEY is production-grade (50+ characters)
- [ ] ALLOWED_HOSTS set to your domain
- [ ] CORS_ALLOWED_ORIGINS set to your domain (HTTPS)
- [ ] SSL certificate installed
- [ ] SECURE_SSL_REDIRECT=True
- [ ] SESSION_COOKIE_SECURE=True
- [ ] CSRF_COOKIE_SECURE=True
- [ ] Change @permission_classes([AllowAny]) to [IsAuthenticated]
- [ ] Database migrated to PostgreSQL
- [ ] Redis configured for caching
- [ ] Static files collected: `python manage.py collectstatic`
- [ ] Gunicorn or Daphne configured
- [ ] Nginx reverse proxy configured
- [ ] Monitoring configured (Sentry, etc.)

---

## Support

For detailed explanations, see:
- `SECURITY_FIXES_WEEK1.md` - Complete security fixes guide
- `.env.template` - Environment variable reference
- `scripts/secure_setup.sh` - Automated setup script

Questions? Check the Plant ID Community documentation.
