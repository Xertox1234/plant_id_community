---
status: pending
priority: p2
issue_id: "006"
tags: [code-review, configuration, cors, developer-experience, audit]
dependencies: []
---

# Fix CORS Configuration for Port 5174 in .env.example

## Problem Statement
The `.env.example` file contains incorrect CORS configuration that doesn't match the actual React dev server port. According to `CLAUDE.md`, the React dev server runs on port **5174**, but `.env.example` only includes ports 3000 and 5173, causing CORS errors for new developers.

## Findings
- Discovered during comprehensive codebase audit (October 31, 2025)
- Location: `backend/.env.example:82-83`
- **Current configuration**:
  ```bash
  CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
  CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
  ```

- **Actual dev server**: `http://localhost:5174` (per CLAUDE.md)
- **Impact**: New developers following `.env.example` get immediate CORS errors

**Evidence from CLAUDE.md**:
```markdown
## Port Reference
- **8000** - Django backend + Wagtail CMS
- **5174** - React web frontend (Vite dev server)  <-- ACTUAL PORT
- **6379** - Redis cache server
```

## Proposed Solutions

### Option 1: Update to Port 5174 Only (Recommended)
**Pros**:
- Matches actual configuration
- Simpler configuration
- Prevents confusion

**Cons**:
- Removes support for port 5173 (legacy?)
- Removes support for port 3000 (unused?)

**Effort**: Small (2 minutes)
**Risk**: None (only affects new setups)

**Implementation**:
```bash
# CORS & Security Settings
CORS_ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
CSRF_TRUSTED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
```

### Option 2: Include All Possible Ports
**Pros**:
- Maximum compatibility
- Supports legacy configurations
- Developers can use any port

**Cons**:
- Broader attack surface in development
- Confusing (which port is "correct"?)

**Effort**: Small (2 minutes)
**Risk**: Low

**Implementation**:
```bash
# CORS & Security Settings (multiple dev server ports)
CORS_ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174,http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000
CSRF_TRUSTED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174,http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000
```

### Option 3: Add Comment Explaining Correct Port
**Combination of Option 1 + documentation**

**Implementation**:
```bash
# CORS & Security Settings
# Note: React dev server runs on port 5174 (see CLAUDE.md)
# Add additional ports if using different configuration
CORS_ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
CSRF_TRUSTED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
```

## Recommended Action
**Option 3** - Update to port 5174 with clear documentation.

This approach:
1. Matches actual configuration (prevents immediate errors)
2. Documents the correct port in comments
3. Allows developers to add additional ports if needed
4. Maintains security by not opening unnecessary ports

## Technical Details
- **Affected Files**:
  - `backend/.env.example` (lines 82-83)
  - `backend/.env.template` (if it exists)

- **Related Configuration**:
  - Backend settings.py already has CORS configured (lines 539-541, 580-581)
  - Vite config: `web/vite.config.js`
  - Package.json dev script: `web/package.json:7`

- **Verification**:
  Check `web/vite.config.js` for actual port configuration

## Resources
- CLAUDE.md port reference (lines 102-106)
- Backend CORS settings: `plant_community_backend/settings.py:539-541, 580-581`
- Code review audit: October 31, 2025

## Acceptance Criteria
- [ ] Update CORS_ALLOWED_ORIGINS in `.env.example` to include port 5174
- [ ] Update CSRF_TRUSTED_ORIGINS in `.env.example` to include port 5174
- [ ] Add comment documenting the correct dev server port
- [ ] Verify `web/vite.config.js` confirms port 5174
- [ ] Update `.env.template` if it exists
- [ ] Test new developer setup follows updated configuration
- [ ] Optional: Remove legacy ports 3000, 5173 if confirmed unused

## Work Log

### 2025-10-31 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered port mismatch during codebase audit
- Verified actual port from CLAUDE.md documentation
- Checked backend settings.py CORS configuration
- Categorized as P2 configuration issue (affects new developers)

**Learnings:**
- CLAUDE.md says port 5174 is the React dev server
- .env.example has ports 3000 and 5173 (both incorrect)
- Backend settings.py already correctly configured for 5174
- Only .env.example needs updating

## Notes
Source: Code review performed on October 31, 2025
Review command: `/compounding-engineering:review audit code base`
Severity: P2 (impacts new developer onboarding)
Category: Configuration - CORS
Quick fix: 2 minutes to update 2 lines
