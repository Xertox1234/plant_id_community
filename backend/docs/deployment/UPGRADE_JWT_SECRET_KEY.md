# BREAKING CHANGE: JWT_SECRET_KEY Required

**Effective:** November 3, 2025
**Commit:** `24a9506`
**Severity:** 🔴 BREAKING CHANGE
**Impact:** All environments (development, staging, production)

---

## What Changed

As of commit `24a9506`, **`JWT_SECRET_KEY` is now required in all environments** (previously only required in production).

### Previous Behavior (Before)
```python
# Development: Allowed fallback to SECRET_KEY
if DEBUG:
    JWT_SECRET_KEY = config('JWT_SECRET_KEY', default=None)
    if JWT_SECRET_KEY:
        SIMPLE_JWT['SIGNING_KEY'] = JWT_SECRET_KEY
    else:
        SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY  # ⚠️ Security risk
```

### New Behavior (After)
```python
# All environments: JWT_SECRET_KEY is REQUIRED
JWT_SECRET_KEY = config('JWT_SECRET_KEY', default=None)
if not JWT_SECRET_KEY:
    raise ImproperlyConfigured(
        "JWT_SECRET_KEY environment variable is required."
    )
if JWT_SECRET_KEY == SECRET_KEY:
    raise ImproperlyConfigured(
        "JWT_SECRET_KEY must be different from SECRET_KEY."
    )
SIMPLE_JWT['SIGNING_KEY'] = JWT_SECRET_KEY
```

---

## Why This Change Was Made

### Security Vulnerability: Secret Key Reuse

Using the same key for both Django sessions/CSRF and JWT authentication creates a **cascade compromise** risk:

**Attack Scenario:**
1. Attacker discovers `SECRET_KEY` through error logs, config leak, or side-channel attack
2. With `SECRET_KEY`, attacker can:
   - Forge Django session cookies (impersonate any user)
   - Generate valid CSRF tokens (bypass CSRF protection)
   - **If JWT uses same key:** Forge JWT tokens (authenticate as any user)

**With Separate Keys:**
1. Attacker discovers `SECRET_KEY`
2. Can only compromise Django sessions/CSRF
3. **JWT authentication remains secure** (different key)

### Industry Standards

- **OWASP**: Recommends separate keys for different authentication mechanisms
- **NIST SP 800-57**: "Cryptographic keys should be purpose-specific"
- **CWE-798**: Use of Hard-coded Credentials includes key reuse as anti-pattern

---

## Who Is Affected

### ✅ Unaffected (No Action Required)
- Production environments already using `JWT_SECRET_KEY`
- Deployments with `JWT_SECRET_KEY` in `.env` file

### ⚠️ Affected (Action Required)
- **All developers** without `JWT_SECRET_KEY` in local `.env`
- **Staging environments** using `SECRET_KEY` fallback
- **CI/CD pipelines** without `JWT_SECRET_KEY` configured
- **Docker containers** using default `.env` template

---

## How to Upgrade

### Step 1: Generate JWT_SECRET_KEY

**Method 1: Python secrets module (Recommended)**
```bash
python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

**Method 2: Django's get_random_secret_key**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

**Output Example:**
```
Kj8Vx2Ym_5qN9wLpZ3rTc7Uf1hAs6Dg0iEoWbXvYnMzQlRkUjHtGfCsPaN4rBemI
```

### Step 2: Add to .env File

**For Development:**
```bash
cd backend
echo "JWT_SECRET_KEY=<your-generated-key>" >> .env
```

**For Production/Staging:**
```bash
# Add to your secrets management system:
# - AWS Secrets Manager
# - HashiCorp Vault
# - Kubernetes Secrets
# - Environment variables in hosting platform

# Example: Heroku
heroku config:set JWT_SECRET_KEY="<your-generated-key>" --app your-app-name

# Example: Docker Compose
# Add to docker-compose.yml environment section
```

### Step 3: Verify Keys Are Different

**Critical:** `JWT_SECRET_KEY` must be **completely different** from `SECRET_KEY`.

```bash
cd backend
python manage.py shell

# In Django shell:
from django.conf import settings
print(f"SECRET_KEY: {settings.SECRET_KEY[:20]}...")
print(f"JWT_SECRET_KEY: {settings.JWT_SECRET_KEY[:20]}...")
print(f"Are they different? {settings.SECRET_KEY != settings.JWT_SECRET_KEY}")
# Should print: True
```

### Step 4: Restart Services

```bash
# Development
python manage.py runserver

# Production (example: systemd)
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# Docker
docker-compose restart backend
```

### Step 5: Verify No Errors

```bash
# Check Django startup
python manage.py check

# Verify JWT authentication works
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}'

# Should return JWT tokens without errors
```

---

## Troubleshooting

### Error: "JWT_SECRET_KEY environment variable is required"

**Cause:** `JWT_SECRET_KEY` not set in `.env` file

**Solution:**
```bash
python -c 'import secrets; print(secrets.token_urlsafe(64))' >> .env
# Then edit .env and add: JWT_SECRET_KEY=<generated-key>
```

### Error: "JWT_SECRET_KEY must be different from SECRET_KEY"

**Cause:** You used the same value for both keys

**Solution:** Generate a new, different key:
```bash
python -c 'import secrets; print(secrets.token_urlsafe(64))'
# Use this new value for JWT_SECRET_KEY
```

### Error: "JWT_SECRET_KEY must be at least 50 characters"

**Cause:** Generated key is too short

**Solution:** Use `secrets.token_urlsafe(64)` instead of shorter generators:
```bash
# ✅ CORRECT (generates 86 characters)
python -c 'import secrets; print(secrets.token_urlsafe(64))'

# ❌ WRONG (generates 32 characters)
python -c 'import secrets; print(secrets.token_hex(16))'
```

### Existing JWT Tokens Still Valid?

**Yes.** JWT tokens issued before the key change **will become invalid** after you change `JWT_SECRET_KEY`.

**Impact:**
- Users will need to log in again
- Mobile apps will need to refresh tokens
- API integrations will need new tokens

**Migration Strategy:**
```python
# Option 1: Grace period (allow old and new keys)
# Add to settings.py temporarily:
SIMPLE_JWT['VERIFYING_KEY'] = [JWT_SECRET_KEY, OLD_JWT_SECRET_KEY]

# Option 2: Force logout all users
# In Django shell:
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
OutstandingToken.objects.all().delete()
```

---

## Rollback Instructions

**⚠️ Emergency Rollback Only - Not Recommended**

If you must rollback due to deployment issues:

### Step 1: Revert Code Changes
```bash
git revert 24a9506
git push origin main
```

### Step 2: Allow Fallback (Temporary)
```python
# In settings.py, add back fallback:
JWT_SECRET_KEY = config('JWT_SECRET_KEY', default=None)
if JWT_SECRET_KEY:
    SIMPLE_JWT['SIGNING_KEY'] = JWT_SECRET_KEY
else:
    SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY  # ⚠️ INSECURE
    logger.warning("[SECURITY] Using SECRET_KEY for JWT (insecure fallback)")
```

### Step 3: Plan Fix
- Schedule maintenance window
- Generate proper `JWT_SECRET_KEY`
- Deploy with correct configuration

**Do not run with fallback for more than 24 hours.**

---

## CI/CD Configuration

### GitHub Actions

```yaml
# .github/workflows/test.yml
env:
  SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
  JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY }}  # Add this
  DATABASE_URL: sqlite:///test.db
```

**GitHub Secrets Setup:**
1. Go to repository Settings → Secrets and variables → Actions
2. Add new secret: `JWT_SECRET_KEY`
3. Generate value: `python -c 'import secrets; print(secrets.token_urlsafe(64))'`

### Docker Compose

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}  # Add this
```

```bash
# .env.docker
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here  # Add this
```

### Kubernetes

```yaml
# kubernetes/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: backend-secrets
type: Opaque
data:
  secret-key: <base64-encoded-secret-key>
  jwt-secret-key: <base64-encoded-jwt-secret-key>  # Add this
```

```yaml
# kubernetes/deployment.yaml
env:
  - name: SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: backend-secrets
        key: secret-key
  - name: JWT_SECRET_KEY  # Add this
    valueFrom:
      secretKeyRef:
        name: backend-secrets
        key: jwt-secret-key
```

---

## Security Best Practices

### Key Generation
✅ **DO:**
- Use `secrets.token_urlsafe(64)` (cryptographically secure)
- Generate different keys for different environments
- Store keys in secrets management systems
- Rotate keys periodically (every 90 days recommended)

❌ **DON'T:**
- Use predictable patterns (e.g., "my-jwt-secret-key-123")
- Reuse keys across environments
- Commit keys to version control
- Share keys via email/Slack

### Key Storage
✅ **DO:**
- Use environment variables
- Use secrets management (AWS Secrets Manager, Vault)
- Encrypt keys at rest
- Restrict access to keys (least privilege)

❌ **DON'T:**
- Hardcode in settings.py
- Store in plaintext files in repository
- Share keys publicly
- Log keys in application logs

### Key Rotation
✅ **DO:**
- Rotate quarterly (every 90 days)
- Rotate immediately if compromised
- Keep old key for 24-hour grace period
- Notify users of forced logout

❌ **DON'T:**
- Never rotate keys
- Rotate without invalidating old tokens
- Rotate during peak traffic hours
- Forget to update all environments

---

## Validation Checklist

Before marking upgrade complete, verify:

- [ ] `JWT_SECRET_KEY` added to all `.env` files
- [ ] Keys are different from `SECRET_KEY` (verified)
- [ ] Keys are at least 50 characters long
- [ ] Application starts without errors
- [ ] JWT authentication works (tested login)
- [ ] Old tokens invalidated (users logged out)
- [ ] CI/CD pipelines updated
- [ ] Deployment documentation updated
- [ ] Team notified of change

---

## Support

**Questions?** Contact:
- #dev-backend Slack channel
- backend-team@example.com
- Create issue: https://github.com/Xertox1234/plant_id_community/issues

**Related Documentation:**
- `backend/docs/security/AUTHENTICATION_SECURITY.md`
- `backend/.env.example` (updated with JWT_SECRET_KEY)
- `CLAUDE.md` (project setup instructions)

---

## References

- **OWASP**: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- **CWE-798**: https://cwe.mitre.org/data/definitions/798.html
- **Django Simple JWT**: https://django-rest-framework-simplejwt.readthedocs.io/
- **Python secrets module**: https://docs.python.org/3/library/secrets.html

---

**Document Version:** 1.0
**Last Updated:** November 3, 2025
**Applies To:** Commits `24a9506` and later
