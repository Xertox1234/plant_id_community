---
status: completed
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

- [x] The render path for stock-photo images is traced and written down
- [x] Either a credit + link is attached to the saved image and displayed, or
      the existing display path is documented and this is closed as a non-issue

## Notes

p3, not p2: no user-facing breakage and no security exposure — this is a
licensing-terms question about images the app stores. Filed from todo 358 so a
gate-required deletion left a tracked question rather than a silent gap.

## Work Log

### 2026-09-24 - Done: credit + link stored on the plant_spotlight block and rendered everywhere

**Trace (verified on the tree, not assumed).** Unsplash/Pexels images are
created only by `download_and_create_wagtail_image` (`unsplash_service.py`,
`pexels_service.py`), reached only through each service's
`get_best_plant_image` -> `PlantImageService.get_best_plant_image`, whose one
caller is the manual command `apps/blog/management/commands/populate_plant_images.py`.
That command writes the image into the `plant_spotlight` StructBlock of
`BlogPostPage.content_blocks`. The three render paths showed no credit: the
API (`APIImageChooserBlock.get_api_representation` -> `{id,url,alt,width,height}`),
the web `StreamFieldRenderer` `plant_spotlight` case, and the Wagtail template
`templates/blog/blocks/plant_spotlight.html`. There is no custom image model,
and no template read the `photographer:` tag. So the terms gap was real.

**Storage shape.** The credit lives on the block, not the image. That is the
only place these images are displayed, and it needed no custom image model.
- `plant_spotlight` is now `PlantSpotlightBlock` (`apps/blog/blocks.py`) with
  two optional children: `image_credit` (CharBlock, max 255) and
  `image_credit_url` (URLBlock). Migration `blog/0015` holds only this
  `content_blocks` AlterField: a whitespace-insensitive diff against `0013`
  shows the two new entries plus renumbering. `makemigrations --check` was
  clean before the change.
- `PlantImageService.get_attribution_url` (a staticmethod) links the
  photographer. Unsplash gets its profile URL plus the required
  `utm_source=plant_community&utm_medium=referral` (lifted from
  `trigger_download` into `with_unsplash_utm`, with no behaviour change).
  Pexels gets the photographer URL. AI images get `""`. Any value that isn't
  http(s) also gets `""`.
- `populate_plant_images` writes the credit text (the existing
  `get_attribution_text`) and the URL with the image in one update, so a
  `--force` replacement never leaves the previous photographer's credit
  behind.

**Display.** The credit shows under the image, and only when an image is
present:
- Template: `PlantSpotlightBlock.get_context` exposes `credit_href`, vetted by
  `safe_http_url` (absolute http(s) with a host, otherwise `""`). A
  non-http URL renders as plain text.
- Web: a `<figure>`/`<figcaption>` holds the credit. It is linked only
  through `safeExternalUrl`, which moved from `LinkPreviewCard.tsx` to
  `web/src/utils/externalUrl.ts` and is now shared. External links use
  `target="_blank" rel="noopener noreferrer"`, matching the existing
  pattern.
- API v2: StructBlock serialises the new children as-is. Blocks saved
  before the change return `null` for both.

**Evidence.**
- Web: 5 new Vitest cases. 3 failed before the change; the 2 negative guards
  passed before, as expected. `StreamFieldRenderer` + `PostCard` +
  `TipTapEditor` suites: 171/171 pass. `type-check`, `lint` and
  `check:classes` are clean.
- Web mutations: dropping the URL guard, dropping `rel`, and not rendering
  the credit were each caught.
- Backend: the 14 `SimpleTestCase` tests ran via plain `unittest` with no
  DB and pass. Mutations to `safe_http_url`'s scheme check, the unvetted
  `get_context` href, and the dropped UTM were each caught.
- A DB-free template render with a mocked rendition showed four correct
  cases: link, `javascript:` as text, no credit, and credit without a URL.
- The DB-backed tests (template render, the command -> stored block -> API
  flow) are written but not yet run here.

**Residual.** There is one link, to the photographer. Unsplash's guideline
also asks for a link to Unsplash itself; the credit text names Unsplash but
does not link it.

### 2026-09-24 - Review round 1 (bundled /code-review, PR #820): 5 repaired

- **Regression: a null photographer dropped the image.** The credit text is
  now built before the save, and `get_attribution_text` did
  `image_data.get("photographer", {}).get(...)`, which raises on
  `"photographer": null`. It now reads `or {}`. Tests (red with the old
  line): the text helper, and the command still saving the image.
- **Backend and web disagreed on credentialed URLs.** `safe_http_url` moved
  to `apps/core/utils/urls.py` (re-exported from `apps/blog/blocks.py`) and
  now rejects `user:pass@`, a missing host and `https:///x`, matching the
  web's `safeExternalUrl`. Red with the credentials check removed.
- `get_attribution_url` reuses `safe_http_url` instead of its own
  `startswith` check, so a hostless provider URL is never stored.
- **An overlong credit would break every later admin edit** (CharBlock
  max_length 255). The command truncates to `IMAGE_CREDIT_MAX_LENGTH`. Red
  with the slice removed.
- The `image_credit` help text tells editors to update or clear it when they
  change the image (the migration was regenerated for the help text;
  `makemigrations --check` is clean).
- Deferred to todo 438: backfilling credits for spotlight photos already in
  production (rebuildable from the `photographer:` tags), the command's
  bare `post.save()` (no revision, no cache invalidation, pre-existing), the
  three copies of the web URL check, and linking "Unsplash" itself.
