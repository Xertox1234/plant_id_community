---
status: in_progress
priority: p1
issue_id: "061"
tags: [forum, frontend, image-upload, search, phase-6, enhancement]
dependencies: []
related_issues: ["#61"]
estimated_effort: "18-24 hours"
---

# Forum Phase 6 Completion: Image Upload & Search

## Problem Statement

Phase 6 (React Frontend) is 85% complete with 3 remaining tasks that block Phase 3 launch:
1. **Image Upload Widget** - Users cannot attach images to forum posts
2. **Search Interface** - No way to search forum threads and posts
3. **Real-time Updates** - Deferred to Phase 7 (requires WebSocket infrastructure)

**Impact**:
- Forum posts lack visual context (plant photos critical for identification help)
- Content discoverability is poor without search
- Blocks Phase 3 (Rich Content) launch

**Context**: Phases 1 and 2 are production-ready (96 tests passing). Phase 6 frontend has 24+ component tests but missing key features.

## Findings

**Current State**:
- ✅ `CategoryList`, `ThreadList`, `ThreadDetail` pages complete
- ✅ TipTap rich text editor integrated
- ✅ Responsive design (mobile, tablet, desktop)
- ✅ 24+ component tests passing
- ❌ No image upload capability
- ❌ No search functionality
- ❌ No real-time updates

**Technical Requirements**:
- **Image Upload**: Max 6 images per post, drag-and-drop reordering, 5MB limit, thumbnails
- **Search**: PostgreSQL full-text search, filters (category, author, date), highlighted results, <200ms response
- **Accessibility**: WCAG 2.2 AA compliance, keyboard navigation, ARIA labels

## Proposed Solutions

### Option 1: Complete All 3 Tasks (Recommended)
Implement image upload + search + real-time updates.

**Pros**:
- Full feature parity with requirements
- Best user experience
- No deferred work

**Cons**:
- Requires WebSocket infrastructure (Django Channels or Pusher)
- Additional 6 hours for real-time updates
- More complex deployment

**Effort**: High (24 hours)
**Risk**: Medium (WebSocket complexity)

### Option 2: Complete Image Upload + Search, Defer Real-time (Selected)
Implement critical features (image upload + search), use polling for updates as interim.

**Pros**:
- Focuses on high-value features
- Simpler deployment (no WebSockets)
- Unblocks Phase 3 launch
- Can add real-time later without rework

**Cons**:
- Real-time updates less responsive (polling every 30s)
- Slight UX gap vs Option 1

**Effort**: Medium (18 hours)
**Risk**: Low

### Option 3: Minimal (Search Only)
Only implement search, defer image upload and real-time.

**Pros**:
- Fastest path to Phase 3
- Minimal effort

**Cons**:
- Forum posts lack visual context
- Major feature gap
- User complaints likely

**Effort**: Low (6 hours)
**Risk**: High (user dissatisfaction)

## Recommended Action

**Option 2** - Complete Image Upload + Search, defer real-time updates.

**Implementation Plan**:

### Task 13.2: Image Upload Widget (6 hours, Priority: HIGH)

**Files**:
- `web/src/components/forum/ImageUploadWidget.jsx` - Main upload component
- `web/src/components/forum/SortableImagePreview.jsx` - Drag-and-drop preview
- `web/src/services/forumService.js` - Upload API client
- `backend/apps/forum/viewsets/post_viewset.py` - Upload endpoint
- `backend/apps/forum/models.py` - PostImage model

**Implementation Steps**:
1. **Frontend Component** (3 hours)
   - File picker with multi-select
   - Preview grid with thumbnails (150x150px)
   - Drag-and-drop reordering (@dnd-kit/core)
   - Delete with confirmation
   - Validation (max 6, 5MB, JPEG/PNG/WebP/GIF only)
   - Loading states and error messages
   - Accessibility (keyboard nav, ARIA labels)

2. **Backend Endpoint** (2 hours)
   - `POST /api/v1/forum/posts/{uuid}/upload-image/`
   - Validate file size, MIME type, count
   - PIL thumbnail generation (150x150)
   - Store in `media/forum/posts/{year}/{month}/{day}/`
   - Return image data with URLs

3. **Testing** (1 hour)
   - 7 component tests (Vitest)
   - Upload, validate, reorder, delete
   - Accessibility tests
   - Backend integration tests

**Acceptance Criteria**:
- [ ] Can select 1-6 images via file picker
- [ ] See instant preview thumbnails with loading states
- [ ] Reorder images via drag-and-drop
- [ ] Delete images with confirmation dialog
- [ ] See validation errors (size, type, count)
- [ ] Images upload to backend successfully
- [ ] WCAG 2.2 AA compliant (keyboard nav, ARIA, screen reader)
- [ ] 7 component tests passing
- [ ] Backend integration test passing

**Dependencies**:
```bash
npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
pip install Pillow  # Already installed
```

**Database Migration**:
```python
# Create PostImage model
class PostImage(models.Model):
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='forum/posts/%Y/%m/%d/')
    thumbnail = models.ImageField(upload_to='forum/thumbnails/%Y/%m/%d/', blank=True)
    order = models.PositiveIntegerField(default=0)
    alt_text = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

**Verification**:
```bash
# Frontend tests
cd web
npm run test ImageUploadWidget.test.jsx

# Backend tests
cd backend
python manage.py test apps.forum.tests.test_post_viewset::PostViewSetTests::test_upload_image_action --keepdb -v 2

# Manual E2E
# 1. Navigate to http://localhost:5174/forum/thread/[slug]
# 2. Upload 1-6 images
# 3. Drag to reorder
# 4. Delete one image
# 5. Try uploading 7th image (should error)
# 6. Try uploading 6MB file (should error)
```

---

### Task 13.3: Search Interface (6 hours, Priority: HIGH)

**Files**:
- `web/src/pages/forum/SearchPage.jsx` - Main search page
- `web/src/components/forum/SearchBar.jsx` - Search input
- `web/src/components/forum/SearchResults.jsx` - Results display
- `web/src/components/forum/SearchFilters.jsx` - Filter controls
- `web/src/utils/highlightSearchTerms.js` - Highlight utility
- `backend/apps/forum/viewsets/search_viewset.py` - Search endpoint

**Implementation Steps**:
1. **Backend Search** (2 hours)
   - PostgreSQL full-text search (SearchVector + SearchQuery + SearchRank)
   - Search threads (title, excerpt) and posts (content)
   - Filters: category, author, date range
   - Pagination (20 per page)
   - Response time <200ms

2. **Frontend UI** (3 hours)
   - Search bar with debounce (300ms)
   - Live results as user types
   - Filter sidebar (category, author, date)
   - Highlighted search terms in results
   - Pagination controls
   - "No results" state
   - Loading states

3. **Testing** (1 hour)
   - 6 component tests (Vitest)
   - Debouncing, filtering, pagination
   - Accessibility tests

**Acceptance Criteria**:
- [ ] Can search threads and posts via unified search bar
- [ ] See live results as typing (debounced 300ms)
- [ ] Filter by category, author, date range
- [ ] Search terms highlighted in results
- [ ] Paginate through results (20 per page)
- [ ] See "No results" message when appropriate
- [ ] Keyboard accessible (tab navigation, ARIA labels)
- [ ] Search response time <200ms
- [ ] 6 component tests passing

**Backend Endpoint**:
```python
GET /api/v1/forum/search/?q=watering&category=care-advice&page=1

Response:
{
  "query": "watering",
  "threads": [...],
  "posts": [...],
  "total_threads": 15,
  "total_posts": 42,
  "page": 1,
  "page_size": 20
}
```

**Verification**:
```bash
# Frontend tests
cd web
npm run test SearchPage.test.jsx

# Backend tests
cd backend
python manage.py test apps.forum.tests.test_search_viewset --keepdb -v 2

# Manual E2E
# 1. Navigate to http://localhost:5174/forum/search
# 2. Search for "watering"
# 3. Verify results appear in <300ms
# 4. Filter by category
# 5. Verify search terms highlighted
# 6. Navigate to page 2
```

---

### Task 13.5: Real-time Updates (DEFERRED to Phase 7)

**Status**: Deferred
**Reason**: Requires WebSocket infrastructure (Django Channels or Pusher)
**Priority**: MEDIUM
**Alternative**: Polling-based updates (check for new posts every 30s)

**Future Implementation**:
- Django Channels with Redis backend
- WebSocket endpoint for live post updates
- "New posts available" notification banner
- Estimated effort: 6 hours

## Technical Details

### Image Upload Technical Specs

**Frontend**:
- **Component**: `ImageUploadWidget.jsx` (React functional component)
- **State**: `useState` for images array, loading, errors
- **Drag-and-drop**: @dnd-kit/core (lightweight, accessible)
- **Validation**: Client-side (instant feedback) + server-side (security)
- **Styling**: Tailwind CSS 4 with custom grid layout

**Backend**:
- **Endpoint**: `POST /api/v1/forum/posts/{uuid}/upload-image/`
- **Permissions**: `IsAuthenticated` + ownership check
- **Storage**: Django's `ImageField` with `upload_to` pattern
- **Thumbnails**: PIL/Pillow (150x150 with LANCZOS resampling)
- **Validation**: Size (5MB), MIME type, count (max 6)

**Database**:
```sql
CREATE TABLE forum_postimage (
    id BIGSERIAL PRIMARY KEY,
    post_id UUID NOT NULL REFERENCES forum_post(uuid),
    image VARCHAR(100) NOT NULL,
    thumbnail VARCHAR(100),
    order INTEGER DEFAULT 0,
    alt_text VARCHAR(200),
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_postimage_post_order ON forum_postimage(post_id, order);
```

### Search Technical Specs

**Backend**:
- **PostgreSQL Full-Text Search**:
  ```python
  search_vector = SearchVector('title', weight='A') + SearchVector('excerpt', weight='B')
  search_query = SearchQuery(query)
  qs = qs.annotate(
      search=search_vector,
      rank=SearchRank(search_vector, search_query)
  ).filter(search=search_query).order_by('-rank', '-created_at')
  ```
- **Performance**: GIN indexes on `title` and `content` columns
- **Ranking**: Title matches weighted higher than content matches

**Frontend**:
- **Debouncing**: Custom `useDebounce` hook (300ms delay)
- **URL State**: React Router's `useSearchParams` for shareable URLs
- **Highlighting**: DOMPurify-sanitized `<mark>` tags
- **Pagination**: Custom `Pagination` component with page state

### Testing Strategy

**Unit Tests** (Backend):
- Model validation (PostImage)
- ViewSet actions (upload_image, search)
- Serializer validation
- Permission checks

**Component Tests** (Frontend):
- ImageUploadWidget: upload, validate, reorder, delete
- SearchPage: search, filter, paginate
- Accessibility: keyboard nav, ARIA labels

**Integration Tests**:
- Image upload → storage → preview flow
- Search → results → navigation flow

**E2E Tests** (Playwright):
- Full image upload workflow
- Full search workflow
- Accessibility audit (Lighthouse)

## Resources

**Documentation**:
- `/backend/docs/forum/PHASE_2C_RECOMMENDATIONS.md` - Implementation template
- `/backend/DIAGNOSIS_API_PATTERNS_CODIFIED.md` - DRF UUID patterns
- `/CLAUDE.md` - Project instructions (ports, testing, architecture)
- `/backend/apps/forum/docs/API_REFERENCE.md` - Forum API docs (1,275 lines)

**Code Examples**:
- `/backend/apps/forum/viewsets/post_viewset.py` - Existing ViewSet patterns
- `/web/src/components/forum/ThreadList.jsx` - React component patterns
- `/web/src/components/forum/TipTapEditor.jsx` - Rich editor integration

**External Resources**:
- DnD Kit: https://dndkit.com/
- PostgreSQL Full-Text Search: https://www.postgresql.org/docs/current/textsearch.html
- PIL/Pillow: https://pillow.readthedocs.io/
- WCAG 2.2: https://www.w3.org/WAI/WCAG22/quickref/

## Acceptance Criteria

### Task 13.2: Image Upload
- [ ] Can upload 1-6 images to forum posts
- [ ] See preview thumbnails immediately after upload
- [ ] Reorder images via drag-and-drop
- [ ] Delete images with confirmation
- [ ] Validation errors display clearly (size, type, count)
- [ ] Images stored in backend with thumbnails
- [ ] Keyboard accessible (tab, enter, space for actions)
- [ ] Screen reader announces upload progress and errors
- [ ] 7 component tests passing (100%)
- [ ] Backend integration test passing

### Task 13.3: Search Interface
- [ ] Search bar debounces input (300ms)
- [ ] Results appear in <200ms (backend optimization)
- [ ] Filter by category, author, date range
- [ ] Search terms highlighted in results (`<mark>` tags)
- [ ] Pagination works (20 results per page)
- [ ] "No results" message displays when appropriate
- [ ] URL reflects search query and filters (shareable links)
- [ ] Keyboard accessible (tab through results, enter to navigate)
- [ ] 6 component tests passing (100%)
- [ ] Backend search tests passing

### Overall Phase 6 Success
- [ ] All 24+ existing tests still passing
- [ ] 13+ new tests passing (7 image + 6 search)
- [ ] Lighthouse accessibility score >95
- [ ] Zero console errors or warnings
- [ ] Image upload <5s for 6 images
- [ ] Search perceived as instant (<300ms with debounce)
- [ ] Code review approved
- [ ] Documentation updated (`API_REFERENCE.md`)

## Work Log

### 2025-11-02 - TODO Created
**By:** Claude Code Work Planning System
**Actions:**
- Created comprehensive work plan for Phase 6 completion
- Identified 2 critical tasks (image upload, search)
- Deferred real-time updates to Phase 7 (WebSocket complexity)
- Estimated 18 hours total effort
- Defined acceptance criteria (Given-When-Then format)

**Implementation Priority**:
1. Task 13.2: Image Upload Widget (6 hours) - Start here
2. Task 13.3: Search Interface (6 hours) - Second
3. Task 13.5: Real-time Updates (Deferred) - Phase 7

**Next Steps**:
- Review work plan with team
- Start implementation with Task 13.2
- Run tests after each task
- Deploy after all tests passing

**Timeline**:
- Week 1: Implement both tasks (12-18 hours)
- Week 2: Testing, code review, deployment
- Target: Phase 6 complete by November 9, 2025

## Notes

**Why Option 2?**
- Focuses on high-value, user-facing features
- Simpler deployment (no WebSocket infrastructure)
- Unblocks Phase 3 (Rich Content) work
- Real-time updates nice-to-have, not critical
- Polling (30s) acceptable interim solution

**Dependencies**:
- None - Phase 1 and 2 complete and production-ready
- Can start immediately

**Risks**:
- Low - Well-defined tasks with clear patterns
- Existing similar implementations (blog image uploads, plant search)
- Comprehensive test coverage requirement reduces regression risk

**Success Metrics**:
- User can attach photos to plant identification requests
- User can find relevant threads via search
- All accessibility requirements met (WCAG 2.2 AA)
- Test coverage >90% for new code
- Zero production errors after deployment

Source: Issue #61 - Forum Implementation Tracker
Created: November 2, 2025
Phase: 6 (React Frontend)
Status: In Progress (85% → 100%)
