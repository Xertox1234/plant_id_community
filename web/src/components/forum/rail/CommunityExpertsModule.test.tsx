import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import CommunityExpertsModule from './CommunityExpertsModule';
import type { ForumExpert } from '../../../types/forum';

const mockFetchExperts = vi.fn();
vi.mock('../../../services/forumService', () => ({
  fetchExperts: (...args: unknown[]) => mockFetchExperts(...args),
}));

function expert(overrides: Partial<ForumExpert> = {}): ForumExpert {
  return {
    username: 'irisd',
    display_name: 'Iris Delgado',
    avatar: null,
    trust_level: 3,
    title: '',
    ...overrides,
  };
}

function renderModule() {
  return render(
    <MemoryRouter>
      <CommunityExpertsModule />
    </MemoryRouter>
  );
}

describe('CommunityExpertsModule', () => {
  // Block body, not an implicit-return arrow — see FromTheBlogModule.test.tsx's
  // note: under Vitest 4's global `mockReset: true`, an implicit-return
  // `beforeEach` registers as a teardown callback and replays whatever
  // implementation the test just configured (including a rejection) after
  // the test has already passed.
  beforeEach(() => {
    mockFetchExperts.mockReset();
  });

  it('renders experts as links to their profile, using the served title', async () => {
    mockFetchExperts.mockResolvedValue([
      expert({ username: 'irisd', display_name: 'Iris Delgado', title: 'Plant Pathologist' }),
    ]);
    renderModule();

    const link = await screen.findByRole('link', { name: /iris delgado/i });
    expect(link).toHaveAttribute('href', '/forum/users/irisd');
    expect(screen.getByText('Plant Pathologist')).toBeInTheDocument();
    expect(screen.getByText('Community experts')).toBeInTheDocument();
  });

  it('falls back to the trust-level label when the server sends no title', async () => {
    mockFetchExperts.mockResolvedValue([expert({ title: '', trust_level: 3 })]);
    renderModule();

    await screen.findByText('Iris Delgado');
    expect(screen.getByText('Regular')).toBeInTheDocument();
  });

  it('falls back to "New" (trust_level 0, shared TRUST_LEVEL_LABELS) when trust_level is null', async () => {
    mockFetchExperts.mockResolvedValue([expert({ title: '', trust_level: null })]);
    renderModule();

    await screen.findByText('Iris Delgado');
    expect(screen.getByText('New')).toBeInTheDocument();
  });

  it('falls back to the generic "Member" label for a trust_level outside the known map', async () => {
    mockFetchExperts.mockResolvedValue([expert({ title: '', trust_level: 99 })]);
    renderModule();

    await screen.findByText('Iris Delgado');
    expect(screen.getByText('Member')).toBeInTheDocument();
  });

  it('renders nothing when there are no experts', async () => {
    mockFetchExperts.mockResolvedValue([]);
    const { container } = renderModule();

    await waitFor(() => expect(mockFetchExperts).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing on fetch error', async () => {
    mockFetchExperts.mockRejectedValue(new Error('nope'));
    const { container } = renderModule();

    await waitFor(() => expect(mockFetchExperts).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('uses the server-supplied avatar over the specimen fallback when present', async () => {
    mockFetchExperts.mockResolvedValue([
      expert({ username: 'irisd', avatar: 'https://example.com/avatars/irisd.jpg' }),
    ]);
    renderModule();

    const link = await screen.findByRole('link', { name: /iris delgado/i });
    expect(link.querySelector('img')).toHaveAttribute(
      'src',
      'https://example.com/avatars/irisd.jpg'
    );
  });

  it('renders no presence dot — each row is exactly an avatar image plus its name/title text', async () => {
    mockFetchExperts.mockResolvedValue([
      expert({ username: 'irisd', display_name: 'Iris Delgado', title: 'Plant Pathologist' }),
    ]);
    renderModule();

    const link = await screen.findByRole('link', { name: /iris delgado/i });
    const row = link.closest('li') as HTMLElement;
    // Structural assertion, not a class-name search for a dot: the row's only
    // elements are the avatar <img> and exactly two text <span>s (name,
    // title/trust-label) nested inside the wrapper span. A presence dot would
    // be an additional element, so this fails the moment one is added without
    // the module's honesty comment being revisited (spec §9 / todo 301).
    expect(row.querySelectorAll('img')).toHaveLength(1);
    expect(row.querySelectorAll('span')).toHaveLength(3);
  });
});
