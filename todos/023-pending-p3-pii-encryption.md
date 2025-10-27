---
status: ready
priority: p3
issue_id: "023"
tags: [security, privacy, gdpr, pii]
dependencies: []
---

# Encrypt PII Fields at Rest

**CVSS**: 5.3 (Medium) - AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N

## Problem

Email addresses stored in plaintext in PostgreSQL. If database is compromised, all user emails are exposed.

## Findings

**security-sentinel**:
- User.email field stored unencrypted
- PostgreSQL backups contain plaintext emails
- GDPR Article 32 requires "encryption of personal data"
- No field-level encryption implemented

**architecture-strategist**:
- Database-at-rest encryption not confirmed
- Application-level encryption recommended for sensitive fields

## Proposed Solutions

### Option 1: django-encrypted-model-fields (Recommended)
```python
from encrypted_model_fields.fields import EncryptedEmailField

class User(AbstractUser):
    email = EncryptedEmailField(max_length=254, unique=True)
```

**Pros**: Transparent encryption, query support, key rotation
**Cons**: Requires FIELD_ENCRYPTION_KEY in settings, performance overhead
**Effort**: 2 hours (includes migration)
**Risk**: Medium (requires careful key management)

### Option 2: PostgreSQL pgcrypto Extension
```python
# Raw SQL for encryption at database level
SELECT pgp_sym_encrypt('email@example.com', 'encryption_key');
```

**Pros**: Database-level security, no Django changes
**Cons**: Complex queries, manual key management, no Django ORM support
**Effort**: 4 hours
**Risk**: High (complex migration)

### Option 3: Database-Level Encryption (Defer to Infrastructure)
Enable PostgreSQL Transparent Data Encryption (TDE)

**Pros**: No code changes, encrypts entire database
**Cons**: Doesn't protect against SQL injection, requires infrastructure access
**Effort**: 1 hour (infrastructure team)
**Risk**: Low (handled by DB team)

## Recommended Action

**Hybrid Approach**:
1. Short-term: Enable PostgreSQL TDE (Option 3) - Infrastructure team
2. Long-term: Implement django-encrypted-model-fields (Option 1) for email/phone
3. Document encryption strategy in security policy

**Rationale**: TDE protects backups immediately, field-level encryption protects against SQL injection

## Technical Details

**Location**: `backend/apps/users/models.py`

**Affected fields**:
- User.email (currently CharField/EmailField)
- Potential: phone_number, address fields if added

**Key management**:
```python
# settings.py
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY')  # 32-byte key from secrets.token_bytes(32)
```

**Migration strategy**:
1. Add encrypted field: `email_encrypted`
2. Copy data: `User.objects.all().update(email_encrypted=F('email'))`
3. Swap fields in code
4. Drop old field

## Resources

- django-encrypted-model-fields: https://pypi.org/project/django-encrypted-model-fields/
- GDPR Article 32: https://gdpr-info.eu/art-32-gdpr/
- PostgreSQL pgcrypto: https://www.postgresql.org/docs/current/pgcrypto.html
- Key management: Django SECRET_KEY rotation patterns

## Acceptance Criteria

- [ ] Email addresses encrypted at rest (verify with pg_dump)
- [ ] Encryption key stored securely (not in git, use env vars)
- [ ] Query performance acceptable (<100ms for user lookup)
- [ ] Key rotation procedure documented
- [ ] Backup/restore tested with encrypted fields
- [ ] GDPR compliance documented

## Work Log

- 2025-10-25: Issue identified by security-sentinel agent

## Notes

**Priority rationale**: P3 (Medium) - GDPR compliance issue but not actively exploited
**Dependencies**: Requires SECRET_KEY validation (issue #002 from previous audit)
**Related**: IP address logging (issue #016) also contains PII
