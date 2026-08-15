import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import PostCard from './PostCard';
import { createMockPost } from '../../tests/forumUtils';

/**
 * Helper to render PostCard with Router context.
 * Passes onEdit/onDelete/onReact by default so display tests stay unaffected
 * by the handler-presence guards.
 */
function renderPostCard(post, onEdit = vi.fn(), onDelete = vi.fn(), onReact = vi.fn()) {
  return render(
    <BrowserRouter>
      <PostCard post={post} onEdit={onEdit} onDelete={onDelete} onReact={onReact} />
    </BrowserRouter>
  );
}

describe('PostCard', () => {
  it('renders post author information', () => {
    const post = createMockPost({
      author: {
        username: 'plantlover',
        display_name: 'Green Thumb',
        avatar: null,
        trust_level: 2,
      },
    });

    renderPostCard(post);

    expect(screen.getByText('Green Thumb')).toBeInTheDocument();
    expect(screen.getByText('Member')).toBeInTheDocument();
  });

  it('links the author name to their public profile (todo 257 H7)', () => {
    const post = createMockPost({
      author: {
        username: 'plantlover',
        display_name: 'Green Thumb',
        avatar: null,
        trust_level: 2,
      },
    });

    renderPostCard(post);

    const link = screen.getByRole('link', { name: 'Green Thumb' });
    expect(link).toHaveAttribute('href', '/forum/users/plantlover');
  });

  it('does not link a [deleted] author (no profile to open)', () => {
    const post = createMockPost({
      author: { username: '[deleted]', display_name: '[deleted]', avatar: null, trust_level: null },
    });

    renderPostCard(post);

    expect(screen.queryByRole('link', { name: '[deleted]' })).not.toBeInTheDocument();
    expect(screen.getByText('[deleted]')).toBeInTheDocument();
  });

  it('hides the trust badge for a NEW (level 0) author', () => {
    const post = createMockPost({
      author: {
        username: 'newbie',
        display_name: 'New Person',
        avatar: null,
        trust_level: 0,
      },
    });

    renderPostCard(post);

    // Level 0 (New) is intentionally un-badged (preserves the prior falsy-0
    // hidden behaviour); only levels >= 1 get a label pill.
    expect(screen.queryByText('New')).not.toBeInTheDocument();
    expect(screen.getByText('New Person')).toBeInTheDocument(); // author still renders
  });

  it('falls back to username when display_name is missing', () => {
    const post = createMockPost({
      author: {
        username: 'plantlover',
        display_name: undefined,
        avatar: null,
        trust_level: 1,
      },
    });

    renderPostCard(post);

    expect(screen.getByText('plantlover')).toBeInTheDocument();
  });

  it('renders "Original Post" badge for first post', () => {
    const post = createMockPost({ is_first_post: true });

    renderPostCard(post);

    expect(screen.getByText('Original Post')).toBeInTheDocument();
  });

  it('does not show "Original Post" badge for replies', () => {
    const post = createMockPost({ is_first_post: false });

    renderPostCard(post);

    expect(screen.queryByText('Original Post')).not.toBeInTheDocument();
  });

  it('renders StreamField body blocks and sanitizes HTML to prevent XSS', () => {
    const post = createMockPost({
      body: [
        { id: '1', type: 'paragraph', value: '<p>Safe content</p><script>alert("xss")</script>' },
      ],
    });

    const { container } = renderPostCard(post);

    // Should render the text content from the paragraph block
    expect(screen.getByText('Safe content')).toBeInTheDocument();

    // StreamFieldRenderer sanitizes via DOMPurify — script tags must not appear
    const scripts = container.querySelectorAll('script');
    expect(scripts.length).toBe(0);
  });

  it('renders StreamField paragraph body with safe HTML elements', () => {
    const post = createMockPost({
      body: [
        {
          id: '1',
          type: 'paragraph',
          value: '<p>Test <strong>bold</strong> and <a href="#">link</a></p>',
        },
      ],
    });

    const { container } = renderPostCard(post);

    expect(container.querySelector('p')).toBeInTheDocument();
    expect(container.querySelector('strong')).toBeInTheDocument();
    expect(container.querySelector('a')).toBeInTheDocument();
  });

  it('displays formatted relative timestamp', () => {
    const post = createMockPost({
      created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(), // 45 min ago
    });

    renderPostCard(post);

    expect(screen.getByText(/ago/i)).toBeInTheDocument();
  });

  it('shows edit timestamp when post was edited', () => {
    const post = createMockPost({
      edited_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(), // 15 min ago
      edited_by: {
        username: 'moderator',
        display_name: 'Mod Team',
      },
    });

    renderPostCard(post);

    expect(screen.getByText(/edited/i)).toBeInTheDocument();
    expect(screen.getByText(/Mod Team/i)).toBeInTheDocument();
  });

  it('does not show edit info when post has not been edited', () => {
    const post = createMockPost({
      edited_at: null,
      edited_by: null,
    });

    renderPostCard(post);

    expect(screen.queryByText(/edited/i)).not.toBeInTheDocument();
  });

  it('renders reaction counts with emojis when onReact is provided', () => {
    const post = createMockPost({
      reaction_counts: {
        like: 5,
        love: 2,
        helpful: 3,
        thanks: 1,
      },
    });

    renderPostCard(post);

    expect(screen.getByText('👍')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('❤️')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('💡')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('🙏')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('sets aria-pressed on reaction buttons the current user has reacted to (M23)', () => {
    const post = createMockPost({
      reaction_counts: { like: 3, love: 1 },
      reacted: ['like'],
    });

    renderPostCard(post); // renderPostCard passes onReact (interactive buttons)

    expect(screen.getByRole('button', { name: 'React like' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByRole('button', { name: 'React love' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
  });

  it('marks decorative reaction emoji as aria-hidden (L14)', () => {
    const post = createMockPost({ reaction_counts: { like: 5 } });

    renderPostCard(post);

    expect(screen.getByText('👍')).toHaveAttribute('aria-hidden', 'true');
  });

  it('shows all four reaction options in the picker when no reactions exist yet and onReact is provided', () => {
    const post = createMockPost({
      reaction_counts: {},
    });

    renderPostCard(post);

    // At rest, zero-count buttons are hidden — only "Add reaction" shows.
    expect(screen.queryByLabelText('React like')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /add reaction/i }));

    // Expanding the picker reveals all four reaction options.
    expect(screen.getByLabelText('React like')).toBeInTheDocument();
    expect(screen.getByLabelText('React love')).toBeInTheDocument();
    expect(screen.getByLabelText('React helpful')).toBeInTheDocument();
    expect(screen.getByLabelText('React thanks')).toBeInTheDocument();
  });

  it('shows only the non-zero reaction as a pill at rest; the zero one appears in the picker', () => {
    const post = createMockPost({
      reaction_counts: {
        like: 0,
        love: 2,
      },
    });

    renderPostCard(post);

    expect(screen.getByLabelText('React love')).toHaveTextContent('2');
    expect(screen.queryByLabelText('React like')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /add reaction/i }));

    expect(screen.getByLabelText('React like')).toBeInTheDocument();
  });

  it('hides reaction buttons when onReact is not provided', () => {
    const post = createMockPost({ reaction_counts: { like: 5 } });

    render(
      <BrowserRouter>
        <PostCard post={post} />
      </BrowserRouter>
    );

    expect(screen.queryByLabelText('React like')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('React love')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('React helpful')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('React thanks')).not.toBeInTheDocument();
  });

  it('calls onReact with the post id and reaction type when clicked', async () => {
    const onReact = vi.fn();
    const post = createMockPost({ id: 'post-9' });

    render(
      <BrowserRouter>
        <PostCard post={post} onReact={onReact} />
      </BrowserRouter>
    );

    await userEvent.click(screen.getByRole('button', { name: /add reaction/i }));
    await userEvent.click(screen.getByLabelText('React like'));

    expect(onReact).toHaveBeenCalledWith('post-9', 'like');
  });

  it('marks the opening post with the primary-bordered chip', () => {
    const post = createMockPost({ is_first_post: true });

    renderPostCard(post);

    expect(screen.getByText('Original Post')).toHaveClass('border-primary/40');
  });

  it('renders the default specimen engraving when the author has no avatar', () => {
    const post = createMockPost({
      author: {
        username: 'gardener',
        display_name: 'Garden Expert',
        avatar: null,
        trust_level: 3,
      },
    });

    const { container } = renderPostCard(post);

    // Deterministic per-username fallback from /public/avatars (Field Notes).
    const img = container.querySelector('img[src^="/avatars/specimen-"]');
    expect(img).toBeInTheDocument();
  });

  it('renders the avatar image when the author has an avatar (todo 257)', () => {
    const post = createMockPost({
      author: {
        username: 'gardener',
        display_name: 'Garden Expert',
        avatar: 'http://x/media/avatar.jpg',
        trust_level: 3,
      },
    });

    const { container } = renderPostCard(post);

    // Decorative (alt="") — the author's name sits right beside it (Avatar
    // component contract), so it's queried by src, not accessible name.
    // Exactly one <img> renders in this tree (the default mock body has no
    // image blocks), so this pins both the presence AND the correct src —
    // a src-scoped selector alone would pass vacuously on a mismatched src.
    const imgs = container.querySelectorAll('img');
    expect(imgs).toHaveLength(1);
    expect(imgs[0]).toHaveAttribute('src', 'http://x/media/avatar.jpg');
  });

  it('keys the specimen engraving off the username (stable identity)', () => {
    const post = createMockPost({
      author: {
        username: 'plantlover',
        display_name: undefined,
        avatar: null,
        trust_level: 1,
      },
    });

    const { container, unmount } = renderPostCard(post);
    const first = container.querySelector('img[src^="/avatars/specimen-"]')?.getAttribute('src');
    expect(first).toBeTruthy();
    unmount();

    // Same username -> same specimen, every render.
    const { container: again } = renderPostCard(post);
    const second = again.querySelector('img[src^="/avatars/specimen-"]')?.getAttribute('src');
    expect(second).toBe(first);
  });

  it('shows edit/delete buttons when can_edit/can_delete are true and handlers are provided', () => {
    const post = createMockPost({ can_edit: true, can_delete: true });

    renderPostCard(post);

    // Buttons must be in the DOM regardless of hover state (CSS hides them on md+).
    expect(screen.getByTitle('Edit post')).toBeInTheDocument();
    expect(screen.getByTitle('Delete post')).toBeInTheDocument();
    // Hidden-yet-focusable controls must reveal on keyboard focus, not just
    // hover (WCAG 2.4.7; audit 2026-07-11 H20). jsdom can't compute CSS, so
    // pin the class contract.
    const actions = screen.getByTitle('Edit post').parentElement!;
    expect(actions.className).toContain('md:group-focus-within:opacity-100');
    // The variant only activates under an ancestor carrying the literal
    // `group` class — pin that half of the contract too (Phase 6 review).
    expect(actions.closest('.group')).not.toBeNull();
  });

  it('hides edit/delete buttons when the capability flags are false', () => {
    const post = createMockPost({ can_edit: false, can_delete: false });

    renderPostCard(post);

    expect(screen.queryByTitle('Edit post')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Delete post')).not.toBeInTheDocument();
  });

  it('hides edit/delete buttons when no handlers are provided even if capable', () => {
    const post = createMockPost({ can_edit: true, can_delete: true });

    render(
      <BrowserRouter>
        <PostCard post={post} />
      </BrowserRouter>
    );

    expect(screen.queryByTitle('Edit post')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Delete post')).not.toBeInTheDocument();
  });

  it('calls onEdit/onDelete with the post when the buttons are clicked', async () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    const post = createMockPost({ id: 'post-7', can_edit: true, can_delete: true });

    render(
      <BrowserRouter>
        <PostCard post={post} onEdit={onEdit} onDelete={onDelete} />
      </BrowserRouter>
    );

    await userEvent.click(screen.getByTitle('Edit post'));
    await userEvent.click(screen.getByTitle('Delete post'));

    expect(onEdit).toHaveBeenCalledWith(post);
    expect(onDelete).toHaveBeenCalledWith(post);
  });

  it('shows the report control when can_report is true and onReport is provided', () => {
    const post = createMockPost({ can_report: true });

    render(
      <BrowserRouter>
        <PostCard post={post} onReport={vi.fn()} />
      </BrowserRouter>
    );

    expect(screen.getByTitle('Report post')).toBeInTheDocument();
  });

  it('hides the report control when can_report is false', () => {
    const post = createMockPost({ can_report: false });

    render(
      <BrowserRouter>
        <PostCard post={post} onReport={vi.fn()} />
      </BrowserRouter>
    );

    expect(screen.queryByTitle('Report post')).not.toBeInTheDocument();
  });

  it('hides the report control when no onReport handler is provided even if capable', () => {
    const post = createMockPost({ can_report: true });

    render(
      <BrowserRouter>
        <PostCard post={post} />
      </BrowserRouter>
    );

    expect(screen.queryByTitle('Report post')).not.toBeInTheDocument();
  });

  it('submits the selected reason and shows a confirmation', async () => {
    const onReport = vi.fn().mockResolvedValue(undefined);
    const post = createMockPost({ id: 'post-9', can_report: true });

    render(
      <BrowserRouter>
        <PostCard post={post} onReport={onReport} />
      </BrowserRouter>
    );

    await userEvent.click(screen.getByTitle('Report post'));
    await userEvent.selectOptions(screen.getByLabelText('Report reason'), 'abuse');
    await userEvent.click(screen.getByText('Submit'));

    expect(onReport).toHaveBeenCalledWith('post-9', 'abuse');
    expect(screen.getByText('Reported')).toBeInTheDocument();
    expect(screen.queryByTitle('Report post')).not.toBeInTheDocument();
  });

  it('leaves the picker open (no false confirmation) when the report request fails', async () => {
    const onReport = vi.fn().mockRejectedValue(new Error('network error'));
    const post = createMockPost({ can_report: true });

    render(
      <BrowserRouter>
        <PostCard post={post} onReport={onReport} />
      </BrowserRouter>
    );

    await userEvent.click(screen.getByTitle('Report post'));
    await userEvent.click(screen.getByText('Submit'));

    expect(onReport).toHaveBeenCalled();
    expect(screen.queryByText('Reported')).not.toBeInTheDocument();
    expect(screen.getByText('Submit')).toBeInTheDocument(); // picker still open for retry
  });

  it('cancels the reason picker without calling onReport', async () => {
    const onReport = vi.fn();
    const post = createMockPost({ can_report: true });

    render(
      <BrowserRouter>
        <PostCard post={post} onReport={onReport} />
      </BrowserRouter>
    );

    await userEvent.click(screen.getByTitle('Report post'));
    await userEvent.click(screen.getByText('Cancel'));

    expect(onReport).not.toHaveBeenCalled();
    expect(screen.getByTitle('Report post')).toBeInTheDocument();
  });

  it('copies a permalink to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const post = createMockPost({ id: '21' });

    render(
      <BrowserRouter>
        <PostCard post={post} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /copy link/i }));
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('#post-21'))
    );
    expect(await screen.findByText(/copied/i)).toBeInTheDocument();
  });

  it('copies the CANONICAL thread URL + anchor, not the page-scoped one (audit M11)', async () => {
    // AC1: the copied link must be one a fresh visitor can open. Post pagination
    // is cursor-based and never appears in the URL, so the canonical thread path
    // plus #post-N is the whole address — ThreadDetailPage's Wave-1 arrival
    // effect then chases later cursor pages until the anchor renders (pinned by
    // ThreadDetailPage.test.tsx "deep-link to a post on a later cursor page…").
    // Any query string on the current URL must be dropped: it is view state
    // (?order=, ?tag=), not part of the post's identity.
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    window.history.pushState({}, '', '/forum/3-plant-care/12-watering-tips?order=-created_at');

    render(
      <BrowserRouter>
        <PostCard post={createMockPost({ id: '21' })} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /copy link/i }));
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(
        `${window.location.origin}/forum/3-plant-care/12-watering-tips#post-21`
      )
    );
  });

  it('shows non-zero reaction counts read-only when logged out (no onReact)', () => {
    const post = createMockPost({ reaction_counts: { like: 2, love: 0 } });

    render(
      <BrowserRouter>
        <PostCard post={post} />
      </BrowserRouter>
    );

    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /add reaction/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /react love/i })).not.toBeInTheDocument();
    // The read-only count button is not a toggle → aria-pressed is omitted
    // entirely (not "false"), so a screen reader doesn't announce it as pressable.
    expect(screen.getByRole('button', { name: '2 like' })).not.toHaveAttribute('aria-pressed');
  });

  it('hides zero counts at rest and expands the picker on demand', () => {
    const onReact = vi.fn();
    const post = createMockPost({ id: '21', reaction_counts: { like: 1 } });

    render(
      <BrowserRouter>
        <PostCard post={post} onReact={onReact} />
      </BrowserRouter>
    );

    expect(screen.queryByRole('button', { name: /react love/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /add reaction/i }));
    fireEvent.click(screen.getByRole('button', { name: /react love/i }));
    expect(onReact).toHaveBeenCalledWith('21', 'love');
  });

  it('renders no reaction row at all for a zero-reaction post viewed logged out', () => {
    const post = createMockPost({ reaction_counts: {} });

    render(
      <BrowserRouter>
        <PostCard post={post} />
      </BrowserRouter>
    );

    expect(screen.queryByRole('button', { name: /add reaction/i })).not.toBeInTheDocument();
    expect(screen.queryByText('👍')).not.toBeInTheDocument();
  });

  // --- Accepted answer (audit H6)

  it('labels the accepted answer in text, not by colour alone', () => {
    render(
      <BrowserRouter>
        <PostCard post={createMockPost()} isSolution />
      </BrowserRouter>
    );

    expect(screen.getByText(/accepted answer/i)).toBeInTheDocument();
  });

  it('shows no accepted-answer label on an ordinary post', () => {
    render(
      <BrowserRouter>
        <PostCard post={createMockPost()} />
      </BrowserRouter>
    );

    expect(screen.queryByText(/accepted answer/i)).not.toBeInTheDocument();
  });

  it('offers no mark-as-answer control without a handler', () => {
    // The handler's presence IS the permission gate — the thread page passes it
    // only when the backend says this viewer may mark.
    render(
      <BrowserRouter>
        <PostCard post={createMockPost()} />
      </BrowserRouter>
    );

    expect(screen.queryByRole('button', { name: /mark as answer/i })).not.toBeInTheDocument();
  });

  it('calls onToggleSolution with the post when marking', () => {
    const post = createMockPost();
    const onToggleSolution = vi.fn();

    render(
      <BrowserRouter>
        <PostCard post={post} onToggleSolution={onToggleSolution} />
      </BrowserRouter>
    );

    const button = screen.getByRole('button', { name: /mark as answer/i });
    expect(button).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(button);

    expect(onToggleSolution).toHaveBeenCalledWith(post);
  });

  it('reads as pressed and offers removal once accepted', () => {
    const onToggleSolution = vi.fn();

    render(
      <BrowserRouter>
        <PostCard post={createMockPost()} isSolution onToggleSolution={onToggleSolution} />
      </BrowserRouter>
    );

    const button = screen.getByRole('button', { name: /accepted/i });
    expect(button).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(button);

    expect(onToggleSolution).toHaveBeenCalledTimes(1);
  });
});
