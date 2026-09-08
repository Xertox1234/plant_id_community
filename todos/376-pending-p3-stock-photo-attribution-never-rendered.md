---
status: pending
priority: p3
issue_id: "376"
tags: [backend, compliance, plant-identification]
dependencies: []
source_review: "todos/archive/358-completed-p3-widen-requests-exception-drift-guard.md"
---

# Unsplash/Pexels attribution is built and dropped on the saved image

## Problem

`UnsplashImageService.download_and_create_wagtail_image` and its Pexels twin
each built a display attribution string and then never used it:

```python
# unsplash_service.py (before todo 358)
photographer = image_data.get("photographer", {})
attribution = f"Photo by {photographer.get('name', 'Unknown')} on Unsplash"

wagtail_image = Image(title=title, file=image_file)
wagtail_image.save()
```

Todo 358 deleted both lines. They were dead — `flake8 F841`, and touching those
files for the first time put them under the pre-commit gate, which the repo
forbids suppressing further. **Deleting a dead local changed nothing at
runtime, but it removed the only in-repo evidence that this path was meant to
record attribution**, which is why that question is written down here instead of
disappearing with the line.

## Findings

Verified on the tree at todo 358's merge, not assumed:

- The **search** path does carry attribution: `unsplash_service.py:177` and
  `pexels_service.py:165` put `attribution_url` in each result dict, and
  `plant_image_service.get_attribution_text` (line 189, used at 284) renders a
  credit string.
- The **download/save** path does not run either of those. The Wagtail `Image`
  it creates gets `title`, `file`, and taggit tags — for Unsplash
  `["unsplash", "botanical", f"photographer:{username}", f"unsplash_id:{id}"]`.
- So a photographer *username* is recoverable from a tag, but no rendered
  credit and no link back to the photographer or to Unsplash/Pexels is attached
  to the stored image.
- The path is live, not dead: both services call it from their own
  `search`-to-image flow (`unsplash_service.py:289`, `pexels_service.py:282`).
  `ai_image_service.py:226` has a same-named method that is a separate concern.

## Open question

Unsplash's API terms require attribution **on display**, with a link back to the
photographer and to Unsplash, and Pexels' terms are similar. A taggit tag is not
display. Whether this repo is actually out of compliance depends on where these
stored images are surfaced, which this todo has not traced.

## Recommended Action

1. Trace where images created by `download_and_create_wagtail_image` are
   rendered (blog StreamField? plant detail pages?) and whether any template
   emits a credit.
2. If nothing does, decide the storage shape — a Wagtail Image custom field, a
   sibling model, or a structured tag — and populate it in both services from
   `image_data`, which already carries `attribution_url`.
3. If a credit *is* rendered from the `photographer:` tag somewhere, close this
   and record where.

## Acceptance Criteria

- [ ] The render path for stock-photo images is traced and written down
- [ ] Either a credit + link is attached to the saved image and displayed, or
      the existing display path is documented and this is closed as a non-issue

## Notes

p3, not p2: no user-facing breakage and no security exposure — this is a
licensing-terms question about images the app stores. Filed from todo 358 so a
gate-required deletion left a tracked question rather than a silent gap.
