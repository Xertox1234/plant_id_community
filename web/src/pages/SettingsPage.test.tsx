// web/src/pages/SettingsPage.test.tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import SettingsPage from './SettingsPage';

const renderPage = () =>
  render(
    <ThemeProvider>
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    </ThemeProvider>
  );

describe('SettingsPage theme controls', () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.palette;
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
  });

  it('renders four palette swatches', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /loam/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /garden/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /forest/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /heritage/i })).toBeInTheDocument();
  });

  it('clicking a swatch applies the palette to <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /forest/i }));
    expect(document.documentElement).toHaveAttribute('data-palette', 'forest');
    expect(screen.getByRole('button', { name: /forest/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /loam/i })).toHaveAttribute('aria-pressed', 'false');
  });

  it('changing density applies it to <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /compact/i }));
    expect(document.documentElement).toHaveAttribute('data-density', 'compact');
  });

  it('dark toggle flips mode on <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /dark/i }));
    expect(document.documentElement).toHaveAttribute('data-mode', 'dark');
  });
});
