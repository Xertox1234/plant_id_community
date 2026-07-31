import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import SavedThreadsPage from './SavedThreadsPage';
import { createMockCategory, createMockThread } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';

vi.mock('../../services/forumService');

function renderSavedThreadsPage() {
  return render(
    <MemoryRouter initialEntries={['/forum/saved']}>
      <SavedThreadsPage />
    </MemoryRouter>
  );
}

describe('SavedThreadsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a loading spinner while fetching', () => {
    vi.spyOn(forumService, 'fetchBookmarks').mockImplementation(() => new Promise(() => {}));

    renderSavedThreadsPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders the saved threads returned by the API', async () => {
    vi.spyOn(forumService, 'fetchBookmarks').mockResolvedValue({
      items: [
        createMockThread({ id: '12', title: 'Saved thread one' }),
        createMockThread({ id: '13', title: 'Saved thread two' }),
      ],
      meta: { count: 2, next: null, previous: null },
    });

    renderSavedThreadsPage();

    expect(await screen.findByText('Saved thread one')).toBeInTheDocument();
    expect(screen.getByText('Saved thread two')).toBeInTheDocument();
  });

  it('links each row through its OWN board, not a single stamped-on one', async () => {
    // The regression this guards: the saved list spans boards, so reusing the
    // board-list mapper (which leaves `category` empty) would render every link
    // as `/forum/-/…`. Two rows on two different boards must produce two
    // different board prefixes.
    vi.spyOn(forumService, 'fetchBookmarks').mockResolvedValue({
      items: [
        createMockThread({
          id: '12',
          slug: 'aloe-help',
          title: 'Aloe help',
          category: createMockCategory({ id: '3', slug: 'plant-care', name: 'Plant Care' }),
        }),
        createMockThread({
          id: '13',
          slug: 'monstera-id',
          title: 'Monstera ID',
          category: createMockCategory({ id: '7', slug: 'plant-id', name: 'Plant ID' }),
        }),
      ],
      meta: { count: 2, next: null, previous: null },
    });

    renderSavedThreadsPage();

    expect(await screen.findByRole('link', { name: /Aloe help/i })).toHaveAttribute(
      'href',
      '/forum/3-plant-care/12-aloe-help'
    );
    expect(screen.getByRole('link', { name: /Monstera ID/i })).toHaveAttribute(
      'href',
      '/forum/7-plant-id/13-monstera-id'
    );
  });

  it('shows an empty state that names the Save affordance', async () => {
    vi.spyOn(forumService, 'fetchBookmarks').mockResolvedValue({
      items: [],
      meta: { count: 0, next: null, previous: null },
    });

    renderSavedThreadsPage();

    expect(await screen.findByText(/Nothing saved yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Save button/i)).toBeInTheDocument();
  });

  it('shows an error state with a working retry', async () => {
    const spy = vi
      .spyOn(forumService, 'fetchBookmarks')
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        items: [createMockThread({ id: '12', title: 'Back online' })],
        meta: { count: 1, next: null, previous: null },
      });

    renderSavedThreadsPage();

    await screen.findByText('Network error');
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));

    expect(await screen.findByText('Back online')).toBeInTheDocument();
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it('appends the next page and passes the absolute cursor URL through unchanged', async () => {
    const cursorUrl = 'https://api.example.test/forum/me/bookmarks/?cursor=abc123';
    const spy = vi
      .spyOn(forumService, 'fetchBookmarks')
      .mockResolvedValueOnce({
        items: [createMockThread({ id: '12', title: 'First page thread' })],
        meta: { count: 2, next: cursorUrl, previous: null },
      })
      .mockResolvedValueOnce({
        items: [createMockThread({ id: '13', title: 'Second page thread' })],
        meta: { count: 2, next: null, previous: null },
      });

    renderSavedThreadsPage();

    await userEvent.click(await screen.findByRole('button', { name: /Load More/i }));

    expect(await screen.findByText('Second page thread')).toBeInTheDocument();
    // The first page stays rendered — this appends, it does not replace.
    expect(screen.getByText('First page thread')).toBeInTheDocument();
    // Absolute cursor passed verbatim; re-prefixing the API base would 404.
    expect(spy).toHaveBeenLastCalledWith(cursorUrl);
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Load More/i })).not.toBeInTheDocument();
    });
  });
});
