---
status: ready
priority: p4
issue_id: "028"
tags: [security, configuration, secrets]
dependencies: []
---

# Move Hardcoded API Keys to Environment Variables

## Problem

API timeout constants hardcoded in `constants.py`. While not sensitive secrets themselves, pattern indicates potential for hardcoding actual secrets.

## Findings

**security-sentinel**:
- `PLANT_ID_API_TIMEOUT = 30` hardcoded (line 45)
- `PLANTNET_API_REQUEST_TIMEOUT = 20` hardcoded (line 82)
- Pattern: Configuration that might change per environment should use env vars
- Not an active vulnerability but indicates configuration management gap

**best-practices-researcher**:
- 12-Factor App: "Store config in environment"
- Timeouts may vary by deployment (dev vs prod)
- Easier to tune without code changes

## Proposed Solutions

### Option 1: Environment Variables with Defaults (Recommended)
```python
# constants.py
import os

PLANT_ID_API_TIMEOUT = int(os.getenv('PLANT_ID_API_TIMEOUT', 30))
PLANTNET_API_REQUEST_TIMEOUT = int(os.getenv('PLANTNET_API_TIMEOUT', 20))
```

```bash
# .env
PLANT_ID_API_TIMEOUT=45  # Longer timeout for production
PLANTNET_API_TIMEOUT=30
```

**Pros**: Environment-specific tuning, no code changes for config updates
**Cons**: Adds env var management overhead
**Effort**: 30 minutes
**Risk**: Very low (has defaults)

### Option 2: Keep Hardcoded (Status Quo)
**Pros**: Simpler, fewer environment variables
**Cons**: Requires code deploy to change timeouts
**Risk**: Very low (just configuration)

## Recommended Action

**Option 2** - Keep hardcoded for now:
- These are not secrets, just configuration
- No evidence of environment-specific timeout needs
- Focus on actual secrets (API keys) which are already in env vars
- Revisit if timeout tuning becomes necessary

**Alternative**: Document in `.env.example` as optional overrides

## Technical Details

**Current values**:
- Plant.id timeout: 30 seconds
- PlantNet timeout: 20 seconds

**Location**: `backend/apps/plant_identification/constants.py`

**Actual secrets (already using env vars correctly)**:
- `PLANT_ID_API_KEY` ✅ Uses env var
- `PLANTNET_API_KEY` ✅ Uses env var
- `JWT_SECRET_KEY` ✅ Uses env var

**Pattern comparison**:
```python
# Good - secrets use env vars
PLANT_ID_API_KEY = os.getenv('PLANT_ID_API_KEY')

# Acceptable - non-secret config hardcoded
PLANT_ID_API_TIMEOUT = 30

# Bad - would be a problem if this was a secret
PLANT_ID_API_KEY = 'hardcoded-key-here'  # Not present in codebase ✅
```

## Resources

- 12-Factor App Config: https://12factor.net/config
- Django settings best practices: https://docs.djangoproject.com/en/5.2/topics/settings/
- django-environ: https://django-environ.readthedocs.io/

## Acceptance Criteria

- [ ] Decision documented (keep hardcoded vs env vars)
- [ ] If using env vars: `.env.example` updated
- [ ] If using env vars: Type coercion (int()) implemented
- [ ] If using env vars: Tests verify default values work

## Work Log

- 2025-10-25: Issue identified by security-sentinel agent

## Notes

**Priority rationale**: P4 (Low) - Not a security issue, just a pattern observation
**False positive**: Auditor may have conflated timeout constants with API keys
**Recommendation**: Close as "Won't Fix" or "Working as Intended"
**Actual issue**: Ensure API keys never hardcoded (already verified ✅)
