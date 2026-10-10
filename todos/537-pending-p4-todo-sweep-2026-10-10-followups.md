---
status: pending
priority: p4
issue_id: "537"
tags: [todo-sweep, follow-ups]
dependencies: []
triage: blocked-owner
triaged: 2026-10-10
blocked_on: "Owner picks which findings to fix now, which to promote to their own todos, and which to close (prod row count goes to 536, engine items go to the engine batch)."
owner_decision: "Slice: fix the backend mail-gate group (#976 findings 1-5) now; promote the web composer (#977) and link-preview (#978) groups to their own todos; move #979-2 (prod row count) to 536 and the engine items to 529 (2026-10-10)"
---

# Todo sweep run 2026-10-10-0234: follow-ups from 4 merged PRs

## Problem

Todo-sweep run 2026-10-10-0234 merged four PRs: #976 (todos 454, 533), #977 (526), #978 (535) and #979 (532).
Their review rounds reported non-blocking findings. As in run 2026-10-02-0335, the owner chose one consolidated
follow-up todo for the whole run (2026-10-10). Duplicate reports are merged below, and no finding was refuted.
Line numbers are as of the merge, so re-check each finding against main before acting on it.

## Findings

### PR #976 (todos 454, 533): mail deprecation gate

1. **`backend/apps/core/checks.py:41`** (medium, defect). `core.E364` false positive: when an SMTP subclass is
   set via `EMAIL_BACKEND` with empty credentials (a no-auth relay), its OPTIONS carry `username=""`/`password=""`.
   The rebuild gives `None`, so `("", "") != (None, None)` and the check fails `manage.py check`/`migrate` and the
   deploy, even though SMTP `open()` logs in only when both are truthy. Prod is unaffected: the owner confirmed
   prod's `EMAIL_BACKEND` is Django's SMTP backend.
   Suggested: compare `(x or None)` per field, or fail only when the backend has credentials. Add a test for an
   empty-credential subclass. Reported by 5 reviewers across both rounds.
2. **`backend/apps/core/checks.py:30`** (low). The rebuild omits the `_ignore_unknown_kwargs` that
   `MailersHandler.create_connection` passes. A subclass whose `__init__` rejects `alias`/`username` raises, and the
   broad `except` misreports it as "cannot be built". Suggested: match the handler's kwargs and build in its own
   `try` with a distinct message.
3. **`backend/apps/core/services/notification_service.py:118`** (medium, gap). `send_notification` and
   `_schedule_notification` (around l.231) still wrap the send in `except Exception`, so forum reply/mention and
   ID-result mail swallow a planted deprecation. The owner scoped 454 to five sites, so this is not a regression.
   Suggested: add `except Warning: raise` and a gate test driven through `send_forum_reply_notification`.
4. **`backend/packages/wagtail_forum/wagtail_forum/digest.py:229`, `backend/apps/blog/newsletter.py:210`** (low).
   The docstrings still say "never raises". On a re-raised Warning, `send_forum_digest` does not restore
   `last_digest_sent_at`, and `request_confirmation` does not roll back `confirmation_sent_at`. Only reachable under
   the pytest warning filter. Suggested: fix the docstrings, and optionally restore the claim in
   `except BaseException`, as `send_blog_newsletter._send_one` does.
5. **`backend/apps/core/tests/test_mail_call_sites_deprecation_gate.py:56`** (low). The name
   `test_the_planted_argument_is_deprecated_and_still_delivers` claims delivery, but the test only asserts the
   warning. Rename it, or add a delivery case with the warning ignored.

### PR #977 (todo 526): composer TipTap JSON

1. **`web/src/pages/forum/ThreadDetailPage.tsx:919`** (medium, pre-existing). An untouched re-save still PATCHes
   when a body ends in an image, quote, list or heading. StarterKit v3's TrailingNode appends an empty paragraph on
   the first transaction, `docToBodyBlocks` emits `<p></p>`, and `isUnchangedBody` is false. Suggested: drop
   trailing empty paragraph blocks before comparing, and test against a real editor after a selection transaction.
2. **Tests** (low). The page test for the untouched-save case is tautological, since the stubbed editor never fires
   `onChange`. `forumBody.test.ts` `throughEditor` dispatches no transaction and uses `FORUM_SCHEMA_EXTENSIONS`,
   not the live extension set (mention suggestion + Placeholder). Suggested: mount the real `TipTapEditor` and
   assert `isUnchangedBody(editor.getJSON(), stored)`.
3. **`web/src/utils/forumBody.ts:134` `toComposerDoc`** (low). A JSON draft that fails the schema `check()` becomes
   `emptyDoc()` with no signal, and NewThreadPage's persist effect then overwrites the stored draft. A future schema
   change would silently delete drafts. Suggested: salvage the text nodes into paragraphs, or log and leave the
   stored draft untouched until the user edits.
4. **`web/src/pages/forum/ThreadDetailPage.tsx:621` `handleQuote`** (low, pre-existing). `isBlankDoc` treats an
   image-only reply as blank, so quoting drops the image already in the reply.
5. **Layering and perf** (low). `ForumBodyWriteBlock` lives in `utils/forumBody.ts` while `types/forum.ts`
   imports it; move it into `types`. `utils/forumBody.ts` imports `components/forum/forumEditorSchema`.
   `isBlankDoc` serialises the whole doc several times per keystroke; memoise or scan cheaply.
6. **Docs** (low). `.claude/agents/{wagtail,react-typescript}-reviewer.md` still name the removed helpers
   (`bodyBlocksToHtml`, `htmlToBodyBlocks`, …); the worker's sandbox denied that edit.

### PR #978 (todo 535): link-preview follow-ups

1. **`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py:377/820`** (low, perf). `_stored_without_cards`
   runs `autolink_rich_text` on every rich-text block before the fetch, and the cleaned loop repeats it. With the
   200k raw ceiling, worst-case sanitize CPU per write rises roughly 2–4x. Suggested: autolink once and reuse.
2. **`sanitize.py:590/826`** (low). The pre-fetch check measures a resent card as an auto-linked paragraph, not as
   its URL. A near-cap body stored under the old rule, or whose card came from a bare-URL paragraph (mobile sends
   no `<p>`), can 400 when resent unchanged. Suggested: measure resent cards as their URL in the pre-fetch check.
3. **`sanitize.py:562/827`** (low). The "a refused body costs no fetch" claim has two holes. Legacy bare-PK image
   normalisation is not applied in `_stored_without_cards`. Video oEmbed `warm_embeds` runs before the pre-fetch
   check. Suggested: normalise images there, and move the check before the embed conversion.
4. **`sanitize.py:511` `_ANCHOR_START_TAG`** (low, unverified). The pattern ends at the first `>`, so a raw `>` in an
   href (if nh3 leaves one) skips the target/rel discount. Suggested: use an attribute-aware pattern and add a test.
5. **`backend/apps/forum_host/link_preview.py:463`** (low). Any `InvalidPreviewURL` on a redirect hop is relabelled
   `deadline` once the deadline has passed, including a private-IP or bad-port refusal whose lookup finished late.
   It then goes uncached. Suggested: flag the timed-out lookup itself rather than checking the clock.
6. **`backend/packages/wagtail_forum/wagtail_forum/link_previews.py:731` `log_host`** (low). A printable host with
   spaces or `=` passes through unquoted, so a rejected URL can fake `key=value` text in a log line. Suggested:
   pass a host through unquoted only when it matches a hostname/IP charset, and `repr()` it otherwise.
7. **Timing tests** (medium, flake risk). `test_link_preview.py:361` and `test_link_preview_images.py:477` use real
   sleeps against `elapsed < 0.9`, with ~0.1–0.3 s of slack. `test_link_previews.py:932` depends on thread
   scheduling. `test_link_preview.py:335` imports the private `_loopback_drip` from a sibling test module.
   Suggested: widen the margins or assert the socket timeout passed, use an Event handshake, and move the helper to
   a conftest.

### PR #979 (todo 532): DemoData drop

1. **`todos/archive/532-completed-p4-delete-unused-demodata-model.md`** (low, record). The ticked criterion
   "Table dropped in a later PR" and the re-pointed "State-only removal shipped and deployed" describe an
   expand/contract sequence that did not happen: one DeleteModel shipped, by owner decision. A note in the archive
   would make the record accurate.
2. **No prod row count before `DROP TABLE users_demodata`** (low). Recording the count in todo 536 alongside the
   deploy confirmation would close the "nothing reads it" claim on the data side too. Owner-only (prod).
   The deploy-window FK risk (`created_by` SET_NULL) was owner-accepted and is documented in 0018 and todo 536.

### Sweep engine (for the deferred engine batch)

1. **Workers stop with a tree that fails pre-commit** (low). On g4 (#978) the verified tree hit Black (one line
   join) and detect-secrets (a fake `?token=` test URL). `ensure-worktree` tolerates only the
   trailing-whitespace/EOF fixers, so Land had to hand-patch with owner approval and re-record `tree_id`.
   Suggested: have the worker run `pre-commit run --files <staged>` before stopping, or add Black's reformat to
   the tolerated fixers.
2. **Triage missed an FK** (low). Triage for 532 said "the model has no FK", but `created_by` was an FK to `User`,
   and the worker caught it. Suggested: the triager prompt should check `ForeignKey`/`on_delete` on any model
   being deleted.
3. **Follow-up lists are capped at 10 per todo, and a group's shared findings are copied to each of its todos**
   (low). This adds to todo 529's ranking item.

## Promotions (2026-10-10, owner decision)

- #976 1–5: fixed in this todo.
- #977 1–6: promoted → todo 538.
- #978 1–7: promoted → todo 539.
- #979 1: fixed in this todo (record note in the archived 532).
- #979 2: promoted → todo 536 (owner-only, prod).
- Sweep engine 1–2: promoted → todo 540. Engine 3: promoted → todo 529.

## Acceptance Criteria

- [ ] Each finding above is fixed, or closed with a dated reason, or promoted to its own todo.

## Work Log
