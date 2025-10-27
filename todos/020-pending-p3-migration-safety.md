---
status: ready
priority: p3
issue_id: "020"
tags: [database, migrations, data-integrity]
dependencies: []
---

# Fix Non-Reversible Migrations

## Problem

Migration 0008 alters email field without data migration for NULL → empty string conversion.

## Solution

Add RunPython before AlterField:
```python
def migrate_null_emails(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(email__isnull=True).update(email='')

migrations.RunPython(migrate_null_emails, migrations.RunPython.noop),
migrations.AlterField(...),
```

**Effort**: 30 minutes
