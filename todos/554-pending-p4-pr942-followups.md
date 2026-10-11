---
status: pending
priority: p4
issue_id: "554"
tags: [todo-sweep, follow-ups, backend, web]
dependencies: []
---

# Follow-ups from PR #942 (todos 433, 443, 516), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #942; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #942 (todos 433, 443, 516)

1. **`web/src/components/forum/PlantCareAskPanel.tsx:179`** (medium, defect). PlantCareAskPanel signed-in 401 branch: a signed-in 403 is untested, and a 401 during auth bootstrap latches 'Sign in' for a signed-in user. The only isAuthenticated:true case (test:216) is a 401, so deleting `err.status === 401 &&` at :179 leaves the suite green while a signed-in non-premium 403 would read 'Your session expired', never latch, and invite repeated failing asks. The anonymous-401 test's /sign in/i also matches SESSION\_EXPIRED ('Sign in again'). Pre-existing and narrowed by this PR: isAuthenticated is !!user, false while AuthProvider bootstraps in a tab with no sessionStorage user, so a 401 then latches SIGN\_IN; the identity-change reset clears the service latch but not the panel's useState(unavailable).
   Suggested: Add a signed-in 403 case (premium notice, Ask disabled, isPlantCareAskUnavailable() true) and tighten the anonymous-401 regex to /premium account to ask/i. For the bootstrap window, take isLoading from useAuth and treat a 401 while loading as session-expired, or re-derive unavailable from isPlantCareAskUnavailable() in an effect keyed on user?.id.
   Seen on main: PlantCareAskPanel.tsx:179 `err instanceof RagError && err.status === 401 && isAuthenticated`; test.tsx:216 is the only `isAuthenticated: true`, :184 403 case runs anonymous, :207 findByText(/sign in/i). AuthContext.tsx:163 isLoading starts true, :178-180 user seeded only from sessionStorage, :440 isAuthenticated: !!user.

2. **`web/src/components/forum/ThreadSummaryPanel.test.tsx:284`** (medium, defect). Three new todo-433 tests pass against the regressions they name: throttled-wait plural, unmount listener removal, Retry-After anchors. 'pluralizes the throttled wait' uses toHaveTextContent(string), a substring match: the pre-fix 'about 1 minutes' contains 'about 1 minute', and 90 s reads 'about 2 minutes' under both formulas, so reverting throttledMessage stays green. 'abandons a hidden-tab wait on unmount' passes with visibilityCleanupRef.current?.() deleted: the leaked listener settles on the dispatched event and the run exits at the token check, so fetchSummary stays at 1. retryAfter.test.ts negatives (absent, HTTP-date, no Headers) never put digits beside other text, so dropping ^ or $ from the regex survives.
   Suggested: Plural: add [45, /about 45 seconds\\./] (the old code says 'about 1 minutes') and anchor the rows on the period, e.g. /about 1 minute\\./. Unmount: vi.spyOn(document, 'removeEventListener') and assert a 'visibilitychange' removal at unmount, before the dispatch. readRetryAfter: add toBeNull cases '60s' (kills a dropped $) and 'x60' (kills a dropped ^).
   Seen on main: ThreadSummaryPanel.test.tsx:284-302 it.each([[60,'about 1 minute'],[90,'about 2 minutes']]) with toHaveTextContent(text); pre-fix `${Math.ceil(retryAfter / 60)} minutes` (64527318 diff). :327 asserts only fetchSummary calls; cleanup ThreadSummaryPanel.tsx:95, token return :157. retryAfter.ts:16 /^\\d+$/; negatives retryAfter.test.ts:17-26.

3. **`web/src/services/forumService.ts:891`** (medium, defect). Capability-latch wrapper-to-key mapping and the per-wrapper identity reset are not pinned by any test. forumService.test.ts has no latch cases, capabilityLatch.test.ts uses literal keys, and each consumer test reads its own wrappers self-consistently, so pointing the plant-care (or topic-summary) wrappers at 'composeAssist' stays green while a plant-care 403 would then hide the compose-assist button. AuthContext.test marks only the compose-assist and topic-summary latches before the identity change, so the plant-care latch (the anonymous 401 that signing in must clear) is never asserted through its wrapper.
   Suggested: In forumService.test.ts, per capability: mark via its wrapper, assert its own is\*() is true and the other two false, and that its reset\*() clears only its key. In AuthContext.test, mark all three latches via the wrappers (or iterate them) and assert each clears on identity change.
   Seen on main: forumService.ts:891/895/899 (plantCareAsk) and :983/987/991 (topicSummary) are one-line string-key calls; grep 'Unavailable|Availability' in forumService.test.ts finds nothing; AuthContext.test.tsx:52-56 marks compose assist and topic summary only, :67-68 asserts those two.

4. **`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py:452`** (low, defect). Stored alt is not a fixed point of the composer round trip at two edges, despite the docstring's 'no-op for every alt' claim. Truncation runs after strip, so a >255-char alt whose 255th char is whitespace is stored with a trailing space; the composer's .trim() drops it, so re-saving an untouched post PATCHes a changed alt\_text, the symptom todo 443 targeted. Python str.strip() also keeps U+FEFF, which JS trim() removes. Only direct API/CMS writes reach the length edge (the composer input has maxLength 255).
   Suggested: Use `alt.strip()[:MAX_ALT_TEXT_LENGTH].rstrip()`, optionally drop U+FEFF beside the NUL deletion, and add a test for 'x'\*254 + ' ' + 'y'\*10 asserting no trailing whitespace and that the stored alt equals its own re-normalisation; otherwise narrow the docstring (lines 433-434) to CR/CRLF/NUL.
   Seen on main: sanitize.py:452 `alt = alt.strip()[:MAX_ALT_TEXT_LENGTH]`; python: ('x'\*254+' '+'y'\*10).strip()[:255] ends with ' ', and a U+FEFF-edged string survives strip(); node trim() removes it. forumBody.ts:86 `(el.getAttribute('alt') ?? '').trim()`. TipTapEditor.tsx:872 maxLength={255}.

5. **`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py:572`** (low, defect). NUL is removed only from body image alts: other body text values and the upload alt still reach Postgres and 500. Pre-existing, same mechanism the 443 work log proved for alt (jsonb rejects U+0000, DataError, 500). heading, quote, code.code/language and post\_quote.text pass the str-only shape checks with NUL intact and land in the jsonb body; POST /forum/images/ stores \_alt\_text's value.strip()[:255] in Image.description, which psycopg2 refuses with NUL. Any authenticated writer gets a 500 instead of a 400. Traced, not reproduced end to end for these paths.
   Suggested: One shared normaliser: delete NUL (or 400 'Invalid post body.') for every str value in validate\_forum\_body, and run the alt normalisation (CRLF/CR to LF, drop NUL, strip, cap) in \_alt\_text too; add a NUL test per text block type and one on the upload endpoint.
   Seen on main: sanitize.py:557 `else isinstance(v, str)` and :572 `elif not isinstance(block_value, str)` only type-check; :451 is the package's only NUL replace. serializers.py:1074 body = serializers.JSONField(). views.py:1435 `return value.strip()[:255]`, :1520 description=\_alt\_text(request).

6. **`web/src/components/forum/ThreadSummaryPanel.tsx:176`** (low, defect). ThreadSummaryPanel state edges: 404 unmounts the button just clicked, TOO\_SHORT shows beside a ready summary, postCount lags new replies. The new 404 branch (like the 403) sets unavailable, which unmounts 'Summarize thread' and drops keyboard focus to \<body>; docs/rules/react.md:81-83 prefers mounted + disabled, and the 404 test pins absence. A disabled button still honours the owner's 404 'message only, no latch'. The TOO\_SHORT line has no outcome gate, so deleting a post after a summary shows both. The postCount doc says the page keeps it current as replies land, but at the end of a thread the poll only sets newReplyCount, so the button stays hidden until the pill is clicked. MIN\_POSTS mirrors SUMMARY\_MIN\_POSTS by comment only, no drift test.
   Suggested: Keep the button mounted and disabled when unavailable and assert toBeDisabled() in the 404 test. Gate the TOO\_SHORT line on !outcome. Pass postCount={totalPosts + newReplyCount + 1} from ThreadDetailPage, or reword the prop doc. Add a drift test (like apps/core/tests/\*\_drift.py) comparing const MIN\_POSTS with constants.SUMMARY\_MIN\_POSTS.
   Seen on main: ThreadSummaryPanel.tsx:176 setUnavailable(true) on 404; :198 `{!unavailable && !tooShort && (`; :214 `{tooShort && <p ...>{TOO_SHORT}</p>}`; :62 'keeps it current as replies land'; :42 MIN\_POSTS = 3 vs constants.py:302. test.tsx:276 not.toBeInTheDocument(). ThreadDetailPage.tsx:344-350 setTotalPosts only if nextCursorRef; :1140 postCount={totalPosts + 1}.

7. **`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py:435`** (low, polish). Todo-443 written record: literal NUL in the docstring, 'escaping cannot stop that' is wrong for CR, README silent on normalisation, todo 526 Scope misses files. The non-raw \_normalise\_image\_value docstring writes the u0000 escape, so \_\_doc\_\_ holds a real NUL. Line 429 says escaping cannot stop the parser's normalisation, but a numeric reference keeps CR; only NUL cannot survive, and todo 526 (lines 16-17, 28-29) repeats the premise. The package README's 'Alt text' section never mentions the CRLF/CR to LF and NUL deletion the API now applies, though 443 said to document it. Todo 526's Scope puts the data-image-id/data-decorative/data-post-id markers in TipTapEditor.tsx; they live in forumImageNode.ts and forumBlockquoteAttrs.ts.
   Suggested: Write U+0000 (or a doubled backslash) in the docstring; reword to 'no escape preserves NUL and CR means nothing in alt text, so normalise on write' in sanitize.py and todo 526; add a README 'Alt text' bullet on the write-time normalisation; add forumImageNode.ts, forumBlockquoteAttrs.ts and their tests to todo 526's Scope.
   Seen on main: sanitize.py:435 non-raw '``\\u0000``': ast.get\_docstring holds 1 NUL; :429 'Escaping cannot stop that'. jsdom: alt='a&#13;b' reads back a CR, &#0; gives U+FFFD, raw CR gives LF. README.md:358-403 has no normalisation text. data-\* marker grep hits forumImageNode.ts and forumBlockquoteAttrs.ts, none in TipTapEditor.tsx (todo 526:46-48).

8. **`web/src/services/forumService.ts:773`** (low, polish). Stale latch pointers after the registry refactor: forumService comment and testing.md still describe per-feature resets. The ComposeAssistError comment says the latch is cleared 'see resetComposeAssistAvailability's callers'; its only caller is now a test, and production clears through resetAllCapabilityLatches in AuthContext. web/docs/patterns/testing.md 'Session-Scoped API State' still teaches a per-feature `let` in forumService with no AuthContext reset, so following it adds a latch the reset-all never clears (the todo 275 bug).
   Suggested: Point the comment at resetAllCapabilityLatches (capabilityLatch.ts, called by AuthContext). Update the testing.md snippet: a new capability adds a CapabilityKey (plus named wrappers), and AuthContext's resetAllCapabilityLatches covers it.
   Seen on main: forumService.ts:773 '// clears the latch — see resetComposeAssistAvailability's callers).'; its only caller is TipTapEditor.test.tsx:75. AuthContext.tsx:227-229 useEffect(() => { resetAllCapabilityLatches(); }, [user?.id]). testing.md:331-335 `let composeAssistUnavailable = false;` plus the reset wrapper.

## Acceptance Criteria

- [ ] Each of its 8 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).
