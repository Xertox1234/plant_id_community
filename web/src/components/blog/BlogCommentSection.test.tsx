import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import BlogCommentSection from './BlogCommentSection';
import * as commentService from '../../services/blogCommentService';
import { ForumApiError } from '../../services/forumService';
import type { BlogComment } from '../../types/blog';

vi.mock('../../services/blogCommentService', async () => {
  const actual = await vi.importActual<typeof import('../../services/blogCommentService')>(
    '../../services/blogCommentService'
  );
  return {
    ...actual,
    fetchBlogComments: vi.fn(),
    addBlogComment: vi.fn(),
    flagBlogComment: vi.fn(),
  };
});

// Mutable auth posture — the vi.mock factory is hoisted above the imports,
// so the holder must be created with vi.hoisted.
const authState = vi.hoisted(() => ({
  current: {
    user: null as { id: number; username: string } | null,
    isAuthenticated: false,
    isLoading: false,
  },
}));
vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => authState.current }));
vi.mock('../../utils/logger', () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));

const me = { id: 1, username: 'me' };
const meAuthor = { id: 1, username: 'me', display_name: 'Me' };
const june = { id: 2, username: 'june_park', display_name: 'June Park' };
const ada = { id: 3, username: 'ada', display_name: 'Ada L.' };

function makeComment(overrides: Partial<BlogComment> = {}): BlogComment {
  return {
    id: 11,
    post: 6,
    author: june,
    content: 'First!',
    parent: null,
    is_approved: true,
    is_reply: false,
    replies: [],
    created_at: '2026-09-05T09:00:00Z',
    updated_at: '2026-09-05T09:00:00Z',
    ...overrides,
  };
}

const fetchMock = vi.mocked(commentService.fetchBlogComments);
const addMock = vi.mocked(commentService.addBlogComment);
const flagMock = vi.mocked(commentService.flagBlogComment);

function renderSection(props: Partial<React.ComponentProps<typeof BlogCommentSection>> = {}) {
  return render(
    <MemoryRouter>
      <BlogCommentSection postId={6} allowComments commentCount={0} {...props} />
    </MemoryRouter>
  );
}

const notice = () => screen.getByTestId('blog-comments-notice');
const composer = () => screen.getByLabelText('Add a comment');

describe('BlogCommentSection (todo 352)', () => {
  beforeEach(() => {
    authState.current = { user: me, isAuthenticated: true, isLoading: false };
    fetchMock.mockResolvedValue([]);
    addMock.mockResolvedValue(makeComment({ id: 99, author: meAuthor, content: 'posted' }));
    flagMock.mockResolvedValue({ detail: 'Comment has been flagged for review.' });
  });

  it('comments closed on the post: shows the note, no composer, and never fetches', () => {
    renderSection({ allowComments: false, commentCount: 0 });
    expect(screen.getByText('Comments are closed on this post.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Add a comment')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign in to comment' })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('closed by the server (GET 403) when the page payload did not say so', async () => {
    fetchMock.mockRejectedValue(new ForumApiError('Comments are disabled for this post.', 403));
    renderSection({ allowComments: undefined });
    expect(await screen.findByText('Comments are closed on this post.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Add a comment')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });

  it('signed out: the list still loads and a sign-in link replaces the composer', async () => {
    authState.current = { user: null, isAuthenticated: false, isLoading: false };
    fetchMock.mockResolvedValue([makeComment()]);
    renderSection();
    expect(await screen.findByText('First!')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(6);
    expect(screen.getByRole('link', { name: 'Sign in to comment' })).toHaveAttribute(
      'href',
      '/login'
    );
    expect(screen.queryByLabelText('Add a comment')).not.toBeInTheDocument();
    // No write controls for a visitor either.
    expect(screen.queryByRole('button', { name: 'Reply' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Flag' })).not.toBeInTheDocument();
  });

  it('empty: "No comments yet." with the composer', async () => {
    renderSection();
    expect(await screen.findByText('No comments yet.')).toBeInTheDocument();
    expect(composer()).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Comments (0)' })).toBeInTheDocument();
  });

  it('loaded with replies: author, body as plain text, nested reply; the heading swaps from comment_count to the loaded approved count', async () => {
    const reply = makeComment({
      id: 12,
      author: ada,
      content: 'A reply\nwith a second line',
      parent: 11,
      is_reply: true,
    });
    const pendingMine = makeComment({
      id: 13,
      author: meAuthor,
      content: 'mine, held',
      is_approved: false,
    });
    fetchMock.mockResolvedValue([
      makeComment({ content: '<b>not html</b>', replies: [reply] }),
      pendingMine,
    ]);
    renderSection({ commentCount: 7 });
    // Before the list lands, the server's count.
    expect(screen.getByRole('heading', { name: 'Comments (7)' })).toBeInTheDocument();

    const list = await screen.findByRole('list', { name: 'Comments' });
    // Plain text: the tag characters render literally, nothing is parsed.
    const body = within(list).getByText('<b>not html</b>');
    expect(body.tagName).toBe('P');
    expect(body.className).toContain('whitespace-pre-wrap');
    expect(list.querySelector('b')).toBeNull();
    expect(within(list).getByText('June Park')).toBeInTheDocument();

    const replies = within(list).getByRole('list', { name: 'Replies' });
    expect(within(replies).getByText('Ada L.')).toBeInTheDocument();
    expect(within(replies).getByText(/A reply/)).toHaveTextContent('A reply with a second line');

    // Own pending comment from the load carries the badge.
    expect(screen.getByText('Awaiting moderation — only you can see this')).toBeInTheDocument();
    // 1 approved top-level + 1 approved reply; the pending one is not counted.
    expect(screen.getByRole('heading', { name: 'Comments (2)' })).toBeInTheDocument();
  });

  it('submit (approved): POSTs the content, appends the comment, clears the draft, announces', async () => {
    addMock.mockResolvedValue(
      makeComment({ id: 99, author: meAuthor, content: 'Great read', is_approved: true })
    );
    renderSection();
    await screen.findByText('No comments yet.');

    await userEvent.type(composer(), '  Great read  ');
    await userEvent.click(screen.getByRole('button', { name: 'Post comment' }));

    expect(await screen.findByText('Great read')).toBeInTheDocument();
    expect(addMock).toHaveBeenCalledWith(6, { content: 'Great read' });
    expect(composer()).toHaveValue('');
    expect(notice()).toHaveTextContent('Comment posted.');
    expect(
      screen.queryByText('Awaiting moderation — only you can see this')
    ).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Comments (1)' })).toBeInTheDocument();
  });

  it('submit (pending): shows the comment with the awaiting-moderation badge', async () => {
    addMock.mockResolvedValue(
      makeComment({ id: 99, author: meAuthor, content: 'held one', is_approved: false })
    );
    renderSection();
    await screen.findByText('No comments yet.');

    await userEvent.type(composer(), 'held one');
    await userEvent.click(screen.getByRole('button', { name: 'Post comment' }));

    expect(await screen.findByText('held one')).toBeInTheDocument();
    expect(screen.getByText('Awaiting moderation — only you can see this')).toBeInTheDocument();
    expect(notice()).toHaveTextContent('awaiting moderation');
    // Not counted until approved.
    expect(screen.getByRole('heading', { name: 'Comments (0)' })).toBeInTheDocument();
  });

  it('disables the composer while submitting and caps the draft at the client limit', async () => {
    let resolveAdd: (c: BlogComment) => void = () => {};
    addMock.mockImplementation(
      () =>
        new Promise<BlogComment>((resolve) => {
          resolveAdd = resolve;
        })
    );
    renderSection();
    await screen.findByText('No comments yet.');
    expect(composer()).toHaveAttribute('maxlength', String(commentService.BLOG_COMMENT_MAX_LENGTH));
    expect(screen.getByText(`0/${commentService.BLOG_COMMENT_MAX_LENGTH}`)).toBeInTheDocument();

    await userEvent.type(composer(), 'hi');
    await userEvent.click(screen.getByRole('button', { name: 'Post comment' }));
    expect(composer()).toBeDisabled();
    expect(screen.getByRole('button', { name: /Posting…/ })).toBeDisabled();

    resolveAdd(makeComment({ id: 99, author: meAuthor, content: 'hi' }));
    await waitFor(() => expect(composer()).toBeEnabled());
  });

  it('429: the rate-limit message', async () => {
    // The real envelope line — the status, not the text, is what we branch on.
    addMock.mockRejectedValue(
      new ForumApiError('Rate limit exceeded. Please try again later.', 429)
    );
    renderSection();
    await screen.findByText('No comments yet.');
    await userEvent.type(composer(), 'fast');
    await userEvent.click(screen.getByRole('button', { name: 'Post comment' }));
    await waitFor(() =>
      expect(notice()).toHaveTextContent("You're commenting too fast — try again in a minute.")
    );
    // The draft survives a failed post.
    expect(composer()).toHaveValue('fast');
  });

  it('403: the server detail', async () => {
    addMock.mockRejectedValue(new ForumApiError('Comments are disabled for this post.', 403));
    renderSection();
    await screen.findByText('No comments yet.');
    await userEvent.type(composer(), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Post comment' }));
    await waitFor(() => expect(notice()).toHaveTextContent('Comments are disabled for this post.'));
  });

  it('reply flow: one composer at a time, POSTs the parent, nests the reply, and a 400 parent error shows its message', async () => {
    fetchMock.mockResolvedValue([
      makeComment({ id: 11, author: june, content: 'first' }),
      makeComment({ id: 21, author: ada, content: 'second' }),
    ]);
    renderSection();
    const list = await screen.findByRole('list', { name: 'Comments' });
    const replyButtons = within(list).getAllByRole('button', { name: 'Reply' });
    expect(replyButtons).toHaveLength(2);

    await userEvent.click(replyButtons[0]);
    expect(screen.getByLabelText('Reply to June Park')).toBeInTheDocument();

    // Opening the second closes the first — exactly one reply composer.
    await userEvent.click(replyButtons[1]);
    expect(screen.queryByLabelText('Reply to June Park')).not.toBeInTheDocument();
    const replyBox = screen.getByLabelText('Reply to Ada L.');
    expect(screen.getAllByRole('textbox')).toHaveLength(2); // main composer + this one

    // 400 from the backend's parent validation (flattened "parent: <text>").
    addMock.mockRejectedValueOnce(
      new ForumApiError(
        'parent: That comment is awaiting moderation and cannot be replied to yet.',
        400
      )
    );
    await userEvent.type(replyBox, 'nope');
    await userEvent.click(screen.getByRole('button', { name: 'Post reply' }));
    await waitFor(() =>
      expect(notice()).toHaveTextContent(
        'That comment is awaiting moderation and cannot be replied to yet.'
      )
    );
    expect(notice()).not.toHaveTextContent('parent:');
    expect(addMock).toHaveBeenLastCalledWith(6, { content: 'nope', parent: 21 });
    // The composer stays open with the draft after a failure.
    expect(screen.getByLabelText('Reply to Ada L.')).toHaveValue('nope');

    // Then a successful reply nests under the second comment and closes the composer.
    addMock.mockResolvedValueOnce(
      makeComment({ id: 31, author: meAuthor, content: 'my reply', parent: 21, is_reply: true })
    );
    await userEvent.click(screen.getByRole('button', { name: 'Post reply' }));
    const replies = await within(list).findByRole('list', { name: 'Replies' });
    expect(within(replies).getByText('my reply')).toBeInTheDocument();
    const secondItem = within(list).getByText('second').closest('li');
    expect(secondItem).toContainElement(replies);
    expect(screen.queryByLabelText('Reply to Ada L.')).not.toBeInTheDocument();
    expect(notice()).toHaveTextContent('Reply posted.');
    // A reply is a leaf: it gets no Reply control of its own.
    expect(within(replies).queryByRole('button', { name: 'Reply' })).not.toBeInTheDocument();
  });

  it('flag flow: no Flag on my own comment; flagging another marks it "Flagged" and announces the server detail', async () => {
    fetchMock.mockResolvedValue([
      makeComment({ id: 11, author: meAuthor, content: 'mine' }),
      makeComment({ id: 21, author: ada, content: 'theirs' }),
    ]);
    renderSection();
    const list = await screen.findByRole('list', { name: 'Comments' });
    const mine = within(list).getByText('mine').closest('li') as HTMLElement;
    const theirs = within(list).getByText('theirs').closest('li') as HTMLElement;
    expect(within(mine).queryByRole('button', { name: 'Flag' })).not.toBeInTheDocument();
    expect(within(mine).getByRole('button', { name: 'Reply' })).toBeInTheDocument();

    await userEvent.click(within(theirs).getByRole('button', { name: 'Flag' }));
    const flagged = await within(theirs).findByRole('button', { name: 'Flagged' });
    expect(flagged).toBeDisabled();
    expect(flagged).toHaveAttribute('aria-pressed', 'true');
    expect(flagMock).toHaveBeenCalledWith(21);
    expect(notice()).toHaveTextContent('Comment has been flagged for review.');
  });

  it('a late list for the previous post never renders into the current one (stale-response race)', async () => {
    let resolveA: (c: BlogComment[]) => void = () => {};
    let resolveB: (c: BlogComment[]) => void = () => {};
    fetchMock.mockImplementation(
      (postId) =>
        new Promise<BlogComment[]>((resolve) => {
          if (postId === 1) resolveA = resolve;
          else resolveB = resolve;
        })
    );
    const { rerender } = render(
      <MemoryRouter>
        <BlogCommentSection postId={1} allowComments commentCount={0} />
      </MemoryRouter>
    );
    rerender(
      <MemoryRouter>
        <BlogCommentSection postId={2} allowComments commentCount={0} />
      </MemoryRouter>
    );
    expect(fetchMock).toHaveBeenCalledWith(1);
    expect(fetchMock).toHaveBeenCalledWith(2);

    resolveB([makeComment({ id: 2, content: 'from post B' })]);
    expect(await screen.findByText('from post B')).toBeInTheDocument();

    // Post A's list settles late — it must be dropped, not painted over B's.
    resolveA([makeComment({ id: 1, content: 'from post A' })]);
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText('from post A')).not.toBeInTheDocument();
    expect(screen.getByText('from post B')).toBeInTheDocument();
  });

  it('the live region is mounted and EMPTY before a load failure, then carries the error with a working Retry', async () => {
    let rejectLoad: (e: unknown) => void = () => {};
    fetchMock.mockImplementationOnce(
      () =>
        new Promise<BlogComment[]>((_, reject) => {
          rejectLoad = reject;
        })
    );
    renderSection();
    const region = notice();
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveTextContent('');
    expect(region).toHaveClass('sr-only');
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();

    rejectLoad(new Error('boom'));
    await waitFor(() => expect(region).toHaveTextContent("Couldn't load comments."));
    expect(region).not.toHaveClass('sr-only');
    // Same node, not a remount — that is the live-region contract.
    expect(notice()).toBe(region);

    fetchMock.mockResolvedValueOnce([makeComment({ content: 'after retry' })]);
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('after retry')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(region).toHaveTextContent('');
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });

  it('a write outcome is never shadowed by a stale load error in the live region', async () => {
    fetchMock.mockRejectedValueOnce(new Error('boom'));
    addMock.mockResolvedValueOnce(
      makeComment({ id: 50, content: 'still works', is_approved: false })
    );
    renderSection();
    await screen.findByText("Couldn't load comments.");

    await userEvent.type(screen.getByLabelText('Add a comment'), 'still works');
    await userEvent.click(screen.getByRole('button', { name: 'Post comment' }));

    await waitFor(() =>
      expect(screen.getByTestId('blog-comments-notice')).toHaveTextContent(/awaiting moderation/)
    );
    expect(screen.getByTestId('blog-comments-notice')).not.toHaveTextContent(
      "Couldn't load comments."
    );
  });

  it('a retry that refreshes the list while a submit is in flight never duplicates the comment', async () => {
    let resolveSubmit: (c: BlogComment) => void = () => {};
    fetchMock.mockRejectedValueOnce(new Error('boom'));
    addMock.mockImplementationOnce(
      () =>
        new Promise<BlogComment>((resolve) => {
          resolveSubmit = resolve;
        })
    );
    renderSection();
    await screen.findByText("Couldn't load comments.");
    await userEvent.type(screen.getByLabelText('Add a comment'), 'twice?');
    await userEvent.click(screen.getByRole('button', { name: 'Post comment' }));

    // The refresh already contains the comment the server created…
    fetchMock.mockResolvedValueOnce([makeComment({ id: 77, content: 'twice?' })]);
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    const list = await screen.findByRole('list', { name: 'Comments' });
    await within(list).findByText('twice?');
    // …and then the submit's own echo lands.
    await act(async () => {
      resolveSubmit(makeComment({ id: 77, content: 'twice?' }));
    });

    const rows = within(list)
      .getAllByRole('listitem')
      .filter((li) => li.textContent?.includes('twice?'));
    expect(rows).toHaveLength(1);
  });

  it('strips every recognised field prefix from a multi-field 400, not just the first', async () => {
    addMock.mockRejectedValueOnce(
      new ForumApiError('content: Too long; parent: That comment is not on this post.', 400)
    );
    renderSection();
    await userEvent.type(await screen.findByLabelText('Add a comment'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Post comment' }));

    await waitFor(() =>
      expect(screen.getByTestId('blog-comments-notice')).toHaveTextContent(
        'Too long; That comment is not on this post.'
      )
    );
  });
});
