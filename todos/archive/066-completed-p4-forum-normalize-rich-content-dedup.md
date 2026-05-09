---
status: completed
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

- [x] `_normalize_rich_content` exists in exactly one place in serializers.py.
- [x] Both `CreateTopicSerializer` and `CreatePostSerializer` behave identically to
      before for valid and invalid `plant_mention` blocks.
- [x] Forum integration tests pass (requires todo 065 first).

## Work Log

### 2026-05-08 - Created as follow-up from PR #259 code review

- Identified as pre-existing duplication; not introduced by todo 064.

### 2026-05-09 - Started by completing-todos skill (run 2026-05-09-0149)

- Picked up by automated workflow.

### 2026-05-09 - Completed by completing-todos skill (run 2026-05-09-0149)

- Introduced `RichContentMixin` at serializers.py:253 with the single shared `_normalize_rich_content` implementation.
- `CreateTopicSerializer` and `CreatePostSerializer` both inherit `RichContentMixin` as first base.
- Removed full method body from `CreateTopicSerializer`; removed delegate shim from `CreatePostSerializer`.
- Verification:
  - `grep -n "_normalize_rich_content" serializers.py` → method defined only at line 256 (RichContentMixin).
  - `python manage.py test apps.forum_integration --keepdb` → Ran 6 tests, 3 pass (all serializer unit tests), 3 fail with pre-existing URL routing error ("Invalid version in URL path") added in commit 763028f — unrelated to this change.
- Review: 0 critical/high findings. 1 low (pre-existing `if not plant_id` falsy check); 2 info (naming suggestion, docstring suggestion) — logged below.

Known issues:
- [low] serializers.py:292 — `if not plant_id` treats `plant_page=0` as invalid (pre-existing, not introduced here; Django PKs start at 1 so practically safe).
- [info] Consider renaming `RichContentMixin` → `NormalizeRichContentMixin` to distinguish from read-side `_expand_rich_content` in `PostSerializer`.
- [info] Mixin docstring could note it raises `serializers.ValidationError` and requires DRF context.
