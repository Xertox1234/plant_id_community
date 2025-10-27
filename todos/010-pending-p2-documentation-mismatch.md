---
status: ready
priority: p2
issue_id: "010"
tags: [documentation, verification]
dependencies: []
---

# Fix Documentation vs Reality Mismatch

## Problem

CLAUDE.md claims 15 UI modernization files exist but they're not in /web/src/. Either on unmerged branch feature/ui-modernization or documentation is wrong.

## Missing Files

- layouts/RootLayout.jsx, ProtectedLayout.jsx
- components/layout/Header.jsx, Footer.jsx, UserMenu.jsx
- components/ui/Button.jsx, Input.jsx
- pages/auth/LoginPage.jsx, SignupPage.jsx
- contexts/AuthContext.jsx
- services/authService.js
- utils/logger.js
- config/sentry.js

**Action**: Verify branch status or update docs  
**Effort**: 30 minutes
