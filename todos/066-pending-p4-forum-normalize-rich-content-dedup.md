---
status: pending
priority: p4
issue_id: "066"
tags: [refactor, forum, serializer]
dependencies: []
---

# Extract _normalize_rich_content into shared mixin (CreateTopicSerializer / CreatePostSerializer)

## Problem

`_normalize_rich_content` is defined identically in both `CreateTopicSerializer` and
`CreatePostSerializer` in `backend/apps/forum_integration/serializers.py`. Any bug fix
or behaviour change must be applied in two places, and the implementations will diverge
over time.

## Findings

- `backend/apps/forum_integration/serializers.py`: identical `_normalize_rich_content`
  method body appears in `CreateTopicSerializer` (line ~351) and `CreatePostSerializer`
  (line ~465).
- Surfaced during PR #259 code review as pre-existing technical debt.
- The method validates and normalises `plant_mention` blocks in StreamField-like rich
  content JSON — pure logic with no model dependencies beyond `PlantSpeciesPage`.

## Recommended Action

1. Define a `RichContentMixin` class above both serializers:

   ```python
   class RichContentMixin:
       def _normalize_rich_content(self, rich_content):
           ...  # single shared implementation
   ```

2. Add `RichContentMixin` as the first base class of both `CreateTopicSerializer`
   and `CreatePostSerializer`.
3. Delete the duplicate method bodies from both serializers.
4. Run the forum_integration test suite to confirm no regressions (after todo 065
   fixes the Machina test environment).

## Technical Details

- File: `backend/apps/forum_integration/serializers.py`
- Depends on: todo 065 (Machina test env) for full test coverage after the change.

## Acceptance Criteria

- [ ] `_normalize_rich_content` exists in exactly one place in serializers.py.
- [ ] Both `CreateTopicSerializer` and `CreatePostSerializer` behave identically to
      before for valid and invalid `plant_mention` blocks.
- [ ] Forum integration tests pass (requires todo 065 first).

## Work Log

### 2026-05-08 - Created as follow-up from PR #259 code review

- Identified as pre-existing duplication; not introduced by todo 064.
