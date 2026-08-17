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

Unlike forum/blog, these four pages are personal/authenticated data surfaces (saved plants, live
identification/diagnosis results) rather than public seeded content — no demo-content seeding is
in scope here.

## 2. Decisions

| Decision | Choice |
|---|---|
| PR scope | Single PR 4 covering all four areas (not split), per the parent spec's landing plan |
| New primitives | None — `Card`, `Tile`, `Chip`, `HeroCard`, `StatCard`, `Pagination` (all built in PR 1/2) cover every surface below |
| Backend changes | None |
| Home "activity modules" | Deferred — Home stays a static page (same content for all users), restyled onto the primitives. No personalized activity feed, no new data |
| Visual QA | Manual: log into a dev server, add garden plants + run a real identification + a real diagnosis, screenshot dark + light mode. No seed-command extension |
| e2e coverage | New Playwright spec added (§6) |

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
becomes a `Chip` (top suggestion keeps its highlighted treatment via the existing accent-tile
color). Disease-warning block keeps semantic `warn` coloring, restyled onto `Card`. The 1-2-3
step `InfoCard`s → `Tile` row, matching Home's feature-card treatment. `FileUpload`'s drop-zone
restyled to the Canopy surface/border treatment (behavior unchanged).

### 3.3 Garden (`web/src/pages/MyPlantsPage.tsx`, 192 lines)

Current: raw `article` cards, confidence badge, hand-rolled prev/next buttons.

Change: plant grid → `Card` per plant (image or `Leaf` icon placeholder unchanged). Confidence %
and "Saved {date}" become `Chip`s — presentational only. There is no live care-tracking status in
the data (`care_instructions_json.watering` is free text, not a due/overdue state), so "status
chips" here means confidence/recency/common-name-count, not a watering-due indicator. Hand-rolled
pagination buttons replaced by the existing `Pagination` primitive. Empty and error states
restyled onto `Card`.

### 3.4 Diagnose (`web/src/pages/diagnosis/DiseaseDiagnosePage.tsx` 134 + `components/diagnosis/DiseaseResultsList.tsx` 75)

Current: raw form in a `bg-surface-2 rounded-2xl` box.

Change: form shell → `Card`. Result rows in `DiseaseResultsList` → `Card`s with a match-%
`Chip`. The `needs_help` notice keeps its `role="status"` copy and behavior, restyled onto the
new surface. Unrouted `DiagnosisListPage`/`DiagnosisDetailPage` stay untouched (parent spec §11).

## 4. Components

No new primitives required. `ClayButton`, `Eyebrow`, `GrainOverlay` are retired from these four
pages' usage (mirrors `.wf-*` retiring in PR 2) — if other pages (auth, PR 5's territory) still
use them, the components themselves are not deleted, only these call sites change. Sidebar nav
active-item highlighting (built in PR 1) needs no changes.

## 5. Backend

None. All four pages already have working data flows (`plantIdService`, `diseaseService`); only
markup and styling change.

## 6. Testing & acceptance

- Existing Vitest suites (`HomePage.test.tsx`, `IdentifyPage.test.tsx`, `MyPlantsPage.test.tsx`,
  `DiseaseDiagnosePage.test.tsx`, `DiseaseResultsList` coverage, `FileUpload` coverage) updated
  for new markup/classes.
- New Playwright spec `web/e2e/canopy-areas.spec.ts`, following `forum-golden-path.spec.ts`'s
  pattern (auto-starts dev servers): Home hero renders and links navigate; Identify upload →
  result flow with a fixture image, confidence chip renders; Garden empty state and (with a
  saved plant) populated grid + pagination; Diagnose form submit → results render, `needs_help`
  copy shows on that status.
- Manual visual QA: dev server, real login, add garden plants + run a real identification + a
  real diagnosis, screenshot dark + light mode. Judged against the Canopy token/primitive
  language established in PR 1/2/3 (no page-specific mockup screens exist for these four areas).
- Gates: `npm test`, `tsc`, `npm run build`, existing Playwright shell/theme smoke plus the new
  spec above, kimi-review, user-reviewed merge (repo convention).

## 7. Execution

Branch `feat/canopy-areas` off `main` (isolated worktree, since another in-progress todo held
uncommitted changes on the original checkout). SDD-style like PR 2.5/3: task-by-task
implementation → per-task review → final whole-branch review → kimi-review gate → user-reviewed
merge.

## 8. Out of scope

- Backend changes of any kind.
- Home personalization / activity feed (deferred — flagged as a future todo if wanted later).
- `DiagnosisListPage`, `DiagnosisDetailPage` (unrouted, parent spec §11).
- Auth, Profile, Settings, `App.css` cleanup — PR 5's territory.
- New component primitives.
