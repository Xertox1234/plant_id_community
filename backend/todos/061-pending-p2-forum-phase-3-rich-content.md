---
status: pending
priority: p2
issue_id: "061"
tags: [forum, backend, content-sanitization, security, phase-3, enhancement]
dependencies: ["061-in_progress-p1-forum-phase-6-completion"]
related_issues: ["#61"]
estimated_effort: "34-40 hours (3-4 weeks)"
---

# Forum Phase 3: Rich Content & Advanced Features

## Problem Statement

Phase 3 adds rich content capabilities and advanced features to the forum:
1. **Content Sanitization** - Prevent XSS attacks while allowing rich HTML
2. **Markdown Support** - Convert markdown to safe HTML
3. **AI Assistance Tracking** - Track when users use AI tools to write posts
4. **Post Templates** - Common scenarios ("Help Identify", "Pest Problem", "Care Advice")
5. **Image Validation** - Comprehensive validation for uploaded images
6. **Plant Mention System** - Link posts to plant database with autocomplete
7. **Reaction Aggregation** - Most helpful posts, top contributors leaderboard

**Impact**:
- Without sanitization: XSS vulnerabilities (CRITICAL security issue)
- Without markdown: Users forced to write raw HTML (poor UX)
- Without templates: New users struggle to write effective posts
- Without plant mentions: Posts disconnected from plant database
- Without aggregation: No way to surface quality content

**Context**: Phase 6 must be complete (image upload + search) before starting Phase 3. This phase focuses on backend business logic and security.

## Findings

**Current State**:
- ✅ Phase 1: Core models and API complete (96 tests passing)
- ✅ Phase 2: Caching and performance optimized (40% hit rate, <50ms)
- ✅ Phase 6: React frontend 85% complete (image upload + search in progress)
- ❌ No content sanitization (XSS vulnerability)
- ❌ No markdown support (users write raw HTML or plain text)
- ❌ No post templates (new users struggle with formatting)
- ❌ No plant integration (posts isolated from plant database)

**Security Analysis**:
- **XSS Risk**: Users can inject `<script>` tags in post content
- **OWASP Top 10**: A03:2021 - Injection (XSS is #3)
- **Impact**: Session hijacking, credential theft, malware distribution
- **Mitigation**: Content sanitization with whitelist approach (Bleach library)

**User Experience Gaps**:
- New users don't know how to format posts effectively
- No standard format for common scenarios (plant ID help, pest problems)
- Markdown users have to write HTML manually
- Posts about specific plants not linked to plant database

## Proposed Solutions

### Option 1: Full Phase 3 Implementation (Recommended)
Implement all 11 tasks across 3-4 weeks.

**Pros**:
- Complete feature set
- Strong security posture (XSS prevention)
- Best user experience (templates, markdown, plant mentions)
- Quality content surfacing (aggregation)

**Cons**:
- Significant time investment (34-40 hours)
- More complex testing requirements
- Larger deployment scope

**Effort**: High (3-4 weeks)
**Risk**: Medium (scope creep possible)

### Option 2: Security-First Minimal (Alternative)
Only implement content sanitization and image validation.

**Pros**:
- Addresses critical security issues
- Minimal scope
- Fast deployment

**Cons**:
- Poor user experience (no templates, markdown, plant links)
- No quality content surfacing
- Users complain about missing features

**Effort**: Low (1 week)
**Risk**: High (user dissatisfaction)

### Option 3: Phased Rollout
Week 1-2: Security (sanitization, validation)
Week 3-4: Features (markdown, templates, mentions)

**Pros**:
- Security addressed first
- Incremental value delivery
- Easier testing and deployment

**Cons**:
- Two deployments needed
- Features delayed

**Effort**: Medium-High (3-4 weeks total)
**Risk**: Low

## Recommended Action

**Option 1** - Full Phase 3 implementation with weekly checkpoints.

**Implementation Plan**:

## Week 1-2: Rich Content (Tasks 3.1-3.5)

### Task 3.1: Content Sanitization Service (5 hours, Priority: CRITICAL)

**Security Issue**: XSS vulnerability in post content.

**Files**:
- `backend/apps/forum/services/content_sanitization_service.py` - Sanitization service
- `backend/apps/forum/models.py` - Update Post model with sanitization
- `backend/apps/forum/tests/test_content_sanitization.py` - XSS prevention tests

**Implementation**:
```python
import bleach

class ContentSanitizationService:
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 's',
        'ul', 'ol', 'li',
        'h2', 'h3', 'h4', 'h5', 'h6',
        'a', 'img',
        'blockquote', 'code', 'pre',
        'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ]

    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title', 'rel'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'code': ['class'],
    }

    ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

    @classmethod
    def sanitize(cls, html: str) -> str:
        return bleach.clean(
            html,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            protocols=cls.ALLOWED_PROTOCOLS,
            strip=True
        )
```

**Model Update**:
```python
class Post(models.Model):
    content_raw = models.TextField(help_text='Raw user input')
    content = models.TextField(help_text='Sanitized HTML for display')

    def save(self, *args, **kwargs):
        from apps.forum.services.content_sanitization_service import ContentSanitizationService
        self.content = ContentSanitizationService.sanitize(self.content_raw)
        super().save(*args, **kwargs)
```

**Security Tests** (OWASP XSS examples):
```python
def test_strips_script_tags(self):
    html = '<script>alert("XSS")</script><p>Hello</p>'
    result = ContentSanitizationService.sanitize(html)
    self.assertNotIn('<script>', result)
    self.assertIn('<p>Hello</p>', result)

def test_strips_onclick_handlers(self):
    html = '<a href="#" onclick="alert(\'XSS\')">Click</a>'
    result = ContentSanitizationService.sanitize(html)
    self.assertNotIn('onclick', result)

def test_strips_javascript_urls(self):
    html = '<a href="javascript:alert(\'XSS\')">Click</a>'
    result = ContentSanitizationService.sanitize(html)
    self.assertNotIn('javascript:', result)

def test_allows_safe_html(self):
    html = '<p>Hello <strong>world</strong></p>'
    result = ContentSanitizationService.sanitize(html)
    self.assertEqual(result, html)
```

**Acceptance Criteria**:
- [ ] XSS attacks prevented (6+ OWASP test cases passing)
- [ ] Safe HTML tags preserved (p, strong, em, ul, ol, li, a, img)
- [ ] Dangerous attributes stripped (onclick, onerror, javascript:)
- [ ] Links sanitized (only http, https, mailto protocols)
- [ ] Service used in Post model's save() method
- [ ] Migration adds content_raw field
- [ ] 6+ security tests passing

**Migration**:
```bash
python manage.py makemigrations forum --name add_content_raw_field
python manage.py migrate
```

**Verification**:
```bash
cd backend
python manage.py test apps.forum.tests.test_content_sanitization --keepdb -v 2

# Manual XSS testing
python manage.py shell
>>> from apps.forum.services.content_sanitization_service import ContentSanitizationService
>>> ContentSanitizationService.sanitize('<script>alert("XSS")</script><p>Safe</p>')
'<p>Safe</p>'
```

---

### Task 3.2: Markdown Support (3 hours, Priority: MEDIUM)

**Files**:
- `backend/apps/forum/services/content_sanitization_service.py` - Add sanitize_markdown()
- `backend/apps/forum/serializers.py` - Add content_format field
- `backend/apps/forum/tests/test_markdown_conversion.py` - Markdown tests

**Implementation**:
```python
class ContentSanitizationService:
    @classmethod
    def sanitize_markdown(cls, markdown: str) -> str:
        import markdown
        html = markdown.markdown(
            markdown,
            extensions=['extra', 'codehilite', 'nl2br']
        )
        return cls.sanitize(html)
```

**Serializer Update**:
```python
class PostCreateSerializer(serializers.ModelSerializer):
    content_format = serializers.ChoiceField(
        choices=['html', 'markdown'],
        default='html',
        write_only=True
    )

    def create(self, validated_data):
        content_format = validated_data.pop('content_format', 'html')
        if content_format == 'markdown':
            validated_data['content'] = ContentSanitizationService.sanitize_markdown(
                validated_data['content_raw']
            )
        return super().create(validated_data)
```

**Acceptance Criteria**:
- [ ] Markdown converted to HTML (headings, lists, bold, italic, links, code blocks)
- [ ] Syntax highlighting for code blocks
- [ ] Newlines converted to `<br>` tags
- [ ] Output sanitized (no XSS)
- [ ] 3+ markdown conversion tests passing

---

### Task 3.3: AI Assistance Tracking (3 hours, Priority: LOW)

**Files**:
- `backend/apps/forum/migrations/XXXX_add_ai_assistance_fields.py` - Migration
- `backend/apps/forum/models.py` - Add ai_assisted, ai_prompts_used fields
- `backend/apps/forum/serializers.py` - Include new fields
- `web/src/components/forum/PostEditor.jsx` - Add AI checkbox

**Migration**:
```python
migrations.AddField(
    model_name='post',
    name='ai_assisted',
    field=models.BooleanField(default=False)
),
migrations.AddField(
    model_name='post',
    name='ai_prompts_used',
    field=models.JSONField(blank=True, null=True)
),
```

**Frontend**:
```jsx
<label>
  <input
    type="checkbox"
    checked={aiAssisted}
    onChange={(e) => setAiAssisted(e.target.checked)}
  />
  I used AI tools to help write this post
</label>

{aiAssisted && (
  <textarea
    placeholder="Optional: What prompts did you use? (for transparency)"
    value={aiPrompts}
    onChange={(e) => setAiPrompts(e.target.value)}
  />
)}
```

**Acceptance Criteria**:
- [ ] Database fields added (ai_assisted, ai_prompts_used)
- [ ] Checkbox in post editor
- [ ] Optional prompt text field when checked
- [ ] Data saved to backend
- [ ] Index on ai_assisted for analytics
- [ ] 2+ tracking tests passing

---

### Task 3.4: Post Templates (4 hours, Priority: MEDIUM)

**Files**:
- `backend/apps/forum/models.py` - PostTemplate model
- `backend/apps/forum/viewsets/template_viewset.py` - ReadOnlyViewSet
- `backend/apps/forum/management/commands/seed_post_templates.py` - Seed data
- `web/src/components/forum/TemplateSelector.jsx` - Template picker

**Model**:
```python
class PostTemplate(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    content_template = models.TextField(help_text='Markdown template')
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-usage_count', 'name']
```

**Templates to Seed**:
1. **Help Identify Plant**
   - Fields: Where found, plant characteristics, photos, notes
   - Category: Plant Identification

2. **Report Pest/Disease**
   - Fields: Plant species, symptoms, environment, photos, treatments tried
   - Category: Plant Health

3. **Ask for Care Advice**
   - Fields: Plant name, current care routine, question, goal, photos
   - Category: Care Advice

**ViewSet**:
```python
class PostTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PostTemplate.objects.filter(is_active=True)
    serializer_class = PostTemplateSerializer

    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        template = self.get_object()
        template.usage_count += 1
        template.save(update_fields=['usage_count'])
        return Response({'detail': 'Usage tracked'})
```

**Acceptance Criteria**:
- [ ] 3+ post templates seeded (plant ID, pest report, care advice)
- [ ] Template selector in post editor
- [ ] Template content pre-fills editor
- [ ] Usage count increments when template used
- [ ] Templates filterable by category
- [ ] 4+ template tests passing

---

### Task 3.5: Image Upload Validation (3 hours, Priority: HIGH)

**Note**: Most validation covered in Phase 6 Task 13.2. This task adds additional backend validation layers.

**Files**:
- `backend/apps/forum/viewsets/post_viewset.py` - Enhanced validation
- `backend/apps/forum/tests/test_image_validation.py` - Validation tests

**Additional Validation**:
```python
@action(detail=True, methods=['post'])
def upload_image(self, request, uuid=None):
    post = self.get_object()

    # Existing validations:
    # - Max 6 images
    # - Max 5MB per image
    # - MIME type (JPEG, PNG, WebP, GIF)

    # Additional validations:
    # - Total post size limit (50MB)
    total_size = sum(img.image.size for img in post.images.all())
    if total_size + image_file.size > 50 * 1024 * 1024:
        return Response(
            {'detail': 'Total post size exceeds 50MB'},
            status=400
        )

    # - Image dimensions (max 8000x8000)
    img = Image.open(image_file)
    if img.width > 8000 or img.height > 8000:
        return Response(
            {'detail': 'Image dimensions must be less than 8000x8000'},
            status=400
        )

    # - Verify image integrity
    try:
        img.verify()
    except Exception:
        return Response(
            {'detail': 'Invalid or corrupted image file'},
            status=400
        )
```

**Acceptance Criteria**:
- [ ] Max 6 images enforced
- [ ] Max 5MB per image enforced
- [ ] Total post size limit (50MB) enforced
- [ ] MIME type validation (JPEG, PNG, WebP, GIF only)
- [ ] Image dimensions validated (max 8000x8000)
- [ ] Image integrity verified (not corrupted)
- [ ] 5+ validation tests passing

---

## Week 3-4: Plant Integration (Tasks 3.6-3.8)

### Task 3.6: Plant Mention System (6 hours, Priority: MEDIUM)

**Files**:
- `backend/apps/forum/models.py` - PlantMention model
- `backend/apps/forum/viewsets/post_viewset.py` - Autocomplete endpoint
- `web/src/components/forum/PlantMentionExtension.jsx` - TipTap extension
- `backend/apps/forum/tests/test_plant_mentions.py` - Mention tests

**Model**:
```python
class PlantMention(models.Model):
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='plant_mentions')
    plant_species = models.ForeignKey(
        'plant_identification.PlantSpecies',
        on_delete=models.CASCADE,
        related_name='forum_mentions'
    )
    mentioned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['post', 'plant_species']]
        indexes = [
            models.Index(fields=['post']),
            models.Index(fields=['plant_species'])
        ]
```

**Autocomplete Endpoint**:
```python
@action(detail=False, methods=['get'])
def autocomplete_plants(self, request):
    query = request.query_params.get('q', '').strip()
    if len(query) < 2:
        return Response({'results': []})

    from apps.plant_identification.models import PlantSpecies
    results = PlantSpecies.objects.filter(
        Q(scientific_name__icontains=query) |
        Q(common_name__icontains=query)
    ).values('id', 'scientific_name', 'common_name', 'thumbnail_url')[:10]

    return Response({'results': list(results)})
```

**TipTap Extension** (Frontend):
```javascript
import { Node } from '@tiptap/core'
import { ReactRenderer } from '@tiptap/react'
import tippy from 'tippy.js'
import { PlantMentionList } from './PlantMentionList'

export const PlantMention = Node.create({
  name: 'plantMention',
  group: 'inline',
  inline: true,
  selectable: false,
  atom: true,

  addAttributes() {
    return {
      id: { default: null },
      scientificName: { default: null },
      commonName: { default: null },
    }
  },

  parseHTML() {
    return [{ tag: 'span[data-plant-mention]' }]
  },

  renderHTML({ node }) {
    return ['span', {
      'data-plant-mention': node.attrs.id,
      class: 'plant-mention'
    }, `@${node.attrs.scientificName}`]
  },

  addKeyboardShortcuts() {
    return {
      '@': () => {
        // Trigger autocomplete popup
        return true
      }
    }
  }
})
```

**Acceptance Criteria**:
- [ ] Typing "@aloe" triggers autocomplete
- [ ] Autocomplete shows top 10 matching plants
- [ ] Selecting plant inserts mention with thumbnail
- [ ] PlantMention records created in database
- [ ] Mentions displayed with plant thumbnails
- [ ] Clicking mention navigates to plant page
- [ ] 5+ mention tests passing

---

### Task 3.7: Reaction Aggregation Endpoints (4 hours, Priority: LOW)

**Files**:
- `backend/apps/forum/viewsets/post_viewset.py` - Aggregation endpoints
- `web/src/pages/forum/TopPostsPage.jsx` - Top posts page
- `web/src/pages/forum/LeaderboardPage.jsx` - Contributors leaderboard
- `backend/apps/forum/tests/test_aggregation.py` - Aggregation tests

**Endpoints**:

1. **Most Helpful Posts**:
```python
@action(detail=False, methods=['get'])
def most_helpful(self, request):
    from django.db.models import Count
    posts = Post.objects.filter(is_active=True).annotate(
        helpful_count=Count('reactions', filter=Q(reactions__reaction_type='helpful'))
    ).filter(helpful_count__gt=0).order_by('-helpful_count')[:20]

    serializer = PostListSerializer(posts, many=True)
    return Response(serializer.data)
```

2. **Top Contributors**:
```python
@action(detail=False, methods=['get'])
def top_contributors(self, request):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    contributors = User.objects.annotate(
        post_count=Count('forum_posts', filter=Q(forum_posts__is_active=True)),
        helpful_reactions=Count(
            'forum_posts__reactions',
            filter=Q(forum_posts__reactions__reaction_type='helpful')
        )
    ).filter(post_count__gt=0).order_by('-helpful_reactions', '-post_count')[:50]

    return Response([{
        'username': u.username,
        'post_count': u.post_count,
        'helpful_reactions': u.helpful_reactions
    } for u in contributors])
```

**Acceptance Criteria**:
- [ ] Most helpful posts endpoint returns top 20
- [ ] Top contributors endpoint returns top 50
- [ ] Leaderboard sorted by helpful reactions, then post count
- [ ] Frontend pages display data with charts
- [ ] Endpoints cached (15 minutes)
- [ ] 4+ aggregation tests passing

---

### Task 3.8: Phase 3 Testing (6 hours, Priority: HIGH)

**Test Coverage Goals**:
- Content sanitization: 6 tests (XSS prevention)
- Markdown conversion: 3 tests (rendering accuracy)
- AI tracking: 2 tests (data persistence)
- Post templates: 4 tests (seeding, usage tracking)
- Image validation: 5 tests (all validation rules)
- Plant mentions: 5 tests (autocomplete, insertion, display)
- Reaction aggregation: 4 tests (ranking, caching)

**Total**: 29+ new tests for Phase 3

**Testing Strategy**:

1. **Unit Tests** (Backend):
```bash
cd backend
python manage.py test apps.forum.tests.test_content_sanitization --keepdb -v 2
python manage.py test apps.forum.tests.test_markdown_conversion --keepdb -v 2
python manage.py test apps.forum.tests.test_ai_tracking --keepdb -v 2
python manage.py test apps.forum.tests.test_post_templates --keepdb -v 2
python manage.py test apps.forum.tests.test_image_validation --keepdb -v 2
python manage.py test apps.forum.tests.test_plant_mentions --keepdb -v 2
python manage.py test apps.forum.tests.test_aggregation --keepdb -v 2
```

2. **Security Scanning**:
```bash
cd backend
bandit -r apps/forum/
safety check
```

3. **Component Tests** (Frontend):
```bash
cd web
npm run test TemplateSelector.test.jsx
npm run test PlantMentionExtension.test.jsx
```

4. **Integration Tests**:
- Post creation → sanitization → display
- Markdown → HTML conversion → display
- Template selection → pre-fill → submission
- Plant mention → autocomplete → link

5. **E2E Tests** (Playwright):
```bash
cd web
npm run test:e2e -- forum-phase-3
```

**Manual Testing Checklist**:
- [ ] Try XSS attack: `<script>alert('XSS')</script>` (should strip)
- [ ] Create post with markdown (should convert)
- [ ] Use "Help Identify" template (should pre-fill)
- [ ] Type "@aloe" in editor (should autocomplete)
- [ ] View most helpful posts (should rank)
- [ ] View leaderboard (should display top contributors)
- [ ] Upload 7 images (should error)
- [ ] Upload 6MB image (should error)

**Acceptance Criteria**:
- [ ] 29+ new tests passing (100%)
- [ ] Test coverage >90% for new code
- [ ] Zero security vulnerabilities (Bandit clean)
- [ ] All manual tests pass
- [ ] Performance: Sanitization <50ms, search <200ms
- [ ] No N+1 queries (verified with Django Debug Toolbar)

---

## Technical Details

### Security Architecture

**Defense in Depth**:
1. **Input Validation**: Client-side validation for UX
2. **Content Sanitization**: Server-side with Bleach (whitelist approach)
3. **Output Encoding**: Django templates auto-escape by default
4. **CSP Headers**: Content Security Policy prevents inline scripts

**Bleach Configuration**:
- **Whitelist**: Only safe tags allowed (no script, iframe, object)
- **Attribute Filtering**: Only safe attributes (no event handlers)
- **Protocol Filtering**: Only http, https, mailto (no javascript:, data:)
- **Strip Mode**: Remove disallowed tags completely (don't escape)

### Database Schema

**New Tables**:
```sql
-- Post content split
ALTER TABLE forum_post ADD COLUMN content_raw TEXT;
ALTER TABLE forum_post ADD COLUMN ai_assisted BOOLEAN DEFAULT FALSE;
ALTER TABLE forum_post ADD COLUMN ai_prompts_used JSONB;

-- Post templates
CREATE TABLE forum_posttemplate (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    content_template TEXT NOT NULL,
    category_id BIGINT REFERENCES forum_category(id),
    is_active BOOLEAN DEFAULT TRUE,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Plant mentions
CREATE TABLE forum_plantmention (
    id BIGSERIAL PRIMARY KEY,
    post_id UUID NOT NULL REFERENCES forum_post(uuid),
    plant_species_id BIGINT NOT NULL REFERENCES plant_identification_plantspecies(id),
    mentioned_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(post_id, plant_species_id)
);

CREATE INDEX idx_plantmention_post ON forum_plantmention(post_id);
CREATE INDEX idx_plantmention_species ON forum_plantmention(plant_species_id);
CREATE INDEX idx_post_ai_assisted ON forum_post(ai_assisted);
```

### Performance Considerations

**Sanitization**:
- Bleach is fast (~50ms for 10KB content)
- Cache sanitized content (don't re-sanitize on every read)
- Sanitize only on save, not on display

**Markdown**:
- Markdown library is slower (~100ms for 10KB)
- Cache converted HTML
- Syntax highlighting adds overhead (use Pygments with cache)

**Plant Autocomplete**:
- Limit to 10 results
- Index on scientific_name and common_name (GIN trigram)
- Debounce client-side (300ms)

**Aggregation**:
- Cache most helpful posts (15 minutes)
- Cache leaderboard (15 minutes)
- Use database-level aggregation (not Python)

## Resources

**Documentation**:
- Bleach: https://bleach.readthedocs.io/
- Python Markdown: https://python-markdown.github.io/
- OWASP XSS Prevention: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- TipTap Mentions: https://tiptap.dev/experiments/mentions

**Internal Docs**:
- `/backend/docs/forum/PHASE_2C_RECOMMENDATIONS.md` - Implementation template
- `/backend/docs/development/SECURITY_PATTERNS_CODIFIED.md` - Security patterns
- `/backend/DIAGNOSIS_API_PATTERNS_CODIFIED.md` - DRF patterns

**Code Examples**:
- `/backend/apps/plant_identification/services/plant_id_service.py` - Service pattern
- `/backend/apps/blog/models.py` - Content sanitization (Wagtail uses similar)
- `/web/src/components/forum/TipTapEditor.jsx` - Rich editor

## Acceptance Criteria

### Week 1-2: Rich Content
- [ ] Content sanitization prevents all XSS attacks (6+ tests)
- [ ] Markdown converts to safe HTML (3+ tests)
- [ ] AI assistance tracking works (2+ tests)
- [ ] 3 post templates seeded and usable (4+ tests)
- [ ] Image validation comprehensive (5+ tests)
- [ ] Security scan clean (Bandit, Safety)

### Week 3-4: Plant Integration
- [ ] Plant mention autocomplete works (5+ tests)
- [ ] Most helpful posts endpoint works (2+ tests)
- [ ] Top contributors leaderboard works (2+ tests)
- [ ] All aggregations cached (15 min TTL)

### Overall Phase 3 Success
- [ ] 29+ new tests passing (100%)
- [ ] Test coverage >90% backend, >80% frontend
- [ ] Zero XSS vulnerabilities (OWASP test suite)
- [ ] Performance: Sanitization <50ms, search <200ms
- [ ] Template usage >20% of new posts (within 1 month)
- [ ] Plant mentions in >10% of posts (within 1 month)
- [ ] Code review approved
- [ ] Documentation updated

## Work Log

### 2025-11-02 - TODO Created
**By:** Claude Code Work Planning System
**Actions:**
- Created Phase 3 work plan (11 tasks, 34-40 hours)
- Prioritized security (content sanitization) first
- Organized into 2 sprints (rich content + plant integration)
- Defined 29+ test cases across 7 feature areas
- Established success metrics (usage, performance, security)

**Dependencies**:
- Phase 6 must be 100% complete before starting
- Blocks Phase 4 (Moderation & Trust System)

**Timeline**:
- Week 1-2: Rich content (Tasks 3.1-3.5, 18 hours)
- Week 3-4: Plant integration (Tasks 3.6-3.8, 16-22 hours)
- Target: Phase 3 complete by November 30, 2025

**Next Steps**:
1. Wait for Phase 6 completion
2. Start with Task 3.1 (Content Sanitization) - CRITICAL
3. Run security tests after each task
4. Deploy after all tests passing + security scan clean

## Notes

**Why Option 1 (Full Implementation)?**
- Security is critical (XSS prevention non-negotiable)
- User experience features drive engagement (templates, markdown)
- Plant integration ties forum to core product (plant database)
- Aggregation surfaces quality content (community building)

**Security Priority**:
- Task 3.1 (Content Sanitization) is CRITICAL priority
- Must pass OWASP XSS test suite before proceeding
- Bandit and Safety scans required before deployment

**User Experience Focus**:
- Templates reduce friction for new users
- Markdown improves content quality
- Plant mentions create connections to plant database
- Aggregation rewards quality contributors

**Success Metrics**:
- **Security**: Zero XSS vulnerabilities
- **Usage**: 20%+ posts use templates within 1 month
- **Engagement**: 10%+ posts mention plants within 1 month
- **Performance**: Sanitization <50ms, aggregation cached
- **Quality**: Test coverage >90%

Source: Issue #61 - Forum Implementation Tracker
Created: November 2, 2025
Phase: 3 (Rich Content & Advanced Features)
Status: Pending (awaits Phase 6 completion)
