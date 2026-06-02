// Dev-only probe: exercises the core token utilities so Tailwind generates
// them, and gives Playwright stable testids to assert resolution against.
export default function ThemePreviewPage() {
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
