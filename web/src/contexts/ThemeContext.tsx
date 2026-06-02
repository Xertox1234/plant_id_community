import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

export type Palette = 'loam' | 'garden' | 'forest' | 'heritage';
export type Density = 'comfortable' | 'cozy' | 'compact';
export type Mode = 'light' | 'dark';

interface ThemeContextValue {
  palette: Palette;
  density: Density;
  mode: Mode;
  setPalette: (p: Palette) => void;
  setDensity: (d: Density) => void;
  setMode: (m: Mode) => void;
  toggleMode: () => void;
}

const PALETTES: readonly Palette[] = ['loam', 'garden', 'forest', 'heritage'];
const DENSITIES: readonly Density[] = ['comfortable', 'cozy', 'compact'];
const MODES: readonly Mode[] = ['light', 'dark'];
const KEYS = { palette: 'gt-palette', density: 'gt-density', mode: 'gt-mode' } as const;

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function read<T extends string>(key: string, fallback: T, valid: readonly T[]): T {
  try {
    const v = localStorage.getItem(key);
    return v && (valid as readonly string[]).includes(v) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}
function persist(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore quota/denied */
  }
}

interface ThemeProviderProps {
  children: ReactNode;
}
export function ThemeProvider({ children }: ThemeProviderProps) {
  const [palette, setPaletteState] = useState<Palette>(() => read(KEYS.palette, 'loam', PALETTES));
  const [density, setDensityState] = useState<Density>(() => read(KEYS.density, 'cozy', DENSITIES));
  const [mode, setModeState] = useState<Mode>(() => read(KEYS.mode, 'light', MODES));

  useEffect(() => {
    document.documentElement.dataset.palette = palette;
  }, [palette]);
  useEffect(() => {
    document.documentElement.dataset.density = density;
  }, [density]);
  useEffect(() => {
    document.documentElement.dataset.mode = mode;
  }, [mode]);

  const setPalette = useCallback((p: Palette) => {
    setPaletteState(p);
    persist(KEYS.palette, p);
  }, []);
  const setDensity = useCallback((d: Density) => {
    setDensityState(d);
    persist(KEYS.density, d);
  }, []);
  const setMode = useCallback((m: Mode) => {
    setModeState(m);
    persist(KEYS.mode, m);
  }, []);
  const toggleMode = useCallback(() => {
    setModeState((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      persist(KEYS.mode, next);
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider
      value={{ palette, density, mode, setPalette, setDensity, setMode, toggleMode }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

// Only theme-control UI (Settings, theme toggle) uses this. Everything else
// renders correctly from the :root default with no provider (learning A).
// eslint-disable-next-line react-refresh/only-export-components
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
