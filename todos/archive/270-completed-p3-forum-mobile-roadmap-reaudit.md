---
status: completed
priority: p3
issue_id: "270"
tags: [forum, docs, roadmap]
dependencies: []
---

# Full re-audit of PLANNING/20_FORUM_MOBILE_ROADMAP.md against current forum code

## Problem

`PLANNING/20_FORUM_MOBILE_ROADMAP.md` was recovered from months of git-invisibility in PR #467 (a `.gitignore` case-insensitivity bug had silently untracked it). A `/code-review` pass on that PR fixed 9 concrete issues — 7 stale file-path/line-number references and 2 sections wrongly describing shipped work (Phase 5.1 @Mentions, 5.2 Topic Following) as unbuilt — but the pass was targeted at what the review agents happened to flag, not an exhaustive re-validation. The doc still isn't fully trustworthy as current mobile-forum planning guidance.

## Findings

- PR #467 corrected 9 issues, each independently verified against the live repo (file existence, grep-confirmed line numbers, model/API existence). See `docs/LEARNINGS.md` "Repo Hygiene (2026-07-16 additions)" for the root-cause writeup.
- **Phase 1.4** (`PLANNING/20_FORUM_MOBILE_ROADMAP.md` §1.4, "ThreadDetailPage: Responsive Header"): `web/src/pages/forum/ThreadDetailPage.tsx:372` already renders the title as `text-xl sm:text-3xl`, matching the fix's specified responsive sizing. Not verified: whether the rest of the fix (vertical stacking, badge placement below title on mobile) is also done. Left as a "check before starting" hedge rather than a confirmed verdict.
- **Phase 2.2** (§2.2, "ThreadListPage: Infinite Scroll"): pagination already moved from the described "Previous / Page N / Next" buttons to a cursor-based `handleLoadMore` (`web/src/pages/forum/ThreadListPage.tsx:265`) — better than what's documented, but still a manual tap, not the IntersectionObserver-triggered auto-scroll the fix specifies. Partially done, not fully matching the original spec.
- **Phases 3 (Mobile-Native Interactions) and 4 (Performance & Offline)**: zero verification performed. Every "Problem"/"Fix" claim in these two phases is exactly as originally written May 23, 2026 and has not been checked against current code at all.
- The doc's own header note (added in PR #467) already discloses this limitation inline, so readers aren't misled — but the underlying gap is still open.

## Recommended Action

1. Read the current `ThreadDetailPage.tsx`, `ThreadListPage.tsx`, `PostCard.tsx`, `TipTapEditor.tsx`, and `SearchPage.tsx` in full.
2. For each Phase 1–4 "Problem" statement, check it against actual current behavior/code and mark it explicitly: shipped / partially shipped / still open — same style already used for Phase 5.1/5.2 (strikethrough problem + "Done:" evidence, or leave as-is if genuinely still open).
3. Resolve the two existing hedge notes (Phase 1.4, 2.2) to a definitive status instead of "check before starting."
4. Sweep the rest of the doc (Phase 3, 4, Testing Strategy, Flutter Translation Notes, Acceptance Criteria, Dependencies & Risks) for any other file-path/line-number citations and confirm each resolves to a real location.
5. Update the doc's header "Corrected" note to reflect the full audit date once done.

## Technical Details

- File under audit: `PLANNING/20_FORUM_MOBILE_ROADMAP.md` (479 lines as of PR #467).
- Related forum frontend files: `web/src/pages/forum/*.tsx`, `web/src/components/forum/*.tsx`, `web/src/services/forumService.ts`.
- Context on what's already shipped from the todo 253 notifications epic: mentions (`wagtail_forum/mentions.py`, slice 4), topic subscriptions (`wagtail_forum/models/subscriptions.py`, slice 3) — both already reflected correctly in the doc as of PR #467.

## Acceptance Criteria

- [x] Every Phase 1–4 "Problem" statement in the doc has been checked against current code and marked shipped / partially shipped / still open
- [x] Phase 1.4 and 2.2 hedge notes resolved to a definitive status
- [x] No remaining file-path or line-number citation in the doc that fails to resolve to a real location
- [x] Header "Corrected" note updated to reflect the completed full audit

## Notes

Priority p3: this is documentation-accuracy hardening on a planning doc, not a functional bug or blocker — nothing currently depends on this doc being fully current. Bumped above pure backlog-filler because a stale "unbuilt" claim in planning docs has already caused real confusion once (Phase 5.1/5.2 in this same file), so the risk is real, just not urgent.

## Work Log

### 2026-07-29 - Started by completing-todos skill (run 2026-07-29-0248)

- Picked up by automated workflow. Branch `todo/270-forum-mobile-roadmap-reaudit`.

### 2026-07-29 - Full re-audit performed

Read in full: `PostCard.tsx` (339 L), `ThreadListPage.tsx` (293 L), `ThreadDetailPage.tsx`
(715 L), `TipTapEditor.tsx` (356 L), `SearchPage.tsx` (495 L), plus
`StreamFieldRenderer.tsx`, `forumDrafts.ts`, `forumService.ts`, `forum-responsive.spec.ts`
and `wagtail_forum/api/serializers.py`.

**Verdicts — all 19 Phase 1–4 sub-phases** (4 ✅ shipped, 3 🟡 partially shipped, 12 ⬜ still open).
Tally re-derived from the doc's own headings rather than counted by hand — the first
write of this line said "18 (5/3/10)", which the 19-row table below already contradicted:

| Phase | Verdict | Basis |
|-------|---------|-------|
| 1.1 Hover→overflow menu | ✅ shipped (differently) | no `onMouseEnter` in `PostCard.tsx`; actions `md:opacity-0 md:group-hover/focus-within` = always visible < `md`; the `⋯` menu itself was never built |
| 1.2 Interactive reactions | ✅ shipped | `onReact` + `aria-pressed` + `+🙂` picker; via `toggleReaction`, not `addReaction`/`removeReaction`; post-response not optimistic |
| 1.3 Collapsible toolbar | ✅ shipped (differently) | 7 buttons + `flex-wrap` + 44px targets; grouping dropdowns never built, most grouped buttons deleted (nh3 allowlist) |
| 1.4 Responsive header | 🟡 partial | title `text-xl sm:text-3xl` ✅; container is `flex items-start flex-wrap`, **not** `flex-col sm:flex-row` |
| 1.5 Breadcrumb collapse | ⬜ open | both trails full, `flex items-center gap-2`, no mobile variant |
| 2.1 Stacked toolbar | 🟡 partial | `flex-col sm:flex-row` ✅; `max-w-md` still unconditional, sort not full-width |
| 2.2 Thread infinite scroll | ⬜ open | manual `handleLoadMore`; zero `IntersectionObserver` in `web/src/` outside the jsdom mock |
| 2.3 Post infinite scroll | ⬜ open | manual button; deep-link chase is anchor- not scroll-driven |
| 2.4 Reply FAB | ⬜ open | no FAB, composer static at page end |
| 2.5 Search overlay | ⬜ open | plain page, no `autoFocus`, no recent searches |
| 3.1 Pull-to-refresh | ⬜ open | no `touchstart`/`touchmove`/library |
| 3.2 Quote/reply | ⬜ open | no `quoted_post`/`parent_post` in `wagtail_forum`, no UI |
| 3.3 Action sheet | 🟡 partial | copy-link/report/edit/delete all ship inline; **no** Web Share, no sheet |
| 3.4 Sticky composer | ⬜ open | no `visualViewport` anywhere |
| 3.5 Lightbox | ⬜ open | no lightbox/gallery/pinch code |
| 4.1 Skeletons | ⬜ open | forum lists all still `LoadingSpinner` |
| 4.2 Draft persistence | ✅ shipped | `forumDrafts.ts` in both composers; `sessionStorage` + key `forum-draft:{kind}:{id}`, saves every change, no restore prompt |
| 4.3 Offline queue | ⬜ open | no IndexedDB, no `online` listener |
| 4.4 Image optimization | ⬜ open | no `loading`/`decoding`/`srcset`; **premise false**, see below |

**Two false premises corrected** (these misdirect implementers, unlike stale line numbers):

1. **Phase 4.4** claimed "Backend already generates `thumbnail`, `large_thumbnail`, and
   original." False. `serialize_image_for_api`
   (`backend/packages/wagtail_forum/wagtail_forum/api/serializers.py:254-271`) returns
   exactly one `max-1200x1200` rendition as `{id, url, alt, width, height}`. The
   "thumbnail for grid / large_thumbnail for lightbox" fix was unbuildable as written;
   rewrote it as backend-first work, flagging the N+1 risk to `build_forum_image_map`.
2. **Phase 2.2** claimed "`fetchThreads` already supports `page` and `limit` — no backend
   changes." False. Real signature is `{ board, cursor, sort }`; `page` survives only as
   an explicitly-ignored legacy field (`forumService.ts:116-141`).

**Verification — AC1/AC2/AC4**: `git diff` on `PLANNING/20_FORUM_MOBILE_ROADMAP.md` shows
every Phase 1–4 heading carries a ✅/🟡/⬜ marker, the 1.4 and 2.2 hedges are replaced with
"revised Jul 29, 2026 — this supersedes the … hedge" verdicts, and the header carries a
new **Fully re-audited** line.

**Verification — AC3** (mechanical, not a reading pass). Wrote a resolver that extracts
every `@/path`, `path:NNN` and bare-basename citation from the doc, resolves it (including
the `wagtail_forum/` src-layout indirection), and prints the actual cited line:

```text
OK    web/src/pages/forum/ThreadListPage.tsx:133 -> 'const handleLoadMore = useCallback(async () => {'
OK    web/src/components/forum/TipTapEditor.tsx:167 -> '<div className="bg-surface border-b border-line-2 p-2 flex gap-1 flex-wrap">'
OK    ThreadDetailPage.tsx:522 -> '<h1 className="text-xl sm:text-3xl font-bold text-ink mb-2">{thread.title}</h1>'
OK    backend/.../api/serializers.py:254-271 -> 'def serialize_image_for_api(image, request=None):'
OK    backend/apps/core/services/notification_service.py:411 -> 'def send_forum_mention_notification('

--- 72 citations resolved, 0 failures ---
verify_citations exit code: 0
```

The first pass surfaced 3 real problems, all fixed before the clean run: `PostCard.tsx:58-59`,
`PostCard.tsx:135-151` and `TipTapEditor.tsx:74` still carried live line numbers inside
struck-through *historical* problem statements, and now point at unrelated code (an empty
line, a `useState`, an extension import). Reworded to "(lines 58-59 *as of May 2026*)" so
they read as history rather than as current pointers.

Anti-rot measure: every new citation names a nearby anchor (a function name or a JSX
comment such as `{/* Toolbar */}`) alongside the line number, since this doc has now rotted
its line numbers twice and PR #467's fix lasted ~2 weeks.

**Also swept** (beyond the four ACs, because leaving them stale would defeat the purpose):
Current State table (7 of 12 rows were flatly wrong — reactions, edit/delete, toolbar,
search, thread list/detail, infinite scroll), the doc's own Acceptance Criteria checkboxes
(3 flipped to `[x]` with named evidence; the 320px one stays `[ ]` and is explicitly marked
*unproven, not failed* — E2E covers 375/768/1280 only), Testing Strategy (mobile-viewport
tests already exist in `forum-responsive.spec.ts`), and Dependencies & Risks (added the
single-rendition blocker; corrected the E2E row to say specs *exist* but pass/fail is
unverified since Playwright is excluded from CI).

Scope note: E2E was **not** executed — this is a p3 doc audit, and the doc now states
plainly that existence ≠ passing rather than implying a green run.

### 2026-07-29 - Code review + repair

`code-review-orchestrator` routed to **zero** domain reviewers (docs-only diff; the routing
table covers source files) and correctly declined to invent findings.

Because the real risk here is a *wrong verdict*, not code quality, an adversarial
fact-checker independently re-verified all 18 phase verdicts and both premise corrections
against source. It **confirmed 11/11** claim groups — and refuted two things, both
independently re-verified by me before repair:

**Repair 1 — Phase 5.1 credited dead code (inherited from PR #467, high value).**
The line credited `send_forum_mention_notification`
(`backend/apps/core/services/notification_service.py:411`). The citation *resolves* — it is
the method definition — but the method has **zero call sites** repo-wide:

```text
$ grep -rn "send_forum_mention_notification" --include="*.py" . | grep -v "def send_"
NONE — definition only, zero call sites
```

The shipped mention path is `resolve_mentioned_users` (`wagtail_forum/mentions.py:64`) →
`create_notifications(…, verb=NotificationVerb.MENTION)` (`wagtail_forum/notifications.py:17`),
called from `apps/forum_host/notifications.py:193` and `:82`. Doc re-pointed, with a note
explaining that this is precisely the failure a resolves-to-a-real-line check cannot catch:
**the citation was valid, the claim around it was not.**

**Repair 2 — I overclaimed E2E coverage for the 1.3 acceptance criterion.**
I wrote that the 375px no-overflow assertion "covers the pages that host" the TipTap
toolbar. It does not. The authenticated Playwright projects match `.js` specs only
(`testMatch: /(forum-authenticated|auth)\.spec\.js/`, `web/playwright.config.ts:134`), so
the `.ts` responsive spec always runs **signed-out**, and an anonymous visitor gets the
"Log in to post a reply" box instead of the composer (`ThreadDetailPage.tsx:656`) — the
toolbar is never in the DOM. Re-worded the criterion to cite the markup as its evidence,
and added the auth/spec-extension coverage gap as a second E2E caveat in Testing Strategy,
since it silently limits every future mobile spec.

Two nits also folded in: "explicitly destructured away" → the legacy fields are simply
never destructured; and the CI command is `npm run test -- --run`, not `vitest --run`.

Re-ran the citation resolver after the repairs (new citations were introduced):

```text
OK    wagtail_forum/mentions.py:64 -> 'def resolve_mentioned_users(post, *, exclude_pks=()):'
OK    wagtail_forum/notifications.py:17 -> 'def create_notifications('
OK    backend/apps/forum_host/notifications.py:193 -> 'create_notifications('
OK    web/playwright.config.ts:134 -> 'testMatch: /(forum-authenticated|auth)\.spec\.js/,'
OK    web/src/pages/forum/ThreadDetailPage.tsx:656 -> ') : !isAuthenticated ? ('

--- 76 citations resolved, 0 failures ---
EXIT: 0
```

No blocking (critical/high) findings remained. No `Known issues` outstanding.

### 2026-07-29 - Completed by completing-todos skill (run 2026-07-29-0248)

- Verification: all 4 acceptance criteria passed; AC3 proven mechanically (76 citations, 0 failures, exit 0).
- Review: orchestrator returned no applicable reviewers (docs-only); adversarial fact-check confirmed 11/11 verdicts and surfaced 2 findings, both repaired.
