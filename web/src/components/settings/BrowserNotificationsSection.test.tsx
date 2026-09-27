import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const service = vi.hoisted(() => ({
  getBrowserPushState: vi.fn(),
  enableBrowserPush: vi.fn(),
  disableBrowserPush: vi.fn(),
}));
vi.mock('../../services/pushService', () => service);

import BrowserNotificationsSection from './BrowserNotificationsSection';

describe('BrowserNotificationsSection', () => {
  it('turns browser notifications on', async () => {
    service.getBrowserPushState.mockResolvedValue('off');
    service.enableBrowserPush.mockResolvedValue('on');
    render(<BrowserNotificationsSection />);

    fireEvent.click(await screen.findByRole('button', { name: 'Turn on for this browser' }));

    expect(await screen.findByRole('button', { name: 'Turn off on this browser' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });

  it('explains a blocked permission and offers no button', async () => {
    service.getBrowserPushState.mockResolvedValue('denied');
    render(<BrowserNotificationsSection />);

    expect(await screen.findByText(/blocked for this site/)).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('says so when the server has no key pair', async () => {
    service.getBrowserPushState.mockResolvedValue('unavailable');
    render(<BrowserNotificationsSection />);

    expect(
      await screen.findByText('Browser notifications are not available yet.')
    ).toBeInTheDocument();
  });

  it('shows an error and keeps the state when turning on fails', async () => {
    service.getBrowserPushState.mockResolvedValue('off');
    service.enableBrowserPush.mockRejectedValue(new Error('boom'));
    render(<BrowserNotificationsSection />);

    fireEvent.click(await screen.findByRole('button', { name: 'Turn on for this browser' }));

    await waitFor(() =>
      expect(screen.getByText("That didn't work. Please try again.")).toBeInTheDocument()
    );
    expect(screen.getByRole('button', { name: 'Turn on for this browser' })).toBeEnabled();
  });
});
