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
- **Image Upload**: Max 6 images per post, drag-and-drop reordering, 10MB limit, thumbnails
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
- `backend/apps/forum/models.py` - Existing `Attachment` model

**Implementation Steps**:
1. **Frontend Component** (3 hours)
   - File picker with multi-select
   - Preview grid with thumbnails (150x150px)
   - Drag-and-drop reordering (@dnd-kit/core)
   - Delete with confirmation
   - Validation (max 6, 10MB, JPEG/PNG/WebP/GIF only)
   - Loading states and error messages
   - Accessibility (keyboard nav, ARIA labels)

2. **Backend Endpoint** (2 hours)
   - `POST /api/v1/forum/posts/{uuid}/upload_image/`
   - Validate file size, MIME type, count
   - ImageKit thumbnail/medium/large renditions
   - Store via the `Attachment.image` upload path
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
# Existing Attachment model is used for post images.
# Key fields: post, image, original_filename, file_size, mime_type,
# display_order, alt_text, is_active, created_at.
# ImageKit provides thumbnail, medium, and large renditions.
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
- **Endpoint**: `POST /api/v1/forum/posts/{uuid}/upload_image/`
- **Permissions**: `CanUploadImages` + `IsAuthorOrModerator`
- **Storage**: Existing `Attachment.image` `ImageField`
- **Thumbnails**: ImageKit thumbnail/medium/large renditions
- **Validation**: Size (10MB), MIME type, count (max 6)

**Database**:
```sql
-- Existing forum_attachment table is used.
-- Active attachments are ordered by display_order and scoped by post_id.
CREATE INDEX forum_attach_active_idx ON forum_attachment(post_id, display_order)
WHERE is_active = TRUE;
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
- **Performance**: GIN index coverage exists for post content; explicit thread title/excerpt search indexes remain pending
- **Ranking**: Title matches weighted higher than content matches

**Frontend**:
- **Debouncing**: Custom `useDebounce` hook (300ms delay)
- **URL State**: React Router's `useSearchParams` for shareable URLs
- **Highlighting**: DOMPurify-sanitized `<mark>` tags
- **Pagination**: Custom `Pagination` component with page state

### Testing Strategy

**Unit Tests** (Backend):
- Model validation (`Attachment`)
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
- [x] Can upload 1-6 images to forum posts
- [x] See preview thumbnails immediately after upload
- [x] Reorder images via drag-and-drop
- [x] Delete images with confirmation
- [x] Validation errors display clearly (size, type, count)
- [x] Images stored in backend with thumbnails
- [x] Keyboard accessible (tab, enter, space for actions)
- [x] Screen reader announces upload progress and errors
- [x] 7 component tests passing (100%)
- [x] Backend integration test passing

### Task 13.3: Search Interface
- [x] Search bar debounces input (300ms)
- [ ] Results appear in <200ms (backend optimization)
- [x] Filter by category, author, date range
- [x] Search terms highlighted in results (`<mark>` tags)
- [x] Pagination works (20 results per page)
- [x] "No results" message displays when appropriate
- [x] URL reflects search query and filters (shareable links)
- [x] Keyboard accessible (tab through results, enter to navigate)
- [x] 6 component tests passing (100%)
- [x] Backend search tests passing

### Overall Phase 6 Success
- [ ] All 24+ existing tests still passing
- [ ] 13+ new tests passing (7 image + 6 search)
- [ ] Lighthouse accessibility score >95
- [ ] Zero console errors or warnings
- [ ] Image upload <5s for 6 images
- [ ] Search perceived as instant (<300ms with debounce)
- [x] Code review approved
- [x] Documentation updated (`API_REFERENCE.md`)

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

### 2026-05-01 - Phase 6 Follow-up
**Actions:**
- Fixed frontend attachment compatibility with backend `AttachmentSerializer` fields (`image_url`, `thumbnail_url`, `medium_url`, `large_url`).
- Updated `ImageUploadWidget` to support multi-select/multi-drop uploads up to the 6-image limit, add delete confirmation, expose clearer max-count feedback, and announce errors/status changes for assistive tech.
- Fixed backend `upload_image` to count only active attachments and persist `mime_type`, preventing required-field failures when creating attachments.
- Added drag-and-drop and keyboard button image reordering in `ImageUploadWidget`, backed by a new `reorder_images` post action that persists `display_order` for active attachments.
- Fixed review findings: action-level permissions now apply to image reordering, uploads append `display_order` under a post row lock, `alt_text` is validated before database writes, moderator image deletion honors the `Moderators` group, the upload drop zone exposes disabled/in-progress state, and drag start sets transfer data for Firefox compatibility.
- Added search date range filters, switched search input debounce to 300ms, and added highlighted result snippets with `<mark>` tags.
- Added backend tests for image reorder success, incomplete/duplicate reorder payloads, permissions, upload append order, alt text validation, and active-only upload counts.
- Validated frontend with `npm run type-check` and targeted Vitest coverage: `ImageUploadWidget` + `SearchPage` (50 tests passing).
- Validated backend syntax with `python -m py_compile apps/forum/viewsets/post_viewset.py apps/forum/tests/test_post_viewset.py`.

**Remaining:**
- Backend integration/search tests could not be run in the current container because Django/DRF are not installed.

### 2026-05-02 - Backend Validation Unblocked

**Actions:**

- Installed backend dependencies with pip legacy resolver due existing pinned dependency conflicts (`celery==5.5.3` requires `kombu<5.6`, but requirements pin `kombu==5.6.0`).
- Started a temporary PostgreSQL 16 container matching the test settings.
- Fixed `garden_calendar` migration `0005_add_plantimage_uuid_primary_key` so `RunSQL` receives executable SQL strings instead of `psycopg2.sql.Composed` objects, unblocking fresh test database migrations.
- Added Forum API documentation for unified search, image upload, image deletion, and image reordering.
- Corrected API documentation examples to match serializer contracts (`content_raw`, `first_post_format`, UUID primary keys, `AttachmentSerializer` URL fields).
- Validated targeted backend image/search coverage: `test_upload_image_success`, `test_reorder_images_success`, and `test_search_response_includes_all_expected_fields` all passed.
- Validated broader backend forum post/thread coverage: `apps.forum.tests.test_post_viewset` and `apps.forum.tests.test_thread_viewset` passed (65 tests).
- Validated fresh SQLite `garden_calendar` migrations after adding a non-PostgreSQL no-op path for the primary-key swap SQL.
- Completed code review with no remaining blockers.

**Remaining:**

- Full web test suite still needs a longer validation pass before closing the todo.
- Measured <200ms backend search response and Lighthouse accessibility score remain manual/performance validation items.
