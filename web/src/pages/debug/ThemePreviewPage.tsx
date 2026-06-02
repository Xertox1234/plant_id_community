// Dev-only probe: exercises the core token utilities so Tailwind generates
// them, and gives Playwright stable testids to assert resolution against.

const PALETTES = ['loam', 'garden', 'forest', 'heritage'] as const;
const DENSITIES = ['comfortable', 'cozy', 'compact'] as const;
const MODES = ['light', 'dark'] as const;

function HtmlProbe() {
  return (
    <div className="bg-surface text-ink p-screen min-h-screen">
      <div data-testid="probe-surface" className="bg-surface p-card rounded-md shadow-2">
        surface
      </div>
      <div data-testid="probe-surface-2" className="bg-surface-2">
        surface-2
      </div>
      <div data-testid="probe-clay" className="bg-clay text-on-clay">
        clay
      </div>
      <div data-testid="probe-primary" className="bg-primary text-on-primary">
        primary
      </div>
      <div data-testid="probe-secondary" className="bg-secondary">
        secondary
      </div>
      <div data-testid="probe-tertiary" className="bg-tertiary">
        tertiary
      </div>
      <p data-testid="probe-ink" className="text-ink">
        ink
      </p>
      <p data-testid="probe-ink-2" className="text-ink-2">
        ink-2
      </p>
      <p data-testid="probe-ink-3" className="text-ink-3">
        ink-3
      </p>
      <p data-testid="probe-leaf" className="text-leaf">
        leaf
      </p>
      <p data-testid="probe-berry" className="text-berry">
        berry
      </p>
      <p data-testid="probe-sky" className="text-sky">
        sky
      </p>
      <p data-testid="probe-error" className="text-error">
        error
      </p>
      <div data-testid="probe-line" className="border border-line">
        line
      </div>
      <div data-testid="probe-pad" className="p-card">
        pad
      </div>
      <div data-testid="probe-alpha" className="bg-clay/10">
        alpha
      </div>
      <h2 data-testid="probe-display" className="gt-display">
        Green Thumb
      </h2>
      <span data-testid="probe-mono" className="font-mono italic">
        Monstera deliciosa
      </span>
    </div>
  );
}

function Swatches() {
  return (
    <div className="space-y-1">
      <h3 className="gt-h3">Aa Bricolage</h3>
      <div className="flex gap-1">
        <span className="rounded-sm bg-clay px-2 text-on-clay">clay</span>
        <span className="rounded-sm bg-primary px-2 text-on-primary">moss</span>
        <span className="rounded-sm bg-tertiary px-2">honey</span>
      </div>
      <div className="flex gap-1 text-xs">
        <span className="text-leaf">leaf</span>
        <span className="text-berry">berry</span>
        <span className="text-sky">sky</span>
        <span className="text-error">error</span>
      </div>
      <p className="font-mono italic text-ink-2">Monstera deliciosa</p>
      <p className="text-ink-3">muted ink-3</p>
    </div>
  );
}

export default function ThemePreviewPage() {
  return (
    <div className="min-h-screen bg-neutral-100 p-4">
      <HtmlProbe />
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {PALETTES.flatMap((palette) =>
          DENSITIES.flatMap((density) =>
            MODES.map((mode) => (
              <div
                key={`${palette}-${density}-${mode}`}
                data-testid="combo-card"
                data-palette={palette}
                data-density={density}
                data-mode={mode}
                className="bg-surface text-ink p-card rounded-md shadow-2 border border-line"
              >
                <p className="text-[10px] uppercase tracking-wide text-ink-3">
                  {palette}/{density}/{mode}
                </p>
                <Swatches />
              </div>
            ))
          )
        )}
      </div>
    </div>
  );
}
