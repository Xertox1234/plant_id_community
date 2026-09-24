---
status: completed
priority: p3
issue_id: "426"
tags: [forum, backend, embeds, spam]
dependencies: []
---

# Spam text extraction renders embed blocks through the provider

## Problem

`wagtail_forum/spam/base.py::extract_text` flattens a post body with
`str(getattr(block, "value", ""))`. For an `embed` block, the value is a
Wagtail `EmbedValue`, and `EmbedValue.__str__` returns `self.html`, which is
`embed_to_frontend_html(url)` → `get_embed(url)`.

- If the embed cache has a fresh row (the usual case, since
  `validate_forum_body` warms it at write time), this is one DB read and
  returns the provider's iframe HTML.
- If it does not (the warm-up timed out, or the provider failed), this is a
  **second provider fetch inside the request**. It happens during spam
  screening, bounded only by `TimeoutOEmbedFinder`'s timeout. That breaks
  the rule in `embeds.py` that the network is touched once, at write time,
  and bounded.
- The text screened is provider HTML, not what the author wrote.

This was already true for explicit embed blocks from the web composer
(todo 344). Todo 421 (server-side conversion) sends every mobile video link
down this path too.

## Findings

- The only callers are the spam backends (`spam/base.py`,
  `spam/heuristic.py`, and the host's LLM backend through `check_text`).
  Mention resolution does NOT use it: `mentions.py` has its own walker,
  `_mention_scan_text`, which reads `raw_data` and runs `strip_tags`.
- Hypothesis, not verified: the LLM spam backend receives the iframe HTML
  as part of its prompt text.

## Recommended Action

In `extract_text`, flatten an `embed` block as its URL
(`block.value.url`), never `str(block.value)`. Pin it with a test showing
that extracting text from a post with an embed block makes no finder call
(patch `wagtail.embeds.embeds.get_finder_for_embed` to raise) and includes
the URL.

## Acceptance Criteria

- [x] `extract_text` on a body with an `embed` block does not call the
      finder. Pinned by a test that fails before the change.
- [x] The URL is in the extracted text, so the link-count heuristic still
      counts it.

## Work Log

### 2026-09-24 - Filed while implementing todo 421

### 2026-09-24 - Done: embeds flatten to their URL

- `extract_text` (`wagtail_forum/spam/base.py`) now flattens an
  `EmbedValue` as `value.url`. It matches on the value type, not the block
  name, so any embed block in any body is covered.
- Test: `test_spam.py::test_extract_text_flattens_an_embed_to_its_url_without_the_finder`
  patches `wagtail.embeds.embeds.get_finder_for_embed` to raise. It failed
  before the change (`AssertionError: extract_text must not call an embed
  finder`) and passes after it. It also asserts the URL is in the text and
  no `<iframe` is.
- `pytest packages/wagtail_forum apps/forum_host --create-db`: 1494 passed.
- Not verified: the hypothesis that the LLM backend received the iframe HTML.
  It no longer can, since both backends read `extract_text`.
- Found on the way, not changed: `test_spam.py` fails 8 tests when run as a
  file on its own (`Database access not allowed`), because `get_setting`
  reaches `forum_host.forum_settings._load_values` on a cold memo. It passes
  inside the full suite, where an earlier DB test warms the memo.
