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

  it('renders no presence dot for an offline expert (online: false)', async () => {
    mockFetchExperts.mockResolvedValue([
      expert({ username: 'irisd', display_name: 'Iris Delgado', online: false }),
    ]);
    renderModule();

    const link = await screen.findByRole('link', { name: /iris delgado/i });
    const row = link.closest('li') as HTMLElement;
    expect(row.querySelectorAll('.bg-ok')).toHaveLength(0);
    expect(screen.getByText('Community experts')).toBeInTheDocument();
  });

  it('renders no presence dot and no online claim when `online` is absent (todo 301 AC3)', async () => {
    // Deliberately omits `online` entirely — not `online: false` — as a
    // distinct fixture from the offline test above, so a future change that
    // special-cases `undefined` differently from `false` gets caught here.
    // Server/client version skew is the real-world case this covers.
    mockFetchExperts.mockResolvedValue([
      { username: 'irisd', display_name: 'Iris Delgado', avatar: null, trust_level: 3, title: '' },
    ]);
    renderModule();

    const link = await screen.findByRole('link', { name: /iris delgado/i });
    const row = link.closest('li') as HTMLElement;
    expect(row.querySelectorAll('.bg-ok')).toHaveLength(0);
    expect(screen.getByText('Community experts')).toBeInTheDocument();
    expect(screen.queryByText('Experts online')).not.toBeInTheDocument();
  });

  it('renders a presence dot and switches the title when an expert is online', async () => {
    mockFetchExperts.mockResolvedValue([
      expert({ username: 'irisd', display_name: 'Iris Delgado', online: true }),
    ]);
    renderModule();

    const link = await screen.findByRole('link', { name: /iris delgado/i });
    const row = link.closest('li') as HTMLElement;
    expect(row.querySelectorAll('.bg-ok')).toHaveLength(1);
    expect(screen.getByText('Experts online')).toBeInTheDocument();
    expect(screen.queryByText('Community experts')).not.toBeInTheDocument();
  });

  it('gives an online row a screen-reader-only "(online)" cue, since the dot itself is aria-hidden', async () => {
    mockFetchExperts.mockResolvedValue([
      expert({ username: 'irisd', display_name: 'Iris Delgado', online: true }),
      expert({ username: 'mgardener', display_name: 'Mo Gardener', online: false }),
    ]);
    renderModule();

    // The row's accessible name (link name) includes the sr-only text, so an
    // online row's link is findable by name including "online" while the
    // offline row's isn't.
    await screen.findByText('Iris Delgado');
    expect(screen.getByRole('link', { name: /iris delgado.*online/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /mo gardener.*online/i })).not.toBeInTheDocument();
  });

  it('switches the title to "Experts online" if ANY row is online, even when others are not', async () => {
    mockFetchExperts.mockResolvedValue([
      expert({ username: 'irisd', display_name: 'Iris Delgado', online: false }),
      expert({ username: 'mgardener', display_name: 'Mo Gardener', online: true }),
    ]);
    renderModule();

    await screen.findByText('Iris Delgado');
    expect(screen.getByText('Experts online')).toBeInTheDocument();
    // Only the online row gets a dot.
    const offlineRow = screen
      .getByRole('link', { name: /iris delgado/i })
      .closest('li') as HTMLElement;
    const onlineRow = screen
      .getByRole('link', { name: /mo gardener/i })
      .closest('li') as HTMLElement;
    expect(offlineRow.querySelectorAll('.bg-ok')).toHaveLength(0);
    expect(onlineRow.querySelectorAll('.bg-ok')).toHaveLength(1);
  });
});
