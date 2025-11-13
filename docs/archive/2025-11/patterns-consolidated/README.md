# Archived Pattern Files - November 2025

**Archive Date**: November 13, 2025
**Reason**: Consolidated into organized pattern library
**Files Archived**: 23 pattern documentation files

---

## What Happened

These pattern files were consolidated into a new, organized pattern library located at:
```
backend/docs/patterns/
├── README.md                # Pattern library index
├── security/                # 5 security patterns
├── performance/             # 1 performance pattern
├── architecture/            # 4 architecture patterns
└── domain/                  # 4 domain-specific patterns
```

**Consolidation Summary**: `backend/docs/PATTERN_CONSOLIDATION_COMPLETE.md`

---

## Archived Files Mapping

### Security Patterns → `backend/docs/patterns/security/`

| Archived File | Consolidated Into |
|---------------|-------------------|
| `AUTHENTICATION_PATTERNS.md` | `security/authentication.md` |
| `REACT_DJANGO_AUTH_PATTERNS.md` | `security/authentication.md` |
| `SECURITY_PATTERNS_CODIFIED.md` | `security/*.md` (multiple files) |
| `PLANT_SAVE_PATTERNS_CODIFIED.md` | `security/csrf-protection.md` |

### Performance Patterns → `backend/docs/patterns/performance/`

| Archived File | Consolidated Into |
|---------------|-------------------|
| `N1_OPTIMIZATION_PATTERNS_CODIFIED.md` | `performance/query-optimization.md` |
| `PERFORMANCE_TESTING_PATTERNS_CODIFIED.md` | `performance/query-optimization.md` |
| `REVIEWER_UPDATE_N1_PATTERNS.md` | `performance/query-optimization.md` |

### Architecture Patterns → `backend/docs/patterns/architecture/`

| Archived File | Consolidated Into |
|---------------|-------------------|
| `SERVICE_ARCHITECTURE.md` | `architecture/services.md` |
| `RATE_LIMITING_PATTERNS_CODIFIED.md` | `architecture/rate-limiting.md` |

### Domain-Specific Patterns → `backend/docs/patterns/domain/`

| Archived File | Consolidated Into |
|---------------|-------------------|
| `PLANT_ID_PATTERNS_CODIFIED.md` | `domain/plant-identification.md` |
| `DIAGNOSIS_API_PATTERNS_CODIFIED.md` | `domain/diagnosis.md` |
| `SPAM_DETECTION_PATTERNS_CODIFIED.md` | `domain/forum.md` |
| `TRUST_LEVEL_PATTERNS_CODIFIED.md` | `domain/forum.md` |
| `WAGTAIL_AI_PATTERNS_CODIFIED.md` | `domain/blog.md` |
| `WAGTAIL_AI_V3_MIGRATION_PATTERNS.md` | `domain/blog.md` |
| `WAGTAIL_ADMIN_WIDGET_PATTERNS_CODIFIED.md` | `domain/blog.md` |

### Summary & Meta Documents

| Archived File | Description |
|---------------|-------------|
| `PATTERNS_CODIFICATION_SUMMARY.md` | Historical summary of pattern codification |
| `AI_AGENT_WORK_PLAN_PATTERNS.md` | Agent work plan patterns |
| `PHASE_2_PATTERNS_CODIFIED.md` | Phase 2 implementation patterns |
| `P2_PATTERNS_INTEGRATION_COMPLETE.md` | Phase 2 completion document |
| `PHASE_6_PATTERNS_CODIFIED.md` | Phase 6 implementation patterns |
| `UI_MODERNIZATION_PATTERNS_CODIFIED.md` | UI modernization patterns |
| `DJANGO_TESTING_PATTERNS_CODIFIED.md` | Django testing patterns |

---

## Why Archive?

**Problem**: Patterns were scattered across 27+ files in repo root, making them:
- ❌ Hard to discover
- ❌ Difficult to navigate
- ❌ Inconsistently formatted
- ❌ Not optimized for AI agent consumption

**Solution**: Consolidated into organized pattern library with:
- ✅ Clear category structure (security, performance, architecture, domain)
- ✅ Easy discovery (README with quick reference)
- ✅ Consistent format (problem → solution → testing)
- ✅ Comprehensive coverage (50+ patterns)
- ✅ AI-agent optimized

**Result**:
- 27+ scattered files → 16 organized files + README
- ~16,000+ lines consolidated
- 60-99% code reduction (no duplication)
- Single source of truth

---

## Using Archived Files

**DON'T USE THESE FILES** - They are archived for historical reference only.

**Instead, use the new pattern library:**
```bash
# New pattern library location
cat backend/docs/patterns/README.md

# Example: Read authentication patterns
cat backend/docs/patterns/security/authentication.md

# Example: Read query optimization patterns
cat backend/docs/patterns/performance/query-optimization.md
```

---

## Archive Retention

These files are kept for:
- Historical reference
- Pattern evolution tracking
- Issue context (many are tied to specific GitHub issues)
- Future pattern discovery

**Retention Policy**: Indefinite (part of project history)

---

## Related Documentation

- **New Pattern Library**: `backend/docs/patterns/README.md`
- **Consolidation Summary**: `backend/docs/PATTERN_CONSOLIDATION_COMPLETE.md`
- **Backend Docs Hub**: `backend/docs/README.md`

---

**Archived**: November 13, 2025
**Files**: 23 pattern documentation files
**Status**: Historical reference only - use new pattern library instead
