import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LiveUpdatesSection from './LiveUpdatesSection';
import { LIVE_UPDATES_KEY } from '../../utils/liveUpdatesStore';

describe('LiveUpdatesSection', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders a "Live updates" switch, on by default', () => {
    render(<LiveUpdatesSection />);
    expect(screen.getByRole('switch', { name: /live updates/i })).toBeChecked();
  });

  it('turning it off stores off', async () => {
    render(<LiveUpdatesSection />);
    await userEvent.click(screen.getByRole('switch', { name: /live updates/i }));
    expect(screen.getByRole('switch', { name: /live updates/i })).not.toBeChecked();
    expect(localStorage.getItem(LIVE_UPDATES_KEY)).toBe('off');
  });

  it('says the setting is for this browser', () => {
    render(<LiveUpdatesSection />);
    expect(screen.getByText(/in this browser/i)).toBeInTheDocument();
  });
});
