# Canopy PR 4 — Identify + Garden + Diagnose + Home

**Date:** 2026-08-16
**Status:** Approved direction; spec pending user review
**Parent spec:** `docs/superpowers/specs/2026-08-13-canopy-design.md` (§6 per-area treatment, §9 landing plan)
**Scope:** `web/` React frontend only. No backend changes.

## 1. Context

PRs 1 (foundation), 2 (forum), 2.5 (forum content), 3 (blog + seed) are merged. Home, Identify,
Garden (`MyPlantsPage`), and Diagnose still render their pre-Canopy markup wearing PR 1's
re-mapped tokens (sane colors, old component structure) — the parent spec's landing plan names
these four as PR 4.

Unlike forum/blog, these four pages are personal data surfaces (saved plants, live
identification/diagnosis results) rather than public seeded content — no demo-content seeding is
in scope here. Auth split (confirmed in `App.tsx`'s route tree): **Home and Identify are public**
(outside `ProtectedLayout`); **Garden (`/my-plants`) and Diagnose (`/diagnose`) both require
auth** — this drives the e2e split in §6.

## 2. Decisions

| Decision | Choice |
|---|---|
| PR scope | Single PR 4 covering all four areas (not split), per the parent spec's landing plan |
| New primitives | None — `Card`, `Tile`, `HeroCard`, `StatCard`, `Pagination` (all built in PR 1/2) cover every surface below. `Chip` is deliberately **not** used for the static readouts (confidence %, saved date) — see §4 |
| Backend changes | None |
| Home "activity modules" | Deferred — Home stays a static page (same content for all users), restyled onto the primitives. No personalized activity feed, no new data |
| Visual QA | Manual: log into a dev server, add garden plants + run a real identification + a real diagnosis, screenshot dark + light mode. No seed-command extension |
| e2e coverage | Two new Playwright specs, split on auth + a `playwright.config.ts` wiring change (§6.2) |

## 3. Per-page treatment

### 3.1 Home (`web/src/pages/HomePage.tsx`, 97 lines)

Current: `GrainOverlay` wrapper, `Eyebrow` + `ClayButton` hero, three raw `FeatureCard` divs.

Change: `HeroCard` for the welcome section (same headline/copy, "Get Started" → Identify,
"Join Community" → Forum, matching the CTA pattern already used on forum/blog heroes). Three
feature cards become `Tile`-fronted `Card`s (AI Identification / Discussion Forum / Plant Blog),
same copy and links. `GrainOverlay`/`Eyebrow`/`ClayButton` usages retired from this page.

### 3.2 Identify (`web/src/pages/IdentifyPage.tsx` 315 + `components/PlantIdentification/FileUpload.tsx` 238 + `IdentificationResults.tsx` 151)

Current: raw `bg-surface-2 rounded-2xl` page shell, ad-hoc suggestion `div`s with a plain
percentage badge, three raw `InfoCard` divs.

Change: page shell → `Card`. Each suggestion in `IdentificationResults` → `Card`, confidence
becomes a static pill (§4 — not `Chip`; top suggestion keeps its highlighted treatment via the
existing accent-tile color). Disease-warning block keeps semantic `warn` coloring, restyled onto
`Card`. The 1-2-3 step `InfoCard`s → `Tile` row, matching Home's feature-card treatment.
`FileUpload`'s drop-zone restyled to the Canopy surface/border treatment (behavior unchanged) —
**shared with Diagnose (§3.4)**, one component, restyled once; both pages' tests need updating.

### 3.3 Garden (`web/src/pages/MyPlantsPage.tsx`, 192 lines)

Current: raw `article` cards, confidence badge, hand-rolled prev/next buttons.

Change: plant grid → `Card` per plant, following `BlogCard.tsx`'s established image-bleed
pattern (`.canopy-card` has no built-in padding — `overflow: hidden` only — so a full-bleed
`w-full h-40 object-cover` image sits as the first child, then a padded wrapper holds the rest;
confirmed by reading `Card.tsx` + the `.canopy-card` CSS rule, no prop changes needed). Confidence
% and "Saved {date}" become static pills (§4 — not `Chip`s). There is no live care-tracking status
in the data (`care_instructions_json.watering` is free text, not a due/overdue state), so "status"
here means confidence/recency/common-name-count, not a watering-due indicator. Hand-rolled
pagination buttons replaced by the existing `Pagination` primitive — confirmed direct prop fit:
`page={currentPage}`, `onPageChange={setCurrentPage}`, `hasPrevious={currentPage > 1}`,
`hasNext={currentPage < totalPages}`, `totalPages={totalPages}`, no primitive changes needed.
Empty and error states restyled onto `Card`.

### 3.4 Diagnose (`web/src/pages/diagnosis/DiseaseDiagnosePage.tsx` 134 + `components/diagnosis/DiseaseResultsList.tsx` 75)

Current: raw form in a `bg-surface-2 rounded-2xl` box.

Change: form shell → `Card`. Result rows in `DiseaseResultsList` → `Card`s with a match-%
static pill (§4). The `needs_help` notice keeps its `role="status"` copy and behavior, restyled
onto the new surface. Shares `FileUpload` with Identify (§3.2 — one restyle, both pages' tests
updated). Unrouted `DiagnosisListPage`/`DiagnosisDetailPage` stay untouched (parent spec §11).

## 4. Components

No new primitives required — confirmed by reading `Card.tsx`, `Chip.tsx`, `Pagination.tsx`, and
the `.canopy-card` CSS rule, not just by listing the directory.

**`Chip` is wrong for the static readouts** (confidence %, "Saved {date}", match %) and is
excluded from this PR's usage of it: `Chip.tsx` renders `<button type="button"
aria-pressed={active}>` — it's built for filter toggles and reaction pills (its real, correct
consumers elsewhere), not a static value. Wrapping a non-interactive number in a button with
`aria-pressed` is an a11y regression, not a restyle. Instead, these three spots use a plain
`<span>` styled like the pill idiom `BlogCard.tsx` already establishes for its category label
(`rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[11px] ... text-ink-2`)
— inlined at each of the three call sites, not extracted into a new shared component (only three
uses, YAGNI).

`ClayButton`, `Eyebrow`, `GrainOverlay` are retired from these four pages' usage (mirrors `.wf-*`
retiring in PR 2) — if other pages (auth, PR 5's territory) still use them, the components
themselves are not deleted, only these call sites change. Sidebar nav active-item highlighting
(built in PR 1) needs no changes.

## 5. Backend

None. All four pages already have working data flows (`plantIdService`, `diseaseService`); only
markup and styling change.

## 6. Testing & acceptance

### 6.1 Vitest

Existing suites (`HomePage.test.tsx`, `IdentifyPage.test.tsx`, `MyPlantsPage.test.tsx`,
`DiseaseDiagnosePage.test.tsx`, `DiseaseResultsList` coverage, `FileUpload` coverage) updated for
new markup/classes.

### 6.2 Playwright e2e — two files, split on auth (per §1's route audit)

The existing e2e setup is more specific than "add a spec file" — read from `playwright.config.ts`
and the existing specs before planning tasks:

- **Auth wiring is filename-keyed, not directory-keyed.** The `chromium-authenticated` /
  `firefox-authenticated` projects only run files matching
  `/(forum-authenticated|auth)\.spec\.js/`; every other project explicitly `testIgnore`s that
  same pattern. A new authenticated spec file is invisible to both sides of that split unless
  `playwright.config.ts` is edited to add its filename to both regexes. **This is an in-scope
  config change**, not just new spec files.
- **Two new spec files**, matching the existing `.ts` (unauthenticated) vs `.js`
  (authenticated, storageState-driven) convention:
  - `web/e2e/canopy-areas.spec.ts` (public, default `chromium` project): Home hero renders and
    its links navigate; Identify upload → result flow (network-mocked, see below) → confidence
    pill renders → "Save to collection" call fires.
  - `web/e2e/canopy-areas-authenticated.spec.js` (reuses `auth.setup.js` + `.auth/user.json`
    storageState, added to the authenticated projects' `testMatch` and every other project's
    `testIgnore` in `playwright.config.ts`): Garden populated grid + pagination render for a
    pre-seeded plant; Diagnose form submit → mocked results render, `needs_help` copy shows on
    that status.
  - True empty-state for Garden is **not** e2e-covered (the shared `e2e_test_user` persists
    across runs once seeded — no clean-slate guarantee) — the empty state stays covered by
    `MyPlantsPage.test.tsx`'s existing Vitest case.
- **No live external API calls.** Identify hits Plant.id/PlantNet and Diagnose hits the disease
  service through the backend — both cost money and flake under CI-like conditions. Both specs
  intercept via `page.route()`:
  - `POST **/api/v1/plant-identification/identify/` → fixture suggestion JSON
  - `POST **/api/v1/plant-identification/disease-requests/` and
    `GET **/api/v1/plant-identification/disease-requests/*/results/` → fixture diagnosis JSON
- **Garden fixture data** is seeded via direct authenticated API calls (Playwright's `request`
  fixture, reusing the same storageState) in the spec's own `beforeAll` — not routed through the
  Identify UI, and not a change to `create_test_user` or any backend fixture code (keeps the
  "no backend changes" decision intact). **Prerequisite, confirmed by reading
  `plantIdService.ts`**: `POST /api/v1/plant-identification/plants/` requires an existing
  `UserPlantCollection` (`saveToCollection` throws "No collection found" otherwise), and neither
  `create_test_user` nor any model signal creates one automatically — so `beforeAll` calls
  `POST /api/v1/users/collections/` first (idempotent-safe: only if the user has none) and then
  `POST /api/v1/plant-identification/plants/` with a fixture payload.
  Left-behind data across runs is an accepted tradeoff, same as `forum-authenticated.spec.js`.

### 6.3 Baseline recorded in this worktree (2026-08-16, before any PR 4 changes)

Ran `./node_modules/.bin/playwright test --project=chromium` for all four existing non-authenticated
specs (RTK mangles Playwright's filter args — direct binary only):

- `command-palette.spec.ts`, `green-thumb-theme.spec.ts`: **all passing**.
- `forum-golden-path.spec.ts`, `forum-responsive.spec.ts`: **8 failing**, pre-existing —
  `a[href^="/forum/"]` unscoped selector matches a PR-1 header link and redirects the click to
  `/login`. Already recorded as an open PR-5 carry-in (parent-spec memory, PR 2's review). Not
  caused by, and not fixed by, PR 4 — §6.4's gate line names only the passing baseline plus the
  new PR 4 specs, so this pre-existing failure isn't misattributed.

### 6.4 Visual QA & gates

- Manual visual QA: dev server, real login, add garden plants + run a real identification + a
  real diagnosis, screenshot dark + light mode. Judged against the Canopy token/primitive
  language established in PR 1/2/3 (no page-specific mockup screens exist for these four areas).
- Gates: `npm test`, `tsc`, `npm run build`, `command-palette.spec.ts` + `green-thumb-theme.spec.ts`
  - the two new PR 4 specs (§6.2) — `forum-golden-path`/`forum-responsive` excluded from the PR 4
  gate as a known pre-existing failure (§6.3) — kimi-review, user-reviewed merge (repo
  convention).

## 7. Execution

Branch `feat/canopy-areas` off `main` (isolated worktree, since another in-progress todo held
uncommitted changes on the original checkout). SDD-style like PR 2.5/3: task-by-task
implementation → per-task review → final whole-branch review → kimi-review gate → user-reviewed
merge.

## 8. Out of scope

- Backend changes of any kind.
- Home personalization / activity feed — deferred. A todo file gets written as part of this PR
  (matching every other deferral in this program: todos 300–306), not left as an unlogged hedge.
- `DiagnosisListPage`, `DiagnosisDetailPage` (unrouted, parent spec §11).
- Auth, Profile, Settings, `App.css` cleanup — PR 5's territory.
- New component primitives.
