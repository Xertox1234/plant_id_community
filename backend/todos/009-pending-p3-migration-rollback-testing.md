---
status: pending
priority: p3
issue_id: "009"
tags: [code-review, testing, migrations, database, devops, audit]
dependencies: []
---

# Create Migration Rollback Testing Framework

## Problem Statement
The codebase has 50 database migration files across multiple apps, including complex PostgreSQL-specific features (GIN indexes, trigrams). While migrations appear well-structured, there's no evidence of systematic rollback testing or documentation. Migration safety is critical for production deployments and disaster recovery.

## Findings
- Discovered during comprehensive codebase audit (October 31, 2025)
- **Migration count**: 50 files across apps
- **Complexity**: PostgreSQL-specific features (GIN indexes, full-text search)
- **Current state**:
  - ✅ Migrations exist and appear well-written
  - ✅ PostgreSQL features properly guarded (vendor checks)
  - ✅ Good example: `apps/blog/migrations/0007_add_performance_indexes.py`
  - ❌ No rollback testing documentation
  - ❌ No rollback test suite
  - ❌ No migration safety checklist

**Example of good migration** (with vendor check):
```python
# apps/blog/migrations/0007_add_performance_indexes.py
def forwards_func(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        # PostgreSQL-specific indexes
        schema_editor.execute("CREATE INDEX ...")
    # else: skip for SQLite (development)
```

**Risk scenarios without rollback testing**:
1. Data loss during rollback (no reverse migration)
2. Broken rollback SQL (syntax errors)
3. Failed rollback leaves database in inconsistent state
4. Production incident recovery impossible

## Proposed Solutions

### Option 1: Comprehensive Rollback Testing Framework (Recommended)
**Create systematic testing process**:

**Phase 1 - Testing Script** (2 hours):
```bash
#!/bin/bash
# scripts/test_migration_rollback.sh

APP_NAME=$1
MIGRATION_NUMBER=$2

echo "Testing migration ${APP_NAME}.${MIGRATION_NUMBER}"

# 1. Get current migration state
CURRENT=$(python manage.py showmigrations ${APP_NAME} | grep "\[X\]" | tail -1)

# 2. Forward migration
echo "Applying migration..."
python manage.py migrate ${APP_NAME} ${MIGRATION_NUMBER}
if [ $? -ne 0 ]; then
    echo "❌ Forward migration failed"
    exit 1
fi

# 3. Create test data
echo "Creating test data..."
python manage.py shell -c "
from apps.${APP_NAME}.models import *
# Create test objects to verify data integrity
"

# 4. Rollback migration
echo "Rolling back migration..."
python manage.py migrate ${APP_NAME} $((MIGRATION_NUMBER - 1))
if [ $? -ne 0 ]; then
    echo "❌ Rollback failed"
    exit 1
fi

# 5. Re-apply migration
echo "Re-applying migration..."
python manage.py migrate ${APP_NAME} ${MIGRATION_NUMBER}
if [ $? -ne 0 ]; then
    echo "❌ Re-application failed"
    exit 1
fi

# 6. Verify data integrity
echo "Verifying data integrity..."
python manage.py shell -c "
from apps.${APP_NAME}.models import *
# Verify test objects still exist
"

echo "✅ Migration rollback test passed"
```

**Phase 2 - Migration Checklist** (1 hour):
```markdown
# Migration Safety Checklist

Before merging any migration:

## Design
- [ ] Migration has both forwards and backwards operations
- [ ] Data transformations are reversible
- [ ] No data loss in rollback (backup to temporary table if needed)
- [ ] PostgreSQL-specific features guarded with vendor checks

## Testing
- [ ] Run forward migration on test database
- [ ] Create test data
- [ ] Run rollback successfully
- [ ] Re-apply migration successfully
- [ ] Verify data integrity maintained

## Production Readiness
- [ ] Tested on PostgreSQL (production database)
- [ ] Tested on SQLite (development database)
- [ ] Migration can run with zero downtime (if required)
- [ ] Large data migrations use batching (RunPython)
- [ ] Rollback plan documented in migration file docstring

## Documentation
- [ ] Migration purpose documented in docstring
- [ ] Risks documented (if any)
- [ ] Rollback procedure documented
- [ ] Data backup recommended (if destructive)
```

**Phase 3 - CI Integration** (1 hour):
```yaml
# .github/workflows/migration-test.yml
name: Migration Safety Tests

on:
  pull_request:
    paths:
      - '**/migrations/*.py'

jobs:
  test-migrations:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:18
        env:
          POSTGRES_DB: test_db
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Test migration rollbacks
        run: |
          # Run rollback test for each new migration
          ./scripts/test_migration_rollback.sh
```

**Effort**: Medium (4 hours initial setup)
**Risk**: Low

### Option 2: Manual Testing Protocol
Document manual testing steps without automation.

**Pros**:
- Quick to implement
- No CI overhead

**Cons**:
- Relies on developer discipline
- No systematic enforcement

**Effort**: Small (1 hour)
**Risk**: Medium (easy to skip)

## Recommended Action
**Option 1** - Full framework with CI integration.

Rationale:
1. 50 migrations is significant complexity
2. PostgreSQL-specific features require careful testing
3. Production deployments need rollback safety guarantees
4. Automation prevents human error

**Implementation timeline**:
- **Week 1**: Create rollback testing script
- **Week 2**: Create migration checklist, document process
- **Week 3**: Add CI workflow (optional but recommended)
- **Week 4**: Run retroactive tests on critical migrations

## Technical Details
- **Migration Distribution**:
  - `apps/plant_identification/`: ~15 migrations
  - `apps/blog/`: ~10 migrations
  - `apps/users/`: ~8 migrations
  - `apps/forum/`: ~10 migrations
  - `apps/core/`: ~5 migrations
  - Other apps: ~2 migrations

- **Complex Migrations** (need thorough testing):
  - GIN index creation: `apps/blog/migrations/0007_add_performance_indexes.py`
  - Full-text search: `apps/plant_identification/migrations/0013_add_search_gin_indexes.py`
  - Data transformations: Any RunPython operations

- **Database Compatibility**:
  - Production: PostgreSQL 18
  - Development: SQLite (some features unavailable)

## Resources
- Django migration docs: https://docs.djangoproject.com/en/5.2/topics/migrations/
- Migration safety guide: `backend/docs/development/MIGRATION_0008_SAFETY_IMPROVEMENTS.md`
- Example migration: `apps/blog/migrations/0007_add_performance_indexes.py`
- Code review audit: October 31, 2025

## Acceptance Criteria
- [ ] Create rollback testing script (`scripts/test_migration_rollback.sh`)
- [ ] Create migration safety checklist (`docs/development/MIGRATION_CHECKLIST.md`)
- [ ] Document rollback testing process
- [ ] Run retroactive tests on 5 most complex migrations
- [ ] Optional: Add CI workflow for automatic testing
- [ ] Update developer onboarding docs with migration testing
- [ ] Add migration testing to PR template checklist

## Work Log

### 2025-10-31 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Counted 50 migration files during codebase audit
- Reviewed migration complexity (PostgreSQL features)
- Found good practices (vendor checks) but no testing framework
- Categorized as P3 DevOps issue (preventive)

**Learnings:**
- Migrations are well-written (good vendor checks)
- But no evidence of systematic rollback testing
- PostgreSQL-specific features add complexity
- Need safety net for production deployments

**Good examples found**:
- `apps/blog/migrations/0007_add_performance_indexes.py` - proper vendor check
- `apps/plant_identification/migrations/0012_add_performance_indexes.py` - good structure

## Notes
Source: Code review performed on October 31, 2025
Review command: `/compounding-engineering:review audit code base`
Severity: P3 (DevOps best practice, not urgent)
Category: Testing - Migration Safety
Current risk: Low (migrations appear well-written)
Future risk: Medium (as codebase grows, complexity increases)
