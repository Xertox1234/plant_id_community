# Canopy PR 4 (Identify + Garden + Diagnose + Home) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle Home, Identify, Garden (`MyPlantsPage`), and Diagnose onto the Canopy design system's existing primitives — pure frontend visual work, no backend changes, no new primitives.

**Architecture:** Each page swaps its pre-Canopy raw-Tailwind markup for the `Card`/`Tile`/`HeroCard`/`Pagination` primitives already shipped in PR 1–3, following the real working patterns already proven in `BlogListPage.tsx`, `CategoryCard.tsx`, and `BlogCard.tsx` — not reinvented. `Chip` is deliberately excluded (button semantics, wrong for static values); static readouts use a plain styled `<span>` instead. Two new Playwright specs (one public, one authenticated) close out e2e coverage, with a `playwright.config.ts` wiring change the authenticated spec needs to actually run.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 4, Vitest + Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-16-canopy-areas-design.md` (this plan implements it in full; read both — the spec carries the *why*, this plan carries the *how*).

## Global Constraints

- No backend changes anywhere in this plan (spec §5, reaffirmed §6.2 — the Garden e2e fixture is seeded via API calls in the spec's own test setup, never by touching `create_test_user` or any other backend fixture code).
- No new `web/src/components/ui/` primitives (spec §2/§4) — every task below only *consumes* `Card`, `Tile`, `HeroCard`, `ButtonLink`, `Button`, `Pagination`.
- `Chip` is never used for a static (non-interactive) value — it renders `<button aria-pressed>` and using it for a read-only percentage or date is an a11y regression (spec §4). Static readouts use a plain `<span>` styled like `BlogCard.tsx`'s category pill: `rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[11px] text-ink-2` (adapted per-context below).
- `ClayButton`, `Eyebrow`, `GrainOverlay` usages are retired from the four pages this plan touches; the components themselves are not deleted (other pages may still use them).
- Every restyled component keeps its existing behavior and accessibility contract unchanged unless a task explicitly says otherwise — several existing tests pin specific DOM structure for accessibility reasons (audit M26 live regions in Task 3 and Task 4) and must keep passing unmodified in that respect.
- Reference real, already-shipped patterns instead of inventing new ones: `web/src/pages/BlogListPage.tsx` (HeroCard + Pagination usage), `web/src/components/forum/CategoryCard.tsx` (Card + Tile composition), `web/src/components/BlogCard.tsx` (Card image-bleed + static pill idiom).
- Run all commands from `web/` (the worktree is at `.worktrees/feat-canopy-areas`, so full paths look like `.worktrees/feat-canopy-areas/web/...`).

---

## Task 1: Home (`HomePage.tsx`)

**Files:**

- Modify: `web/src/pages/HomePage.tsx` (full rewrite of the two sections, keeps the file's overall shape)
- Test: `web/src/pages/HomePage.test.tsx` (full rewrite — both existing tests assert on retired components)

**Interfaces:**

- Consumes: `HeroCard` (`web/src/components/ui/HeroCard.tsx` — props `eyebrow?`, `title`, `description?`, `actions?`, `art?`), `ButtonLink` (`web/src/components/ui/ButtonLink.tsx` — props `to`, `variant?`, `children`), `Card` (`web/src/components/ui/Card.tsx` — props `interactive?`, `className?`, `children`), `Tile` (`web/src/components/ui/Tile.tsx` — props `tone?: 'sage'|'pollen'|'bloom'|'orchid'`, `size?`, `children`). All four already exist; no changes to any of them.
- Produces: nothing consumed by later tasks (Home has no shared sub-components).

- [ ] **Step 1: Read the current file and confirm the two tests you're about to replace**

Read `web/src/pages/HomePage.tsx` (97 lines) and `web/src/pages/HomePage.test.tsx` (26 lines) if you haven't already this session. Confirm the two existing tests (`wraps content in a GrainOverlay`, `renders a ClayButton CTA`) — both must be replaced because `GrainOverlay` and `ClayButton` are retired from this page.

- [ ] **Step 2: Write the new test file**

Replace `web/src/pages/HomePage.test.tsx` entirely:

```tsx
// web/src/pages/HomePage.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import HomePage from './HomePage';

const renderHome = () =>
  render(
    <BrowserRouter>
      <HomePage />
    </BrowserRouter>
  );

describe('HomePage', () => {
  it('renders the hero headline and CTA links, not a GrainOverlay or ClayButton', () => {
    renderHome();
    expect(screen.getByRole('heading', { level: 2, name: /discover the world of plants/i })).toBeInTheDocument();
    expect(screen.queryByTestId('grain-overlay')).not.toBeInTheDocument();

    const getStarted = screen.getByRole('link', { name: /get started/i });
    expect(getStarted).toHaveAttribute('href', '/identify');
    const joinCommunity = screen.getByRole('link', { name: /join community/i });
    expect(joinCommunity).toHaveAttribute('href', '/forum');
  });

  it('renders the three feature cards as links to their pages', () => {
    renderHome();

    expect(screen.getByRole('link', { name: /ai plant identification/i })).toHaveAttribute(
      'href',
      '/identify'
    );
    expect(screen.getByRole('link', { name: /discussion forum/i })).toHaveAttribute(
      'href',
      '/forum'
    );
    expect(screen.getByRole('link', { name: /plant blog/i })).toHaveAttribute('href', '/blog');
  });
});
```

Note: `getByRole('link', { name: /ai plant identification/i })` matches the whole feature card because the `<Link>` wraps the card's heading and description text (same composition as `CategoryCard.tsx` — the entire card is one accessible link, so its accessible name is its full text content, which contains "AI Plant Identification").

- [ ] **Step 3: Run the test file, confirm it fails against the current implementation**

```bash
cd web && npx vitest run src/pages/HomePage.test.tsx
```

Expected: FAIL — `GrainOverlay`/`ClayButton` are still present, feature cards aren't links yet, the hero headline isn't an `h2`.

- [ ] **Step 4: Rewrite `HomePage.tsx`**

```tsx
import { Sparkles, MessagesSquare, BookOpen } from 'lucide-react';
import { Link } from 'react-router-dom';
import HeroCard from '../components/ui/HeroCard';
import ButtonLink from '../components/ui/ButtonLink';
import Card from '../components/ui/Card';
import Tile from '../components/ui/Tile';

interface FeatureCardProps {
  title: string;
  description: string;
  href: string;
  tone: 'sage' | 'bloom' | 'orchid';
  Icon: typeof Sparkles;
}

/**
 * HomePage Component
 *
 * Landing page: hero + three feature cards, on the Canopy primitives
 * (Canopy PR 4). Same copy/links for every visitor — no personalized
 * activity feed (deferred, todo 308).
 */
export default function HomePage() {
  return (
    <div className="flex flex-col gap-8 py-8">
      <HeroCard
        eyebrow="Plant Identification Community"
        title={
          <>
            Discover the World of <span className="text-primary">Plants</span>
          </>
        }
        description="Join our community of plant enthusiasts. Identify plants with AI, share your garden, and learn from experts and fellow plant lovers."
        actions={
          <>
            <ButtonLink to="/identify" variant="primary">
              Get Started
            </ButtonLink>
            <ButtonLink to="/forum" variant="ghost">
              Join Community
            </ButtonLink>
          </>
        }
      />

      <div className="grid gap-5 md:grid-cols-3">
        <FeatureCard
          title="AI Plant Identification"
          description="Upload photos of plants and get instant identification using advanced AI technology."
          href="/identify"
          tone="sage"
          Icon={Sparkles}
        />
        <FeatureCard
          title="Discussion Forum"
          description="Ask questions, share tips, and participate in discussions about plant care."
          href="/forum"
          tone="bloom"
          Icon={MessagesSquare}
        />
        <FeatureCard
          title="Plant Blog"
          description="Read expert articles, care guides, and plant stories from our community."
          href="/blog"
          tone="orchid"
          Icon={BookOpen}
        />
      </div>
    </div>
  );
}

function FeatureCard({ title, description, href, tone, Icon }: FeatureCardProps) {
  return (
    <Card className="p-card">
      <Link to={href} className="flex items-start gap-4">
        <Tile tone={tone} aria-hidden="true">
          <Icon className="h-5 w-5" />
        </Tile>
        <div className="min-w-0 flex-1">
          <h3 className="gt-h3 text-ink">{title}</h3>
          <p className="mt-1 text-sm leading-relaxed text-ink-2">{description}</p>
          <span className="mt-2 inline-block text-sm font-medium text-primary">Learn more →</span>
        </div>
      </Link>
    </Card>
  );
}
```

Note: `FeatureCard` deliberately omits `interactive` on `Card` — `CategoryCard.tsx` only sets `interactive` on rows that need the hover-lift treatment; a plain informational tile-card reads fine without it, and adding it is a one-word change later if the visual QA pass in Task 8 disagrees.

- [ ] **Step 5: Run the test file again, confirm it passes**

```bash
cd web && npx vitest run src/pages/HomePage.test.tsx
```

Expected: PASS (2 tests).

- [ ] **Step 6: Run `tsc` to catch any type errors from the new imports**

```bash
cd web && npm run type-check
```

Expected: zero errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/pages/HomePage.tsx web/src/pages/HomePage.test.tsx
git commit -m "feat(canopy): restyle Home onto HeroCard + Tile/Card primitives"
```

---

## Task 2: `FileUpload` (shared by Identify and Diagnose)

**Files:**

- Modify: `web/src/components/PlantIdentification/FileUpload.tsx`
- Test: `web/src/components/PlantIdentification/FileUpload.test.tsx` (new — no test file exists today, and both consumer pages mock this component entirely in their own tests, so restyling it currently has zero test coverage anywhere)

**Interfaces:**

- Consumes: nothing new — nothing from `ui/` primitives changes here. This is a class-only restyle of the drop-zone; the compression/drag/preview *logic* (lines 1–137 of the current file) is untouched.
- Produces: same public API as today — `onFileSelect(file: File | null)`, `maxSize?: number`. Task 3 (Identify) and Task 4 (Diagnose) both render this component unchanged from their side.

- [ ] **Step 1: Write the new test file**

No prior test exists, so this is genuinely new coverage, not an update. Cover the two states a restyle risks breaking: the idle drop-zone prompt, and the drag-active visual state (both currently pure Tailwind classes with no test pinning them).

```tsx
// web/src/components/PlantIdentification/FileUpload.test.tsx
import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FileUpload from './FileUpload';

/**
 * jsdom implements neither `URL.createObjectURL` nor `revokeObjectURL` (no
 * blob URL store), so selecting a file would throw on preview. Same stub as
 * `TipTapEditor.test.tsx` (web/src/components/forum/TipTapEditor.test.tsx) —
 * copy it exactly, don't invent a different one.
 */
beforeAll(() => {
  const url = URL as unknown as Record<string, unknown>;
  url.createObjectURL = vi.fn(() => 'blob:preview-mock');
  url.revokeObjectURL = vi.fn();
});

describe('FileUpload', () => {
  it('shows the drop-zone prompt when idle', () => {
    render(<FileUpload onFileSelect={vi.fn()} />);
    expect(screen.getByText('Drop your plant photo here')).toBeInTheDocument();
    expect(screen.getByLabelText(/upload plant image/i)).toBeInTheDocument();
  });

  it('applies the drag-active treatment on dragenter and clears it on dragleave', () => {
    render(<FileUpload onFileSelect={vi.fn()} />);
    // The dashed drop-zone is the input's ancestor with the border classes.
    const dropZone = screen.getByLabelText(/upload plant image/i).closest('div')!;

    fireEvent.dragEnter(dropZone);
    expect(dropZone).toHaveClass('border-primary');

    fireEvent.dragLeave(dropZone);
    expect(dropZone).not.toHaveClass('border-primary');
  });

  it('shows a preview and a remove button after a file is selected', () => {
    const onFileSelect = vi.fn();
    render(<FileUpload onFileSelect={onFileSelect} />);

    const file = new File(['x'], 'plant.jpg', { type: 'image/jpeg' });
    const input = screen.getByLabelText(/upload plant image/i);
    fireEvent.change(input, { target: { files: [file] } });

    expect(screen.getByRole('button', { name: /remove image/i })).toBeInTheDocument();
    expect(onFileSelect).toHaveBeenCalledWith(file);
  });
});
```

- [ ] **Step 2: Run the test file, confirm it fails or passes against the CURRENT implementation**

```bash
cd web && npx vitest run src/components/PlantIdentification/FileUpload.test.tsx
```

Expected: all 3 PASS already — this is a characterization test of existing behavior, written before the restyle so Step 4 has a safety net. (If any assertion fails here, the assertion is wrong for the current markup — fix the test, not the component, before proceeding.)

- [ ] **Step 3: Restyle the drop-zone (behavior unchanged, only classes)**

In `web/src/components/PlantIdentification/FileUpload.tsx`, replace the drop-zone `<div>`'s className (lines 142–151 in the current file) to use the Canopy surface/border tokens instead of raw `border-line-2`/`bg-primary/10` etc. Replace:

```tsx
          className={`relative border-2 border-dashed rounded-xl p-12 transition-colors ${
            dragActive
              ? 'border-primary bg-primary/10'
              : error
                ? 'border-error/30 bg-error/10'
                : isCompressing
                  ? 'border-sky/30 bg-sky/10'
                  : 'border-line-2 hover:border-primary'
          }`}
```

with:

```tsx
          className={`relative rounded-md border-2 border-dashed bg-surface-2/40 p-12 transition-colors ${
            dragActive
              ? 'border-primary bg-primary/10'
              : error
                ? 'border-error/30 bg-error/10'
                : isCompressing
                  ? 'border-orchid/30 bg-orchid/10'
                  : 'border-line hover:border-primary'
          }`}
```

(`sky` was PR 1's legacy accent name, already re-pointed to `orchid` — using `orchid` directly here instead of the legacy alias, since this is new code being written, not an untouched carry-over. `border-line-2` → `border-line` matches the token scale used by `Card`/`CategoryCard` elsewhere.) Leave every other line in the file — the compression logic, the preview `<img>`, the remove button, the compression-stats overlay — untouched. The compression-stats overlay's `bg-white/90` (line 221) is a pre-existing light-mode-only bug outside this plan's scope (not mentioned in the spec); leave it as-is.

- [ ] **Step 4: Run the test file again, confirm it still passes**

```bash
cd web && npx vitest run src/components/PlantIdentification/FileUpload.test.tsx
```

Expected: PASS (3 tests) — the restyle changed colors, not structure or behavior, so the same assertions hold.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/PlantIdentification/FileUpload.tsx web/src/components/PlantIdentification/FileUpload.test.tsx
git commit -m "feat(canopy): restyle FileUpload drop-zone onto Canopy tokens, add first test coverage"
```

---

## Task 3: Identify (`IdentifyPage.tsx` + `IdentificationResults.tsx`)

**Files:**

- Modify: `web/src/pages/IdentifyPage.tsx`
- Modify: `web/src/components/PlantIdentification/IdentificationResults.tsx`
- Test: `web/src/components/PlantIdentification/IdentificationResults.test.tsx` (new — no test file exists today; `IdentifyPage.test.tsx` never asserts on this component's markup)
- Test: `web/src/pages/IdentifyPage.test.tsx` (no assertions on the retired classes exist — verify unchanged, see Step 5)

**Interfaces:**

- Consumes: `Card`, `Tile` (same as Task 1). `FileUpload` unchanged from Task 2.
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Write the new `IdentificationResults` test file**

```tsx
// web/src/components/PlantIdentification/IdentificationResults.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import IdentificationResults from './IdentificationResults';
import type { PlantIdentificationResult } from '@/types';

const RESULTS: PlantIdentificationResult = {
  plant_name: 'Swiss cheese plant',
  confidence: 0.82,
  source: 'plant_id',
  suggestions: [
    {
      plant_name: 'Swiss cheese plant',
      scientific_name: 'Monstera deliciosa',
      probability: 0.82,
      confidence: 0.82,
      source: 'plant_id',
    },
    {
      plant_name: 'Heartleaf philodendron',
      scientific_name: 'Philodendron hederaceum',
      probability: 0.11,
      confidence: 0.11,
      source: 'plant_id',
    },
  ],
};

describe('IdentificationResults', () => {
  it('renders each suggestion with a confidence pill, not a Chip button', () => {
    render(<IdentificationResults results={RESULTS} loading={false} error={null} />);

    expect(screen.getByText('Swiss cheese plant')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getByText('11%')).toBeInTheDocument();

    // The confidence readout is a static value — must not be a button.
    expect(screen.queryByRole('button', { name: /82%/ })).not.toBeInTheDocument();
  });

  it('renders disease suggestions with a match-percentage pill', () => {
    const withDisease: PlantIdentificationResult = {
      ...RESULTS,
      disease_suggestions: [{ name: 'Leaf spot', probability: 0.6, description: 'Fungal.' }],
    };
    render(<IdentificationResults results={withDisease} loading={false} error={null} />);

    expect(screen.getByText('Leaf spot')).toBeInTheDocument();
    expect(screen.getByText('60%')).toBeInTheDocument();
  });

  it('shows the save-to-collection action per suggestion when onSavePlant is provided', () => {
    render(
      <IdentificationResults
        results={RESULTS}
        loading={false}
        error={null}
        onSavePlant={vi.fn()}
        savedPlants={new Map()}
        savingPlant={null}
      />
    );
    expect(
      screen.getAllByRole('button', { name: /save .* to collection/i })
    ).toHaveLength(2);
  });
});
```

- [ ] **Step 2: Run the test file, confirm it fails against the current implementation**

```bash
cd web && npx vitest run src/components/PlantIdentification/IdentificationResults.test.tsx
```

Expected: FAIL — the current confidence readout renders as `"{pct}%"` inside a `<div>`, not queryable the same way after the restyle changes structure (and the "not a button" assertion may pass today only by accident, since the current badge is a `<div>`, not a `<button>` — that assertion should already pass; the two `%` text assertions confirm the exact rendered string, which today is unchanged, so run this first to see which of the three tests actually fail before assuming all three do).

- [ ] **Step 3: Restyle `IdentificationResults.tsx`**

Replace the whole file:

```tsx
import { Loader2, Check } from 'lucide-react';
import Card from '../ui/Card';
import { getPlantKey } from '../../utils/plantUtils';
import type { PlantIdentificationResult } from '@/types';

interface IdentificationResultsProps {
  results: PlantIdentificationResult | null;
  loading: boolean;
  error: string | null;
  onSavePlant?: (plant: PlantIdentificationResult) => void;
  savedPlants?: Map<string, boolean>;
  savingPlant?: string | null;
}

/** Static, non-interactive percentage readout — never a Chip (button semantics). */
function ConfidencePill({ value, tone = 'text-ink-2' }: { value: number; tone?: string }) {
  return (
    <span
      className={`shrink-0 rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[13px] tabular-nums ${tone}`}
    >
      {Math.round(value * 100)}%
    </span>
  );
}

export default function IdentificationResults({
  results,
  loading,
  error,
  onSavePlant,
  savedPlants,
  savingPlant,
}: IdentificationResultsProps) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
        <p className="text-lg font-medium text-ink">Analyzing your plant...</p>
        <p className="text-sm text-ink-2 mt-2">This may take a few seconds</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-error/10 border border-error/30 rounded-md p-6">
        <h3 className="text-lg font-semibold text-error mb-2">Identification Failed</h3>
        <p className="text-error">{error}</p>
      </div>
    );
  }

  if (!results) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-ink mb-4">Identification Results</h3>

        <div className="space-y-4">
          {results.suggestions?.map((suggestion, index) => (
            <Card key={index} className={`p-5 ${index === 0 ? 'border-primary/40' : ''}`}>
              <div className="flex items-start justify-between mb-2 gap-3">
                <div className="flex-1">
                  <h4 className="text-lg font-semibold text-ink">{suggestion.plant_name}</h4>
                  {suggestion.scientific_name && (
                    <p className="text-sm italic text-ink-2">{suggestion.scientific_name}</p>
                  )}
                </div>
                <ConfidencePill
                  value={suggestion.probability}
                  tone={index === 0 ? 'text-primary' : 'text-ink-2'}
                />
              </div>

              {suggestion.description && (
                <p className="text-ink-2 mt-2">{suggestion.description}</p>
              )}

              {suggestion.similar_images && suggestion.similar_images.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-ink-2 mb-2">Similar images:</p>
                  <div className="grid grid-cols-4 gap-2">
                    {suggestion.similar_images.slice(0, 4).map((img, idx) => (
                      <img
                        key={idx}
                        src={img.url}
                        alt={`Similar ${idx + 1}`}
                        className="w-full h-20 object-cover rounded-md"
                      />
                    ))}
                  </div>
                </div>
              )}

              {onSavePlant &&
                (() => {
                  const plantKey = getPlantKey(suggestion);
                  const isSaved = savedPlants?.has(plantKey);
                  const isSaving = savingPlant === plantKey;

                  return (
                    <button
                      onClick={() => onSavePlant(suggestion)}
                      disabled={isSaved || isSaving}
                      aria-busy={isSaving}
                      aria-label={
                        isSaved
                          ? `${suggestion.plant_name} saved to collection`
                          : `Save ${suggestion.plant_name} to collection`
                      }
                      className={`mt-4 w-full px-4 py-2 rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 flex items-center justify-center gap-2 ${
                        isSaved
                          ? 'bg-surface-3 text-ink-2 cursor-not-allowed'
                          : isSaving
                            ? 'bg-clay/80 text-on-clay cursor-wait'
                            : 'bg-clay text-on-clay hover:bg-clay/90 focus:ring-primary'
                      }`}
                    >
                      {isSaving && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}
                      {isSaved && <Check className="w-4 h-4" aria-hidden="true" />}
                      {isSaved
                        ? 'Saved to Collection'
                        : isSaving
                          ? 'Saving...'
                          : 'Save to My Collection'}
                    </button>
                  );
                })()}
            </Card>
          ))}
        </div>
      </div>

      {results.disease_suggestions && results.disease_suggestions.length > 0 && (
        <div className="bg-warn/10 border border-warn/30 rounded-md p-6">
          <h4 className="text-lg font-semibold text-warn mb-3">Potential Health Issues</h4>
          <div className="space-y-3">
            {results.disease_suggestions.map((disease, index) => (
              <div key={index} className="bg-surface-2 p-4 rounded-md flex items-start justify-between gap-3">
                <div>
                  <h5 className="font-medium text-ink">{disease.name}</h5>
                  {disease.description && (
                    <p className="text-sm text-ink-2 mt-1">{disease.description}</p>
                  )}
                </div>
                <ConfidencePill value={disease.probability} tone="text-warn" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

Notes on what changed and why: `bg-clay` on the save button is left exactly as-is — the spec doesn't call for restyling that action button, only the results display, and it's already Canopy-token-based (`clay` was re-pointed to `pollen` in PR 1). The two `rounded-xl`/`rounded-lg` instances that aren't `Card` (the disease block, the similar-images thumbnails) move to `rounded-md` to match `Card`'s own radius token, per the parent spec's card-radius consistency note (memory: the PR-5 carry-in about `Card` radius was about *inconsistent* radii across pages, not about `Card` needing a prop — using `rounded-md` everywhere here avoids reintroducing that inconsistency).

- [ ] **Step 4: Run the test file again, confirm it passes**

```bash
cd web && npx vitest run src/components/PlantIdentification/IdentificationResults.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Run the full `IdentifyPage` suite — it mocks `FileUpload` but renders the REAL `IdentificationResults`, so it exercises this change indirectly**

```bash
cd web && npx vitest run src/pages/IdentifyPage.test.tsx
```

Expected: PASS unchanged (5 tests, empirically confirmed against the current file while writing this plan) — none of `IdentifyPage.test.tsx`'s assertions touch suggestion-card markup or the confidence badge, only the save-error live region and the "Ask the community" navigation flow, both untouched by this task.

- [ ] **Step 6: Restyle the `IdentifyPage.tsx` shell and step cards**

In `web/src/pages/IdentifyPage.tsx`, add the import and replace the three marked sections. Add near the top with the other imports:

```tsx
import Card from '../components/ui/Card';
import Tile from '../components/ui/Tile';
```

Replace the page header + main content wrapper (current lines 173–192, the `<div className="bg-gradient-to-br ...">` through the opening of the `Card`-equivalent wrapper):

```tsx
  return (
    <div className="flex flex-col gap-8 py-8">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <Tile tone="sage" size="md" aria-hidden="true">
          <Sparkles className="w-5 h-5" />
        </Tile>
        <div>
          <h1 className="text-3xl font-bold text-ink">AI Plant Identification</h1>
          <p className="text-ink-2 mt-1">Upload a photo to identify your plant instantly</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="mx-auto w-full max-w-4xl">
        <Card className="p-card">
```

(This changes the outer wrapper's max-width container to wrap the `Card`, not sit inside a separate header band — matching how `IdentifyPage` already puts everything in one `max-w-4xl` column, just now backed by `Card` instead of a raw `bg-surface-2 rounded-2xl` div.) Then, further down, replace the closing of that section (current line 280's `</div>` that closes the `bg-surface-2 rounded-2xl` box) — change it to close the `Card` (`</Card>`) instead, and close the two new wrapping divs added above. Also replace the Info Cards block (current lines 282–299):

```tsx
        {/* Info Cards */}
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          <InfoTile
            title="Upload Photo"
            description="Take or upload a clear photo of your plant"
            step="1"
          />
          <InfoTile
            title="AI Analysis"
            description="Our AI identifies your plant using advanced recognition"
            step="2"
          />
          <InfoTile
            title="Get Results"
            description="Receive detailed information about your plant"
            step="3"
          />
        </div>
      </div>
    </div>
  );
}

function InfoTile({ title, description, step }: InfoCardProps) {
  return (
    <Card className="p-card">
      <div className="flex items-start gap-4">
        <Tile tone="sage" size="sm" aria-hidden="true">
          <span className="font-mono text-sm font-semibold">{step}</span>
        </Tile>
        <div>
          <h3 className="font-semibold text-ink mb-1">{title}</h3>
          <p className="text-sm text-ink-2">{description}</p>
        </div>
      </div>
    </Card>
  );
}
```

(`InfoCardProps` interface, already defined near the top of the file, is reused as-is — only the render function renamed from `InfoCard` to `InfoTile` and its markup swapped.) The save/ask-community error live region (current lines 222–242) and the results-section conditional (current lines 244–279) are otherwise unchanged in place — only their surrounding container moved from a `div` to being inside `Card`.

- [ ] **Step 7: Run the full test file, confirm it still passes**

```bash
cd web && npx vitest run src/pages/IdentifyPage.test.tsx
```

Expected: PASS (5 tests) — this task changed layout classes only; none of the file's assertions query by class, only by role/text/live-region.

- [ ] **Step 8: Run `tsc`**

```bash
cd web && npm run type-check
```

Expected: zero errors.

- [ ] **Step 9: Commit**

```bash
git add web/src/pages/IdentifyPage.tsx web/src/components/PlantIdentification/IdentificationResults.tsx web/src/components/PlantIdentification/IdentificationResults.test.tsx
git commit -m "feat(canopy): restyle Identify results and page shell onto Card/Tile, drop Chip"
```

---

## Task 4: Diagnose (`DiseaseDiagnosePage.tsx` + `DiseaseResultsList.tsx`)

**Files:**

- Modify: `web/src/pages/diagnosis/DiseaseDiagnosePage.tsx`
- Modify: `web/src/components/diagnosis/DiseaseResultsList.tsx`
- Test: `web/src/components/diagnosis/DiseaseResultsList.test.tsx` (new)
- Test: `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx` (verify unchanged — see Step 5; this file pins load-bearing a11y structure, see the constraint below)

**Interfaces:**

- Consumes: `Card` (same as prior tasks). `FileUpload` unchanged from Task 2.
- Produces: nothing new consumed elsewhere.

**Hard constraint carried from `DiseaseDiagnosePage.test.tsx`'s existing tests (audit M26):** the current file wraps its submit button and its `aria-live="assertive"` error region together in one `<div>` that is the last child of a `.space-y-6` container — this exact nesting is what makes the live region "already mounted" (not remounted when the error text changes) and keeps it out of Tailwind v4's `space-y-6` margin calculation. Three existing tests pin this (`swaps the error into a live region that was already mounted`, `keeps the live region out of the space-y child list`, plus the mount-order check inside `submits and renders a diagnosis result`). **Do not restructure that specific div — wrap the surrounding content in `Card`, but leave the `.space-y-6` container and its last-child button+region wrapper exactly as they are today.**

- [ ] **Step 1: Write the new `DiseaseResultsList` test file**

```tsx
// web/src/components/diagnosis/DiseaseResultsList.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DiseaseResultsList from './DiseaseResultsList';
import type { PlantDiseaseResult } from '@/types/diagnosis';

const RESULT: PlantDiseaseResult = {
  id: 1,
  uuid: 'u1',
  request_id: 'r1',
  suggested_disease_name: 'Black Spot',
  suggested_disease_type: 'fungal',
  confidence_score: 0.88,
  confidence_percentage: 88,
  diagnosis_source: 'api_plant_health',
  severity_assessment: 'moderate',
  symptoms_identified: 'black spots',
  recommended_treatments: 'fungicide',
  immediate_actions: 'remove affected leaves',
  notes: '',
  is_primary: true,
  display_name: 'Black Spot',
};

describe('DiseaseResultsList', () => {
  it('renders a result with a match-percentage pill, not a Chip button', () => {
    render(<DiseaseResultsList results={[RESULT]} />);

    expect(screen.getByText('Black Spot')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /88%/ })).not.toBeInTheDocument();
    expect(screen.getByText(/black spots/)).toBeInTheDocument();
  });

  it('renders a system_message result as a status notice, not a disease card', () => {
    const notice: PlantDiseaseResult = {
      ...RESULT,
      diagnosis_source: 'system_message',
      notes: 'Service unavailable — please try again.',
    };
    render(<DiseaseResultsList results={[notice]} />);

    expect(screen.getByRole('status')).toHaveTextContent('Service unavailable');
    expect(screen.queryByText('88%')).not.toBeInTheDocument();
  });

  it('shows the empty-results message when there are no results', () => {
    render(<DiseaseResultsList results={[]} />);
    expect(screen.getByRole('status')).toHaveTextContent('No diagnosis was produced');
  });
});
```

- [ ] **Step 2: Run the test file, confirm it fails**

```bash
cd web && npx vitest run src/components/diagnosis/DiseaseResultsList.test.tsx
```

Expected: FAIL on the "88%" text match (current code renders `"88% confidence"`, not `"88%"` alone) — confirms the test is exercising the pre-restyle markup.

- [ ] **Step 3: Restyle `DiseaseResultsList.tsx`**

Replace the whole file:

```tsx
import Card from '../ui/Card';
import type { PlantDiseaseResult } from '@/types/diagnosis';

interface Props {
  results: PlantDiseaseResult[];
}

/**
 * Renders disease diagnosis results. A `system_message` result (the honest "service
 * unavailable / ask the community" fallback) is rendered as a notice, not a disease card.
 */
export default function DiseaseResultsList({ results }: Props) {
  if (results.length === 0) {
    return (
      <p className="text-ink-2" role="status">
        No diagnosis was produced. Please try a clearer photo and a fuller symptom description.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((r) => {
        if (r.diagnosis_source === 'system_message') {
          return (
            <div
              key={r.id}
              role="status"
              className="bg-surface-3 border border-line rounded-md p-4 text-ink-2"
            >
              {r.notes}
            </div>
          );
        }
        return (
          <Card key={r.id} className={`p-5 ${r.is_primary ? 'border-primary/40' : ''}`}>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-ink">
                {r.suggested_disease_name || r.display_name || 'Unknown condition'}
              </h3>
              <span className="shrink-0 rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[13px] tabular-nums text-ink-2">
                {r.confidence_percentage}%
              </span>
            </div>
            {r.severity_assessment && (
              <p className="mt-1 text-sm text-ink-2">Severity: {r.severity_assessment}</p>
            )}
            {r.symptoms_identified && (
              <p className="mt-3 text-sm text-ink">
                <span className="font-medium">Symptoms: </span>
                {r.symptoms_identified}
              </p>
            )}
            {r.immediate_actions && (
              <p className="mt-2 text-sm text-ink">
                <span className="font-medium">Immediate actions: </span>
                {r.immediate_actions}
              </p>
            )}
            {r.recommended_treatments && (
              <p className="mt-2 text-sm text-ink">
                <span className="font-medium">Recommended treatments: </span>
                {r.recommended_treatments}
              </p>
            )}
          </Card>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run the test file again, confirm it passes**

```bash
cd web && npx vitest run src/components/diagnosis/DiseaseResultsList.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Run the `DiseaseDiagnosePage` suite — it renders the real `DiseaseResultsList`, so confirm the copy change (`"88% confidence"` → `"88%"`) doesn't break it**

```bash
cd web && npx vitest run src/pages/diagnosis/DiseaseDiagnosePage.test.tsx
```

Expected: **`submits and renders a diagnosis result` FAILS** — it asserts `screen.getByText(/88% confidence/)`, which no longer exists. Fix that one assertion (only that one — the other three tests don't touch this text) in `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx`:

```diff
-    expect(screen.getByText(/88% confidence/)).toBeInTheDocument();
+    expect(screen.getByText('88%')).toBeInTheDocument();
```

Re-run — expected: PASS (5 tests, all unchanged in behavior).

- [ ] **Step 6: Restyle the `DiseaseDiagnosePage.tsx` shell — wrap in `Card`, touch nothing inside the `.space-y-6` block's structure**

Add the import:

```tsx
import Card from '../../components/ui/Card';
```

Replace the header + opening wrapper (current lines 44–56):

```tsx
  return (
    <div className="mx-auto w-full max-w-4xl py-8">
      <div className="flex items-center gap-3 mb-8">
        <Tile tone="bloom" size="md" aria-hidden="true">
          <Stethoscope className="w-5 h-5" />
        </Tile>
        <div>
          <h1 className="text-3xl font-bold text-ink">Diagnose a sick plant</h1>
          <p className="text-ink-2 mt-1">Upload a photo and describe the symptoms.</p>
        </div>
      </div>

      <Card className="p-card space-y-6">
```

(add `import Tile from '../../components/ui/Tile';` alongside the `Card` import) and change the closing tag at the end of the JSX (current line 131's `</div>`, the one that closes `bg-surface-2 rounded-2xl shadow-sm border border-line p-8 space-y-6`) to `</Card>`. Also update the outer closing `</div>` (current line 132, closing `max-w-4xl mx-auto px-4 ...`) to match the new outer wrapper from above. **Every div between the opening `<Card className="p-card space-y-6">` and its closing `</Card>` — the `FileUpload`, the symptoms textarea, the condition/location inputs, and critically the button+live-region wrapper `<div>` — stays byte-for-byte identical to the current file.** Only the two outermost wrapper elements (header band, and the `bg-surface-2 rounded-2xl shadow-sm border border-line p-8` box becoming `Card`) change.

- [ ] **Step 7: Run the full test file, confirm all 5 tests pass**

```bash
cd web && npx vitest run src/pages/diagnosis/DiseaseDiagnosePage.test.tsx
```

Expected: PASS (5 tests) — including the two structure-sensitive M26 tests (`swaps the error into a live region that was already mounted`, `keeps the live region out of the space-y child list`), which only pass if Step 6 didn't touch the inner structure.

- [ ] **Step 8: Run `tsc`**

```bash
cd web && npm run type-check
```

Expected: zero errors.

- [ ] **Step 9: Commit**

```bash
git add web/src/pages/diagnosis/DiseaseDiagnosePage.tsx web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx web/src/components/diagnosis/DiseaseResultsList.tsx web/src/components/diagnosis/DiseaseResultsList.test.tsx
git commit -m "feat(canopy): restyle Diagnose results and page shell onto Card, drop Chip"
```

---

## Task 5: Garden (`MyPlantsPage.tsx`)

**Files:**

- Modify: `web/src/pages/MyPlantsPage.tsx`
- Test: `web/src/pages/MyPlantsPage.test.tsx`

**Interfaces:**

- Consumes: `Card`, `Pagination` (`web/src/components/ui/Pagination.tsx` — named export `{ Pagination }`, props `page`, `onPageChange`, `hasPrevious`, `hasNext`, `totalPages?`, `variant?`). This is `Pagination`'s **first real consumer besides `BlogListPage.tsx`** — its prop shape is proven there, follow that usage exactly (spec §3.3, confirmed against `BlogListPage.tsx:287-293`).
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Read the current `MyPlantsPage.test.tsx` pagination assertions before changing anything**

The current tests assert the exact copy `'Showing page 1 of 2 (25 total)'` and `'Showing page 2 of 2 (25 total)'`. `Pagination` has no `totalCount` prop and doesn't render a "(N total)" phrase — `BlogListPage.tsx` doesn't show a total count next to its `Pagination` either (checked directly: no such text exists in that file). This plan drops the "(N total)" phrase to match the one real precedent in the app, rather than inventing a hybrid layout. Update the two pagination-copy assertions now, before touching the component, so the red/green cycle is meaningful:

```diff
-    expect(await screen.findByText('Showing page 1 of 2 (25 total)')).toBeInTheDocument();
+    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument();
```

```diff
-    expect(screen.getByText('Showing page 2 of 2 (25 total)')).toBeInTheDocument();
+    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument();
```

Also update the two confidence-badge assertions (`'97% match'`, `'81% match'`) to match the new pill copy (percentage only, no "match" suffix — same simplification as Task 3's `ConfidencePill`, kept consistent across the app rather than each page inventing its own suffix):

```diff
-    expect(screen.getByText('97% match')).toBeInTheDocument();
-    expect(screen.getByText('81% match')).toBeInTheDocument();
+    expect(screen.getByText('97%')).toBeInTheDocument();
+    expect(screen.getByText('81%')).toBeInTheDocument();
```

- [ ] **Step 2: Run the test file, confirm the four updated assertions now fail against the CURRENT component (everything else still passes)**

```bash
cd web && npx vitest run src/pages/MyPlantsPage.test.tsx
```

Expected: 2 tests FAIL — `renders saved plants with name, common names, and confidence` (the `% match` assertions) and `paginates: Next requests the following page` (the "(N total)" copy). The other 5 tests (loading, display_name preference, empty state, error+retry, hides-pagination-on-one-page) still pass, out of 7 total — confirms the test file's remaining coverage is untouched by this task. (Empirically verified against the current file in this worktree while writing this plan: 2 failed, 5 passed.)

- [ ] **Step 3: Restyle `MyPlantsPage.tsx`**

Replace the whole file:

```tsx
/**
 * MyPlantsPage Component
 *
 * Authenticated page listing the plants the user saved to their collection
 * after an identification ("Save to My Collection" on the identify flow).
 * Read surface for GET /api/v1/plant-identification/plants/ (todo 243).
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Leaf } from 'lucide-react';
import Card from '../components/ui/Card';
import { Pagination } from '../components/ui/Pagination';
import { plantIdService } from '../services/plantIdService';
import { logger } from '../utils/logger';
import type { UserPlant } from '../types/plantId';

const PAGE_SIZE = 20; // Backend DRF PageNumberPagination page size

function StaticPill({ children, tone = 'text-ink-2' }: { children: React.ReactNode; tone?: string }) {
  return (
    <span
      className={`shrink-0 rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[11px] ${tone}`}
    >
      {children}
    </span>
  );
}

export default function MyPlantsPage() {
  const [plants, setPlants] = useState<UserPlant[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  const loadPlants = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await plantIdService.getMyPlants(currentPage);

      setPlants(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err) {
      logger.error('[MyPlantsPage] Failed to load plants:', err);
      setError(err instanceof Error ? err.message : 'Failed to load your plants');
    } finally {
      setLoading(false);
    }
  }, [currentPage]);

  useEffect(() => {
    loadPlants();
  }, [loadPlants]);

  return (
    <div className="flex flex-col gap-8 py-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-ink">My Plants</h1>
        <p className="mt-2 text-ink-2">
          Plants you saved to your collection after identifying them
        </p>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
          <p className="mt-4 text-ink-2">Loading your plants...</p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="bg-error/10 border border-error/30 rounded-md p-6 text-center">
          <h3 className="text-lg font-semibold text-error mb-2">Failed to Load Your Plants</h3>
          <p className="text-error mb-4">{error}</p>
          <button
            onClick={loadPlants}
            className="inline-flex items-center px-4 py-2 bg-error text-white rounded-md hover:bg-error/90 transition-colors"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && plants.length === 0 && (
        <Card className="p-12 text-center">
          <Leaf className="w-16 h-16 text-ink-3 mx-auto mb-4" aria-hidden="true" />
          <h3 className="text-lg font-semibold text-ink mb-2">No Plants Yet</h3>
          <p className="text-ink-2 mb-6">
            Identify a plant and save it to your collection to see it here
          </p>
          <Link
            to="/identify"
            className="inline-flex items-center px-4 py-2 bg-clay text-on-clay rounded-md hover:bg-clay/90 transition-colors"
          >
            Identify a Plant
          </Link>
        </Card>
      )}

      {/* Plants Grid */}
      {!loading && !error && plants.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {plants.map((plant) => {
              const commonNames = plant.care_instructions_json?.common_names;
              const watering = plant.care_instructions_json?.watering;
              const confidence = plant.care_instructions_json?.confidence;

              return (
                <Card key={plant.id} className="overflow-hidden">
                  {/* Image or placeholder */}
                  {plant.image_thumbnail ? (
                    <img
                      src={plant.image_thumbnail}
                      alt={plant.display_name || plant.nickname || 'Saved plant'}
                      className="w-full h-40 object-cover"
                    />
                  ) : (
                    <div className="w-full h-40 bg-primary/10 flex items-center justify-center">
                      <Leaf className="w-12 h-12 text-primary" aria-hidden="true" />
                    </div>
                  )}

                  <div className="p-5">
                    <div className="flex items-start justify-between gap-2">
                      <h2 className="text-lg font-semibold text-ink">
                        {plant.display_name || plant.nickname || 'Unnamed plant'}
                      </h2>
                      {typeof confidence === 'number' && (
                        <StaticPill tone="text-primary">{Math.round(confidence * 100)}%</StaticPill>
                      )}
                    </div>

                    {Array.isArray(commonNames) && commonNames.length > 0 && (
                      <p className="mt-1 text-sm text-ink-2">{commonNames.join(', ')}</p>
                    )}

                    {watering && (
                      <p className="mt-3 text-sm text-ink-2 line-clamp-2">
                        <span className="font-medium text-ink">Watering:</span> {watering}
                      </p>
                    )}

                    {plant.notes && (
                      <p className="mt-2 text-sm text-ink-3 line-clamp-2">{plant.notes}</p>
                    )}

                    {plant.created_at && (
                      <div className="mt-3">
                        <StaticPill>
                          Saved {new Date(plant.created_at).toLocaleDateString()}
                        </StaticPill>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <Pagination
              page={currentPage}
              onPageChange={setCurrentPage}
              hasPrevious={currentPage > 1}
              hasNext={currentPage < totalPages}
              totalPages={totalPages}
            />
          )}
        </>
      )}
    </div>
  );
}
```

Note: `plants.map((plant) => ...)` no longer renders a semantic `<article>` — it wraps in `Card`, matching `BlogCard.tsx`'s own precedent (`BlogCard` doesn't use `<article>` either). No existing test in `MyPlantsPage.test.tsx` queries by tag name or `role="article"`, so this is a safe, consistency-driven change, not a silent regression.

- [ ] **Step 4: Run the test file again, confirm all 7 tests pass**

```bash
cd web && npx vitest run src/pages/MyPlantsPage.test.tsx
```

Expected: PASS (7 tests). (Empirically verified against the full rewrite in this worktree while writing this plan, then reverted — `tsc --noEmit` also clean.)

- [ ] **Step 5: Run `tsc`**

```bash
cd web && npm run type-check
```

Expected: zero errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/MyPlantsPage.tsx web/src/pages/MyPlantsPage.test.tsx
git commit -m "feat(canopy): restyle Garden onto Card grid + shared Pagination primitive"
```

---

## Task 6: File the Home-activity-feed deferral todo

**Files:**

- Create: `todos/308-pending-p3-home-activity-feed.md`

**Interfaces:** none — this is a documentation-only task, no code dependency on any other task.

- [ ] **Step 1: Confirm 308 is the next free todo ID**

```bash
ls todos/ | grep -oE '^[0-9]+' | sort -n | tail -3
```

Expected: highest existing ID is `307` — `308` is free. (If a concurrent branch has already claimed 308 by the time this task runs, use the next free number and adjust the filename/frontmatter `issue_id` to match.)

- [ ] **Step 2: Write the todo file**

```markdown
---
status: pending
priority: p3
issue_id: "308"
tags: [web, react, home]
dependencies: []
---

# Personalize Home with a real activity feed for logged-in users

## Problem

Canopy PR 4 restyled Home onto the new primitives (`HeroCard` + `Tile`/`Card`
feature row) but deliberately kept it a static marketing page — same hero and
three feature cards for every visitor, logged in or not. The parent spec's
per-area treatment (`docs/superpowers/specs/2026-08-13-canopy-design.md` §6)
called for "activity modules" on Home; PR 4's own spec
(`docs/superpowers/specs/2026-08-16-canopy-areas-design.md` §2) deferred that
explicitly to avoid scope creep — no new backend endpoints, no client-side
data composition, in a PR that was otherwise a pure restyle.

## Findings

- `web/src/pages/HomePage.tsx` has zero personalization today — no
  `useAuth()` branch, no data fetching beyond the static feature-card copy.
- The closest existing precedent for a personalized "recent activity"
  surface is the forum's `topics/recent/` endpoint (built in PR 2.5) and
  `me/stats/` (also PR 2.5) — either could seed a Home activity module
  without new backend work, or a genuinely new aggregation endpoint could be
  built (closer to how PR 2.5 added `me/stats` and `topics/recent`
  specifically for this kind of surface).
- Garden (`plantIdService.getMyPlants`) and Diagnose have no "recent"
  variant today — only full paginated history.

## Recommended Action

1. Decide the personalization split: reuse existing endpoints
   (`topics/recent/`, `me/stats/`) client-side, or add new aggregation
   (closer to `me/stats`'s shape) if a cross-domain "recent identifications +
   recent garden saves + recent forum activity" feed is wanted.
2. Home renders the activity modules only when `useAuth().isAuthenticated`
   is true; anonymous visitors keep the current static marketing hero and
   feature cards unchanged.
3. Follow the spec's brainstorming path for this (this is new scope, not a
   restyle) — brainstorm → design doc → plan, same as PR 4 itself.

## Acceptance Criteria

- [ ] Logged-in Home shows real recent activity (specifics decided during
      brainstorming for this todo).
- [ ] Logged-out Home is unchanged from PR 4's restyle.
- [ ] No new backend work beyond what's decided in Recommended Action step 1.

## Work Log

### 2026-08-16 - Filed

- Deferred out of Canopy PR 4 (`docs/superpowers/specs/2026-08-16-canopy-areas-design.md`
  §2, §8) to keep that PR a pure restyle with no new data dependencies.
```

- [ ] **Step 3: Commit**

```bash
git add todos/308-pending-p3-home-activity-feed.md
git commit -m "docs: file todo 308 — Home activity feed deferred from Canopy PR 4"
```

---

## Task 7: `playwright.config.ts` wiring + public e2e spec

**Files:**

- Modify: `web/playwright.config.ts`
- Create: `web/e2e/canopy-areas.spec.ts`

**Interfaces:**

- Consumes: the restyled `HomePage` (Task 1) and `IdentifyPage`/`IdentificationResults` (Task 3) — this task must run after both.
- Produces: nothing consumed by Task 8, but Task 8 follows the same `playwright.config.ts` wiring pattern this task establishes for the *authenticated* side.

- [ ] **Step 1: Add the new authenticated spec filename to `playwright.config.ts` now, even though the file doesn't exist yet**

This task only adds the **public** spec, but the config edit for *both* new files (spec §6.2 requires editing the same two regexes for the authenticated file Task 8 adds) is one coherent change — doing it once here avoids a second edit to the same lines in Task 8. In `web/playwright.config.ts`, every project's `testIgnore` currently reads:

```ts
      testIgnore: /(auth\.setup|forum-authenticated\.spec)\.js/,
```

(five occurrences: `chromium`, `firefox`, `webkit`, `Mobile Chrome`, `Mobile Safari`). Change each to also exclude the new authenticated spec:

```ts
      testIgnore: /(auth\.setup|forum-authenticated\.spec|canopy-areas-authenticated\.spec)\.js/,
```

And the two authenticated projects' `testMatch`:

```ts
      testMatch: /(forum-authenticated|auth)\.spec\.js/,
```

becomes:

```ts
      testMatch: /(forum-authenticated|canopy-areas-authenticated|auth)\.spec\.js/,
```

(two occurrences: `chromium-authenticated`, `firefox-authenticated`). The new **public** `canopy-areas.spec.ts` needs no config change — `.ts` files already run under the default `chromium`/`firefox`/`webkit`/mobile projects with no extra wiring, same as `forum-golden-path.spec.ts`.

- [ ] **Step 2: Write `web/e2e/canopy-areas.spec.ts`**

```ts
import { test, expect } from '@playwright/test';

/**
 * Public Canopy PR 4 smoke coverage — Home and Identify, both unauthenticated
 * routes (App.tsx route audit, spec §1). Identify's network calls are mocked;
 * no live Plant.id/PlantNet spend (spec §6.2).
 */

test.describe('Home', () => {
  test('renders the hero and feature-card links', async ({ page }) => {
    await page.goto('/');

    await expect(
      page.getByRole('heading', { level: 2, name: /discover the world of plants/i })
    ).toBeVisible();

    const getStarted = page.getByRole('link', { name: /get started/i });
    await expect(getStarted).toHaveAttribute('href', '/identify');

    await expect(page.getByRole('link', { name: /discussion forum/i })).toHaveAttribute(
      'href',
      '/forum'
    );
  });
});

test.describe('Identify', () => {
  test('upload → mocked result → confidence pill renders', async ({ page }) => {
    await page.route('**/api/v1/plant-identification/identify/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          plant_name: 'Swiss cheese plant',
          confidence: 0.82,
          source: 'plant_id',
          suggestions: [
            {
              plant_name: 'Swiss cheese plant',
              scientific_name: 'Monstera deliciosa',
              probability: 0.82,
              confidence: 0.82,
              source: 'plant_id',
            },
          ],
        }),
      });
    });

    await page.goto('/identify');

    await page.setInputFiles(
      'input[type="file"]',
      { name: 'plant.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('fake-image-bytes') }
    );
    await page.getByRole('button', { name: /identify plant/i }).click();

    await expect(page.getByText('Swiss cheese plant')).toBeVisible();
    await expect(page.getByText('82%')).toBeVisible();
  });
});
```

- [ ] **Step 3: Run the new spec alone to confirm it passes**

```bash
cd web && ./node_modules/.bin/playwright test e2e/canopy-areas.spec.ts --project=chromium
```

(Direct binary — RTK mangles Playwright's filter args, per project memory.) Expected: 2 passed. If the file-input selector doesn't resolve (the real `<input type="file">` inside `FileUpload` has `id="file-upload"` but no stable `data-testid`), fall back to `page.getByLabel(/upload plant image/i)` — the `aria-label` set in Task 2 is stable across the restyle.

- [ ] **Step 4: Re-run the full baseline set to confirm nothing else regressed**

```bash
cd web && ./node_modules/.bin/playwright test --project=chromium e2e/command-palette.spec.ts e2e/green-thumb-theme.spec.ts e2e/canopy-areas.spec.ts
```

Expected: all passing (the two baseline-clean specs from the spec's §6.3 recording, plus the two new tests here). `forum-golden-path.spec.ts`/`forum-responsive.spec.ts` are deliberately excluded — pre-existing failure, spec §6.3/§6.4.

- [ ] **Step 5: Commit**

```bash
git add web/playwright.config.ts web/e2e/canopy-areas.spec.ts
git commit -m "test(canopy): add public e2e smoke coverage for Home + Identify, wire config for the authenticated spec"
```

---

## Task 8: Authenticated e2e spec (Garden + Diagnose)

**Files:**

- Create: `web/e2e/canopy-areas-authenticated.spec.js`

**Interfaces:**

- Consumes: the restyled `MyPlantsPage` (Task 5) and `DiseaseDiagnosePage`/`DiseaseResultsList` (Task 4), and the `playwright.config.ts` wiring from Task 7 Step 1 (must already be in place — this task's spec file is invisible to Playwright without it).
- Produces: nothing consumed by later tasks (this is the last task in the plan).

**Prerequisite (spec §6.2, confirmed by reading `plantIdService.ts`):** `POST /api/v1/plant-identification/plants/` requires an existing `UserPlantCollection` for the user — `beforeAll` must create one via `POST /api/v1/users/collections/` before seeding a plant, since neither `create_test_user` nor any backend signal creates one automatically. This keeps the "no backend changes" decision intact (spec §5) — the collection is created through the same public API the app itself uses, not by touching backend fixture code. (corrected during implementation — the real route is `/api/v1/auth/me/collections/`; see Task 8's shipped `web/e2e/canopy-areas-authenticated.spec.js`.)

- [ ] **Step 1: Confirm the local prerequisites are met**

```bash
cd backend && source venv/bin/activate && python manage.py create_test_user && python manage.py seed_default_forum
```

(Same prerequisite `forum-authenticated.spec.js` already documents in its header comment — the authenticated Playwright project depends on `e2e_test_user` existing regardless of which spec runs.)

- [ ] **Step 2: Write `web/e2e/canopy-areas-authenticated.spec.js`**

```js
import { test, expect } from '@playwright/test';

/**
 * Authenticated Canopy PR 4 smoke coverage — Garden and Diagnose, both behind
 * ProtectedLayout (App.tsx route audit, spec §1). Runs as the seeded
 * e2e_test_user (auth.setup.js → storageState, same as forum-authenticated.spec.js).
 * Diagnose's network calls are mocked; no live disease-service spend (spec §6.2).
 *
 * Garden fixture data is seeded via direct API calls here, not through the
 * Identify UI — see the beforeAll below. Left-behind data across runs is an
 * accepted tradeoff, same as forum-authenticated.spec.js.
 */

test.describe('Garden', () => {
  test.beforeAll(async ({ request }) => {
    // Ensure a UserPlantCollection exists (plantIdService.saveToCollection's
    // real prerequisite) before seeding a plant into it.
    const collections = await request.get('/api/v1/users/collections/');
    const existing = await collections.json();
    let collectionId = existing[0]?.id;

    if (!collectionId) {
      const created = await request.post('/api/v1/users/collections/', {
        data: { name: 'My Plants' },
      });
      const collection = await created.json();
      collectionId = collection.id;
    }

    await request.post('/api/v1/plant-identification/plants/', {
      data: {
        collection: collectionId,
        nickname: 'E2E fixture rose',
        notes: 'Seeded by canopy-areas-authenticated.spec.js',
        care_instructions_json: {
          confidence: 0.9,
          common_names: ['Fixture Rose'],
          watering: 'Water weekly',
          source: 'plant_id',
        },
      },
    });
  });

  test('populated grid renders a saved plant', async ({ page }) => {
    await page.goto('/my-plants');

    await expect(page.getByText('E2E fixture rose')).toBeVisible();
    await expect(page.getByText('90%')).toBeVisible();
  });
});

test.describe('Diagnose', () => {
  test('form submit → mocked results render', async ({ page }) => {
    await page.route('**/api/v1/plant-identification/disease-requests/', async (route) => {
      if (route.request().method() !== 'POST') return route.continue();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ request_id: 'e2e-r1', status: 'diagnosed' }),
      });
    });
    await page.route(
      '**/api/v1/plant-identification/disease-requests/e2e-r1/results/',
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            request_id: 'e2e-r1',
            status: 'diagnosed',
            results: [
              {
                id: 1,
                uuid: 'u1',
                request_id: 'e2e-r1',
                suggested_disease_name: 'Black Spot',
                suggested_disease_type: 'fungal',
                confidence_score: 0.88,
                confidence_percentage: 88,
                diagnosis_source: 'api_plant_health',
                severity_assessment: 'moderate',
                symptoms_identified: 'black spots',
                recommended_treatments: 'fungicide',
                immediate_actions: 'remove affected leaves',
                notes: '',
                is_primary: true,
                display_name: 'Black Spot',
              },
            ],
          }),
        });
      }
    );

    await page.goto('/diagnose');

    await page.setInputFiles(
      'input[type="file"]',
      { name: 'leaf.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('fake-image-bytes') }
    );
    await page.getByLabel(/symptoms/i).fill('black spots on leaves');
    await page.getByRole('button', { name: /^diagnose$/i }).click();

    await expect(page.getByText('Black Spot')).toBeVisible();
    await expect(page.getByText('88%')).toBeVisible();
  });
});
```

- [ ] **Step 3: Run the new spec alone to confirm it passes**

```bash
cd web && ./node_modules/.bin/playwright test e2e/canopy-areas-authenticated.spec.js --project=chromium-authenticated
```

Expected: 2 passed. If `request.get('/api/v1/users/collections/')` 401s, the `request` fixture on `chromium-authenticated` isn't inheriting the project's `storageState` automatically (Playwright's `request` fixture uses the same storage state as the project by default, but confirm — if it doesn't, switch to reading `.auth/user.json` explicitly via `request.newContext({ storageState: '.auth/user.json' })` in `beforeAll`).

- [ ] **Step 4: Run the full authenticated project to confirm `forum-authenticated.spec.js` still passes alongside the new file**

```bash
cd web && ./node_modules/.bin/playwright test --project=chromium-authenticated
```

Expected: all passing (the pre-existing forum lifecycle spec plus this task's 2 new tests) — confirms the `playwright.config.ts` wiring from Task 7 didn't break the existing authenticated spec's matching.

- [ ] **Step 5: Commit**

```bash
git add web/e2e/canopy-areas-authenticated.spec.js
git commit -m "test(canopy): add authenticated e2e smoke coverage for Garden + Diagnose"
```

---

## Final gate (after all 8 tasks)

Not a task of its own — run once, after Task 8, as the PR-level check before requesting review (spec §6.4):

```bash
cd web
npm test                    # full Vitest suite — expect 895 + this plan's new tests, 0 failing
npm run type-check           # zero errors
npm run build                 # must succeed
./node_modules/.bin/playwright test --project=chromium e2e/command-palette.spec.ts e2e/green-thumb-theme.spec.ts e2e/canopy-areas.spec.ts
./node_modules/.bin/playwright test --project=chromium-authenticated
```

Then: `kimi-review --base main --profile plant_id --rules react,typescript`, manual visual QA pass (spec §6.4 — real login, add garden plants, run a real identify + diagnose, screenshot dark + light), and open the PR for user review per repo convention (no auto-merge without review, per project memory).
