---
status: ready
priority: p1
issue_id: "003"
tags: [code-review, configuration, cors, quick-fix]
dependencies: []
---

# Fix Vite Port Configuration Mismatch

## Problem Statement

Vite dev server configured for port 5173, but documentation (CLAUDE.md) references port 5174 in 37 places, and backend CORS is configured for port 5174. This creates immediate CORS failures when developers follow the documentation.

## Findings

- **Discovered by**: kieran-typescript-reviewer, architecture-strategist agents
- **Location**: `web/vite.config.js:9`
- **Current configuration**: `port: 5173` (Vite default)
- **Documentation**: CLAUDE.md references port 5174 (37 mentions)
- **Backend CORS**: `settings.py:539-541, 580-581` configured for 5174
- **Impact**: CORS errors on blog interface, React dev server

## Current State

**vite.config.js**:
```javascript
server: {
  port: 5173,  // ❌ Wrong - doesn't match docs/backend
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

**Backend CORS (settings.py)**:
```python
# Lines 539-541, 580-581
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5174',      # React blog dev server
    'http://127.0.0.1:5174',
    # ... other origins
]
```

**CLAUDE.md references**:
- "Port 5174" mentioned 37 times
- "http://localhost:5174/blog" - blog interface URL
- "Vite dev server (port 5174)" in Port Reference section

## Proposed Solutions

### Option 1: Change Vite to Port 5174 (Recommended)
- **Implementation**: Update `vite.config.js:9` to use port 5174
- **Pros**:
  - Matches documentation (37 references)
  - Matches backend CORS configuration
  - No documentation changes needed
  - Minimal disruption
- **Cons**: None (5174 was intentional, 5173 was oversight)
- **Effort**: Trivial (5 minutes)
- **Risk**: None

### Option 2: Update Documentation and Backend to 5173
- **Implementation**: Change CLAUDE.md (37 places) and settings.py
- **Pros**: Matches Vite default
- **Cons**:
  - Large documentation update
  - Backend configuration changes
  - More error-prone (multiple files)
  - Breaks existing workflows
- **Effort**: Medium (1-2 hours)
- **Risk**: Medium
- **Verdict**: Not recommended

## Recommended Action

**Implement Option 1** - Change Vite port to 5174 (single-line fix).

### Implementation Steps:

1. **Update vite.config.js**:
   ```javascript
   // Line 9
   server: {
     port: 5174,  // ✅ Match documentation and backend CORS
     proxy: {
       '/api': {
         target: 'http://localhost:8000',
         changeOrigin: true,
       },
     },
   }
   ```

2. **Verify change**:
   ```bash
   cd web
   npm run dev
   # Should show: "Local: http://localhost:5174/"
   ```

3. **Test CORS**:
   ```bash
   # In browser at http://localhost:5174/blog
   # Should load without CORS errors
   ```

4. **Update .env.example (if needed)**:
   ```bash
   # Verify web/.env.example mentions correct port
   # Currently may reference 5173
   ```

## Technical Details

**Affected Files**:
- `web/vite.config.js` (primary - line 9)
- `web/.env.example` (verify port documentation)
- `web/package.json` (scripts reference `dev` command, should work automatically)

**Backend Configuration** (no changes needed):
- `backend/plant_community_backend/settings.py:539-541` - Already correct
- `backend/plant_community_backend/settings.py:580-581` - Already correct
- `backend/.env.example` - May need update if it references 5173

**Related Components**:
- Blog interface (primary user - needs port 5174)
- React dev server
- CORS middleware

**Testing URLs**:
- http://localhost:5174/blog (blog list)
- http://localhost:5174/blog/test-post (blog detail)
- http://localhost:5174/ (home page)

**Database Changes**: None

**Configuration Changes**:
- Vite port: 5173 → 5174 (single line)

## Resources

- **Vite docs**: https://vitejs.dev/config/server-options.html#server-port
- **CLAUDE.md**: Lines mentioning port 5174 (37 occurrences)
- **Backend settings.py**: Lines 539-541, 580-581 (CORS configuration)
- **Agent reports**: kieran-typescript-reviewer, architecture-strategist

## Acceptance Criteria

- [ ] `vite.config.js` port changed to 5174
- [ ] Dev server starts on http://localhost:5174
- [ ] Blog interface loads without CORS errors
- [ ] API calls to backend succeed
- [ ] No console errors in browser
- [ ] `.env.example` documentation updated (if applicable)
- [ ] All npm scripts work correctly

## Work Log

### 2025-10-25 - Code Review Discovery
**By**: Claude Code Review System (kieran-typescript-reviewer agent)
**Actions**:
- Discovered during frontend configuration analysis
- Verified Vite config shows port 5173
- Cross-referenced with CLAUDE.md (37 mentions of 5174)
- Verified backend CORS configured for 5174
- Identified as CRITICAL due to immediate CORS failures

**Learnings**:
- Port 5174 was intentional design decision (documented extensively)
- Vite default 5173 was likely oversight during initial setup
- Backend CORS correctly configured for 5174 from the start
- This explains any CORS issues developers may have encountered

**Why Port 5174?**
- Avoids conflict with default Vite port 5173
- Dedicated port for React blog interface
- Clearly separated from other potential dev servers

## Notes

**Source**: Code review performed on 2025-10-25
**Review command**: `audit codebase and report back to me`
**Priority justification**: CRITICAL because it creates immediate CORS failures when following documentation
**Quick win**: 5-minute fix, zero risk, unblocks development
**Root cause**: Initial Vite setup used default port, documentation established 5174 as standard
