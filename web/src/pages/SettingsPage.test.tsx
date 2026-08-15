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
    delete document.documentElement.dataset.density;
    delete document.documentElement.dataset.mode;
  });

  it('renders no palette controls', () => {
    renderPage();
    expect(screen.queryByRole('button', { name: /loam/i })).toBeNull();
  });

  it('changing density applies it to <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /compact/i }));
    expect(document.documentElement).toHaveAttribute('data-density', 'compact');
  });

  it('dark toggle flips mode on <html>', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    expect(document.documentElement).toHaveAttribute('data-mode', 'light');
  });
});
