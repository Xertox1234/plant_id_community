# Wagtail AI Integration - Project Overview

## 🎯 Project Goal

Integrate Wagtail AI 3.0 to enable AI-powered content creation, reducing editorial workload by 30% and improving accessibility compliance to 100%.

---

## 📊 Issue Tracking

### Created Issues

| # | Title | Status | Priority | Effort | Timeline |
|---|-------|--------|----------|--------|----------|
| [#158](https://github.com/Xertox1234/plant_id_community/issues/158) | ⬆️ Wagtail Upgrade (7.0.3→7.1+) | 🔓 Ready | 🟠 High (P2) | S (4-5h) | 1-2 days |
| [#157](https://github.com/Xertox1234/plant_id_community/issues/157) | 🤖 Wagtail AI 3.0 Integration | 📋 Backlog | 🟡 Medium (P3) | XL (2-3w) | 3-4 weeks |

---

## 🔗 Dependency Chain

```
┌─────────────────────────────────────────┐
│  PREREQUISITE                           │
│  Issue #158: Wagtail Upgrade            │
│  ⬆️ 7.0.3 → 7.1+                        │
│                                         │
│  Timeline: 1-2 days (4-5 hours)        │
│  Priority: HIGH (P2)                    │
│  Status: READY TO START ✅              │
└──────────────┬──────────────────────────┘
               │
               │ Unblocks ↓
               │
┌──────────────▼──────────────────────────┐
│  MAIN FEATURE                           │
│  Issue #157: Wagtail AI Integration     │
│  🤖 AI-powered content creation         │
│                                         │
│  Timeline: 2-3 weeks (3 phases)        │
│  Priority: MEDIUM (P3)                  │
│  Status: BLOCKED BY #158 ⏸️             │
└─────────────────────────────────────────┘
```

---

## 📅 Implementation Timeline

### Week 1: Prerequisite (Issue #158)

**Day 1-2**: Wagtail Upgrade
- [ ] Review Wagtail 7.1 changelog (30 min)
- [ ] Upgrade in development (15 min)
- [ ] Run full test suite - 232+ tests (1 hour)
- [ ] Manual testing (blog, admin, API) (1 hour)
- [ ] Deploy to production (1 hour)
- [ ] Verify and close #158

**Deliverable**: ✅ Wagtail 7.1+ installed, all tests passing

---

### Week 2-3: Phase 1 & 2 (Issue #157)

**Phase 1 - Foundation** (2-3 hours):
- [ ] Uncomment `wagtail_ai` in settings
- [ ] Configure OpenAI provider
- [ ] Test basic AI features in admin
- [ ] Create `WAGTAIL_AI_PATTERNS_CODIFIED.md`

**Phase 2 - Blog Integration** (1-2 days):
- [ ] Add AI panels to BlogPostPage
- [ ] Configure contextual image alt text
- [ ] Implement caching layer
- [ ] Create custom botanical prompts
- [ ] Write unit tests (80% coverage)

**Deliverables**:
- ✅ AI title/description generation working
- ✅ Image alt text generation working
- ✅ 80% cache hit rate achieved

---

### Week 4: Phase 3 (Issue #157)

**Phase 3 - Advanced Features** (1 week):
- [ ] Install django-ai-core
- [ ] Configure vector indexing
- [ ] Build BlogPageIndex
- [ ] Add related pages suggestions
- [ ] Implement rate limiting (10 calls/hour)
- [ ] Set up cost monitoring
- [ ] Deploy to production

**Deliverables**:
- ✅ Related pages feature working
- ✅ Rate limiting active
- ✅ API costs <$5/month
- ✅ All documentation complete

---

## 🎯 Success Metrics

### Adoption & Usage
- **Target**: ≥70% of blog posts use AI-generated content
- **Measure**: Track usage in Wagtail admin analytics

### Time Savings
- **Target**: 30% reduction in content creation time
- **Measure**: Survey content editors before/after

### Technical Performance
- **Target**: 80% cache hit rate
- **Measure**: Redis monitoring (`redis-cli info stats`)

### Cost Management
- **Target**: <$5/month API costs
- **Measure**: OpenAI/Anthropic dashboards

### Accessibility
- **Target**: 100% images with contextual alt text
- **Measure**: Audit tool (axe-core, WAVE)

---

## 💰 Cost Analysis

### One-Time Costs
- **Development Time**: 3 weeks × 1 developer = 3 person-weeks
- **Testing Time**: 8 hours (included above)
- **Documentation**: 4 hours (included above)

### Ongoing Costs (Monthly)

| Feature | Usage | Cost/Request | Monthly Cost |
|---------|-------|-------------|--------------|
| Title Generation | 500 | $0.003 | $1.50 |
| Meta Descriptions | 500 | $0.003 | $1.50 |
| Image Alt Text | 1000 | $0.005 | $5.00 |
| Related Pages (embeddings) | 100 | $0.0001 | $0.01 |
| **Subtotal** | | | **$8.01** |
| **With 80% caching** | | | **~$1.60/month** |

**ROI**: If editors save 30% time (10 hours/month @ $50/hour), ROI = $500/month - $1.60 = **$498.40/month** saved

---

## 📁 Project Structure

### New Files Created

```
plant_id_community/
├── backend/
│   ├── apps/blog/
│   │   ├── services/
│   │   │   ├── ai_cache_service.py          # NEW - AI response caching
│   │   │   └── ai_rate_limiter.py           # NEW - API quota protection
│   │   ├── indexes.py                        # NEW - Vector indexing (Phase 3)
│   │   ├── tests/
│   │   │   ├── test_ai_cache_service.py     # NEW
│   │   │   └── test_ai_rate_limiter.py      # NEW
│   │   └── constants.py                      # MODIFIED - Add AI constants
│   ├── apps/forum/
│   │   └── services/
│   │       └── ai_quality_service.py         # NEW - Phase 3 (optional)
│   ├── docs/
│   │   ├── WAGTAIL_AI_PATTERNS_CODIFIED.md  # NEW - 12 implementation patterns
│   │   ├── WAGTAIL_AI_COST_GUIDE.md         # NEW - Cost optimization
│   │   └── WAGTAIL_AI_PROMPTS.md            # NEW - Custom prompts catalog
│   ├── requirements.txt                      # MODIFIED - Wagtail >=7.1
│   └── plant_community_backend/
│       └── settings.py                       # MODIFIED - Uncomment wagtail_ai
├── docs/
│   ├── GITHUB_PROJECT_SETUP.md              # THIS FILE - Project board guide
│   ├── WAGTAIL_AI_PROJECT_OVERVIEW.md       # THIS FILE - High-level overview
│   └── user-guides/
│       └── CMS_AI_FEATURES.md                # NEW - Editor documentation
└── CLAUDE.md                                 # MODIFIED - Add Wagtail AI section
```

---

## 🔧 Technical Architecture

### AI Provider Configuration

```
┌─────────────────────────────────────────────┐
│  Multi-Provider Strategy                    │
├─────────────────────────────────────────────┤
│                                             │
│  Primary: OpenAI GPT-4.1-mini              │
│  ├─ Title generation ($0.003/request)      │
│  ├─ Meta descriptions ($0.003/request)     │
│  └─ Rich text assistance                   │
│                                             │
│  Vision: OpenAI GPT-4-Vision               │
│  └─ Image alt text ($0.005/request)        │
│                                             │
│  Fallback: Anthropic Claude (optional)     │
│  └─ High-quality content (GDPR-compliant)  │
│                                             │
│  Local: Ollama (future)                    │
│  └─ Zero-cost AI (privacy-focused)         │
│                                             │
└─────────────────────────────────────────────┘
```

### Caching Strategy

```
┌────────────────────────────────────────────────┐
│  Redis Caching Layer                           │
├────────────────────────────────────────────────┤
│                                                │
│  Cache Key Format:                             │
│  blog:ai:{feature}:{content_hash}              │
│                                                │
│  TTL: 30 days (2,592,000 seconds)             │
│                                                │
│  Expected Hit Rate: 80%+                       │
│  ├─ First request: API call → Cache           │
│  ├─ Subsequent: Cache hit (instant)            │
│  └─ Cost savings: 80% reduction                │
│                                                │
└────────────────────────────────────────────────┘
```

---

## 🛡️ Risk Mitigation

### Risk Matrix

| Risk | Impact | Likelihood | Mitigation | Owner |
|------|--------|------------|------------|-------|
| **API cost overrun** | High | Medium | Rate limiting + caching | Backend Dev |
| **Wagtail upgrade breaks blog** | High | Low | Full test suite + rollback | Backend Dev |
| **AI quality issues** | Medium | Medium | Custom prompts + manual review | Content Editor |
| **API rate limits** | Medium | Low | Multi-provider fallback | Backend Dev |

---

## 📚 Documentation Checklist

### Developer Docs
- [ ] `WAGTAIL_AI_PATTERNS_CODIFIED.md` - 12 implementation patterns
- [ ] `WAGTAIL_AI_COST_GUIDE.md` - Cost estimation and optimization
- [ ] `WAGTAIL_AI_PROMPTS.md` - Custom prompt catalog
- [ ] Update `CLAUDE.md` - Add Wagtail AI configuration section
- [ ] Update `KEY_ROTATION_INSTRUCTIONS.md` - Add OpenAI/Anthropic keys

### User Docs
- [ ] `CMS_AI_FEATURES.md` - Content editor guide
  - How to use AI title suggestions
  - How to regenerate meta descriptions
  - How to add contextual alt text
  - Best practices for prompt customization

### Operational Docs
- [ ] `WAGTAIL_AI_MONITORING.md` - API usage monitoring
- [ ] Deployment checklist (in Issue #157)
- [ ] Rollback procedures (in Issue #158)

---

## 🎬 Quick Start Guide

### For Developers

1. **Read the issues**:
   - [Issue #158](https://github.com/Xertox1234/plant_id_community/issues/158) - Prerequisite
   - [Issue #157](https://github.com/Xertox1234/plant_id_community/issues/157) - Main feature

2. **Set up project board**:
   - Follow: `docs/GITHUB_PROJECT_SETUP.md`

3. **Start with prerequisite**:
   ```bash
   cd backend
   git checkout -b wagtail-upgrade-7.1
   # Follow Issue #158 implementation steps
   ```

4. **After upgrade complete**:
   ```bash
   git checkout -b wagtail-ai-integration
   # Follow Issue #157 Phase 1 steps
   ```

### For Content Editors

1. **Wait for completion** of Issue #157 Phase 2
2. **Read user guide**: `docs/user-guides/CMS_AI_FEATURES.md`
3. **Test AI features** in Wagtail admin (http://localhost:8000/cms/)
4. **Provide feedback** on AI-generated content quality

### For Project Managers

1. **Track progress** on GitHub Project board
2. **Monitor costs** via OpenAI/Anthropic dashboards
3. **Review metrics** weekly:
   - Adoption rate (% posts using AI)
   - Cache hit rate (target 80%)
   - API costs (target <$5/month)
4. **Adjust priorities** based on ROI

---

## 🔗 Quick Links

### Issues
- [Issue #158: Wagtail Upgrade](https://github.com/Xertox1234/plant_id_community/issues/158)
- [Issue #157: Wagtail AI Integration](https://github.com/Xertox1234/plant_id_community/issues/157)

### Documentation
- [GitHub Project Setup Guide](./GITHUB_PROJECT_SETUP.md)
- [Wagtail AI Official Docs](https://wagtail-ai.readthedocs.io/)
- [OpenAI Platform](https://platform.openai.com/docs)
- [Anthropic Claude Docs](https://docs.anthropic.com/)

### Internal References
- `backend/apps/blog/ai_prompts.py:1-319` - Existing AI prompts (ready to use)
- `backend/apps/blog/models.py:560-823` - BlogPostPage model
- `backend/plant_community_backend/settings.py:1034-1046` - WAGTAIL_AI config

---

## ✅ Definition of Done

**Issue #158 (Prerequisite) Complete When**:
- [x] Wagtail 7.1+ installed
- [x] All 232+ tests passing
- [x] Blog functionality verified (CRUD, API, frontend)
- [x] Production deployment successful
- [x] Issue #157 unblocked

**Issue #157 (Wagtail AI) Complete When**:
- [x] All 3 phases implemented and tested
- [x] AI features working in production
- [x] 80% cache hit rate achieved
- [x] API costs <$5/month verified
- [x] All documentation complete
- [x] Content editor training complete

---

**Last Updated**: November 9, 2025
**Project Owner**: [Your Name]
**Status**: Planning Complete, Ready to Execute