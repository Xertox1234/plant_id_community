# Git Branch Strategy - Plant Community Platform

**Repository**: Plantidentificationapp  
**Owner**: Xertox1234  
**Current Branch**: main  
**Strategy Type**: GitHub Flow (simplified) with environment branches  
**Date**: October 21, 2025

## Overview

This document defines the Git branching strategy for the Plant Community platform, which consists of:
- **Django/Wagtail Backend** (`existing_implementation/backend/`)
- **React PWA Frontend** (`existing_implementation/frontend/`)
- **Flutter Mobile App** (`plant_community_mobile/`)
- **Shared Documentation** (`PLANNING/`, `docs/`)

The strategy is designed to support parallel development across multiple platforms while maintaining stability and enabling coordinated releases.

## Branch Structure

### Core Branches

#### `main`
- **Purpose**: Production-ready code
- **Protection**: Protected, requires PR + review
- **Deployment**: Automatically deploys to production (when CI/CD configured)
- **Merge From**: `staging` only
- **Merge Strategy**: Merge commits (to preserve release history)
- **Never commit directly**: Always merge via PR

#### `staging`
- **Purpose**: Pre-production testing and integration
- **Protection**: Protected, requires PR
- **Deployment**: Automatically deploys to staging environment
- **Merge From**: `develop` and hotfix branches
- **Testing**: Full QA testing happens here
- **Merge Strategy**: Merge commits

#### `develop`
- **Purpose**: Integration branch for ongoing development
- **Protection**: Protected, requires PR
- **Deployment**: Optionally deploys to development environment
- **Merge From**: Feature branches, bugfix branches
- **Merge Strategy**: Squash and merge (clean history)
- **Daily Integration**: Features merge here frequently

### Working Branches

#### Feature Branches: `feature/{platform}/{ticket-number}-{short-description}`

**Format Examples**:
- `feature/mobile/PL-123-plant-identification-camera`
- `feature/web/PL-124-forum-post-creation`
- `feature/backend/PL-125-firebase-auth-integration`
- `feature/shared/PL-126-design-system-updates`

**Rules**:
- Branch from: `develop`
- Merge to: `develop`
- Lifetime: Delete after merge
- Naming: kebab-case, include ticket/issue number
- Platform prefix: `mobile`, `web`, `backend`, `shared`

**Workflow**:
```bash
# Create feature branch
git checkout develop
git pull origin develop
git checkout -b feature/mobile/PL-123-plant-identification-camera

# Work on feature
git add .
git commit -m "feat(mobile): implement camera capture for plant ID"

# Push and create PR
git push origin feature/mobile/PL-123-plant-identification-camera
```

#### Bugfix Branches: `bugfix/{platform}/{ticket-number}-{short-description}`

**Format Examples**:
- `bugfix/mobile/PL-234-fix-image-upload-crash`
- `bugfix/web/PL-235-fix-forum-pagination`
- `bugfix/backend/PL-236-fix-api-rate-limiting`

**Rules**:
- Branch from: `develop`
- Merge to: `develop`
- Similar to feature branches but for bug fixes
- Use when fixing bugs found in development/staging

#### Hotfix Branches: `hotfix/{version}-{short-description}`

**Format Examples**:
- `hotfix/v1.2.1-critical-auth-bug`
- `hotfix/v1.2.2-firebase-connection-timeout`

**Rules**:
- Branch from: `main`
- Merge to: `main` AND `develop` (via staging)
- For critical production bugs only
- Requires immediate review and testing
- Version bump required

**Workflow**:
```bash
# Create hotfix branch
git checkout main
git pull origin main
git checkout -b hotfix/v1.2.1-critical-auth-bug

# Fix and test
git add .
git commit -m "fix(auth): resolve token validation crash"

# Merge to staging for testing
git checkout staging
git merge hotfix/v1.2.1-critical-auth-bug

# After staging tests pass, merge to main
git checkout main
git merge hotfix/v1.2.1-critical-auth-bug
git tag v1.2.1

# Merge back to develop
git checkout develop
git merge hotfix/v1.2.1-critical-auth-bug
```

#### Release Branches: `release/{version}`

**Format Examples**:
- `release/v1.3.0`
- `release/v2.0.0`

**Rules**:
- Branch from: `develop`
- Merge to: `staging` → `main`
- For preparing production releases
- Only bug fixes and version bumps allowed
- No new features

**Workflow**:
```bash
# Create release branch
git checkout develop
git pull origin develop
git checkout -b release/v1.3.0

# Update version numbers, CHANGELOG.md
git add .
git commit -m "chore: prepare release v1.3.0"

# Merge to staging for QA
git checkout staging
git merge release/v1.3.0

# After QA approval, merge to main
git checkout main
git merge release/v1.3.0
git tag v1.3.0

# Merge back to develop
git checkout develop
git merge release/v1.3.0
```

## Platform-Specific Considerations

### Mobile (`plant_community_mobile/`)
- **Build Numbers**: Auto-increment on each release
- **Version Format**: `major.minor.patch+buildNumber` (e.g., `1.3.0+42`)
- **Platform Branches**: Avoid iOS/Android-specific branches; use feature flags
- **Testing**: Requires device testing before merging to staging

### Web Frontend (`existing_implementation/frontend/`)
- **Version Format**: `major.minor.patch` (follows semver)
- **Bundle Size**: Monitor on each PR
- **Browser Testing**: Test across browsers before staging merge

### Backend (`existing_implementation/backend/`)
- **Migrations**: Always include Django migrations in commits
- **API Changes**: Document breaking changes in PR description
- **Database**: Test migrations on staging before main merge

## Commit Message Convention

Follow **Conventional Commits** specification:

### Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring (no feature change or bug fix)
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates
- `ci`: CI/CD configuration changes
- `build`: Build system changes

### Scopes
- `mobile`: Flutter mobile app
- `web`: React PWA frontend
- `backend`: Django backend
- `api`: REST API changes
- `auth`: Authentication/authorization
- `forum`: Forum functionality
- `plant-id`: Plant identification
- `design`: Design system changes
- `deps`: Dependency updates

### Examples
```bash
# Feature
git commit -m "feat(mobile): add plant identification camera capture"

# Bug fix
git commit -m "fix(web): resolve forum pagination infinite loop"

# Backend API
git commit -m "feat(api): add disease diagnosis endpoint"

# Multiple lines
git commit -m "refactor(backend): optimize plant search query

- Add database indexes for common queries
- Implement query result caching
- Reduce N+1 queries in serializers

Closes #PL-145"

# Breaking change
git commit -m "feat(api): redesign authentication flow

BREAKING CHANGE: Auth endpoints now require Firebase tokens
instead of session cookies. Update mobile and web clients
to use new firebase_auth package.

Closes #PL-200"
```

## Pull Request Guidelines

### PR Title Format
```
[Platform] Type: Short description
```

**Examples**:
- `[Mobile] feat: Implement plant identification camera`
- `[Web] fix: Resolve forum post pagination bug`
- `[Backend] refactor: Optimize database queries`
- `[Shared] docs: Update API documentation`

### PR Description Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Platform
- [ ] Mobile (Flutter)
- [ ] Web (React)
- [ ] Backend (Django)
- [ ] Shared/Documentation

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed
- [ ] Tested on iOS device
- [ ] Tested on Android device
- [ ] Tested on Chrome, Firefox, Safari

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
- [ ] Dependent changes merged

## Related Issues
Closes #PL-XXX

## Screenshots (if applicable)
[Add screenshots or screen recordings]

## Migration Notes (if applicable)
[Database migrations, environment variables, deployment steps]
```

### PR Review Process
1. **Author**: Create PR, assign reviewers, add labels
2. **CI/CD**: Automated tests must pass
3. **Reviewers**: At least 1 approval required
4. **Code Review**: Check code quality, tests, documentation
5. **Testing**: Manual testing on staging (if needed)
6. **Merge**: Squash and merge to `develop`, merge commit to `staging`/`main`

### PR Labels
- `platform:mobile` - Flutter mobile changes
- `platform:web` - React web changes
- `platform:backend` - Django backend changes
- `type:feature` - New feature
- `type:bugfix` - Bug fix
- `type:hotfix` - Critical production fix
- `priority:high` - High priority
- `priority:low` - Low priority
- `status:wip` - Work in progress
- `status:review` - Ready for review
- `status:blocked` - Blocked by dependencies
- `breaking-change` - Contains breaking changes

## Branch Protection Rules

### `main` Branch
- [x] Require pull request before merging
- [x] Require 1 approval
- [x] Dismiss stale reviews on new commits
- [x] Require status checks to pass (CI/CD)
- [x] Require branches to be up to date
- [x] Include administrators in restrictions
- [x] Restrict who can push (only release managers)
- [x] Require linear history (no merge commits from feature branches)

### `staging` Branch
- [x] Require pull request before merging
- [x] Require 1 approval
- [x] Require status checks to pass
- [x] Include administrators in restrictions

### `develop` Branch
- [x] Require pull request before merging
- [x] Require status checks to pass
- [ ] Require approval (optional for small teams)

## Versioning Strategy

### Semantic Versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes, major feature releases
- **MINOR**: New features, backward-compatible
- **PATCH**: Bug fixes, backward-compatible

### Version Synchronization
All platforms maintain synchronized versions:
- Backend: `1.3.0`
- Web: `1.3.0`
- Mobile: `1.3.0+42` (where 42 is build number)

### Version Files
- Backend: `backend/plant_community_backend/settings.py` → `VERSION = "1.3.0"`
- Web: `frontend/package.json` → `"version": "1.3.0"`
- Mobile: `plant_community_mobile/pubspec.yaml` → `version: 1.3.0+42`
- Shared: `PLANNING/VERSION.txt` → `1.3.0`

### Tagging Releases
```bash
# Create annotated tag
git tag -a v1.3.0 -m "Release version 1.3.0

Features:
- Plant identification with camera
- Disease diagnosis
- Garden calendar sync

Bug Fixes:
- Forum pagination fixed
- Authentication token refresh

Breaking Changes:
- None
"

# Push tag
git push origin v1.3.0
```

## Workflow Examples

### Starting a New Feature
```bash
# 1. Update develop
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b feature/mobile/PL-123-camera-capture

# 3. Make changes and commit
git add lib/features/plant_id/camera_screen.dart
git commit -m "feat(mobile): add camera capture screen for plant ID"

# 4. Push regularly
git push origin feature/mobile/PL-123-camera-capture

# 5. Keep branch updated
git checkout develop
git pull origin develop
git checkout feature/mobile/PL-123-camera-capture
git rebase develop

# 6. Create PR when ready
# Go to GitHub and create PR from feature branch to develop
```

### Coordinated Multi-Platform Feature
**Scenario**: Adding Firebase authentication requires changes to mobile, web, and backend

```bash
# Backend team
git checkout -b feature/backend/PL-200-firebase-auth
# ... implement backend changes ...
git commit -m "feat(backend): add Firebase token authentication"
# Create PR to develop

# Web team (depends on backend)
git checkout -b feature/web/PL-200-firebase-auth
# ... implement web changes ...
git commit -m "feat(web): integrate Firebase auth with login flow"
# Create PR to develop (mark as depends on backend PR)

# Mobile team (depends on backend)
git checkout -b feature/mobile/PL-200-firebase-auth
# ... implement mobile changes ...
git commit -m "feat(mobile): integrate Firebase auth with app startup"
# Create PR to develop (mark as depends on backend PR)

# Merge order: backend → web → mobile (or web/mobile in parallel)
```

### Releasing to Production
```bash
# 1. Create release branch from develop
git checkout develop
git pull origin develop
git checkout -b release/v1.3.0

# 2. Update version numbers
# - backend/plant_community_backend/settings.py
# - frontend/package.json
# - plant_community_mobile/pubspec.yaml
# - PLANNING/VERSION.txt
# - Update CHANGELOG.md

git add .
git commit -m "chore: bump version to 1.3.0"

# 3. Merge to staging for QA
git checkout staging
git pull origin staging
git merge release/v1.3.0
git push origin staging

# 4. After QA approval, merge to main
git checkout main
git pull origin main
git merge release/v1.3.0
git tag -a v1.3.0 -m "Release v1.3.0"
git push origin main --tags

# 5. Merge back to develop
git checkout develop
git merge release/v1.3.0
git push origin develop

# 6. Delete release branch
git branch -d release/v1.3.0
git push origin --delete release/v1.3.0
```

## Emergency Hotfix Process
```bash
# 1. Create hotfix from main
git checkout main
git pull origin main
git checkout -b hotfix/v1.2.1-auth-crash

# 2. Fix the bug
git add .
git commit -m "fix(auth): prevent crash on null token"

# 3. Test locally
# Run tests, verify fix

# 4. Merge to staging for quick verification
git checkout staging
git merge hotfix/v1.2.1-auth-crash
git push origin staging
# Deploy to staging, verify fix

# 5. Merge to main
git checkout main
git merge hotfix/v1.2.1-auth-crash
git tag v1.2.1
git push origin main --tags

# 6. Merge to develop
git checkout develop
git merge hotfix/v1.2.1-auth-crash
git push origin develop

# 7. Delete hotfix branch
git branch -d hotfix/v1.2.1-auth-crash
```

## CI/CD Integration

### Automated Checks on PR
- [x] Linting (ESLint, Dart analyzer, Flake8)
- [x] Unit tests
- [x] Integration tests (where applicable)
- [x] Build success (Flutter, React, Django)
- [x] Code coverage threshold (80%+)
- [x] Security scanning (Dependabot, Snyk)

### Automated Deployments
- **develop → Dev Environment**: Auto-deploy on merge
- **staging → Staging Environment**: Auto-deploy on merge
- **main → Production**: Auto-deploy on merge (with approval gate)

### Build Triggers
- **Mobile**: Trigger iOS/Android builds on staging/main merge
- **Web**: Build and deploy to CDN on staging/main merge
- **Backend**: Deploy to app servers on staging/main merge

## Git Hygiene Best Practices

### Do's ✅
- **Commit often**: Small, focused commits
- **Write descriptive messages**: Follow conventional commits
- **Keep branches short-lived**: Merge within 2-3 days
- **Rebase before merging**: Keep history clean
- **Delete merged branches**: Clean up after merge
- **Tag releases**: Use semantic versioning tags
- **Update regularly**: Pull develop daily
- **Run tests locally**: Before pushing

### Don'ts ❌
- **Don't commit to main/staging directly**: Always use PR
- **Don't commit secrets**: Use environment variables
- **Don't commit large files**: Use Git LFS for assets
- **Don't commit commented code**: Delete unused code
- **Don't commit generated files**: Add to .gitignore
- **Don't force push to shared branches**: Avoid `--force`
- **Don't mix refactoring with features**: Separate concerns
- **Don't create long-lived feature branches**: Merge frequently

## Conflict Resolution

### Merge Conflicts
1. **Update your branch**:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout feature/your-branch
   git rebase develop
   ```

2. **Resolve conflicts**:
   - Open conflicted files
   - Resolve manually or use merge tool
   - Test after resolution

3. **Continue rebase**:
   ```bash
   git add .
   git rebase --continue
   ```

4. **Force push** (only on feature branches):
   ```bash
   git push --force-with-lease origin feature/your-branch
   ```

## Documentation Requirements

### Code Changes
- Update README.md if setup changes
- Update API documentation for endpoint changes
- Add JSDoc/Dartdoc comments for public APIs
- Update CHANGELOG.md for user-facing changes

### Database Changes
- Document migrations in commit message
- Update DATABASE_SCHEMA.md for schema changes
- Add rollback instructions for complex migrations

### Configuration Changes
- Document new environment variables
- Update deployment guides
- Add migration notes in PR

## Team Responsibilities

### Platform Leads
- **Mobile Lead**: Reviews mobile PRs, manages mobile releases
- **Web Lead**: Reviews web PRs, manages web deployment
- **Backend Lead**: Reviews backend PRs, manages database migrations

### Release Manager
- Creates release branches
- Coordinates version bumps
- Manages production deployments
- Creates release tags and notes

### All Developers
- Follow branch strategy
- Write clear commit messages
- Review code from peers
- Keep documentation updated
- Run tests before pushing

## Monitoring and Metrics

### Branch Health Metrics
- **Branch lifetime**: Target < 3 days
- **PR size**: Target < 400 lines changed
- **Review time**: Target < 24 hours
- **Build success rate**: Target > 95%
- **Merge frequency**: Daily to develop

### Repository Health
- **Stale branches**: Auto-delete after 30 days
- **Open PRs**: Keep < 10 active PRs
- **Failed builds**: Fix within 1 hour
- **Security alerts**: Fix critical within 24 hours

## Tools and Configuration

### Git Configuration
```bash
# Set up user info
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Set default branch
git config init.defaultBranch main

# Enable rebase by default for pull
git config pull.rebase true

# Enable autosquash for interactive rebase
git config rebase.autosquash true

# Set up aliases
git config alias.co checkout
git config alias.br branch
git config alias.ci commit
git config alias.st status
git config alias.unstage 'reset HEAD --'
git config alias.last 'log -1 HEAD'
git config alias.visual 'log --oneline --graph --decorate --all'
```

### Recommended Tools
- **Git Client**: GitKraken, Sourcetree, or CLI
- **Code Review**: GitHub PR interface
- **CI/CD**: GitHub Actions (recommended)
- **Release Management**: GitHub Releases
- **Issue Tracking**: GitHub Issues or Jira

## Troubleshooting

### "Branch is behind main"
```bash
git checkout your-branch
git fetch origin
git rebase origin/main
git push --force-with-lease origin your-branch
```

### "Cannot merge due to conflicts"
```bash
git checkout develop
git pull origin develop
git checkout your-branch
git rebase develop
# Resolve conflicts in files
git add .
git rebase --continue
```

### "Accidentally committed to wrong branch"
```bash
# Save your changes
git stash

# Switch to correct branch
git checkout correct-branch

# Apply changes
git stash pop
git add .
git commit -m "Your message"
```

### "Need to undo last commit"
```bash
# Undo commit but keep changes
git reset --soft HEAD~1

# Undo commit and discard changes
git reset --hard HEAD~1
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-10-21 | Initial branch strategy document |

## References

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Git Best Practices](https://git-scm.com/book/en/v2)

---

**Document Owner**: Development Team  
**Review Cycle**: Quarterly  
**Last Updated**: October 21, 2025
