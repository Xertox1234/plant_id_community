import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TipTapEditor from './TipTapEditor';
import * as forumService from '../../services/forumService';
import { logger } from '../../utils/logger';

/**
 * TipTapEditor Component Tests
 *
 * Tests the rich text editor functionality including:
 * - Toolbar interactions
 * - Content editing
 * - Link insertion
 * - Editable/readonly modes
 */
/**
 * jsdom implements no layout, and its `Range` has neither `getClientRects` nor
 * `getBoundingClientRect`. ProseMirror's `scrollToSelection` → `coordsAtPos` calls
 * `singleRect(textRange(...))` — i.e. on a **Range**, not on the node — so any
 * transaction that scrolls the selection throws `target.getClientRects is not a
 * function`. That surfaces as an UNHANDLED error, which fails the vitest run
 * (exit 1) while still printing every test as passed.
 *
 * The component avoids this on its own AI-assist path (`scrollIntoView: false`),
 * but the undo test below goes through TipTap's Mod-z keybinding, whose
 * scroll-into-view is internal to the History extension and not configurable.
 * An empty rect list is the case `singleRect` already handles for an off-screen
 * selection, so this is inert padding, not simulated layout.
 */
beforeAll(() => {
  const proto = Range.prototype as unknown as Record<string, unknown>;
  if (typeof proto.getClientRects !== 'function') {
    proto.getClientRects = () => Object.assign([], { item: () => null });
  }
  if (typeof proto.getBoundingClientRect !== 'function') {
    proto.getBoundingClientRect = () => new DOMRect(0, 0, 0, 0);
  }
});

/**
 * jsdom implements neither `URL.createObjectURL` nor `revokeObjectURL` (no blob
 * URL store), so the M7 alt prompt's preview would throw on open. Stub both —
 * `revokeObjectURL` is a spy because "the preview is released" is itself an
 * assertion (one leaked blob per inserted image otherwise).
 */
const revokeObjectURL = vi.fn();
beforeAll(() => {
  const url = URL as unknown as Record<string, unknown>;
  url.createObjectURL = vi.fn(() => 'blob:preview-mock');
  url.revokeObjectURL = revokeObjectURL;
});

describe('TipTapEditor', () => {
  beforeEach(() => {
    // The compose-assist unavailability latch is session-scoped module state in
    // forumService (deliberately — see the component), so a 403 case would
    // otherwise disable the button for every later case in this file.
    forumService.resetComposeAssistAvailability();
  });

  it('renders with default placeholder', async () => {
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);

    // Wait for editor to initialize
    await waitFor(() => {
      expect(container.querySelector('.ProseMirror')).toBeInTheDocument();
    });

    // Verify editor is empty (placeholder would be visible)
    const editor = container.querySelector('.ProseMirror');
    expect(editor.textContent).toBe('');
  });

  it('renders with custom placeholder', async () => {
    const { container } = render(
      <TipTapEditor onChange={vi.fn()} placeholder="Enter your comment..." />
    );

    // Wait for editor to initialize
    await waitFor(() => {
      expect(container.querySelector('.ProseMirror')).toBeInTheDocument();
    });

    // Verify editor is empty (custom placeholder would be visible)
    const editor = container.querySelector('.ProseMirror');
    expect(editor.textContent).toBe('');
  });

  it('renders toolbar when editable', async () => {
    render(<TipTapEditor onChange={vi.fn()} editable={true} />);

    await waitFor(() => {
      expect(screen.getByTitle('Bold (Ctrl+B)')).toBeInTheDocument();
    });

    expect(screen.getByTitle('Italic (Ctrl+I)')).toBeInTheDocument();
    expect(screen.getByTitle('Insert Link')).toBeInTheDocument();
    expect(screen.getByTitle('Insert image')).toBeInTheDocument();
  });

  it('toolbar buttons expose accessible names, not just title attributes', async () => {
    // getByTitle only checks the attribute; getByRole(name) checks what the
    // accessibility tree exposes — glyph content would fail this (audit H19).
    render(<TipTapEditor onChange={vi.fn()} editable={true} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Bold (Ctrl+B)' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Italic (Ctrl+I)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Insert image' })).toBeInTheDocument();
  });

  it('does not render toolbar when readonly', async () => {
    render(<TipTapEditor onChange={vi.fn()} editable={false} />);

    await waitFor(() => {
      const editor = screen.queryByRole('textbox');
      expect(editor).toBeDefined();
    });

    expect(screen.queryByTitle('Bold (Ctrl+B)')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Italic (Ctrl+I)')).not.toBeInTheDocument();
  });

  it('renders an editable ProseMirror surface in edit mode', async () => {
    const { container } = render(<TipTapEditor onChange={vi.fn()} editable />);

    await waitFor(() => {
      expect(container.querySelector('.ProseMirror')).toBeInTheDocument();
    });

    // The surface is genuinely editable (not just present) — the old test only
    // asserted the mock was defined, which could never fail (audit L13).
    expect(container.querySelector('.ProseMirror')).toHaveAttribute('contenteditable', 'true');
  });

  it('renders bold toolbar button', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Bold (Ctrl+B)')).toBeInTheDocument();
    });

    const boldButton = screen.getByTitle('Bold (Ctrl+B)');
    expect(boldButton).toHaveAttribute('type', 'button');
  });

  it('renders italic toolbar button', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Italic (Ctrl+I)')).toBeInTheDocument();
    });

    const italicButton = screen.getByTitle('Italic (Ctrl+I)');
    expect(italicButton).toHaveAttribute('type', 'button');
  });

  it('omits the marks the server nh3 allowlist would flatten (Spec 2 PR-3 trim)', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Bold (Ctrl+B)')).toBeInTheDocument();
    });

    expect(screen.queryByTitle('Heading 2')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Heading 3')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Strikethrough')).not.toBeInTheDocument();
    // Quote is deliberately NOT in this list any more (todo 276 / M1): a
    // top-level blockquote is lifted into its own `quote` StreamField block by
    // forumBody.ts, so unlike the marks above it survives the server contract.
    // Its presence is asserted in the next test.
  });

  it('offers a Quote control, which emits a top-level blockquote (todo 276 / M1)', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Quote')).toBeInTheDocument();
    });
    // Glyph-only buttons take their accessible name from `title` via aria-label
    // (audit H19), so the control is reachable by name, not just by title.
    expect(screen.getByRole('button', { name: 'Quote' })).toBeInTheDocument();
  });

  it('renders list toolbar buttons', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Bullet List')).toBeInTheDocument();
    });

    expect(screen.getByTitle('Bullet List')).toBeInTheDocument();
    expect(screen.getByTitle('Numbered List')).toBeInTheDocument();
  });

  it('renders the inline code button but not the (trimmed) code block button', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Inline Code')).toBeInTheDocument();
    });

    expect(screen.queryByTitle('Code Block')).not.toBeInTheDocument();
  });

  it('renders the insert-image button and a hidden file input', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Insert image')).toBeInTheDocument();
    });

    expect(screen.getByTestId('forum-image-input')).toHaveAttribute('type', 'file');
  });

  it('shows loading state before editor initializes', () => {
    // Mock useEditor to return null (loading state)
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);

    // Check if either loading message or editor is present
    const loadingOrEditor =
      screen.queryByText('Loading editor...') || container.querySelector('.ProseMirror');

    expect(loadingOrEditor).toBeTruthy();
  });

  it('applies custom className to editor container', async () => {
    const { container } = render(<TipTapEditor onChange={vi.fn()} className="custom-class" />);

    await waitFor(() => {
      const editorContainer = container.querySelector('.custom-class');
      expect(editorContainer).toBeInTheDocument();
    });
  });

  it('shows the image size/type limits hint (M29)', async () => {
    render(<TipTapEditor onChange={vi.fn()} editable />);
    await waitFor(() => expect(screen.getByTitle('Insert image')).toBeInTheDocument());
    expect(screen.getByText(/up to 10 MB/i)).toBeInTheDocument();
  });

  it('rejects an unsupported image type before uploading (M29)', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage');
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    const input = screen.getByTestId('forum-image-input');
    const file = new File(['x'], 'doc.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText(/unsupported image type/i)).toBeInTheDocument();
    expect(uploadSpy).not.toHaveBeenCalled();
  });

  it('rejects an oversized image before uploading (M29)', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage');
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    const input = screen.getByTestId('forum-image-input');
    const file = new File(['x'], 'big.jpg', { type: 'image/jpeg' });
    Object.defineProperty(file, 'size', { value: 11 * 1024 * 1024 });
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText(/too large/i)).toBeInTheDocument();
    expect(uploadSpy).not.toHaveBeenCalled();
  });

  it('uploads a valid image through the service (L13)', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue({
      id: 1,
      url: 'https://cdn.example/x.jpg',
      alt: '',
      width: 10,
      height: 10,
    });
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    const input = screen.getByTestId('forum-image-input');
    const file = new File(['x'], 'ok.jpg', { type: 'image/jpeg' });
    fireEvent.change(input, { target: { files: [file] } });

    // M7: selecting a file now opens the alt prompt; the upload happens on
    // confirm. Skip is the shortest path to "just upload it".
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledWith(file, ''));
  });

  it('surfaces an upload failure as an error message (L13)', async () => {
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.spyOn(forumService, 'uploadPostImage').mockRejectedValue(new Error('server exploded'));
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    const input = screen.getByTestId('forum-image-input');
    const file = new File(['x'], 'ok.jpg', { type: 'image/jpeg' });
    fireEvent.change(input, { target: { files: [file] } });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));

    expect(await screen.findByText('server exploded')).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Author-supplied alt text (M7 / todo 281)
  // -------------------------------------------------------------------------

  it('prompts for alt text before uploading, not after (M7)', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage');
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [new File(['x'], 'ok.jpg', { type: 'image/jpeg' })] },
    });

    // The prompt is up and NOTHING has been uploaded — the alt must ride the
    // upload request, so capturing it afterwards would be too late.
    expect(await screen.findByLabelText('Describe this image')).toBeInTheDocument();
    expect(uploadSpy).not.toHaveBeenCalled();
  });

  it('sends author-entered alt text on upload (M7)', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue({
      id: 1,
      url: 'https://cdn.example/x.jpg',
      alt: 'A monstera leaf with brown edges',
      width: 10,
      height: 10,
    });
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    const file = new File(['x'], 'ok.jpg', { type: 'image/jpeg' });
    fireEvent.change(screen.getByTestId('forum-image-input'), { target: { files: [file] } });

    await userEvent.type(
      await screen.findByLabelText('Describe this image'),
      'A monstera leaf with brown edges'
    );
    await userEvent.click(screen.getByRole('button', { name: 'Add image' }));

    await waitFor(() =>
      expect(uploadSpy).toHaveBeenCalledWith(file, 'A monstera leaf with brown edges')
    );
  });

  it('Skip uploads with an empty alt and discards anything typed (M7)', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue({
      id: 1,
      url: 'https://cdn.example/x.jpg',
      alt: '',
      width: 10,
      height: 10,
    });
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    const file = new File(['x'], 'ok.jpg', { type: 'image/jpeg' });
    fireEvent.change(screen.getByTestId('forum-image-input'), { target: { files: [file] } });

    await userEvent.type(await screen.findByLabelText('Describe this image'), 'half-typed');
    await userEvent.click(screen.getByRole('button', { name: 'Skip' }));

    // Skip means "no description", not "submit whatever is in the box" — an
    // empty alt is correct for a decorative image and must not block posting.
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledWith(file, ''));
  });

  it('revokes the preview object URL when the prompt closes (M7)', async () => {
    vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue({
      id: 1,
      url: 'https://cdn.example/x.jpg',
      alt: '',
      width: 10,
      height: 10,
    });
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [new File(['x'], 'ok.jpg', { type: 'image/jpeg' })] },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));

    // Without this the composer leaks one blob per inserted image.
    await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith('blob:preview-mock'));
  });

  it('revokes the preview when the composer unmounts with the prompt open (M7)', async () => {
    // The path the Skip test above does NOT cover, and the one that was broken:
    // the cleanup originally revoked inside a setState functional updater, but
    // React DISCARDS a setState on an unmounting component without invoking the
    // updater — so it silently did nothing (measured: 0 revoke calls). Reading a
    // ref in the cleanup is what makes this work. Navigating away mid-prompt is
    // a real path; this editor is also remounted via `key=` after every reply.
    const { container, unmount } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [new File(['x'], 'ok.jpg', { type: 'image/jpeg' })] },
    });
    await screen.findByLabelText('Describe this image');

    revokeObjectURL.mockClear();
    unmount();

    expect(revokeObjectURL).toHaveBeenCalledWith('blob:preview-mock');
  });

  it('opens a styled link editor instead of window.prompt, and validates the URL (M24)', async () => {
    const promptSpy = vi.spyOn(window, 'prompt');
    render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(screen.getByTitle('Insert Link')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle('Insert Link'));
    expect(promptSpy).not.toHaveBeenCalled();

    const urlInput = screen.getByLabelText('Link URL');
    await userEvent.type(urlInput, 'javascript:alert(1)');
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

    // A dangerous scheme is rejected with a message, not silently linked.
    expect(screen.getByText(/valid http/i)).toBeInTheDocument();
  });

  // ------------------------------------------------------------------------- #
  // AI composer assist (todo 275 / M14)
  // ------------------------------------------------------------------------- #

  const AI_TITLE = /improve draft with ai/i;

  it('offers an AI assist button, disabled while the draft is empty (M14)', async () => {
    render(<TipTapEditor onChange={vi.fn()} editable />);
    const button = await screen.findByTitle(AI_TITLE);
    // Nothing to improve yet — and an enabled button would spend a premium call
    // on an empty document.
    expect(button).toBeDisabled();
  });

  it('sends the current draft and swaps in the rewrite (M14)', async () => {
    const improveSpy = vi
      .spyOn(forumService, 'improveDraft')
      .mockResolvedValue('My tomato plant is wilting.');
    const onChange = vi.fn();
    const { container } = render(
      <TipTapEditor content="<p>tomato plant sad</p>" onChange={onChange} editable />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle(AI_TITLE));

    await waitFor(() =>
      expect(improveSpy).toHaveBeenCalledWith(expect.stringContaining('tomato plant sad'))
    );
    await waitFor(() =>
      expect(container.querySelector('.ProseMirror').textContent).toBe(
        'My tomato plant is wilting.'
      )
    );
    // The parent form is told about the swap, or the post would submit the old draft.
    expect(onChange).toHaveBeenCalled();
  });

  it('inserts model output as TEXT, never as parsed markup (M14)', async () => {
    // The endpoint contracts for plain text, but a model can still emit tags.
    // insertContent(<string>) would parse them into real document structure that
    // the user then publishes; node-based insertion cannot.
    vi.spyOn(forumService, 'improveDraft').mockResolvedValue(
      '<b>bold</b> and <img src=x onerror=alert(1)>'
    );
    const { container } = render(
      <TipTapEditor content="<p>draft</p>" onChange={vi.fn()} editable />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle(AI_TITLE));

    const editor = await waitFor(() => {
      const el = container.querySelector('.ProseMirror');
      expect(el.textContent).toContain('<b>bold</b>');
      return el;
    });
    expect(editor.querySelector('b')).toBeNull();
    expect(editor.querySelector('img')).toBeNull();
  });

  it('splits a multi-paragraph rewrite into separate paragraphs (M14)', async () => {
    vi.spyOn(forumService, 'improveDraft').mockResolvedValue(
      'First paragraph.\n\nSecond paragraph.\nThird line.'
    );
    const { container } = render(
      <TipTapEditor content="<p>draft</p>" onChange={vi.fn()} editable />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle(AI_TITLE));

    await waitFor(() => expect(container.querySelectorAll('.ProseMirror p')).toHaveLength(3));
    expect(container.querySelector('.ProseMirror').textContent).toContain('First paragraph.');
    expect(container.querySelector('.ProseMirror').textContent).toContain('Third line.');
  });

  it('is one undo step, so the original draft is recoverable (M14)', async () => {
    // The rewrite is text-only, so images and link marks in the draft are dropped.
    // Undo is the documented escape hatch for that — if the swap were more than one
    // transaction, Ctrl+Z would only partially restore and the tradeoff would be a
    // silent data loss instead.
    vi.spyOn(forumService, 'improveDraft').mockResolvedValue('Rewritten.');
    const { container } = render(
      <TipTapEditor content="<p>the original draft</p>" onChange={vi.fn()} editable />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle(AI_TITLE));
    await waitFor(() =>
      expect(container.querySelector('.ProseMirror').textContent).toBe('Rewritten.')
    );

    // Driven through the real Mod-z keybinding on the editor surface, not a test-only
    // escape hatch on the component — the claim being verified is that the USER can
    // undo it.
    const surface = container.querySelector('.ProseMirror') as HTMLElement;
    surface.focus();
    await userEvent.keyboard('{Control>}z{/Control}');

    await waitFor(() =>
      expect(container.querySelector('.ProseMirror').textContent).toBe('the original draft')
    );
  });

  it('permanently disables the button and explains why on a 403 (M14)', async () => {
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.spyOn(forumService, 'improveDraft').mockRejectedValue(
      new forumService.ComposeAssistError(403, 'This feature requires a premium account.')
    );
    const { container } = render(
      <TipTapEditor content="<p>draft</p>" onChange={vi.fn()} editable />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle(AI_TITLE));

    expect(await screen.findByText(/requires a premium account/i)).toBeInTheDocument();
    // Retrying can never succeed for this account, so the control is disabled —
    // but kept MOUNTED, so the focus the user just placed on it isn't dropped.
    await waitFor(() =>
      expect(screen.getByTitle(/not available for this account/i)).toBeDisabled()
    );
  });

  it('stays disabled across a composer remount after a 403 (M14)', async () => {
    // ThreadDetailPage remounts the reply composer (key={composerKey}) after every
    // post, which resets component state — the latch therefore lives in the
    // service, or a non-premium user gets the failing button back on every reply.
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.spyOn(forumService, 'improveDraft').mockRejectedValue(
      new forumService.ComposeAssistError(403, 'This feature requires a premium account.')
    );
    const first = render(<TipTapEditor content="<p>draft</p>" onChange={vi.fn()} editable />);
    await waitFor(() => expect(first.container.querySelector('.ProseMirror')).toBeInTheDocument());
    await userEvent.click(screen.getByTitle(AI_TITLE));
    await waitFor(() =>
      expect(screen.getByTitle(/not available for this account/i)).toBeDisabled()
    );
    first.unmount();

    const second = render(<TipTapEditor content="<p>draft</p>" onChange={vi.fn()} editable />);
    await waitFor(() => expect(second.container.querySelector('.ProseMirror')).toBeInTheDocument());
    // Fresh mount, still disabled — no second wasted round-trip.
    expect(screen.getByTitle(/not available for this account/i)).toBeDisabled();
  });

  it('keeps the button after a TRANSIENT 503 (provider blip) (M14)', async () => {
    // The regression this guards: `permanent` used to include any 503, so a single
    // provider error/timeout/empty-completion killed the button for the whole tab
    // — with a tooltip blaming the user's account (todo 275 code review).
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.spyOn(forumService, 'improveDraft').mockRejectedValue(
      new forumService.ComposeAssistError(503, 'AI assist is unavailable right now.', 'unavailable')
    );
    const { container } = render(
      <TipTapEditor content="<p>draft</p>" onChange={vi.fn()} editable />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle(AI_TITLE));

    expect(await screen.findByText(/unavailable right now/i)).toBeInTheDocument();
    expect(screen.getByTitle(AI_TITLE)).toBeEnabled();
    expect(forumService.isComposeAssistUnavailable()).toBe(false);
  });

  it('disables the button on a 503 that means the feature is off (M14)', async () => {
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.spyOn(forumService, 'improveDraft').mockRejectedValue(
      new forumService.ComposeAssistError(503, 'AI composer assist is not enabled.', 'disabled')
    );
    const { container } = render(
      <TipTapEditor content="<p>draft</p>" onChange={vi.fn()} editable />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle(AI_TITLE));

    await waitFor(() =>
      expect(screen.getByTitle(/not available for this account/i)).toBeDisabled()
    );
    expect(forumService.isComposeAssistUnavailable()).toBe(true);
  });

  it('keeps the button after a transient 429 (M14)', async () => {
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.spyOn(forumService, 'improveDraft').mockRejectedValue(
      new forumService.ComposeAssistError(429, 'AI assist is temporarily at capacity.')
    );
    const { container } = render(
      <TipTapEditor content="<p>draft</p>" onChange={vi.fn()} editable />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByTitle(AI_TITLE));

    expect(await screen.findByText(/temporarily at capacity/i)).toBeInTheDocument();
    // Transient — a later retry can work, so the button must stay usable, not just
    // stay mounted (it is always mounted now): still enabled, still its normal
    // title, and the session latch untouched.
    const button = screen.getByTitle(AI_TITLE);
    expect(button).toBeEnabled();
    expect(screen.queryByTitle(/not available for this account/i)).not.toBeInTheDocument();
    expect(forumService.isComposeAssistUnavailable()).toBe(false);
  });
});
