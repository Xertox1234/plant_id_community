/**
 * SettingsPage Component
 *
 * Application settings page — theme controls (palette, density, dark mode).
 * Allows users to configure app preferences and notifications.
 *
 * Features (planned):
 * - Email notifications preferences
 * - Privacy settings
 * - Theme preferences (palette / density / dark mode) ← LIVE in Phase A
 * - Language selection
 * - Account deletion
 */
import { useTheme, type Palette, type Density } from '../contexts/ThemeContext';
import Eyebrow from '../components/ui/Eyebrow';

const PALETTE_SWATCH: Record<Palette, string> = {
  loam: '#C9542A',
  garden: '#D86B2C',
  forest: '#F0935A',
  heritage: '#B0481E',
};
const DENSITIES: Density[] = ['comfortable', 'cozy', 'compact'];

function ThemeControls() {
  const { palette, density, mode, setPalette, setDensity, toggleMode } = useTheme();
  return (
    <div className="space-y-8 p-screen">
      <section>
        <Eyebrow>Appearance</Eyebrow>
        <button
          onClick={toggleMode}
          className="mt-2 rounded-pill border border-line px-4 py-2 text-ink"
        >
          {mode === 'dark' ? 'Switch to Light' : 'Switch to Dark'}
        </button>
      </section>

      <section>
        <Eyebrow>Palette</Eyebrow>
        <div className="mt-2 flex flex-wrap gap-2">
          {(Object.keys(PALETTE_SWATCH) as Palette[]).map((p) => (
            <button
              key={p}
              onClick={() => setPalette(p)}
              aria-pressed={palette === p}
              className={`flex items-center gap-2 rounded-sm px-3 py-2 capitalize ${
                palette === p ? 'border-2 border-primary font-bold' : 'border border-line'
              }`}
            >
              <span
                aria-hidden="true"
                className="h-4 w-4 rounded-full"
                style={{ background: PALETTE_SWATCH[p] }}
              />
              {p}
            </button>
          ))}
        </div>
      </section>

      <section>
        <Eyebrow>Density</Eyebrow>
        <div className="mt-2 inline-flex rounded-pill border border-line p-1">
          {DENSITIES.map((d) => (
            <button
              key={d}
              onClick={() => setDensity(d)}
              aria-pressed={density === d}
              className={`rounded-pill px-4 py-1 capitalize ${
                density === d ? 'bg-primary text-on-primary' : 'text-ink-3'
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-ink">Settings</h1>
        <p className="mt-2 text-ink-3">Manage your application preferences and account settings</p>
      </div>

      {/* Theme Controls */}
      <ThemeControls />
    </div>
  );
}
