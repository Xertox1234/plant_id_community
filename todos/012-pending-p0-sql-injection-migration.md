---
status: pending
priority: p0
issue_id: "012"
tags: [security, critical, sql-injection, django, database, migrations]
dependencies: []
---

# SQL Injection Risk in Database Migration

## Problem Statement

Database migration uses string interpolation (f-strings) in raw SQL queries, creating a potential SQL injection vulnerability if table names are ever user-controlled.

**Location:** `backend/apps/search/migrations/0003_simple_search_vectors.py:31-34,53-54`

**CVSS Score:** 8.1 (HIGH)

## Findings

- Discovered during comprehensive security audit by Security Sentinel agent
- **Vulnerable Code:**
  ```python
  # Line 31-34: Forward migration
  for table in tables_to_modify:
      cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS search_vector tsvector;")
      cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table.split('_')[-1]}_search_vector ON {table} USING gin(search_vector);")

  # Line 53-54: Reverse migration
  for table in tables_to_modify:
      cursor.execute(f"DROP INDEX IF EXISTS idx_{table.split('_')[-1]}_search_vector;")
      cursor.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS search_vector;")
  ```

- **Current State:**
  - Table names are hardcoded in `tables_to_modify` list ✅
  - String interpolation bypasses Django ORM's SQL injection protection ❌
  - Migration runs with elevated database privileges ❌
  - Pattern could be copied to user-input contexts ❌

- **Why This Matters:**
  Even though `tables_to_modify` is currently hardcoded, this pattern:
  1. Sets a bad precedent for other developers
  2. Could be copied to user-input contexts
  3. Bypasses Django ORM's SQL injection protection
  4. Violates security best practices
  5. Migration code runs with elevated privileges

- **Exploitation Scenario (if pattern copied):**
  ```python
  # If this pattern is copied to a view that accepts user input:
  table_name = request.GET.get('table')  # User-controlled
  cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN ...")
  # User input: "users; DROP TABLE auth_user; --"
  # Resulting SQL: "ALTER TABLE users; DROP TABLE auth_user; -- ADD COLUMN ..."
  ```

## Proposed Solutions

### Option 1: Use psycopg2.sql.Identifier (RECOMMENDED)

```python
from django.db import migrations
from psycopg2 import sql  # Add this import

def add_search_vectors(apps, schema_editor):
    """Add search vector columns and indexes to specified tables."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    tables_to_modify = [
        'machina_forum_conversation_topic',
        'machina_forum_conversation_post',
        'plant_identification_plantspecies',
        'plant_identification_plantdiseasedatabase',
        'blog_blogpostpage',
    ]

    with schema_editor.connection.cursor() as cursor:
        for table in tables_to_modify:
            # Validate table name against whitelist (defense in depth)
            if table not in tables_to_modify:
                logger.error(f"[SECURITY] Invalid table name: {table}")
                continue

            # ✅ SAFE - Use sql.Identifier for proper escaping
            cursor.execute(
                sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS search_vector tsvector").format(
                    sql.Identifier(table)
                )
            )

            index_name = f"idx_{table.split('_')[-1]}_search_vector"
            cursor.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING gin(search_vector)").format(
                    sql.Identifier(index_name),
                    sql.Identifier(table)
                )
            )

def remove_search_vectors(apps, schema_editor):
    """Remove search vector columns and indexes."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    tables_to_modify = [
        'machina_forum_conversation_topic',
        'machina_forum_conversation_post',
        'plant_identification_plantspecies',
        'plant_identification_plantdiseasedatabase',
        'blog_blogpostpage',
    ]

    with schema_editor.connection.cursor() as cursor:
        for table in tables_to_modify:
            if table not in tables_to_modify:
                continue

            index_name = f"idx_{table.split('_')[-1]}_search_vector"

            # ✅ SAFE - Use sql.Identifier
            cursor.execute(
                sql.SQL("DROP INDEX IF EXISTS {}").format(
                    sql.Identifier(index_name)
                )
            )

            cursor.execute(
                sql.SQL("ALTER TABLE {} DROP COLUMN IF EXISTS search_vector").format(
                    sql.Identifier(table)
                )
            )

class Migration(migrations.Migration):
    dependencies = [
        ('search', '0002_previous_migration'),
    ]

    operations = [
        migrations.RunPython(
            add_search_vectors,
            remove_search_vectors
        ),
    ]
```

**Benefits:**
- Uses PostgreSQL's built-in identifier quoting
- Prevents SQL injection even if table names become dynamic
- Industry-standard pattern
- No performance impact

**Effort:** 1 hour (fix + testing)

### Option 2: Add Explicit Validation (Supplementary)

Even with `sql.Identifier`, add whitelist validation:

```python
ALLOWED_TABLES = {
    'machina_forum_conversation_topic',
    'machina_forum_conversation_post',
    'plant_identification_plantspecies',
    'plant_identification_plantdiseasedatabase',
    'blog_blogpostpage',
}

def add_search_vectors(apps, schema_editor):
    for table in tables_to_modify:
        # Defense in depth: explicit whitelist
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Table not in whitelist: {table}")

        # Then use sql.Identifier as above
        cursor.execute(...)
```

**Benefits:**
- Defense in depth
- Explicit validation
- Fails loudly if table list is modified incorrectly

## Recommended Action

**IMMEDIATE (within 1 hour):**
1. ✅ Update migration file to use `sql.Identifier`
2. ✅ Add explicit whitelist validation
3. ✅ Test migration on development database
4. ✅ Test rollback (reverse migration)

**Within 24 hours:**
5. ✅ Audit all other migrations for similar patterns
6. ✅ Document pattern in CLAUDE.md under "Migration Security"
7. ✅ Add to code review checklist

**Pattern to Add to CLAUDE.md:**
```markdown
### Migration Security (CRITICAL)

**NEVER use f-strings in raw SQL migrations:**

```python
# ❌ BAD - SQL injection risk
cursor.execute(f"ALTER TABLE {table} ADD COLUMN ...")

# ✅ GOOD - Use psycopg2.sql.Identifier
from psycopg2 import sql
cursor.execute(
    sql.SQL("ALTER TABLE {} ADD COLUMN ...").format(
        sql.Identifier(table)
    )
)
```

**Why:** Even if table names are hardcoded now, this pattern could be copied to user-input contexts.
```

## Technical Details

- **Affected Files**:
  - `backend/apps/search/migrations/0003_simple_search_vectors.py` (update required)
  - All other migration files with raw SQL (audit needed)
  - `backend/CLAUDE.md` (add security pattern)

- **Related Components**: Django migrations, PostgreSQL full-text search

- **Dependencies**: psycopg2 (already installed)

- **Database Changes**: None (this is a code fix, not a schema change)

- **Testing Required**:
  ```bash
  # Test forward migration
  python manage.py migrate search 0003

  # Test rollback
  python manage.py migrate search 0002

  # Verify tables have search_vector column
  psql -d plant_community -c "\d machina_forum_conversation_topic"
  ```

## Resources

- Security Sentinel audit report (November 9, 2025)
- CWE-89: SQL Injection
- CVSS Score: 8.1 (HIGH)
- psycopg2.sql documentation: https://www.psycopg.org/docs/sql.html
- Django migration best practices: https://docs.djangoproject.com/en/5.2/topics/migrations/
- OWASP SQL Injection: https://owasp.org/www-community/attacks/SQL_Injection

## Acceptance Criteria

- [ ] Migration file updated to use `sql.Identifier`
- [ ] Whitelist validation added (defense in depth)
- [ ] Forward migration tested on dev database
- [ ] Reverse migration tested (rollback)
- [ ] All other migrations audited for similar patterns
- [ ] Pattern documented in CLAUDE.md
- [ ] Code review checklist updated
- [ ] Tests pass
- [ ] No SQL injection vulnerabilities remain

## Work Log

### 2025-11-09 - Security Audit Discovery
**By:** Claude Code Review System (Security Sentinel Agent)
**Actions:**
- Discovered during comprehensive codebase audit
- Identified as CRITICAL (P0) - SQL injection risk
- CVSS 8.1 - Elevated privileges in migrations
- Pattern violation flagged

**Learnings:**
- F-strings bypass Django ORM's SQL injection protection
- Migrations run with elevated database privileges
- Bad patterns in migrations can be copied to views
- `sql.Identifier` is the PostgreSQL-standard solution
- Defense in depth: use Identifier + whitelist validation

**Next Steps:**
- Fix migration file immediately
- Audit all other migrations
- Document pattern for future developers

## Notes

**Why P0 (Critical):**
- While current code is not exploitable (hardcoded tables), the pattern is a ticking time bomb
- If copied to user-input context, allows database compromise
- Migrations run with elevated privileges (DROP, ALTER permissions)
- Violates Django security best practices

**Migration Testing:**
```bash
# Safe rollback procedure if issues found:
python manage.py migrate search 0002  # Rollback to previous
# Fix migration file
python manage.py migrate search 0003  # Re-apply fixed version
```

Source: Comprehensive security audit performed on November 9, 2025
Review command: /compounding-engineering:review audit codebase
Agent: Security Sentinel
