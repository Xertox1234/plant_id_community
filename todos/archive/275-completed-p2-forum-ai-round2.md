---
status: completed
priority: p2
issue_id: "275"
tags: [forum, ai, premium, wagtail-ai, rag]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M12, M13, M14"
---

# Forum AI features, round 2: semantic search upgrade, composer assist, RAG

## Problem

Todo 255 (forum AI & premium epic) shipped the H15 pgvector "similar topics"
infra: `django_ai_core.contrib.index` is now active (INSTALLED_APPS + the
`CREATE EXTENSION vector` migration), a `SimilarTopics` `VectorIndex` over forum
topics, an OpenAI embedder, and a `find_similar_topics()` helper — all behind
`FORUM_VECTOR_SEARCH_ENABLED`. Three findings from the 2026-07-11 audit were
bundled into 255 but fell OUTSIDE its acceptance criteria (M12/M14 deferred; M13
explicitly gated to stay unstarted until H15 landed). H15 has now landed, so all
three are unblocked.

## Findings (carried from 255)

- **M12 — Semantic search upgrade (premium):** a marginal add now that the H15
  infra exists. `SimilarTopics.search_documents()` is generic; blend semantic
  hits into the existing forum `SearchView` (already Postgres FTS with ranking,
  per H22) so the value-add is synonym/meaning matching. Premium-gated per audit.
- **M14 — AI-assisted composer (draft improvement):** wagtail-ai's editor
  machinery is admin-only, so only the backend `generate_ai_text` substrate
  applies → a bespoke host endpoint + a TipTap toolbar action in `web`. Least
  favorable cost profile (interactive, uncacheable) — throttle + gate.
- **M13 — RAG plant-care answers grounded in the site's plant-ID + blog data:**
  the long-horizon big bet; a strict superset of the H15 infra (which now
  exists). Needs citation UX + hallucination guardrails (plant-care advice has
  real-world consequences). Own design round; do it LAST.

## Recommended Action

1. **Before enabling any of these in prod:** land the todo-255 slice-4
   pre-enablement follow-up — a **dedicated embedding budget** (separate from the
   shared `ai_rate_limit:global` completion counter) so query embeddings can't
   run up unbounded cost. Applies to M12 and M13 too (both embed queries).
2. **M12** first (thinnest): reuse `find_similar_topics`/`search_documents`.
3. **M14** (bespoke endpoint + web TipTap action).
4. **M13** RAG last, with its own design round + guardrails.

## Acceptance Criteria

- [x] M12 semantic search upgrade shipped (premium-gated) or descoped w/ rationale
- [x] M14 composer-assist endpoint + web toolbar action, throttled + gated
- [x] M13 RAG: own design round completed; shipped with citations + hallucination
      guardrails, or explicitly descoped with rationale
- [x] Dedicated embedding budget in place before any of these is enabled in prod

## Work Log

### 2026-07-29 - Started by completing-todos skill (run 2026-07-29-2306)

- Picked up by automated workflow.

### 2026-07-29 - AC4 first: dedicated query-embedding budget

Implemented ahead of M12/M14 because the todo's own Recommended Action makes it
the pre-enablement gate for both.

- `constants.EMBED_BUDGET_CACHE_KEY` (`ai_rate_limit:forum_embed`) +
  `EMBED_BUDGET_LIMIT` (1000/hr), sized in a comment against the 500-char query
  cap and the existing per-IP throttles.
- Wired **inside `find_similar_topics()`**, not at the call sites, so every
  embedding caller inherits it — the similar-topics endpoint, M12's search
  section, and any future RAG retrieval. Peek-then-consume, so a provider outage
  cannot drain the cap through failed attempts.
- Import of `AIRateLimiter` deliberately deferred into the function body: this
  module is imported at `AppConfig.ready()` under a documented import-safety
  contract.

### 2026-07-29 - AC1 (M12): premium semantic section on forum search

- New `apps/forum_host/semantic_search.py` — `SemanticSearchMixin`, composed
  ahead of the package `SearchView` in `apps/forum_host/api.py` so `_throttled`
  still wraps the resolved `get` (a `get()` override on the throttled subclass
  would silently drop the throttle; pinned by a test).
- Opt-in via `?semantic=1`; **absent → the response is byte-identical to before**,
  so no existing client or CDN entry is affected and no embedding is spent for
  callers who did not ask.
- **Separate `semantic` array rather than interleaving into `topics`** — the FTS
  list is offset-paged over keyword rank and vector distance is not commensurable
  with it, so merging would make `page`/`*_has_more` describe a window that no
  longer exists. Rationale recorded in the module docstring since the audit's
  wording ("blend") invites the other reading.
- `semantic_status` is `ok` / `premium_required` / `unavailable` — deliberately
  does **not** distinguish "budget exhausted" (that is a silent quality degrade
  by design; surfacing cost state invites probing).
- **Scope note:** AC1 says "shipped (premium-gated)" and, unlike AC2, does not
  name a web surface — so this is backend + OpenAPI + tests. Wiring the section
  into the web `SearchPage` is a separate, additive UI task and was not done here.

### 2026-07-29 - AC2 (M14): composer assist, dormant behind a flag

- New `apps/forum_host/compose_assist.py` — `POST /api/v1/forum/compose/assist/`,
  bounded four independent ways: `FORUM_COMPOSE_ASSIST_ENABLED` (default **off**
  → 503), `IsPremiumUser`, the per-user `compose_assist` throttle (20/h), and the
  forum-wide `COMPOSE_BUDGET_LIMIT` (200/hr, own counter).
- Ships **inert**, matching every other AI feature here. Without the flag this
  would have been the only AI feature that starts spending the moment it merges —
  which is exactly what AC4's "before any of these is enabled in prod" guards.
- Draft HTML is flattened before the provider sees it; the prompt frames the draft
  as untrusted data and contracts for plain text out.
- Route added to `api_urls.py` **and** to `HOST_ONLY_ROUTES` in
  `tests/test_ratelimits.py` in the same change (the route-drift parity guard).
- Web: `improveDraft()` + `ComposeAssistError` in `forumService.ts`, and a ✨
  toolbar action in `TipTapEditor.tsx`. The rewrite is inserted as **paragraph
  nodes with text content**, never `insertContent(htmlString)` — a model-emitted
  tag must not become document structure in a post the user then publishes
  (test-pinned). One chain → one undo step, so Ctrl+Z restores the draft.
- 403/503 latch the button hidden (never succeeds for this account/deployment);
  429 keeps it (transient). Web has no premium signal in its auth shape, so the
  reason is surfaced from the server response rather than pre-gated.

### 2026-07-29 - AC3 (M13): design round done, implementation descoped

- Design: `docs/superpowers/specs/2026-07-29-forum-rag-plant-care-design.md` —
  corpora/indexes, chunking with citation anchors, retrieval with a similarity
  floor, grounded generation, five guardrail layers, cost model.
- **Correction to the audit's framing recorded there:** M13 said "plant-ID data",
  but per-user identification records are diagnostic artifacts never submitted for
  publication, and no forum-visibility predicate covers that boundary. The corpus
  is species-level reference text, staff-curated — not user identifications.
- **Implementation explicitly descoped** (AC3 permits it) for three reasons:
  the corpus is near-empty and RAG's whole value is grounding in it; its own
  prerequisite (H15) is still dormant in prod with no built index; and guardrail 5
  (the wrong-answer review loop) has no owner, which makes guardrails 1–4
  unfalsifiable in production.
- Execution carried by **todo 289** with four objective enablement gates. Per
  CLAUDE.md the audit's `#M13` stays `- [ ]` and is re-pointed there — `- [x]`
  means shipped — so the audit doc is deliberately **not** renamed `-COMPLETED`.

### 2026-07-29 - Incidental find, filed not fixed: todo 290

Writing the M12 truncation test surfaced a **pre-existing** 500 on the public
search endpoint, isolated with a throwaway probe (deleted) that used no semantic
param at all:

```
500-term plain search (no semantic param) -> 500   # RecursionError
100-term plain search                     -> 200
single 3500-char term                     -> 200
```

Term count, not length. Filed as **todo 290** (p2) rather than fixed here: it is
the FTS path, unrelated to AI round 2, and the fix changes a public package
endpoint's behaviour (truncate vs 400) which deserves its own decision. The M12
test uses one long token specifically to avoid it, with a comment saying why.

### 2026-07-29 - Code review (3 reviewers) + repair

`django-drf-reviewer`, `react-typescript-reviewer` and `cross-cutting-reviewer` on
the staged diff: **15 findings (1 high, 8 medium, 6 low)**. All verified against the
code before acting; 14 repaired, 1 accepted.

**High — `strip_tags` fuses text across block boundaries.** Confirmed
independently before fixing:

```
'<p>Line one</p><p>Line two</p>' -> 'Line oneLine two'
'<ul><li>a</li><li>b</li></ul>'  -> 'ab'
'<p>&nbsp;</p>'                  -> '&nbsp;'      # truthy → bought an LLM call
'<p>Tom &amp; Jerry</p>'         -> 'Tom &amp; Jerry'
```

`strip_tags` substitutes *nothing* for a tag, so every multi-paragraph draft — the
normal case — reached the model with words welded together. Every test fixture used
a single `<p>`, so nothing caught it. Fixed by substituting block boundaries with
newlines before stripping, plus `html.unescape`, which also fixes the
`&nbsp;`-only draft and stops `&amp;` reaching the published post literally.

**Medium, repaired:**

- An empty completion returned 503 *before* charging the budget — it reached the
  provider and was billed, so a provider stuck emitting blanks could be called
  indefinitely without tripping the forum-wide cap. Now charged on any provider
  *return*, matching `find_similar_topics`; only the exception path stays free.
- No result cache on the M12 path, so a premium client paging `?semantic=1`
  re-embedded the identical query per page — and `EMBED_BUDGET_LIMIT`'s sizing
  comment cited a cache that only the sibling endpoint had. Added a pk cache
  *inside* `find_similar_topics` (visibility refetch still always runs, so a
  board restricted after the cache write still cannot leak); comment corrected.
- The query length cap was duplicated at both call sites while the helper claimed
  to be the single entry point — a future caller (M13) routing through the helper
  per the design doc would have inherited the budget but not the cap, invalidating
  its cost math. Moved into `find_similar_topics`, deleted from both callers.
- `test_schema_429.py::THROTTLED_OPERATIONS` was missing the new route — the exact
  precedent followed for the two prior AI endpoints. (`HOST_ONLY_ROUTES` was
  updated; this sibling list was not.)
- The web unavailability latch was component state, but `ThreadDetailPage`
  remounts the composer (`key={composerKey}`) after every reply — so the
  "never left clicking a dead button" claim was false from the second reply on.
  Moved to a session-scoped latch in the service, written by the component's
  single `permanent` branch.
- Two coverage gaps: nothing exercised the multi-paragraph split branch, and
  nothing pinned the single-undo-step claim that the comment makes load-bearing
  for the image/link-mark loss. Both now tested — undo through the real Mod-z
  keybinding rather than a test-only prop.

**Low, repaired:** dead `COMPOSE_PROMPT_VERSION` deleted (it only means something
where it feeds a cache key, and this endpoint has no cache) with a note saying
why there isn't one; `semantic_status` pinned on the degrade test; the a11y
finding folded into the latch fix — the button now stays **mounted and disabled**
instead of unmounting, so a keyboard user who just activated it does not have
focus dropped to `<body>`; the transient-429 test strengthened to assert the
button is still *enabled* (with the button always mounted, "still present" had
become nearly hollow).

**Accepted, not repaired (1):** no Playwright E2E for the assist flow. The feature
ships with the flag off, so an E2E could only assert the 503/disabled path, which
the unit tests already cover; E2E is also excluded from CI. Revisit when the flag
is enabled — and note the `.spec.js`-not-`.spec.ts` naming trap for the
authenticated project.

Also declined (react reviewer, low): an unmount guard on the async `setState`s.
React no-ops these, the reviewer confirmed no data-corruption path, and the
sibling `handleImageSelect` in the same file has the identical shape — guarding
only the new handler would be inconsistent, and changing both is out of scope.

A second jsdom trap surfaced while adding the undo test: prosemirror's
`coordsAtPos` calls `getClientRects` on a **Range** (not a node), which jsdom
lacks — again an unhandled error that fails the run at exit 1 while printing
"passed". Polyfilled in the test file with an explanation.

### 2026-07-29 - Verification

Final state, after the review repairs above:

```
$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py spectacular --file /dev/null   # CI's schema gate
spectacular exit: 0   # /forum/compose/assist/ present with 200/400/429/503;
                      # /forum/search/ documents semantic + semantic_status

$ python -m pytest --create-db -q                 # full backend suite
1304 passed, 0 failed, 8 skipped                  # was 1296 on main → +8

$ python -m pytest apps/forum_host packages/wagtail_forum --create-db -q
577 passed

$ npm run type-check                              # tsc --noEmit
(clean)

$ npm run lint
ESLint: 0 errors, 1 warnings in 1 files   # warning is a coverage artifact, pre-existing

$ ./node_modules/.bin/vitest --run                # full web suite
Test Files  54 passed (54)
     Tests  705 passed (705)                      # was 702 on main
```

New tests: 8 in `test_similar.py` (embedding budget, in-helper cap, pk cache), 13
in `test_semantic_search.py`, 24 in `test_compose_assist.py`, 8 in
`TipTapEditor.test.tsx`, 3 in `forumService.test.ts`.

**Note on the suite runs.** `--create-db`, not `--reuse-db`: a partial re-run
against a reused DB gave 84 phantom failures, all `Page.DoesNotExist(id=1)` in the
page fixtures — the known root-page truncation, not a regression (re-running the
same code with `--create-db` gave 577 passed).

One fix found by the new web tests: the insert chain needed
`focus(null, { scrollIntoView: false })`. Replacing the document made prosemirror
call `coordsAtPos`, which throws in jsdom (`getClientRects` missing) as an
**unhandled error — vitest exit code 1**, i.e. it would have failed CI while
still printing "25 passed". It also avoids a real scroll-jump on rewrite.

## Notes

Spun out of todo 255 at its completion (2026-07-22): 255's AC covered H12–H15 +
L6/L7 + the M13-unstarted gate; M12/M13/M14 were bundled in `source_finding` but
not in 255's AC. The 2026-07-11 audit Finding Status re-points M12/M13/M14 here.

Follow-ups created: **289** (M13 RAG execution, gated), **290** (pre-existing
search `RecursionError`). Nothing in this todo is live on merge — M12 needs
`FORUM_VECTOR_SEARCH_ENABLED`, M14 needs `FORUM_COMPOSE_ASSIST_ENABLED`, both
default off.
