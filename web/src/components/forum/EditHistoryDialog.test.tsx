import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EditHistoryDialog from './EditHistoryDialog';
import { ForumApiError } from '../../services/forumService';

const { fetchPostRevisions, fetchPostRevision } = vi.hoisted(() => ({
  fetchPostRevisions: vi.fn(),
  fetchPostRevision: vi.fn(),
}));

// vi.mock's factory is hoisted above imports, so the mock fns must come from
// vi.hoisted — a bare top-level const throws.
vi.mock('../../services/forumService', async () => {
  // ForumApiError is real, not a stub: the component branches on
  // `instanceof ForumApiError`, so a fake class would make the 403 test pass
  // for the wrong reason.
  const actual = await vi.importActual<typeof import('../../services/forumService')>(
    '../../services/forumService'
  );
  return { ForumApiError: actual.ForumApiError, fetchPostRevisions, fetchPostRevision };
});

const REVISIONS = [
  {
    id: 2,
    created_at: '2026-07-30T12:00:00Z',
    user: { username: 'ada', display_name: 'Ada L.', avatar: null },
  },
  {
    id: 1,
    created_at: '2026-07-29T12:00:00Z',
    user: { username: 'ada', display_name: 'Ada L.', avatar: null },
  },
];

describe('EditHistoryDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchPostRevisions.mockResolvedValue(REVISIONS);
    fetchPostRevision.mockResolvedValue({
      ...REVISIONS[1],
      body: [{ type: 'paragraph', value: '<p>the original wording</p>', id: 'b1' }],
    });
  });

  it('renders nothing when closed, and does not fetch', () => {
    const { container } = render(<EditHistoryDialog open={false} postId="7" onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
    expect(fetchPostRevisions).not.toHaveBeenCalled();
  });

  it('lists the post revisions when opened', async () => {
    render(<EditHistoryDialog open postId="7" onClose={() => {}} />);

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole('button', { name: /View/ })).toHaveLength(2));
    expect(fetchPostRevisions).toHaveBeenCalledWith('7');
  });

  it('renders a selected revision body', async () => {
    render(<EditHistoryDialog open postId="7" onClose={() => {}} />);

    const rows = await screen.findAllByRole('button', { name: /View/ });
    fireEvent.click(rows[1]);

    expect(await screen.findByText('the original wording')).toBeInTheDocument();
    expect(fetchPostRevision).toHaveBeenCalledWith('7', 1);
  });

  it('surfaces a 403 as the moderator-only refusal, not a generic failure', async () => {
    // The backend turns history moderator-only once someone other than the
    // author has edited the post, because earlier revisions still hold what
    // that edit removed. Showing "couldn't load" would misreport a deliberate
    // refusal as a fault.
    //
    // The rejection carries the REAL production message — DRF's
    // PermissionDenied default detail, which `apps/core/exceptions.py`
    // serialises verbatim. It contains neither "403" nor "forbidden", so a
    // component that sniffed the message text instead of the status would
    // fail here (and an earlier version of this test, which mocked
    // `Error('HTTP 403 Forbidden')`, hid exactly that bug).
    fetchPostRevisions.mockRejectedValue(
      new ForumApiError('You do not have permission to perform this action.', 403)
    );
    render(<EditHistoryDialog open postId="7" onClose={() => {}} />);

    expect(await screen.findByText(/only visible to moderators/i)).toBeInTheDocument();
  });

  it('reports a non-403 failure differently from the 403 refusal', async () => {
    fetchPostRevisions.mockRejectedValue(new ForumApiError('Server error', 500));
    render(<EditHistoryDialog open postId="7" onClose={() => {}} />);

    expect(await screen.findByText(/Couldn't load this post's edit history/i)).toBeInTheDocument();
    expect(screen.queryByText(/only visible to moderators/i)).not.toBeInTheDocument();
  });

  it('has an empty live region before anything goes wrong', async () => {
    render(<EditHistoryDialog open postId="7" onClose={() => {}} />);
    // Present and EMPTY — a region that only appears with its content is the
    // anti-pattern an aria-live region exists to avoid, and findByText after
    // the fact would pass either way.
    // Bare aria-live (not role="status") so it never collides with the
    // LoadingSpinner's own status role in `getByRole('status')` queries.
    const dialog = await screen.findByRole('dialog');
    const region = dialog.querySelector('p[aria-live="polite"]');
    expect(region).toBeInTheDocument();
    expect(region).not.toHaveAttribute('role');
    expect(region).toHaveTextContent('');
  });

  it('closes on Escape', async () => {
    const onClose = vi.fn();
    render(<EditHistoryDialog open postId="7" onClose={onClose} />);
    await screen.findByRole('dialog');

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(onClose).toHaveBeenCalled();
  });
});
