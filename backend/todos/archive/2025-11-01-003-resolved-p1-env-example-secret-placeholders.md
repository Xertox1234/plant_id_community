---
status: pending
priority: p1
issue_id: "003"
tags: [code-review, security, secret-management, audit]
dependencies: []
---

# Improve .env.example Secret Key Placeholders

## Problem Statement
The `.env.example` file contains weak placeholder patterns for sensitive credentials that could lead to accidental commits of real keys or developers using insecure defaults in development.

## Findings
- Discovered during comprehensive codebase audit (October 31, 2025)
- Location: `backend/.env.example` (lines 4, 29, 33, 56, 72)
- **Current placeholders**:
  - `SECRET_KEY=your-secret-key-here`
  - `PLANT_ID_API_KEY=your-plant-id-api-key-here`
  - `PLANTNET_API_KEY=your-plantnet-api-key-here`
  - `JWT_SECRET_KEY=your-jwt-secret-key-change-in-production`
  - `FIELD_ENCRYPTION_KEY=your-fernet-key-change-in-production-base64-encoded=`

**Security risks**:
1. Weak patterns might pass validation in development
2. Developers could forget to replace placeholders
3. Pattern-based secret scanners might flag these as false positives
4. No clear indication that these MUST be replaced

## Proposed Solutions

### Option 1: REQUIRED_ Prefix Pattern (Recommended)
**Pros**:
- Clear indication value must be replaced
- Will fail validation if accidentally used
- Includes generation instructions
- Industry standard pattern

**Cons**:
- Slightly longer variable values
- Developers must read comments for instructions

**Effort**: Small (15 minutes)
**Risk**: Low

**Implementation**:
```bash
# Django Core Settings
DEBUG=True
# Generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY=REQUIRED__GENERATE_WITH__python_-c_from_django_get_random_secret_key

# External API Keys
# Get from: https://web.plant.id/
PLANT_ID_API_KEY=REQUIRED__GET_FROM__https://web.plant.id/

# Get from: https://my.plantnet.org/
PLANTNET_API_KEY=REQUIRED__GET_FROM__https://my.plantnet.org/

# JWT Authentication Settings
# Generate with: python -c 'import secrets; print(secrets.token_urlsafe(64))'
JWT_SECRET_KEY=REQUIRED__GENERATE_WITH__python_-c_import_secrets_token_urlsafe_64

# PII Encryption Settings (GDPR Article 32 Compliance)
# Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
FIELD_ENCRYPTION_KEY=REQUIRED__GENERATE_WITH__python_-c_from_cryptography_fernet_Fernet_generate_key
```

### Option 2: Empty Values with Validation
**Pros**:
- Forces explicit configuration
- Clean .env.example file

**Cons**:
- Requires updating Django settings validation
- Less informative for new developers

**Effort**: Medium (1 hour)
**Risk**: Medium (might break existing dev setups)

## Recommended Action
**Option 1** - Replace all sensitive placeholders with `REQUIRED__*` pattern.

This approach:
1. Prevents accidental use of placeholders
2. Provides clear generation/acquisition instructions
3. Fails loudly if forgotten (Django SECRET_KEY validation already in place)
4. Aligns with security best practices

## Technical Details
- **Affected Files**:
  - `backend/.env.example` (primary)
  - `backend/.env.template` (if exists)

- **Related Components**:
  - Django SECRET_KEY validation (settings.py:34-95)
  - JWT authentication configuration
  - PII encryption setup

- **Database Changes**: None

## Resources
- Code review audit: October 31, 2025
- Related security patterns: `backend/docs/development/SECURITY_PATTERNS_CODIFIED.md`
- Key rotation guide: `KEY_ROTATION_INSTRUCTIONS.md`

## Acceptance Criteria
- [ ] Replace all sensitive placeholders in `.env.example` with `REQUIRED__*` pattern
- [ ] Update comments with clear generation/acquisition instructions
- [ ] Verify placeholder patterns would fail Django SECRET_KEY validation
- [ ] Test that developers can follow instructions to generate keys
- [ ] Document pattern in `backend/docs/security/` directory
- [ ] Update `.env.template` if it exists

## Work Log

### 2025-10-31 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive codebase audit
- Analyzed `.env.example` secret management patterns
- Identified weak placeholder patterns across 5 critical keys
- Categorized as P1 security issue

**Learnings:**
- Current validation in settings.py (lines 70-95) would catch most insecure patterns
- But placeholders like "your-secret-key-here" could slip through
- Need explicit "REQUIRED" marker to prevent confusion

## Notes
Source: Code review performed on October 31, 2025
Review command: `/compounding-engineering:review audit code base`
Severity: P1 (prevents security misconfigurations)
Category: Security - Secret Management
