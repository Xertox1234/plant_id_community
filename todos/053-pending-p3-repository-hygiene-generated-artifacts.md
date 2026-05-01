---
status: pending
priority: p3
issue_id: "053"
tags: [repo-hygiene, gitignore, generated-files, security, cleanup]
dependencies: []
---

# Clean Up Tracked Generated Artifacts and Firebase Config Policy

## Problem

The repository currently tracks generated/test artifacts and native Firebase config files despite ignore rules suggesting some should be excluded. This increases noise and can cause confusion about what is required, generated, or safe to commit.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- Tracked generated/test artifacts include:
  - `.playwright-mcp/*.png`
  - `web/playwright-report/index.html`
  - `test-results/.last-run.json`
- Native Firebase config files are tracked:
  - `plant_community_mobile/android/app/google-services.json`
  - `plant_community_mobile/ios/Runner/GoogleService-Info.plist`
- `plant_community_mobile/.gitignore` lists these Firebase config paths, but they remain tracked because they were committed before or despite ignore rules.
- Firebase client API keys are not equivalent to backend secrets, but they should be restricted and handled intentionally.

## Recommended Action

1. Decide policy for Firebase native config files:
   - Commit environment-specific client config intentionally, or
   - Remove tracked files and commit `.example` templates only.
2. Ensure Firebase API keys are restricted in Google Cloud/Firebase Console.
3. Remove generated artifacts from Git tracking.
4. Add missing ignore rules for Playwright reports and MCP screenshots.
5. Document how to regenerate reports/screenshots locally if needed.

## Technical Details

Candidate cleanup commands after policy decision:

```bash
git rm --cached web/playwright-report/index.html
git rm --cached test-results/.last-run.json
git rm --cached .playwright-mcp/*.png
```

Only remove Firebase config from Git after confirming the desired deployment/setup workflow.

## Acceptance Criteria

- [ ] Generated reports/screenshots are no longer tracked.
- [ ] `.gitignore` covers Playwright reports, test results, and generated screenshots.
- [ ] Firebase config tracking policy is documented.
- [ ] If Firebase configs remain tracked, key restrictions are verified and documented.
- [ ] If Firebase configs are removed, example files and setup instructions exist.

## Work Log

### 2026-05-01 - Codebase Assessment

- Classified P3 because this is not immediately blocking, but it adds noise and security/config ambiguity.
