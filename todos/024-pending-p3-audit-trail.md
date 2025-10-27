---
status: ready
priority: p3
issue_id: "024"
tags: [compliance, auditing, data-access]
dependencies: []
---

# Implement Data Access Audit Trail

## Problem

No audit trail for sensitive data access. Cannot track who viewed user emails, identification results, or when data was exported.

## Findings

**security-sentinel**:
- No logging for User model access
- No tracking of PlantIdentificationResult queries
- Admin panel access not audited
- Cannot answer "Who accessed user X's data?" for GDPR requests

**data-integrity-guardian**:
- GDPR Article 30 requires "records of processing activities"
- SOC 2 compliance requires audit trails for data access
- No mechanism to detect unauthorized access

## Proposed Solutions

### Option 1: django-auditlog (Recommended)
```python
# settings.py
INSTALLED_APPS += ['auditlog']

# models.py
from auditlog.registry import auditlog

auditlog.register(User)
auditlog.register(PlantIdentificationResult)
```

**Pros**: Automatic tracking, admin integration, queryable history
**Cons**: Database overhead, storage requirements
**Effort**: 3 hours (includes migration, testing)
**Risk**: Low (mature library)

### Option 2: Custom Middleware Logging
```python
class DataAccessLogger:
    def __call__(self, request):
        if request.path.startswith('/api/users/'):
            logger.info(f"[AUDIT] {request.user} accessed {request.path}")
```

**Pros**: Lightweight, full control
**Cons**: Manual implementation, easy to miss endpoints
**Effort**: 8 hours (comprehensive coverage)
**Risk**: Medium (incomplete coverage risk)

### Option 3: Database-Level Triggers
PostgreSQL triggers log all SELECT queries on sensitive tables

**Pros**: Cannot be bypassed, database-enforced
**Cons**: Performance overhead, complex setup, hard to query
**Effort**: 6 hours
**Risk**: High (database performance impact)

## Recommended Action

**Option 1** - django-auditlog:
1. Install and configure django-auditlog
2. Register User, PlantIdentificationResult models
3. Configure retention policy (90 days default)
4. Add audit log viewer to admin panel
5. Document audit procedures

## Technical Details

**Models requiring audit**:
- `User` - Email access, profile views
- `PlantIdentificationResult` - Identification history
- `UserProfile` - Personal data access
- Future: `BlogPost` if user-generated content

**Audit log schema**:
```python
AuditLogEntry:
    - timestamp
    - user (who accessed)
    - action (view, create, update, delete)
    - object_id (which record)
    - changes (what changed)
    - ip_address
```

**Retention policy**:
- 90 days for operational audits
- 7 years for compliance (GDPR Article 30)
- Implement log archival to S3/cold storage

## Resources

- django-auditlog: https://django-auditlog.readthedocs.io/
- GDPR Article 30: https://gdpr-info.eu/art-30-gdpr/
- SOC 2 audit requirements: https://www.aicpa.org/soc4so
- Log retention best practices: NIST SP 800-92

## Acceptance Criteria

- [ ] All User model access logged (view, update, delete)
- [ ] PlantIdentificationResult queries logged
- [ ] Admin panel access tracked
- [ ] Audit logs queryable by user, date, action type
- [ ] Retention policy configured (90 days active, 7 years archived)
- [ ] Performance impact <5% on API endpoints
- [ ] Documentation for GDPR data access requests

## Work Log

- 2025-10-25: Issue identified by security-sentinel and data-integrity-guardian agents

## Notes

**Priority rationale**: P3 (Medium) - Compliance requirement but not urgent for early development
**Performance impact**: django-auditlog adds ~2-5ms per write operation
**Storage requirements**: Estimate 1KB per audit entry, ~10MB/month for 10k requests
**Related**: Complements IP logging (issue #016) for security monitoring
