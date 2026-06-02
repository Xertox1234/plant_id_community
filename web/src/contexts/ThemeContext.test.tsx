// web/src/contexts/ThemeContext.test.tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider, useTheme } from './ThemeContext';

function Harness() {
  const { palette, density, mode, setPalette, setDensity, toggleMode } = useTheme();
  return (
    <div>
      <span data-testid="state">{`${palette}/${density}/${mode}`}</span>
      <button onClick={() => setPalette('forest')}>forest</button>
      <button onClick={() => setDensity('compact')}>compact</button>
      <button onClick={toggleMode}>toggle</button>
    </div>
  );
}
const renderHarness = () =>
  render(
    <ThemeProvider>
      <Harness />
    </ThemeProvider>
  );

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.palette;
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
  });

  it('applies defaults to <html> on mount', () => {
    renderHarness();
    expect(screen.getByTestId('state')).toHaveTextContent('loam/cozy/light');
    expect(document.documentElement).toHaveAttribute('data-palette', 'loam');
    expect(document.documentElement).toHaveAttribute('data-density', 'cozy');
    expect(document.documentElement).toHaveAttribute('data-mode', 'light');
  });

  it('setPalette updates attribute and persists', async () => {
    renderHarness();
    await userEvent.click(screen.getByText('forest'));
    expect(document.documentElement).toHaveAttribute('data-palette', 'forest');
    expect(localStorage.getItem('gt-palette')).toBe('forest');
  });

  it('setDensity updates attribute and persists', async () => {
    renderHarness();
    await userEvent.click(screen.getByText('compact'));
    expect(document.documentElement).toHaveAttribute('data-density', 'compact');
    expect(localStorage.getItem('gt-density')).toBe('compact');
  });

  it('toggleMode flips mode and persists', async () => {
    renderHarness();
    await userEvent.click(screen.getByText('toggle'));
    expect(document.documentElement).toHaveAttribute('data-mode', 'dark');
    expect(localStorage.getItem('gt-mode')).toBe('dark');
  });

  it('reads persisted values on mount', () => {
    localStorage.setItem('gt-palette', 'garden');
    renderHarness();
    expect(screen.getByTestId('state')).toHaveTextContent('garden/cozy/light');
    expect(document.documentElement).toHaveAttribute('data-palette', 'garden');
  });

  it('ignores an invalid stored value and falls back to default', () => {
    localStorage.setItem('gt-palette', 'ultraviolet'); // not a valid Palette
    renderHarness();
    expect(screen.getByTestId('state')).toHaveTextContent('loam/cozy/light');
    expect(document.documentElement).toHaveAttribute('data-palette', 'loam');
  });
});
