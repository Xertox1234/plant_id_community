import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ForumImagePicker from './ForumImagePicker';

const { listMyForumImages } = vi.hoisted(() => ({ listMyForumImages: vi.fn() }));

// vi.mock's factory is hoisted above imports, so the mock fns must come from
// vi.hoisted — a bare top-level const throws.
vi.mock('../../services/forumService', async () => {
  // ForumApiError is REAL, not a stub: the component branches on
  // `instanceof ForumApiError`, so a fake class would make the 403 test pass
  // for the wrong reason (it would fall into the generic-error branch and the
  // assertion on the forbidden copy would be the thing that failed, not the
  // thing that proved it).
  const actual = await vi.importActual<typeof import('../../services/forumService')>(
    '../../services/forumService'
  );
  return { ForumApiError: actual.ForumApiError, listMyForumImages };
});

const { ForumApiError } = await vi.importActual<typeof import('../../services/forumService')>(
  '../../services/forumService'
);

const img = (id: number, alt = `photo ${id}`) => ({
  id,
  url: `http://x/${id}.jpg`,
  alt,
  decorative: false,
  width: 800,
  height: 600,
});

const page = (items: ReturnType<typeof img>[], next: string | null = null) => ({
  items,
  meta: { count: 0, next, previous: null },
});

describe('ForumImagePicker (todo 374)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMyForumImages.mockResolvedValue(page([img(1), img(2)]));
  });

  it('renders nothing while closed, and does not call the API', () => {
    const { container } = render(
      <ForumImagePicker open={false} onSelect={vi.fn()} onClose={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
    expect(listMyForumImages).not.toHaveBeenCalled();
  });

  it('lists the images once open', async () => {
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    // Counted as TILES, not <img> roles: each image is alt="" on purpose (the
    // button carries the accessible name), which correctly removes it from the
    // a11y tree entirely.
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /Insert photo/i })).toHaveLength(2)
    );
  });

  it('names each tile by its alt text so the grid is navigable by screen reader', async () => {
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(
      await screen.findByRole('button', { name: /Insert photo: photo 1/i })
    ).toBeInTheDocument();
  });

  it('falls back to a generic label when an image has no alt', async () => {
    listMyForumImages.mockResolvedValue(page([img(9, '')]));
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(await screen.findByRole('button', { name: 'Insert photo' })).toBeInTheDocument();
  });

  it('hands the picked image to onSelect', async () => {
    const onSelect = vi.fn();
    render(<ForumImagePicker open onSelect={onSelect} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /Insert photo: photo 2/i }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }));
  });

  // --- the three states that must never collapse into the spinner -----------

  it('a 403 says "not a forum member", NOT "you have no photos"', async () => {
    listMyForumImages.mockRejectedValue(new ForumApiError('nope', 403));
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(await screen.findByTestId('forum-image-picker-forbidden')).toBeInTheDocument();
    expect(screen.queryByTestId('forum-image-picker-empty')).not.toBeInTheDocument();
  });

  it('an empty library says so, and is NOT rendered as a failure', async () => {
    listMyForumImages.mockResolvedValue(page([]));
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(await screen.findByTestId('forum-image-picker-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('forum-image-picker-forbidden')).not.toBeInTheDocument();
  });

  it('a non-403 failure is a failure, not an empty library', async () => {
    listMyForumImages.mockRejectedValue(new ForumApiError('boom', 500));
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(await screen.findByText(/Couldn't load your photos/i)).toBeInTheDocument();
    expect(screen.queryByTestId('forum-image-picker-empty')).not.toBeInTheDocument();
  });

  // --- pagination -----------------------------------------------------------

  it('offers Load more only when the server sent a next cursor', async () => {
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    await screen.findAllByRole('button', { name: /Insert photo/i });
    expect(screen.queryByRole('button', { name: /Load more/i })).not.toBeInTheDocument();
  });

  it('appends the next page rather than replacing the current one', async () => {
    listMyForumImages.mockResolvedValueOnce(page([img(1), img(2)], 'http://api/next'));
    listMyForumImages.mockResolvedValueOnce(page([img(3)]));
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /Load more/i }));
    // 3, not 1 — losing the first page would throw away the user's place.
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /Insert photo/i })).toHaveLength(3)
    );
    expect(listMyForumImages).toHaveBeenLastCalledWith({ cursor: 'http://api/next' });
  });

  it('a failed Load more keeps the images already on screen', async () => {
    listMyForumImages.mockResolvedValueOnce(page([img(1)], 'http://api/next'));
    listMyForumImages.mockRejectedValueOnce(new ForumApiError('boom', 500));
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /Load more/i }));
    expect(await screen.findByText(/Couldn't load more photos/i)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Insert photo/i })).toHaveLength(1);
  });

  // --- modal semantics ------------------------------------------------------

  it('Escape closes', async () => {
    const onClose = vi.fn();
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={onClose} />);
    await screen.findByRole('dialog');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('a backdrop click closes, a click inside does not', async () => {
    const onClose = vi.fn();
    render(<ForumImagePicker open onSelect={vi.fn()} onClose={onClose} />);
    fireEvent.click(await screen.findByRole('dialog'));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('forum-image-picker-backdrop'));
    expect(onClose).toHaveBeenCalled();
  });

  // --- stale responses across open/close (review round 1) --------------------

  it('a load-more still in flight when the picker is reopened is DISCARDED', async () => {
    // The component is never unmounted between opens — the composer renders it
    // permanently and `open` only gates the render — so without a session guard
    // the old page two would be appended onto the new page one.
    let releaseSecond: (v: unknown) => void = () => {};
    const pending = new Promise((resolve) => {
      releaseSecond = resolve;
    });
    listMyForumImages
      .mockResolvedValueOnce(page([img(1)], 'http://api/next')) // first open
      .mockReturnValueOnce(pending) // the load-more we will strand
      .mockResolvedValueOnce(page([img(5)])); // second open, page one

    const { rerender } = render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /Load more/i }));

    // Close and reopen while that request is still outstanding.
    rerender(<ForumImagePicker open={false} onSelect={vi.fn()} onClose={vi.fn()} />);
    rerender(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /Insert photo/i })).toHaveLength(1)
    );

    releaseSecond(page([img(99)]));
    await Promise.resolve();

    // Still exactly the new session's single tile — img 99 must NOT appear.
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /Insert photo/i })).toHaveLength(1)
    );
    expect(
      screen.queryByRole('button', { name: /Insert photo: photo 99/i })
    ).not.toBeInTheDocument();
  });

  it('reopening resets the load-more spinner left behind by the previous open', async () => {
    // Without resetting isLoadingMore, "Load more" renders permanently disabled
    // in the new session.
    let release: (v: unknown) => void = () => {};
    listMyForumImages
      .mockResolvedValueOnce(page([img(1)], 'http://api/next'))
      .mockReturnValueOnce(
        new Promise((resolve) => {
          release = resolve;
        })
      )
      .mockResolvedValueOnce(page([img(5)], 'http://api/next2'));

    const { rerender } = render(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /Load more/i }));
    rerender(<ForumImagePicker open={false} onSelect={vi.fn()} onClose={vi.fn()} />);
    rerender(<ForumImagePicker open onSelect={vi.fn()} onClose={vi.fn()} />);

    const loadMore = await screen.findByRole('button', { name: /Load more/i });
    expect(loadMore).not.toBeDisabled();
    release(page([]));
  });
});
