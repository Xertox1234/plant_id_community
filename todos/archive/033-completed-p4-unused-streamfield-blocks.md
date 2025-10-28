---
status: resolved
priority: p4
issue_id: "033"
tags: [cleanup, blog, wagtail]
dependencies: []
resolved_date: 2025-10-27
---

# Remove Unused StreamField Block Types

## Problem

`apps/blog/blocks.py` defines 15+ block types but only 8 are used in actual blog posts.

## Findings

**pattern-recognition-specialist**:
- Defined blocks: HeadingBlock, ParagraphBlock, ImageBlock, QuoteBlock, CodeBlock, CallToActionBlock, ListBlock, EmbedBlock, PlantSpotlightBlock, SeasonalTipBlock, DifficultyIndicatorBlock, CareTipBlock, etc.
- Used in content (estimate): HeadingBlock, ParagraphBlock, ImageBlock, QuoteBlock, CodeBlock, CallToActionBlock, ListBlock, EmbedBlock
- Unused blocks: PlantSpotlightBlock, SeasonalTipBlock, DifficultyIndicatorBlock (no instances in blog posts)

**code-simplicity-reviewer**:
- YAGNI violation: Building features not yet needed
- 300+ lines of block code, ~40% unused
- StreamFieldRenderer supports all blocks but some never rendered

## Proposed Solutions

### Option 1: Remove Unused Blocks (Recommended)
```python
# apps/blog/blocks.py - Keep only these
StreamBlock([
    ('heading', HeadingBlock()),
    ('paragraph', ParagraphBlock()),
    ('image', ImageBlock()),
    ('quote', QuoteBlock()),
    ('code', CodeBlock()),
    ('call_to_action', CallToActionBlock()),
    ('list', ListBlock()),
    ('embed', EmbedBlock()),
    # Remove: PlantSpotlightBlock, SeasonalTipBlock, etc.
])
```

**Pros**: Simpler codebase, less maintenance, clearer intent
**Cons**: Need to add back if features needed later
**Effort**: 2 hours (audit, remove, test)
**Risk**: Low (unused code, no impact)

### Option 2: Keep All Blocks for Future Use
**Pros**: Ready for future content types
**Cons**: YAGNI, maintenance overhead
**Risk**: Low (just extra code)

### Option 3: Mark as Deprecated
```python
# Commented out but preserved for reference
# ('plant_spotlight', PlantSpotlightBlock()),  # TODO: Implement when plant database ready
```

**Pros**: Documents intent, easy to re-enable
**Cons**: Still clutters codebase
**Effort**: 1 hour

## Recommended Action

**Option 3** (Compromise) - Comment out unused blocks:
1. Audit blog posts to confirm which blocks are actually used:
```bash
# Check blog post content_blocks for block types
python manage.py shell
>>> from apps.blog.models import BlogPostPage
>>> for post in BlogPostPage.objects.all():
...     print(post.content_blocks.stream_block.child_blocks.keys())
```
2. Comment out unused blocks with TODOs
3. Remove corresponding frontend rendering in StreamFieldRenderer.jsx
4. Document in CLAUDE.md which blocks are available

## Technical Details

**Block types defined** (`apps/blog/blocks.py`):
```python
# Core blocks (confirmed used)
HeadingBlock, ParagraphBlock, ImageBlock, QuoteBlock, CodeBlock

# Utility blocks (confirmed used)
CallToActionBlock, ListBlock, EmbedBlock

# Domain-specific blocks (usage unknown)
PlantSpotlightBlock  # Plant database feature
SeasonalTipBlock     # Seasonal content feature
DifficultyIndicatorBlock  # Plant care difficulty
CareTipBlock         # Care instructions
WarningBlock         # Warnings/alerts
```

**Frontend rendering** (`web/src/components/StreamFieldRenderer.jsx`):
- Lines 20-150: Switch statement with 12+ case blocks
- Should match backend available blocks

**Audit query**:
```python
from apps.blog.models import BlogPostPage
from collections import Counter

block_types = []
for post in BlogPostPage.objects.all():
    for block in post.content_blocks:
        block_types.append(block.block_type)

print(Counter(block_types))
# Output: {'paragraph': 45, 'heading': 23, 'image': 12, ...}
```

## Resources

- Wagtail StreamField docs: https://docs.wagtail.org/en/stable/topics/streamfield.html
- YAGNI principle: https://martinfowler.com/bliki/Yagni.html

## Acceptance Criteria

- [x] Audit confirms which block types are actually used
- [x] Unused blocks commented out or removed
- [x] Frontend StreamFieldRenderer matches backend blocks
- [x] No rendering errors for existing blog posts
- [x] Documentation updated (CLAUDE.md lists available blocks)

## Resolution Summary

**Date Completed**: 2025-10-27
**Resolution**: Removed unused StreamField blocks from both backend and frontend

### Changes Made

**Backend** (`/backend/apps/blog/models.py`):
- Removed 4 unused block definitions from BlogStreamBlocks class:
  - `image` - No instances in database (use paragraph with embedded images)
  - `care_instructions` - No instances in database (74 lines removed)
  - `gallery` - No instances in database (4 lines removed)
  - `video_embed` - No instances in database (7 lines removed)
- Added comment documenting removed blocks for future reference
- Retained 5 actively used blocks: heading, paragraph, quote, code, plant_spotlight, call_to_action

**Frontend** (`/web/src/components/StreamFieldRenderer.jsx`):
- Removed rendering logic for unused blocks: image, list, embed
- Updated tests to remove tests for unsupported blocks
- Removed unused imports: `vi`, `beforeEach` from test file

**Verification**:
- Database audit confirmed block usage: heading(10), paragraph(10), quote(2), code(1), plant_spotlight(1), call_to_action(1)
- All 7 existing blog posts still render correctly (no errors)
- Frontend linting passes with no errors
- Frontend build completes successfully (1.74s)
- Code reduction: ~120 lines removed from backend, ~80 lines from frontend tests

### Impact

- **Performance**: Slightly reduced bundle size
- **Maintainability**: Cleaner codebase following YAGNI principle
- **Risk**: Zero - removed code was never used in production
- **Rollback**: Blocks can be easily re-added from git history if needed

## Work Log

- 2025-10-25: Issue identified by pattern-recognition-specialist agent
- 2025-10-27: Resolution completed - removed 4 unused blocks from backend, cleaned up frontend

## Notes

**Priority rationale**: P4 (Low) - Code cleanliness, no functional impact
**Verification needed**: Actual audit of blog post content required
**Trade-off**: Clean code now vs. flexibility later
**Related**: constants.py cleanup (issue #018) - similar YAGNI pattern
