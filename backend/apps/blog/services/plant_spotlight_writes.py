"""The one write path for programmatic `plant_spotlight` updates (todo 438).

`populate_plant_images` and `backfill_spotlight_credits` both change
spotlight blocks outside the admin. A bare `page.save()` (what the populate
command used to do) writes the page row only: the admin's latest revision
still lacks the change, so the editor's next publish silently drops it, and
no `page_published` fires, so `BlogCacheService` keeps serving the old detail
response for up to 24h. This module writes through a revision instead,
following `docs/rules/wagtail.md`:

- **Live page, no unpublished changes** -> `save_revision().publish()` on a
  freshly loaded instance. `page_published` fires (cache invalidation) and the
  latest revision carries the change.
- **Live page WITH unpublished changes** -> SKIPPED and reported. The live row
  is not the editor's draft: a revision built from it and published would
  either discard the draft (it stops being the latest revision) or, built from
  the draft instead, publish work the editor has not approved. Neither is a
  command's call. Publish or discard the draft, then re-run.
- **Not live (never published, or unpublished)** -> `save_revision()` only,
  built from the latest revision (what the admin edits), so the draft gains the
  change and nothing goes live.
- **In a moderation workflow** -> SKIPPED: a new revision would bypass the
  review of the one that was submitted.
- **An alias page** -> SKIPPED: it mirrors its source page, which is where
  the change belongs (Wagtail refuses revisions on aliases).

No user is available in a management command, so the revision and the
publish log entry are system-attributed (`user=None`, which also skips the
publish permission check — the command's operator is the authority). This is
a programmatic publish that bypasses workflows by design; the content it
writes is built by code (an image choice and its credit), not user input.

Between loading the base content and writing, `save_spotlight_updates`
re-reads the page's revision pointers under a row lock and refuses to write
if they moved — an editor who saved during a slow image fetch is never
overwritten.
"""

from dataclasses import dataclass

from django.db import transaction
from wagtail.models import Page

from ..models import BlogPostPage

# Mirrors plant_spotlight.image_credit's CharBlock(max_length=255): a longer
# value would make every later admin edit of the page fail validation on a
# field the editor never touched (PR #820 review).
IMAGE_CREDIT_MAX_LENGTH = 255

PUBLISHED = "published"
DRAFT_SAVED = "draft_saved"
SKIPPED_UNPUBLISHED_CHANGES = "skipped_unpublished_changes"
SKIPPED_IN_WORKFLOW = "skipped_in_workflow"
SKIPPED_ALIAS = "skipped_alias"
SKIPPED_CHANGED_DURING_RUN = "skipped_changed_during_run"
BLOCK_NOT_FOUND = "block_not_found"
NO_CHANGES = "no_changes"

WRITTEN = (PUBLISHED, DRAFT_SAVED)

SKIP_MESSAGES = {
    SKIPPED_UNPUBLISHED_CHANGES: (
        "has unpublished draft changes; publish or discard the draft in the "
        "CMS, then re-run"
    ),
    SKIPPED_IN_WORKFLOW: "is in a moderation workflow; finish it, then re-run",
    SKIPPED_ALIAS: "is an alias; its source page is updated instead",
    SKIPPED_CHANGED_DURING_RUN: "was edited while this command ran; re-run",
    BLOCK_NOT_FOUND: "no longer has the spotlight block; re-run",
}

_PAGE_STATE_FIELDS = (
    "live",
    "has_unpublished_changes",
    "latest_revision_id",
    "live_revision_id",
)


@dataclass
class SpotlightBase:
    """The content a spotlight update is computed from and written back to."""

    page: BlogPostPage
    skip_reason: str | None
    state: tuple


def _page_state(page):
    return tuple(getattr(page, field) for field in _PAGE_STATE_FIELDS)


def load_spotlight_base(page_id):
    """Load the page content a programmatic spotlight write must start from.

    Always returns a `SpotlightBase`; `skip_reason` is set when the page must
    not be written (see the module docstring). Callers decide what to fetch
    from `base.page.content_blocks` and pass the result to
    `save_spotlight_updates`.
    """
    page = BlogPostPage.objects.get(pk=page_id)
    state = _page_state(page)
    skip_reason = None
    if page.alias_of_id:
        skip_reason = SKIPPED_ALIAS
    elif page.live and page.has_unpublished_changes:
        skip_reason = SKIPPED_UNPUBLISHED_CHANGES
    elif page.workflow_in_progress:
        skip_reason = SKIPPED_IN_WORKFLOW

    base = page
    if not page.live and page.latest_revision_id:
        # A draft's content is its latest revision — what the admin edits.
        base = page.get_latest_revision_as_object()
    return SpotlightBase(page=base, skip_reason=skip_reason, state=state)


def save_spotlight_updates(base, updates):
    """Apply `{block_id: {child_name: value}}` to `base` and write a revision.

    Returns one of the outcome constants above. Never writes a partial set:
    if any block id is missing from the base content, nothing is written.
    """
    if base.skip_reason:
        return base.skip_reason
    if not updates:
        return NO_CHANGES

    page = base.page
    stream = page.content_blocks
    found = set()
    for index, block in enumerate(stream):
        block_id = str(block.id)
        if block.block_type != "plant_spotlight" or block_id not in updates:
            continue
        new_value = dict(block.value)
        new_value.update(updates[block_id])
        if "image_credit" in new_value:
            new_value["image_credit"] = (new_value["image_credit"] or "")[
                :IMAGE_CREDIT_MAX_LENGTH
            ]
        # The 3-tuple keeps the block's id; the 2-tuple form would re-id it
        # (comment anchors and any client keyed on block ids would break).
        stream[index] = (block.block_type, new_value, block.id)
        found.add(block_id)
    if found != set(updates):
        return BLOCK_NOT_FOUND

    with transaction.atomic():
        current = (
            Page.objects.select_for_update()
            .filter(pk=page.pk)
            .values_list(*_PAGE_STATE_FIELDS)
            .first()
        )
        if current != base.state:
            return SKIPPED_CHANGED_DURING_RUN
        revision = page.save_revision(log_action=True)
        if page.live:
            revision.publish()
            return PUBLISHED
    return DRAFT_SAVED
