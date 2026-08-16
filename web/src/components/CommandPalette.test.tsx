import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import CommandPalette from './CommandPalette';
import * as forumService from '../services/forumService';
import type { ForumUserSearchResult } from '../services/forumService';
import type { Category, SearchForumResponse, Thread } from '../types/forum';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockAuth = { isAuthenticated: false };
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => mockAuth }));

vi.mock('../services/forumService', () => ({
  fetchCategories: vi.fn(),
  searchForum: vi.fn(),
  searchForumUsers: vi.fn(),
}));

function makeCategory(overrides: Partial<Category> = {}): Category {
  return {
    id: '2',
    name: 'Care & Problems',
    slug: 'care-problems',
    created_at: '',
    ...overrides,
  };
}

function makeThread(overrides: Partial<Thread> = {}): Thread {
  return {
    id: '101',
    title: 'Why are my monstera leaves yellow?',
    slug: 'why-are-my-monstera-leaves-yellow',
    category: makeCategory(),
    author: { username: 'ada', display_name: 'Ada', avatar: null, trust_level: 0 },
    created_at: '',
    last_activity_at: '',
    ...overrides,
  };
}

function makeSearchResponse(threads: Thread[]): SearchForumResponse {
  return {
    query: '',
    threads,
    posts: [],
    total_threads: threads.length,
    total_posts: 0,
    has_more_threads: false,
    has_more_posts: false,
  };
}

function makePerson(overrides: Partial<ForumUserSearchResult> = {}): ForumUserSearchResult {
  return { username: 'grower99', display_name: 'Grower Ninety-Nine', ...overrides };
}

function renderPalette(props: { open?: boolean; onClose?: () => void } = {}) {
  const onClose = props.onClose ?? vi.fn();
  const utils = render(
    <MemoryRouter>
      <CommandPalette open={props.open ?? true} onClose={onClose} />
    </MemoryRouter>
  );
  return { onClose, ...utils };
}

function getInput() {
  return screen.getByRole('textbox', { name: /search plants, posts, people/i });
}

describe('CommandPalette', () => {
  beforeEach(() => {
    mockAuth.isAuthenticated = false;
    vi.mocked(forumService.fetchCategories).mockResolvedValue([]);
    vi.mocked(forumService.searchForum).mockResolvedValue(makeSearchResponse([]));
    vi.mocked(forumService.searchForumUsers).mockResolvedValue([]);
  });

  it('opens with Quick actions visible', () => {
    renderPalette();
    expect(screen.getByRole('dialog', { name: 'Search' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Identify a plant' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Start a thread' })).toBeInTheDocument();
  });

  it('renders null when closed', () => {
    renderPalette({ open: false });
    expect(screen.queryByRole('dialog', { name: 'Search' })).not.toBeInTheDocument();
  });

  it('shows one Quick actions row per board once categories load', async () => {
    const board = makeCategory({ id: '3', name: 'Show & Tell', slug: 'show-tell' });
    vi.mocked(forumService.fetchCategories).mockResolvedValue([board]);
    renderPalette();

    expect(await screen.findByRole('link', { name: 'Show & Tell' })).toBeInTheDocument();
  });

  it('calls searchForum after the debounce and renders topic rows', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(forumService.searchForum).mockResolvedValue(
        makeSearchResponse([makeThread({ title: 'Monstera leaf care' })])
      );
      renderPalette();

      fireEvent.change(getInput(), { target: { value: 'mon' } });
      expect(forumService.searchForum).not.toHaveBeenCalled();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(250);
      });

      expect(forumService.searchForum).toHaveBeenCalledWith({ q: 'mon' });
      expect(screen.getByRole('link', { name: 'Monstera leaf care' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Search everything for "mon"' })).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not show a People section when unauthenticated', async () => {
    mockAuth.isAuthenticated = false;
    renderPalette();

    await userEvent.type(getInput(), 'ad');

    expect(await screen.findByText('Topics')).toBeInTheDocument();
    expect(screen.queryByText('People')).not.toBeInTheDocument();
    expect(forumService.searchForumUsers).not.toHaveBeenCalled();
  });

  it('shows a populated People section when authenticated', async () => {
    mockAuth.isAuthenticated = true;
    vi.mocked(forumService.searchForumUsers).mockResolvedValue([makePerson()]);
    renderPalette();

    await userEvent.type(getInput(), 'ad');

    expect(await screen.findByRole('link', { name: /Grower Ninety-Nine/ })).toBeInTheDocument();
    expect(forumService.searchForumUsers).toHaveBeenCalledWith('ad');
  });

  it('shows the unavailable line when a section search fails', async () => {
    vi.mocked(forumService.searchForum).mockRejectedValue(new Error('boom'));
    renderPalette();

    await userEvent.type(getInput(), 'ad');

    expect(await screen.findByText('Search is unavailable right now')).toBeInTheDocument();
  });

  it('Escape calls onClose', () => {
    const { onClose } = renderPalette();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('ArrowDown moves the roving selection (aria-selected + aria-activedescendant), then Enter navigates and closes', () => {
    const { onClose } = renderPalette();
    const input = getInput();

    fireEvent.keyDown(input, { key: 'ArrowDown' });

    const activeRow = screen.getByRole('link', { name: 'Start a thread' });
    expect(activeRow).toHaveAttribute('aria-selected', 'true');
    // The row the input claims as active must actually exist in the DOM —
    // this is the regression net for finding 1(b): aria-activedescendant
    // pointing at an id with no matching element.
    expect(input).toHaveAttribute('aria-activedescendant', activeRow.id);
    expect(document.getElementById(activeRow.id)).toBe(activeRow);
    // The non-active row is NOT selected.
    expect(screen.getByRole('link', { name: 'Identify a plant' })).toHaveAttribute(
      'aria-selected',
      'false'
    );

    fireEvent.keyDown(input, { key: 'Enter' });

    expect(mockNavigate).toHaveBeenCalledWith('/forum/new-thread');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('drops a stale response when an older query resolves after a newer one (epoch guard)', async () => {
    vi.useFakeTimers();
    try {
      let resolveA: (value: SearchForumResponse) => void = () => {};
      let resolveB: (value: SearchForumResponse) => void = () => {};
      vi.mocked(forumService.searchForum)
        .mockImplementationOnce(
          () =>
            new Promise<SearchForumResponse>((resolve) => {
              resolveA = resolve;
            })
        )
        .mockImplementationOnce(
          () =>
            new Promise<SearchForumResponse>((resolve) => {
              resolveB = resolve;
            })
        );
      renderPalette();
      const input = getInput();

      fireEvent.change(input, { target: { value: 'aaa' } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(250);
      });
      expect(forumService.searchForum).toHaveBeenCalledTimes(1);

      fireEvent.change(input, { target: { value: 'bbb' } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(250);
      });
      expect(forumService.searchForum).toHaveBeenCalledTimes(2);

      // Resolve the NEWER query (B) first.
      await act(async () => {
        resolveB(makeSearchResponse([makeThread({ id: '2', title: 'B result' })]));
      });
      expect(screen.getByRole('link', { name: 'B result' })).toBeInTheDocument();

      // Now resolve the STALE query (A) — it must be dropped, not overwrite B's rows.
      await act(async () => {
        resolveA(makeSearchResponse([makeThread({ id: '1', title: 'A result' })]));
      });
      expect(screen.queryByRole('link', { name: 'A result' })).not.toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'B result' })).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('hides a resolved query’s rows the moment the input moves on, before the next debounce fires', async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(forumService.searchForum).mockResolvedValueOnce(
        makeSearchResponse([makeThread({ title: 'Monstera leaf care' })])
      );
      renderPalette();
      const input = getInput();

      fireEvent.change(input, { target: { value: 'mon' } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(250);
      });
      expect(screen.getByRole('link', { name: 'Monstera leaf care' })).toBeInTheDocument();

      // Type more — deliberately do NOT advance timers past the next
      // debounce window. Query A's rows must not still be on screen under
      // query "monst".
      fireEvent.change(input, { target: { value: 'monst' } });

      expect(screen.queryByRole('link', { name: 'Monstera leaf care' })).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('drops a response that lands for a query already deleted below the minimum length', async () => {
    vi.useFakeTimers();
    try {
      let resolveA: (value: SearchForumResponse) => void = () => {};
      vi.mocked(forumService.searchForum).mockImplementationOnce(
        () =>
          new Promise<SearchForumResponse>((resolve) => {
            resolveA = resolve;
          })
      );
      renderPalette();
      const input = getInput();

      fireEvent.change(input, { target: { value: 'mon' } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(250);
      });
      expect(forumService.searchForum).toHaveBeenCalledTimes(1);

      // Drop the query below the minimum length — the Topics section (and
      // the query it belonged to) is gone.
      fireEvent.change(input, { target: { value: 'm' } });
      expect(screen.queryByText('Topics')).not.toBeInTheDocument();

      // The in-flight response for the now-deleted query lands late.
      await act(async () => {
        resolveA(makeSearchResponse([makeThread({ title: 'Monstera leaf care' })]));
      });

      expect(screen.queryByRole('link', { name: 'Monstera leaf care' })).not.toBeInTheDocument();
      expect(screen.queryByText('Topics')).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('returns focus to the trigger element after Escape closes the palette', () => {
    const onClose = vi.fn();
    function Harness({ open }: { open: boolean }) {
      return (
        <>
          <button type="button">Trigger</button>
          <CommandPalette open={open} onClose={onClose} />
        </>
      );
    }

    const { rerender } = render(
      <MemoryRouter>
        <Harness open={false} />
      </MemoryRouter>
    );

    const trigger = screen.getByRole('button', { name: 'Trigger' });
    trigger.focus();
    expect(trigger).toHaveFocus();

    rerender(
      <MemoryRouter>
        <Harness open={true} />
      </MemoryRouter>
    );
    expect(getInput()).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);

    // Mirror what AppShell does in response to onClose: flip `open` back to
    // false, the same as `setPaletteOpen(false)` would.
    rerender(
      <MemoryRouter>
        <Harness open={false} />
      </MemoryRouter>
    );

    expect(trigger).toHaveFocus();
  });
});
