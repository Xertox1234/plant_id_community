# Migration Safety Checklist

**Last Updated**: November 2, 2025
**Owner**: Engineering Team
**Status**: Active

## Overview

This checklist ensures all Django migrations are production-ready with safe rollback capabilities. Use this checklist before merging any PR that contains database migrations.

**Related Documentation**:
- Rollback testing script: `/backend/scripts/test_migration_rollback.sh`
- Migration safety improvements: `/backend/docs/development/MIGRATION_0008_SAFETY_IMPROVEMENTS.md`
- Dependency update policy: `/backend/docs/development/DEPENDENCY_UPDATE_POLICY.md`

## Quick Reference

### Before Creating Migration
- [ ] Plan data transformations carefully (reversibility required)
- [ ] Consider zero-downtime requirements for production
- [ ] Identify PostgreSQL-specific features that need guards

### After Creating Migration
- [ ] Run rollback testing script: `./scripts/test_migration_rollback.sh <app> <migration>`
- [ ] Test on both PostgreSQL (production) and SQLite (dev)
- [ ] Document rollback procedure in migration docstring

### Before Merging PR
- [ ] All checklist items completed
- [ ] CI tests passing (including migration tests)
- [ ] Code review approved
- [ ] Rollback plan documented

---

## Complete Migration Safety Checklist

### Section 1: Migration Design

#### 1.1 Reversibility
- [ ] **Migration has both forwards and backwards operations**
  - Every `migrations.RunSQL()` has a `reverse_sql` parameter
  - Every `migrations.RunPython()` has a `reverse_code` parameter
  - Schema changes use Django's reversible operations

- [ ] **Data transformations are reversible**
  - No destructive data deletions without backup
  - Data migrations include reverse logic to restore original state
  - Use temporary tables/columns for complex transformations

- [ ] **No data loss in rollback scenario**
  - If dropping columns, data is backed up first
  - If changing data types, conversion is bi-directional
  - Critical data has fallback preservation strategy

Example of reversible data migration:
```python
from django.db import migrations

def forwards_func(apps, schema_editor):
    MyModel = apps.get_model('myapp', 'MyModel')
    for obj in MyModel.objects.all():
        # Transform data with ability to reverse
        obj.new_field = transform(obj.old_field)
        obj.save()

def reverse_func(apps, schema_editor):
    MyModel = apps.get_model('myapp', 'MyModel')
    for obj in MyModel.objects.all():
        # Reverse transformation
        obj.old_field = reverse_transform(obj.new_field)
        obj.save()

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
```

#### 1.2 Database Compatibility
- [ ] **PostgreSQL-specific features are properly guarded**
  - GIN/GiST indexes wrapped in vendor checks
  - Full-text search (pg_trgm) wrapped in vendor checks
  - CONCURRENTLY operations wrapped in vendor checks
  - Graceful skip on SQLite for development environments

Example of vendor check:
```python
from django.db import migrations

def forwards_func(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        # PostgreSQL-specific index creation
        schema_editor.execute(
            "CREATE INDEX CONCURRENTLY idx_name ON table_name USING GIN (column)"
        )
    # else: skip for SQLite (development)

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(forwards_func, migrations.RunPython.noop),
    ]
```

- [ ] **Migration works on both PostgreSQL and SQLite**
  - Test on PostgreSQL: Production database equivalent
  - Test on SQLite: Developer environment compatibility
  - No hard failures when PostgreSQL features unavailable

#### 1.3 Performance Considerations
- [ ] **Large data migrations use batching**
  - Avoid loading all objects into memory at once
  - Use `iterator()` for queryset iteration
  - Process in chunks (e.g., 1000 records at a time)

Example of batched data migration:
```python
def forwards_func(apps, schema_editor):
    MyModel = apps.get_model('myapp', 'MyModel')

    # Process in batches to avoid memory issues
    batch_size = 1000
    total = MyModel.objects.count()

    for start in range(0, total, batch_size):
        batch = MyModel.objects.all()[start:start + batch_size]
        for obj in batch:
            obj.new_field = transform(obj.old_field)
        MyModel.objects.bulk_update(batch, ['new_field'])
```

- [ ] **Index creation uses CONCURRENTLY (PostgreSQL)**
  - Prevents table locking during index creation
  - Allows zero-downtime deployments
  - Wrapped in vendor check for PostgreSQL only

- [ ] **Migration can complete within acceptable timeframe**
  - Estimate migration time on production-sized dataset
  - Consider scheduled maintenance window if needed
  - Test on staging environment first

#### 1.4 Zero-Downtime Requirements
- [ ] **Migration can run while application is serving traffic** (if required)
  - No exclusive table locks
  - Backward-compatible schema changes
  - Multi-phase migrations for complex changes

- [ ] **Migration is idempotent**
  - Can be run multiple times safely
  - Checks for existing state before making changes
  - No errors if operation already applied

---

### Section 2: Testing Requirements

#### 2.1 Automated Rollback Testing
- [ ] **Run rollback testing script**
  ```bash
  cd backend
  ./scripts/test_migration_rollback.sh <app_name> <migration_name>
  ```
  Example:
  ```bash
  ./scripts/test_migration_rollback.sh plant_identification 0020_add_diagnosis_card_and_reminder_models
  ```

- [ ] **Review rollback test output**
  - Forward migration: PASSED
  - Rollback: PASSED
  - Re-application: PASSED
  - Data integrity: VERIFIED

- [ ] **Test on PostgreSQL (production database)**
  ```bash
  # Ensure DATABASE_URL points to PostgreSQL
  export DATABASE_URL="postgresql://user:password@localhost:5432/test_db"
  python manage.py migrate <app_name> <migration_name>
  ```

- [ ] **Test on SQLite (development database)**
  ```bash
  # Use SQLite for local testing
  export DATABASE_URL="sqlite:///test_db.sqlite3"
  python manage.py migrate <app_name> <migration_name>
  ```

#### 2.2 Data Integrity Testing
- [ ] **Create test data before rollback**
  - Insert representative test records
  - Cover edge cases and boundary conditions
  - Include data that exercises all migration operations

- [ ] **Verify test data after rollback cycle**
  - Test data still exists after forward → rollback → forward
  - Data transformations correctly reversed
  - No orphaned records or broken relationships

- [ ] **Run application test suite**
  ```bash
  # Run full test suite
  python manage.py test --keepdb -v 2

  # Run app-specific tests
  python manage.py test apps.<app_name> --keepdb -v 2
  ```

#### 2.3 Performance Testing
- [ ] **Measure migration execution time**
  - Run on production-sized dataset (staging environment)
  - Document expected duration in migration docstring
  - Flag long-running migrations (>5 minutes)

- [ ] **Test with realistic data volume**
  - Create test dataset matching production scale
  - Verify batching works correctly
  - Monitor memory usage during migration

---

### Section 3: Production Readiness

#### 3.1 Documentation
- [ ] **Migration purpose documented in docstring**
  ```python
  class Migration(migrations.Migration):
      """
      Add diagnosis card and reminder models for plant health tracking.

      Changes:
      - Add DiagnosisCard model with UUID primary key
      - Add DiagnosisReminder model with scheduling fields
      - Create indexes on user_id and created_at fields

      Rollback: Safe - drops tables and indexes

      Estimated time: <1 second (no data migration)
      """
      dependencies = [...]
      operations = [...]
  ```

- [ ] **Risks documented (if any)**
  - Data loss potential
  - Performance impact
  - Backward compatibility concerns
  - Required follow-up migrations

- [ ] **Rollback procedure documented**
  - Step-by-step rollback instructions
  - Expected behavior after rollback
  - Data recovery steps if needed
  - Manual cleanup required (if any)

- [ ] **Data backup recommended (if destructive)**
  ```python
  class Migration(migrations.Migration):
      """
      WARNING: This migration drops the old_table.

      BACKUP REQUIRED: Run this before migration:
      pg_dump -t old_table dbname > old_table_backup.sql

      Rollback: Requires manual data restoration from backup
      """
  ```

#### 3.2 Deployment Planning
- [ ] **Migration tested on staging environment**
  - Run on staging database (production equivalent)
  - Verify application behavior post-migration
  - Test rollback on staging

- [ ] **Deployment window identified (if needed)**
  - Schedule maintenance window for long migrations
  - Notify stakeholders of downtime
  - Prepare rollback plan

- [ ] **Monitoring plan in place**
  - Database performance metrics during migration
  - Application error rates post-migration
  - Rollback triggers defined (error thresholds)

#### 3.3 Review and Approval
- [ ] **Code review completed**
  - Migration code reviewed by senior engineer
  - Rollback logic verified
  - Performance considerations addressed

- [ ] **CI tests passing**
  - All automated tests pass
  - Migration tests included in CI pipeline
  - No deprecation warnings

- [ ] **Architecture approval (for complex migrations)**
  - Schema changes reviewed by tech lead
  - Data model changes approved
  - Breaking changes communicated

---

### Section 4: Special Cases

#### 4.1 Data Migrations with RunPython
- [ ] **Historical models used (not current models)**
  ```python
  # Correct: Use apps.get_model()
  def forwards_func(apps, schema_editor):
      MyModel = apps.get_model('myapp', 'MyModel')
      # Use MyModel...

  # Incorrect: Direct model import
  from myapp.models import MyModel  # DON'T DO THIS
  ```

- [ ] **Reverse function provided**
  ```python
  migrations.RunPython(forwards_func, reverse_func)
  # NOT: migrations.RunPython(forwards_func)
  ```

- [ ] **Database operations use schema_editor**
  ```python
  def forwards_func(apps, schema_editor):
      # Use schema_editor for raw SQL
      schema_editor.execute("CREATE INDEX ...")
  ```

#### 4.2 Schema Changes
- [ ] **Nullable fields or defaults provided**
  ```python
  # Good: nullable=True for existing rows
  migrations.AddField('MyModel', 'new_field', models.CharField(null=True))

  # Or: provide default value
  migrations.AddField('MyModel', 'new_field', models.CharField(default=''))
  ```

- [ ] **Multi-phase migration for complex changes**
  ```python
  # Phase 1: Add new nullable column
  # Phase 2: Populate data
  # Phase 3: Make column non-nullable
  # Phase 4: Remove old column
  ```

#### 4.3 Index Creation
- [ ] **Indexes created CONCURRENTLY (PostgreSQL)**
  ```python
  if schema_editor.connection.vendor == 'postgresql':
      schema_editor.execute(
          "CREATE INDEX CONCURRENTLY idx_name ON table (column)"
      )
  ```

- [ ] **Index names follow naming convention**
  - Format: `idx_<table>_<column>` or `idx_<table>_<purpose>`
  - Example: `idx_plant_identification_user_id`
  - Max 63 characters (PostgreSQL limit)

---

### Section 5: Post-Deployment

#### 5.1 Verification
- [ ] **Migration applied successfully in production**
  - Check `django_migrations` table for entry
  - Verify schema changes with `\d` in psql
  - No errors in application logs

- [ ] **Application behavior verified**
  - Smoke test critical features
  - Monitor error rates for 24 hours
  - Check performance metrics

#### 5.2 Documentation Updates
- [ ] **Update schema documentation (if needed)**
  - Update ER diagrams
  - Update API documentation
  - Update developer onboarding docs

- [ ] **Document migration in changelog**
  - Add entry to CHANGELOG.md
  - Include migration purpose and impact
  - Note any breaking changes

---

## Migration Testing Script Usage

### Basic Usage
```bash
cd backend
./scripts/test_migration_rollback.sh <app_name> <migration_name>
```

### Example: Test Plant Identification Migration
```bash
./scripts/test_migration_rollback.sh plant_identification 0020_add_diagnosis_card_and_reminder_models
```

### What the Script Tests
1. Current migration state capture
2. Forward migration application
3. Test data creation (app-specific)
4. Migration rollback
5. Migration re-application (idempotency)
6. Data integrity verification
7. PostgreSQL compatibility check
8. Reverse operation validation

### Test Output
The script generates:
- Console output with colored status indicators
- Log file: `migration_test_YYYYMMDD_HHMMSS.log`
- Test report with pass/fail results

### Interpreting Results
- ✓ All tests passed: Migration is rollback-safe
- ✗ Any test failed: Fix migration before merging
- ⚠ Warnings: Review but may be acceptable

---

## Common Migration Patterns

### Pattern 1: Add Nullable Field
```python
class Migration(migrations.Migration):
    """Add optional description field to Plant model."""

    operations = [
        migrations.AddField(
            model_name='plant',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
    ]
```

### Pattern 2: Add Non-Nullable Field with Default
```python
class Migration(migrations.Migration):
    """Add status field with default value."""

    operations = [
        migrations.AddField(
            model_name='plant',
            name='status',
            field=models.CharField(
                max_length=20,
                default='active',
                choices=[('active', 'Active'), ('archived', 'Archived')],
            ),
        ),
    ]
```

### Pattern 3: Data Migration with Reverse
```python
def forwards_func(apps, schema_editor):
    Plant = apps.get_model('myapp', 'Plant')
    for plant in Plant.objects.all():
        plant.slug = slugify(plant.name)
        plant.save()

def reverse_func(apps, schema_editor):
    Plant = apps.get_model('myapp', 'Plant')
    for plant in Plant.objects.all():
        plant.slug = ''  # Clear slugs on rollback
        plant.save()

class Migration(migrations.Migration):
    """Generate slugs for all existing plants."""

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
```

### Pattern 4: PostgreSQL-Specific Index
```python
def forwards_func(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(
            """
            CREATE INDEX CONCURRENTLY idx_plant_name_trgm
            ON myapp_plant
            USING GIN (name gin_trgm_ops)
            """
        )

def reverse_func(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("DROP INDEX IF EXISTS idx_plant_name_trgm")

class Migration(migrations.Migration):
    """Add trigram index for plant name search."""

    dependencies = [
        ('myapp', '0007_previous_migration'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
```

### Pattern 5: Multi-Phase Migration (Complex Changes)
```python
# Migration 0008: Phase 1 - Add new nullable column
class Migration(migrations.Migration):
    operations = [
        migrations.AddField('Plant', 'new_field', models.CharField(null=True))
    ]

# Migration 0009: Phase 2 - Populate data
class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(populate_new_field, reverse_populate)
    ]

# Migration 0010: Phase 3 - Make non-nullable
class Migration(migrations.Migration):
    operations = [
        migrations.AlterField('Plant', 'new_field', models.CharField(null=False))
    ]

# Migration 0011: Phase 4 - Remove old column
class Migration(migrations.Migration):
    operations = [
        migrations.RemoveField('Plant', 'old_field')
    ]
```

---

## Troubleshooting

### Issue: Migration Fails to Rollback
**Symptoms**: `python manage.py migrate <app> <previous_migration>` fails

**Diagnosis**:
1. Check migration file for `reverse_code` in RunPython
2. Check for irreversible operations (e.g., `RunSQL` without `reverse_sql`)
3. Review error message for SQL syntax issues

**Solution**:
- Add reverse operations to migration file
- Use `migrations.RunPython.noop` if rollback not needed (document why)
- Fix SQL syntax errors in reverse operations

### Issue: Data Lost After Rollback
**Symptoms**: Test data missing after rollback cycle

**Diagnosis**:
1. Check if migration includes destructive operations (DROP TABLE, DROP COLUMN)
2. Verify reverse operation preserves data
3. Review RunPython reverse_code logic

**Solution**:
- Add data backup step to forward migration
- Restore data in reverse migration
- Use temporary tables for complex transformations

### Issue: PostgreSQL Features Break SQLite
**Symptoms**: Migration works on production but fails locally

**Diagnosis**:
1. Check for GIN/GiST indexes without vendor checks
2. Look for PostgreSQL-specific SQL syntax
3. Review pg_trgm extension usage

**Solution**:
- Wrap PostgreSQL features in vendor checks
- Provide SQLite fallback or skip gracefully
- Test on both databases before merging

### Issue: Migration Takes Too Long
**Symptoms**: Migration timeout or excessive runtime

**Diagnosis**:
1. Check for full table scans
2. Look for missing batching in data migrations
3. Review index creation (should use CONCURRENTLY)

**Solution**:
- Add batching to data migrations
- Use CONCURRENTLY for index creation
- Consider multi-phase migration for large changes

---

## References

### Internal Documentation
- Migration testing script: `/backend/scripts/test_migration_rollback.sh`
- Migration safety improvements: `/backend/docs/development/MIGRATION_0008_SAFETY_IMPROVEMENTS.md`
- Example migrations: `/backend/apps/blog/migrations/0007_add_performance_indexes.py`

### External Resources
- Django Migrations: https://docs.djangoproject.com/en/5.2/topics/migrations/
- PostgreSQL Indexes: https://www.postgresql.org/docs/current/indexes.html
- Zero-Downtime Migrations: https://fly.io/django-beats/zero-downtime-migrations/

### Related Policies
- Dependency Update Policy: `/backend/docs/development/DEPENDENCY_UPDATE_POLICY.md`
- Code Review Checklist: `/backend/docs/development/CODE_REVIEW_CHECKLIST.md`

---

## Checklist Template (Copy for PRs)

```markdown
## Migration Safety Checklist

### Design
- [ ] Migration has both forwards and backwards operations
- [ ] Data transformations are reversible
- [ ] No data loss in rollback scenario
- [ ] PostgreSQL-specific features guarded with vendor checks

### Testing
- [ ] Run rollback testing script: `./scripts/test_migration_rollback.sh <app> <migration>`
- [ ] Tested on PostgreSQL (production database)
- [ ] Tested on SQLite (development database)
- [ ] Test data integrity verified after rollback cycle
- [ ] Application test suite passing

### Production Readiness
- [ ] Migration purpose documented in docstring
- [ ] Rollback procedure documented
- [ ] Tested on staging environment
- [ ] CI tests passing
- [ ] Code review completed

### Performance
- [ ] Large data migrations use batching
- [ ] Index creation uses CONCURRENTLY (PostgreSQL)
- [ ] Migration runtime acceptable (<5 minutes)

### Special Cases
- [ ] N/A or (describe special considerations)
```

---

**Version History**:
- v1.0 (2025-11-02): Initial checklist created with rollback testing framework
