# Firebase IAM Patterns

---

## Service Account Principle of Least Privilege

Service accounts used by the backend (Django firebase-admin) must have only the permissions they need:

| Use Case | Required Role |
|---|---|
| Verify ID tokens only | `roles/firebaseauth.viewer` |
| Create/update users | `roles/firebaseauth.admin` |
| Firestore read (backend) | `roles/datastore.viewer` |
| Firestore read+write (backend) | `roles/datastore.user` |
| Cloud Functions invoke | `roles/cloudfunctions.invoker` |

Never grant `roles/owner` or `roles/editor` to service accounts used by application code.

---

## Service Account Key Security

- Service account JSON keys must NEVER be committed to git.
- Store as environment variable: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json`
- In CI/CD: use Workload Identity Federation instead of key files.
- Rotate keys on any suspected compromise — see `KEY_ROTATION_INSTRUCTIONS.md`.

```bash
# Check for accidentally committed key files
git log --all --full-history -- "*.json" | grep -i "service.account\|firebase-adminsdk"
```

---

## Firebase App Check (Future)

For endpoints that should only be called from legitimate app instances, consider enabling App Check. This prevents API abuse from scripts or modified clients.

---

## Environment Separation

Production and development should use separate Firebase projects:

```
plant-id-community-dev    → development / staging
plant-id-community-prod   → production only
```

Service accounts for dev must not have access to prod Firestore data.

---

## Minimum Required Permissions for Django Backend

The Django backend requires:
1. `firebase-admin` SDK to verify ID tokens → needs Auth Admin or a custom role with `identitytoolkit.users.get`
2. Firestore access if writing user profile data → `roles/datastore.user` scoped to the relevant collection

```python
# backend/apps/users/firebase_auth_views.py
# Lazy-init pattern — credentials loaded once, not per-request
def _ensure_firebase_initialized():
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
```
