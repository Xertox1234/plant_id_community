import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ProfilePage from './ProfilePage';
import * as profileService from '../services/profileService';
import type { UserProfile } from '../types/auth';

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 7, email: 'ada@example.com', name: 'Ada' } }),
}));

vi.mock('../services/profileService', () => ({
  fetchProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

const profile: UserProfile = {
  id: 7,
  username: 'ada',
  email: 'ada@example.com',
  first_name: 'Ada',
  last_name: 'Lovelace',
  display_name: 'Ada Lovelace',
  bio: 'Ferns, mostly.',
  location: 'London',
  website: '',
};

describe('ProfilePage (web dead-code audit M3)', () => {
  beforeEach(() => {
    vi.mocked(profileService.fetchProfile).mockReset().mockResolvedValue(profile);
    vi.mocked(profileService.updateProfile).mockReset();
  });

  it('loads the profile into an editable form, with email read-only', async () => {
    render(<ProfilePage />);

    expect(await screen.findByLabelText('First name')).toHaveValue('Ada');
    expect(screen.getByLabelText('Last name')).toHaveValue('Lovelace');
    expect(screen.getByLabelText('Bio')).toHaveValue('Ferns, mostly.');
    expect(screen.getByLabelText('Location')).toHaveValue('London');
    // Email is shown but is not an input: changing it needs re-verification.
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    expect(screen.getAllByText('ada@example.com').length).toBeGreaterThan(0);
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
  });

  it('keeps Save disabled until something changes', async () => {
    render(<ProfilePage />);
    await screen.findByLabelText('First name');
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();

    await userEvent.type(screen.getByLabelText('Location'), ', UK');
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeEnabled();
  });

  it('sends only the changed fields and confirms the save', async () => {
    vi.mocked(profileService.updateProfile).mockResolvedValue({
      ...profile,
      bio: 'Ferns and mosses.',
    });
    render(<ProfilePage />);
    const bio = await screen.findByLabelText('Bio');

    await userEvent.clear(bio);
    await userEvent.type(bio, 'Ferns and mosses.');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() =>
      expect(profileService.updateProfile).toHaveBeenCalledWith({ bio: 'Ferns and mosses.' })
    );
    expect(await screen.findByText('Profile saved.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  });

  it('shows the server error when a save is rejected', async () => {
    vi.mocked(profileService.updateProfile).mockRejectedValue(
      new Error('website: Enter a valid URL.')
    );
    render(<ProfilePage />);
    const website = await screen.findByLabelText('Website');

    await userEvent.type(website, 'not a url');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('website: Enter a valid URL.')).toBeInTheDocument();
  });

  it('shows an error instead of the form when the profile cannot load', async () => {
    vi.mocked(profileService.fetchProfile).mockRejectedValue(new Error('HTTP 500'));
    render(<ProfilePage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 500');
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
  });
});
