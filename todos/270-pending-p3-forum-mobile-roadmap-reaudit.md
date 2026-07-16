---
status: pending
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

- [ ] Every Phase 1–4 "Problem" statement in the doc has been checked against current code and marked shipped / partially shipped / still open
- [ ] Phase 1.4 and 2.2 hedge notes resolved to a definitive status
- [ ] No remaining file-path or line-number citation in the doc that fails to resolve to a real location
- [ ] Header "Corrected" note updated to reflect the completed full audit

## Notes

Priority p3: this is documentation-accuracy hardening on a planning doc, not a functional bug or blocker — nothing currently depends on this doc being fully current. Bumped above pure backlog-filler because a stale "unbuilt" claim in planning docs has already caused real confusion once (Phase 5.1/5.2 in this same file), so the risk is real, just not urgent.
