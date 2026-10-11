---
status: pending
priority: p4
issue_id: "563"
tags: [todo-sweep, follow-ups, web, mobile]
dependencies: []
owner_decision: "Findings 1, 2 and 4, fix both: disambiguate repeated untitled embed names only on collision (append the provider or an ordinal); give untitled video cards the link card's full-URL affordances (web hover title plus an sr-only new-tab hint, mobile long-press sheet); mobile line 2 shows 'Open link' for web parity (2026-10-10) F1: make untitled embed names unique within one post body (the renderer's scope); no page-level state (2026-10-11)"
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #954 (todo 518), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #954; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #954 (todo 518)

1. **`web/src/components/StreamFieldRenderer.tsx:261`** (low, defect). Distinct untitled players on one host now share one iframe title. The iframe title is embedDisplay(...).title, so two untitled youtu.be players both read '`https://youtu.be/…`': split by a paragraph, a first card plus its expanded row (CompactCardRow renders the same embed case), or two posts on one thread page. Before, `title || url` kept them distinct. A screen reader's frame list cannot tell them apart, and no axe check runs anywhere in web/. Mobile full cards split by a non-card block share a semantics label too. A consequence of the owner decision that neither pattern doc records.
   Suggested: Owner call, keeping the short address as the base name: disambiguate only on collision (append the provider or an ordinal to repeated untitled names), or record the duplicate-name trade-off in react-typescript.md and flutter-patterns.md.
   Seen on main: StreamFieldRenderer.tsx:255 `const label = embedDisplay(block.value).title;`, :261 `title={label}`; the PR removed `const label = title || url;`. StreamFieldRenderer.test.tsx:155 pins '`https://youtu.be/…`'. CompactCardRow.tsx:73 `{renderFull()}`. forum\_body\_renderer.dart:471 label from \_embedTitle. No axe-core in web/ or its manifests.

2. **`web/src/components/StreamFieldRenderer.tsx:272`** (low, defect). Untitled video cards lost their only visible full URL, with no hover title or long-press to replace it. Before todo 518 an untitled card's first line was the full URL (web fallback card; mobile \_EmbedCard with a provider). Now it is the short address, and the full URL is reachable only by opening the card (web: the status bar). Link cards keep it reachable under the todo 428 owner decision: web title={href}, mobile long-press sheet plus 'Show full address'/'Copy link'. Titled video cards and video rows never had these. Linked to the mobile second-line item: blanking that line removes the last visible full URL, so decide both together.
   Suggested: Owner call, decided with the second-line item: add title={getSafeHref(url)} plus aria-describedby to an sr-only 'Opens in a new tab' hint on the fallback \<a> (docs/rules/react.md:313-318, or the URL is spoken again) and give \_EmbedCard the link card's onLongPress/customSemanticsActions; or record video cards as exempt in react-typescript.md and flutter-patterns.md.
   Seen on main: StreamFieldRenderer.tsx:272-276 fallback \<a> has href/target/rel/className, no title; :286 shows {label}. LinkPreviewCard.tsx:43-45 title={href}, aria-describedby={hintId}. forum\_body\_renderer.dart:460 label = \_embedTitle(url, title), no onLongPress in \_EmbedCard; link card has it at 571-575, rows only for links (720 isLink ? showAddress : null).

3. **`plant_community_mobile/docs/patterns/flutter-patterns.md:398`** (low, polish). Mobile docs name `_embedTitle` alone as embedDisplay's twin. embedDisplay returns title, detail and label; on mobile the detail and label come from \_embedRow. embedDisplay.ts names both helpers, but flutter-patterns.md and the \_embedTitle doc comment name only \_embedTitle.
   Suggested: Name `_embedTitle` / `_embedRow` as the twin of embedDisplay in flutter-patterns.md:398 and the \_embedTitle doc comment (forum\_body\_renderer.dart:812-813).
   Seen on main: flutter-patterns.md:398-399 'one rule, `_embedTitle`, whose web twin is `embedDisplay`'; forum\_body\_renderer.dart:812 'The web twin is `embedDisplay`'; embedDisplay.ts:26 'The Flutter twin is `_embedTitle` / `_embedRow`'.

4. **`plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart:521`** (low, polish). Mobile untitled no-provider video card shows its short address directly above the full URL; web shows 'Open link' and the pattern doc omits the divergence. Line 2 falls back to url when providerName is empty, so EmbedBlock(url: '`https://vimeo.com/77`') reads '`https://vimeo.com/…`' over '`https://vimeo.com/77`' (visible only, excludeSemantics). The Work Log frames this as a bare-URL embed from an older client, but embed\_envelope blanks title and provider for every embed without a fresh cache row and for all of them under FORUM\_EMBEDS\_ENABLED=False, so it is the common untitled case. flutter-patterns.md records the spoken divergence, not this visible one. Linked to the full-URL item: this line is now the card's only visible full URL.
   Suggested: Owner call, decided with the full-URL item: once the full URL has another home, show 'Open link' (web parity) or drop the line when providerName is empty and update forum\_body\_renderer\_test.dart:113; otherwise record the visible divergence in flutter-patterns.md beside the 'title Open link' note.
   Seen on main: forum\_body\_renderer.dart:519-521 `providerName.isNotEmpty ? 'Watch on $providerName' : url`; StreamFieldRenderer.tsx:288 'Open link'; embeds.py:273-279 `if not enabled: cached = None`, then provider\_name/title ""; forum\_body\_renderer\_test.dart:113 pins find.text('`https://vimeo.com/148751763`'); flutter-patterns.md:402-404 covers only the label.

5. **`web/src/components/StreamFieldRenderer.tsx:255`** (low, polish). Web embed naming nits: a local `label` holds embedDisplay's `title`, and the new `provider_name || ''` guard is dead and unpinned. EmbedDisplay.label is the row's 'title, provider' name, so a later tidy from `.title` to `.label` would put the provider into the iframe title and the fallback card's first line. embedDisplay.ts adds `|| ''` to a field typed string that embed\_envelope always sends as a string (the old CompactCardRow code was `detail = provider_name;`), and no test fails if it is removed.
   Suggested: Use `const { title } = embedDisplay(block.value)` and update its two uses (lines 261, 286); drop `|| ''` in embedDisplay.ts:32 or pin it with a nullish-provider case.
   Seen on main: StreamFieldRenderer.tsx:255 `const label = embedDisplay(block.value).title;`; embedDisplay.ts:15-16 label = "title, provider", :32 `const detail = value.provider_name || '';`; types/blog.ts:143 `provider_name: string;`; embeds.py:277 sends "" or the cached name; Wagtail Embed.provider\_name is TextField(blank=True), never null.

## Acceptance Criteria

- [ ] Each of its 5 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).
