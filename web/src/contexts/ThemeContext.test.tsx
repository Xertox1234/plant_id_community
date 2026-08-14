// web/src/contexts/ThemeContext.test.tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider, useTheme } from './ThemeContext';

function Harness() {
  const { density, mode, setDensity, toggleMode } = useTheme();
  return (
    <div>
      <span data-testid="state">{`${density}/${mode}`}</span>
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
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
  });

  it('applies defaults to <html> on mount', () => {
    renderHarness();
    expect(screen.getByTestId('state')).toHaveTextContent('cozy/dark');
    expect(document.documentElement).toHaveAttribute('data-density', 'cozy');
    expect(document.documentElement).toHaveAttribute('data-mode', 'dark');
    expect(document.documentElement).not.toHaveAttribute('data-palette');
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
    expect(document.documentElement).toHaveAttribute('data-mode', 'light');
    expect(localStorage.getItem('gt-mode')).toBe('light');
  });

  it('reads persisted values on mount', () => {
    localStorage.setItem('gt-mode', 'light');
    renderHarness();
    expect(screen.getByTestId('state')).toHaveTextContent('cozy/light');
    expect(document.documentElement).toHaveAttribute('data-mode', 'light');
  });

  it('ignores an invalid stored value and falls back to default', () => {
    localStorage.setItem('gt-density', 'ultrawide'); // not a valid Density
    renderHarness();
    expect(screen.getByTestId('state')).toHaveTextContent('cozy/dark');
    expect(document.documentElement).toHaveAttribute('data-density', 'cozy');
  });

  it('clears a stale palette attribute and localStorage key from prior sessions', () => {
    document.documentElement.dataset.palette = 'forest';
    localStorage.setItem('gt-palette', 'forest');
    renderHarness();
    expect(document.documentElement).not.toHaveAttribute('data-palette');
    expect(localStorage.getItem('gt-palette')).toBeNull();
  });
});
