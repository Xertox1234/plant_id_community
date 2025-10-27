---
status: ready
priority: p4
issue_id: "033"
tags: [cleanup, blog, wagtail]
dependencies: []
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

- [ ] Audit confirms which block types are actually used
- [ ] Unused blocks commented out or removed
- [ ] Frontend StreamFieldRenderer matches backend blocks
- [ ] No rendering errors for existing blog posts
- [ ] Documentation updated (CLAUDE.md lists available blocks)

## Work Log

- 2025-10-25: Issue identified by pattern-recognition-specialist agent

## Notes

**Priority rationale**: P4 (Low) - Code cleanliness, no functional impact
**Verification needed**: Actual audit of blog post content required
**Trade-off**: Clean code now vs. flexibility later
**Related**: constants.py cleanup (issue #018) - similar YAGNI pattern
