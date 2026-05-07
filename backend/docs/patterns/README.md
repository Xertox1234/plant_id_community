# Backend Pattern Library

**Last Updated**: 2026-05-06
**Total Patterns**: 18 consolidated pattern files (+ 9 cross-platform patterns in web/mobile/firebase)
**Lines Consolidated**: ~16,000+ lines from 27+ source files
**Status**: ✅ Production-Ready

---

## Quick Reference

Use this pattern library when working on specific features or debugging issues. Each pattern file contains:
- ✅ Correct implementation patterns
- ❌ Common anti-patterns to avoid
- 📋 Code examples with explanations
- 🧪 Testing strategies
- ✅ Deployment checklists

**For AI agents**: When working on authentication issues, read `security/authentication.md`. When optimizing queries, read `performance/query-optimization.md`. Etc.

---

## Pattern Categories

### 🔒 Security Patterns (`security/`)

**When to use**: Authentication, authorization, input validation, file uploads, API key management.

| File | Patterns | Use Case |
|------|----------|----------|
| [`authentication.md`](security/authentication.md) | JWT, session management, account lockout | Implementing login, logout, token refresh |
| [`csrf-protection.md`](security/csrf-protection.md) | Django CSRF, Fetch API, React integration | Frontend-backend CSRF handling |
| [`file-upload.md`](security/file-upload.md) | 4-layer validation (extension, MIME, size, PIL) | Secure image/file uploads |
| [`input-validation.md`](security/input-validation.md) | SQL wildcards, XSS, sanitization | Search queries, user input handling |
| [`secret-management.md`](security/secret-management.md) | SECRET_KEY, API keys, .env, .gitignore | Environment configuration, key rotation |

---

### ⚡ Performance Patterns (`performance/`)

**When to use**: Slow queries, N+1 problems, database optimization, testing assertions.

| File | Patterns | Use Case |
|------|----------|----------|
| [`query-optimization.md`](performance/query-optimization.md) | N+1 elimination, aggregation, indexing, testing | Optimizing Django ORM queries |

**Key Patterns**:
- `select_related()` for foreign keys (1-to-1, many-to-1)
- `prefetch_related()` for reverse foreign keys (1-to-many, many-to-many)
- `Count()` + `Q()` for conditional aggregation
- `assertEqual(count, N)` for strict test assertions (not `assertLess`)

---

### 🏗️ Architecture Patterns (`architecture/`)

**When to use**: ViewSets, caching, rate limiting, service design, parallel processing.

| File | Patterns | Use Case |
|------|----------|----------|
| [`caching.md`](architecture/caching.md) | Cache services, key strategies, invalidation | Redis caching, cache warming |
| [`rate-limiting.md`](architecture/rate-limiting.md) | HTTP 429, Retry-After, OpenAPI docs | django-ratelimit, API throttling |
| [`viewsets.md`](architecture/viewsets.md) | DRF permissions, @action decorators | Custom ViewSet actions, security |
| [`services.md`](architecture/services.md) | ThreadPoolExecutor, circuit breakers, locks | Parallel API calls, service layer |

**Critical Patterns**:
- **ViewSet permissions**: Custom `@action` needs `super().get_permissions()` (Issue #131)
- **Rate limiting**: Check `Ratelimited` exception BEFORE DRF handler (Issue #133)
- **Caching**: Dual-strategy for Redis/non-Redis backends
- **Services**: Static methods class for cache services

---

### 🌱 Domain-Specific Patterns (`domain/`)

**When to use**: Plant identification, diagnosis API, forum features, blog/CMS, Wagtail, Celery.

| File | Patterns | Use Case |
|------|----------|----------|
| [`plant-identification.md`](domain/plant-identification.md) | API integration, error handling, environment config | Plant.id, PlantNet APIs |
| [`diagnosis.md`](domain/diagnosis.md) | UUID lookups, DRF serializers, SlugRelatedField | UUID-based ViewSets |
| [`forum.md`](domain/forum.md) | Trust levels, spam detection, moderation | Forum permissions, anti-spam |
| [`blog.md`](domain/blog.md) | Wagtail AI 3.0, caching, prompts | AI-powered content generation |
| [`wagtail.md`](domain/wagtail.md) | instanceof checks, cache invalidation, StreamField, version split | Wagtail CMS (dev 7.1.2 / prod 7.4) |
| [`celery.md`](domain/celery.md) | Idempotency, retry config, beat schedules, error handling | Celery async tasks |

**Highlights**:
- **Plant ID**: Dual API integration, diagnostic scripts, rate limiting
- **Diagnosis**: UUID `lookup_field`, `SlugRelatedField` for UUIDs, `@action(uuid=None)`
- **Forum**: 5-tier trust system, multi-heuristic spam detection, cache warming
- **Blog**: Native Wagtail AI panels, 80-95% cost reduction, <100ms cached responses
- **Wagtail**: `isinstance()` for page type checks, dual-strategy cache invalidation, dev/prod version awareness
- **Celery**: Idempotency guards, `max_retries` required, error handling with `[CELERY]` log prefix

---

## Pattern Usage Guide

### For Developers

**Working on authentication?**
```bash
# Read these patterns
backend/docs/patterns/security/authentication.md
backend/docs/patterns/security/csrf-protection.md
```

**Optimizing slow queries?**
```bash
# Read this pattern
backend/docs/patterns/performance/query-optimization.md
```

**Building a ViewSet with custom actions?**
```bash
# Read these patterns
backend/docs/patterns/architecture/viewsets.md  # Permission patterns
backend/docs/patterns/architecture/rate-limiting.md  # Rate limiting
backend/docs/patterns/domain/diagnosis.md  # UUID lookups (if using UUIDs)
```

**Implementing spam detection?**
```bash
# Read this pattern
backend/docs/patterns/domain/forum.md
```

### For AI Agents

**Agent Instructions**: When working on specific features, use the pattern library:

- **Authentication issues**: Read `security/authentication.md` and `security/csrf-protection.md`
- **Performance issues**: Read `performance/query-optimization.md` and `architecture/caching.md`
- **ViewSet development**: Read `architecture/viewsets.md` and `architecture/rate-limiting.md`
- **Forum features**: Read `domain/forum.md` for trust levels and spam detection
- **Blog/CMS**: Read `domain/blog.md` for Wagtail AI patterns

**Example**:
```
User: "I need to add a custom action to DiagnosisCardViewSet"
Agent: [Reads architecture/viewsets.md for @action patterns, reads domain/diagnosis.md for UUID lookup patterns]
Agent: "Here's the correct implementation with uuid=None parameter and super().get_permissions()..."
```

---

## Pattern Statistics

### Consolidation Metrics

**Source Files Consolidated**: 27+ scattered pattern files
**Output Files Created**: 16 organized pattern files
**Total Lines**: ~16,000+ lines of comprehensive documentation
**Code Reduction**: 60-99% (examples: Wagtail AI 1,103 → 451 lines)

### Pattern Coverage

| Category | Files | Key Patterns |
|----------|-------|--------------|
| Security | 5 | JWT, CSRF, file validation, secret management |
| Performance | 1 | N+1, aggregation, indexing, test assertions |
| Architecture | 4 | Caching, rate limiting, ViewSets, services |
| Domain-Specific (backend) | 6 | Plant ID, diagnosis, forum, blog, Wagtail, Celery |
| Web (web/docs/patterns/) | 3 | React/TypeScript, Tailwind, testing |
| Mobile (plant_community_mobile/docs/patterns/) | 3 | Flutter, Firebase Auth, Riverpod |
| Firebase (firebase/docs/patterns/) | 3 | Cloud Functions, Firestore rules, IAM |
| **Total** | **25** | **70+ production-tested patterns** |

---

## Pattern File Structure

Each pattern file follows this structure:

1. **Overview**: Context, status, performance metrics
2. **Pattern Sections**: Problem, solution, code examples
3. **Anti-Patterns**: Common mistakes to avoid
4. **Testing**: Test strategies and examples
5. **Pitfalls**: Edge cases and gotchas
6. **Summary**: Key takeaways, related patterns
7. **Checklist**: Pre-deployment verification

---

## Related Documentation

**Source Files** (archived):
- Original pattern files in repo root (many will be archived to `docs/archive/2025-11/`)
- Issue completion documents
- Implementation summaries

**Other Docs**:
- `/backend/docs/README.md` - Backend documentation hub
- `/backend/docs/development/` - Development guides
- `CLAUDE.md` - Development instructions for AI agents

---

## Contributing Patterns

When creating new patterns:

1. ✅ Use clear problem/solution structure
2. ✅ Include code examples (correct + anti-pattern)
3. ✅ Add testing strategies
4. ✅ Document performance metrics
5. ✅ Include deployment checklist
6. ✅ Cross-reference related patterns
7. ✅ Update this README with new pattern

**Template**: See any existing pattern file for structure.

---

## Pattern Maintenance

**Update Frequency**: Update patterns when:
- Code changes affect pattern validity
- New issues discovered
- Performance metrics change
- Framework versions update

**Review Process**:
1. Test pattern validity in current codebase
2. Update code examples
3. Refresh performance metrics
4. Update "Last Reviewed" date
5. Commit with clear message

---

**Last Reviewed**: 2026-05-06
**Pattern Count**: 25 files (18 backend + 3 web + 3 mobile + 3 firebase — all seeded; pattern-codifier appends after each review session)
**Status**: ✅ Production-validated
**Consolidation**: Complete
