# Audit Trail Procedures

**Document Version:** 1.0
**Last Updated:** October 27, 2025
**Status:** Production Ready
**Compliance:** GDPR Article 30, SOC 2

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Audited Models](#audited-models)
4. [Querying Audit Logs](#querying-audit-logs)
5. [GDPR Compliance](#gdpr-compliance)
6. [Retention Policy](#retention-policy)
7. [Production Deployment](#production-deployment)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Plant Community backend implements comprehensive audit trail logging using **django-auditlog** to comply with:

- **GDPR Article 30**: "Records of processing activities"
- **SOC 2**: Audit trail requirements for security monitoring
- **Security Monitoring**: Detect unauthorized access to sensitive data

### What is Audited?

All create, update, and delete operations on sensitive models are automatically logged, capturing:

- **Who**: User who made the change (or "System" if automated)
- **What**: Which model instance was changed and what fields were modified
- **When**: Precise timestamp of the change
- **Where**: IP address of the request (if available)
- **Changes**: Before and after values for all modified fields

---

## System Architecture

### Implementation

- **Library**: `django-auditlog==3.3.0`
- **Middleware**: `auditlog.middleware.AuditlogMiddleware`
- **Database Tables**: `auditlog_logentry`
- **Performance Impact**: ~2-5ms per write operation (acceptable for compliance)
- **Storage**: ~1KB per audit entry, ~10MB/month for 10k requests

### Configuration Files

1. **Settings**: `/backend/plant_community_backend/settings.py`
   ```python
   AUDITLOG_INCLUDE_ALL_MODELS = False  # Explicit registration only
   AUDITLOG_RETENTION_DAYS = 90  # Active retention period
   ```

2. **Model Registration**:
   - `/backend/apps/users/auditlog.py`
   - `/backend/apps/plant_identification/auditlog.py`

3. **App Configuration**:
   - `/backend/apps/users/apps.py` (imports auditlog registration in `ready()`)
   - `/backend/apps/plant_identification/apps.py`

---

## Audited Models

### Users App

#### User Model
**Fields Tracked:**
- `username`, `email`, `first_name`, `last_name`
- `is_active`, `is_staff`, `is_superuser`
- `bio`, `location`, `hardiness_zone`
- `profile_visibility`, `show_email`, `trust_level`

**Fields Excluded:**
- `password` (never logged for security)
- `last_login` (too verbose)

**M2M Fields Tracked:**
- `groups` (permission changes)
- `user_permissions` (permission changes)
- `following` (social graph changes)

#### UserPlantCollection Model
**Fields Tracked:**
- `name`, `description`, `is_public`

#### ActivityLog Model
**Purpose**: Meta-tracking (audit the audit)
**Fields Tracked:**
- `activity_type`, `description`, `is_public`

### Plant Identification App

#### PlantIdentificationResult Model
**Fields Tracked:**
- `confidence_score`, `identification_source`
- `is_accepted`, `is_primary`
- `upvotes`, `downvotes`
- `suggested_scientific_name`, `suggested_common_name`

**Fields Excluded:**
- `api_response_data` (large JSON, performance consideration)

#### PlantIdentificationRequest Model
**Fields Tracked:**
- `status`, `location`, `latitude`, `longitude`
- `description`, `plant_size`, `habitat`
- `processed_by_ai`

#### PlantSpecies Model
**Fields Tracked:**
- `scientific_name`, `common_names`, `family`, `genus`, `species`
- `is_verified`, `auto_stored`, `confidence_score`
- `identification_count`, `api_source`

#### UserPlant Model
**Fields Tracked:**
- `nickname`, `acquisition_date`, `location_in_home`
- `notes`, `is_alive`, `is_public`

#### SavedCareInstructions Model
**Fields Tracked:**
- `plant_scientific_name`, `plant_common_name`, `custom_nickname`
- `personal_notes`, `care_difficulty_experienced`, `current_status`
- `share_with_community`, `is_favorite`

**Fields Excluded:**
- `care_instructions_data` (large JSON)

#### PlantDiseaseResult Model
**Fields Tracked:**
- `confidence_score`, `diagnosis_source`, `severity_assessment`
- `is_accepted`, `is_primary`, `stored_to_database`

**Fields Excluded:**
- `api_response_data` (large JSON)

---

## Querying Audit Logs

### Django Admin

Access audit logs at: **http://localhost:8000/admin/auditlog/logentry/**

Filters available:
- Content type (model)
- Action (create, update, delete, access)
- Timestamp
- Actor (user)

### Programmatic Queries

#### 1. All Actions on User Model
```python
from auditlog.models import LogEntry

user_logs = LogEntry.objects.filter(
    content_type__model='user'
).order_by('-timestamp')
```

#### 2. Changes to a Specific User
```python
from apps.users.models import User

user = User.objects.get(username='john_doe')
user_logs = LogEntry.objects.filter(
    content_type__model='user',
    object_pk=str(user.pk)
).order_by('-timestamp')
```

#### 3. All Actions by a Specific User
```python
user_actions = LogEntry.objects.filter(
    actor=user
).order_by('-timestamp')
```

#### 4. Recent Audit Entries (Last 24 Hours)
```python
from django.utils import timezone
from datetime import timedelta

recent_cutoff = timezone.now() - timedelta(hours=24)
recent_logs = LogEntry.objects.filter(
    timestamp__gte=recent_cutoff
).order_by('-timestamp')
```

#### 5. Changes to a Specific Field
```python
# Find all logs where email was changed
email_changes = LogEntry.objects.filter(
    content_type__model='user',
    changes__has_key='email'
).order_by('-timestamp')
```

#### 6. Deleted Objects (Still Tracked)
```python
deleted_objects = LogEntry.objects.filter(
    action=LogEntry.Action.DELETE
).order_by('-timestamp')
```

---

## GDPR Compliance

### Article 30 Requirements

**GDPR Article 30** requires organizations to maintain "records of processing activities" including:

1. ✅ **Name and contact details** of the controller (User model)
2. ✅ **Purposes of the processing** (Stored in `action` field)
3. ✅ **Description of data subjects and categories** (Content type)
4. ✅ **Categories of recipients** (Actor field)
5. ✅ **Transfers to third countries** (IP address tracking)
6. ✅ **Time limits for erasure** (Retention policy below)
7. ✅ **Security measures** (Encrypted fields, access control)

### Responding to GDPR Data Access Requests

When a user requests their data access history (Article 15):

```python
from apps.users.models import User
from auditlog.models import LogEntry

# Get user
user = User.objects.get(email='user@example.com')

# Get all data accessed related to this user
access_logs = LogEntry.objects.filter(
    object_pk=str(user.pk),
    content_type__model='user'
).order_by('-timestamp')

# Export to CSV
import csv
with open('gdpr_export.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['Timestamp', 'Action', 'Actor', 'IP Address', 'Changes'])
    for log in access_logs:
        writer.writerow([
            log.timestamp,
            log.get_action_display(),
            log.actor or 'System',
            log.remote_addr or 'N/A',
            log.changes
        ])
```

### Right to Erasure (Article 17)

**IMPORTANT**: Audit logs are **NOT deleted** when objects are deleted. This is intentional and required for compliance.

- User deletion removes personal data but preserves audit trail
- Audit logs serve as "records of processing activities" (Article 30)
- Retention applies even after deletion (7 years for some jurisdictions)

---

## Retention Policy

### Active Logs (0-90 days)

**Storage**: PostgreSQL database
**Access**: Real-time via Django Admin or API
**Performance**: Indexed for fast queries
**Purpose**: Operational monitoring, security incident response

### Archived Logs (90 days - 7 years)

**Storage**: S3/cold storage (to be implemented)
**Access**: On-demand retrieval
**Compliance**: GDPR Article 30, SOC 2
**Cleanup**: Automated via management command

### Cleanup Commands

#### Manual Cleanup (Development)
```bash
# Delete logs older than 90 days
python manage.py auditlogflush --before-days 90 --no-input
```

#### Automated Cleanup (Production)

**Option 1: Cron Job**
```bash
# Add to crontab
0 2 * * 0 cd /app && python manage.py auditlogflush --before-days 90 --no-input
```

**Option 2: Celery Beat** (Recommended)
```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'archive-audit-logs': {
        'task': 'apps.core.tasks.archive_audit_logs',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Weekly on Sunday at 2 AM
    },
}
```

### Archival Implementation (Future)

```python
# apps/core/management/commands/archive_audit_logs.py
import boto3
import json
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from auditlog.models import LogEntry

class Command(BaseCommand):
    help = 'Archive audit logs older than 90 days to S3'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=90)
        old_logs = LogEntry.objects.filter(timestamp__lt=cutoff)

        # Export to JSON
        logs_data = []
        for log in old_logs:
            logs_data.append({
                'timestamp': log.timestamp.isoformat(),
                'action': log.action,
                'actor_id': str(log.actor_id) if log.actor_id else None,
                'content_type_id': log.content_type_id,
                'object_pk': log.object_pk,
                'changes': log.changes,
                'remote_addr': log.remote_addr,
            })

        # Upload to S3
        s3 = boto3.client('s3')
        filename = f'audit_logs_{cutoff.date()}.json'
        s3.put_object(
            Bucket='plant-community-audit-logs',
            Key=filename,
            Body=json.dumps(logs_data, indent=2)
        )

        # Delete archived logs from database
        deleted_count = old_logs.count()
        old_logs.delete()

        self.stdout.write(
            self.style.SUCCESS(f'Archived {deleted_count} logs to S3: {filename}')
        )
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] Run migrations: `python manage.py migrate`
- [ ] Verify audit logs are created: `python test_audit_trail.py`
- [ ] Configure S3 bucket for log archival
- [ ] Set up automated archival (Celery Beat or cron)
- [ ] Configure monitoring/alerts for audit log storage growth
- [ ] Document incident response procedures
- [ ] Train staff on audit log access

### Environment Variables

```bash
# .env
AUDITLOG_RETENTION_DAYS=90  # Optional, default is 90
```

### Performance Monitoring

```sql
-- Check audit log table size
SELECT
    pg_size_pretty(pg_total_relation_size('auditlog_logentry')) as total_size,
    count(*) as row_count
FROM auditlog_logentry;

-- Most active models (last 30 days)
SELECT
    content_type_id,
    COUNT(*) as change_count
FROM auditlog_logentry
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY content_type_id
ORDER BY change_count DESC
LIMIT 10;
```

---

## Troubleshooting

### Issue: No Audit Logs Created

**Diagnosis**:
```python
# Check if auditlog is installed
from django.conf import settings
print('auditlog' in settings.INSTALLED_APPS)

# Check if models are registered
from auditlog.registry import auditlog
print(auditlog._registry.keys())
```

**Solutions**:
1. Ensure `auditlog` is in `INSTALLED_APPS`
2. Ensure `auditlog.middleware.AuditlogMiddleware` is in `MIDDLEWARE`
3. Verify model registration in `apps.py`

### Issue: Audit Logs Missing IP Address

**Diagnosis**: IP address requires middleware and proper request context

**Solutions**:
1. Verify middleware order (must be after `AuthenticationMiddleware`)
2. Ensure views use `request` parameter
3. For management commands, IP will be `None` (expected)

### Issue: Performance Degradation

**Diagnosis**:
```sql
-- Check index usage
SELECT * FROM pg_indexes WHERE tablename = 'auditlog_logentry';
```

**Solutions**:
1. Ensure database indexes are created (automatic with migrations)
2. Archive old logs more frequently
3. Exclude large JSON fields from auditing (already configured)

### Issue: Storage Growth

**Diagnosis**:
```python
from auditlog.models import LogEntry
total_logs = LogEntry.objects.count()
print(f"Total audit entries: {total_logs}")
print(f"Estimated storage: {total_logs * 1} KB")
```

**Solutions**:
1. Implement automated archival (see Retention Policy)
2. Reduce retention period for non-critical models
3. Exclude verbose fields from auditing

---

## References

- **django-auditlog Documentation**: https://django-auditlog.readthedocs.io/
- **GDPR Article 30**: https://gdpr-info.eu/art-30-gdpr/
- **SOC 2 Requirements**: https://www.aicpa.org/soc4so
- **NIST SP 800-92** (Logging Best Practices): https://csrc.nist.gov/publications/detail/sp/800-92/final

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-27 | 1.0 | Initial documentation - audit trail implementation complete |

---

**Document Owner**: Engineering Team
**Review Frequency**: Quarterly
**Next Review**: January 2026
