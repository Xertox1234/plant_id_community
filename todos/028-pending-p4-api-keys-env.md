---
status: resolved
priority: p4
issue_id: "028"
tags: [security, configuration, secrets]
dependencies: []
resolved_date: 2025-10-27
resolution: verified_correct
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

- [x] Decision documented (keep hardcoded vs env vars)
- [x] If using env vars: `.env.example` updated
- [x] If using env vars: Type coercion (int()) implemented
- [x] If using env vars: Tests verify default values work

## Work Log

- 2025-10-25: Issue identified by security-sentinel agent
- 2025-10-27: Resolution verified - all API keys properly managed

## Resolution Summary (2025-10-27)

**Status**: VERIFIED CORRECT - No action required

**Findings**:
1. All sensitive API keys are properly stored in environment variables (not hardcoded):
   - `PLANT_ID_API_KEY` - Uses `config('PLANT_ID_API_KEY', default='')` in settings.py:719
   - `PLANTNET_API_KEY` - Uses `config('PLANTNET_API_KEY', default='')` in settings.py:719
   - `JWT_SECRET_KEY` - Uses `config('JWT_SECRET_KEY', default=None)` with validation in settings.py:507-543
   - `SECRET_KEY` - Uses environment variable with production validation

2. Timeout constants are appropriately hardcoded in `constants.py`:
   - `PLANT_ID_API_TIMEOUT = 35` (line 29)
   - `PLANTNET_API_REQUEST_TIMEOUT = 60` (line 34)
   - These are NOT secrets - just configuration values
   - No evidence of environment-specific timeout tuning needs

3. `.env.example` properly documented with:
   - API key placeholders (lines 29, 33, 56)
   - Generation instructions for SECRET_KEY and JWT_SECRET_KEY
   - URLs to obtain API keys from providers
   - Proper security warnings

4. `.env` files properly gitignored:
   - Root `.gitignore` includes `.env` and `.env.local`
   - No `.env` files tracked in git (verified with `git ls-files`)
   - No hardcoded API keys found in codebase (searched for known patterns)

5. Service implementations follow best practices:
   - `plant_id_service.py`: Uses `getattr(settings, 'PLANT_ID_API_KEY', None)` with validation
   - `plantnet_service.py`: Uses `getattr(settings, 'PLANTNET_API_KEY', None)` with validation
   - Both services raise `ValueError` if API key not set

**Decision**: Keep timeout constants hardcoded (Option 2 from original analysis)
- Rationale: These are not secrets, just reasonable default values
- No evidence of environment-specific timeout tuning requirements
- Adding env vars would increase complexity without clear benefit
- Actual secrets (API keys) are already properly managed

**Security Verification**: PASSED
- No API keys hardcoded in source code
- All sensitive credentials use environment variables
- .env files properly excluded from version control
- Service-level validation prevents missing keys

## Notes

**Priority rationale**: P4 (Low) - Not a security issue, just a pattern observation
**False positive**: Auditor may have conflated timeout constants with API keys
**Recommendation**: Close as "Won't Fix" or "Working as Intended"
**Actual issue**: Ensure API keys never hardcoded (already verified ✅)

**Resolution**: This TODO was based on a false positive. The system is already following best practices for API key management. Timeout constants in `constants.py` are appropriate as hardcoded values.
