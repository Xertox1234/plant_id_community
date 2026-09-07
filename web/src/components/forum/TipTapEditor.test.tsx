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

/**
 * jsdom has no layout, so `document.elementFromPoint` does not exist. ProseMirror's
 * drop handler resolves a document position from the event coordinates BEFORE it
 * consults `handleDrop`, and bails when that returns nothing — so without this
 * shim the drop tests below would pass vacuously (no upload attempted, no error
 * raised). Returning the editor element is enough for posAtCoords to resolve.
 */
beforeAll(() => {
  const doc = document as unknown as Record<string, unknown>;
  if (typeof doc.elementFromPoint !== 'function') {
    doc.elementFromPoint = () => document.querySelector('.ProseMirror');
  }
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
      decorative: false,
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
    await waitFor(() =>
      // The 3rd arg is the Idempotency-Key: a double-submit of the same
      // selection must replay server-side rather than store a 2nd image.
      expect(uploadSpy).toHaveBeenCalledWith(file, '', expect.any(String))
    );
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
      decorative: false,
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
      expect(uploadSpy).toHaveBeenCalledWith(
        file,
        'A monstera leaf with brown edges',
        expect.any(String)
      )
    );
  });

  it('Skip uploads with an empty alt and discards anything typed (M7)', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue({
      id: 1,
      url: 'https://cdn.example/x.jpg',
      alt: '',
      decorative: false,
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
    await waitFor(() =>
      // The 3rd arg is the Idempotency-Key: a double-submit of the same
      // selection must replay server-side rather than store a 2nd image.
      expect(uploadSpy).toHaveBeenCalledWith(file, '', expect.any(String))
    );
  });

  it('revokes the preview object URL when the prompt closes (M7)', async () => {
    vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue({
      id: 1,
      url: 'https://cdn.example/x.jpg',
      alt: '',
      decorative: false,
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

  it('keeps a quoted post id on a blockquote through its schema (todo 342)', async () => {
    // Pins the editor's OWN configuration (ForumBlockquoteAttrs registered):
    // the attribute reaches the live ProseMirror DOM, so getHTML() on save
    // carries it back to forumBody's post_quote branch. Without the
    // extension the schema drops it and every quote degrades to `quote`.
    const { container } = render(
      <TipTapEditor
        content='<blockquote data-post-id="7"><p>quoted</p></blockquote><p></p>'
        onChange={vi.fn()}
        editable
      />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    expect(container.querySelector('.ProseMirror blockquote[data-post-id="7"]')).not.toBeNull();
  });
});

// --- todo 357: one request, more ways in, editable alt ----------------------

describe('TipTapEditor image upload (todo 357)', () => {
  const uploaded = {
    id: 1,
    url: 'https://cdn.example/x.jpg',
    alt: '',
    decorative: false,
    width: 10,
    height: 10,
  };

  // Prior content BY DEFAULT. An empty document is the one shape where
  // ProseMirror falls back to a NodeSelection after an insert, which is what
  // made the original edit-alt test pass against a button that was disabled in
  // every real post.
  async function mount(content = '<p>hello there</p><p>second para</p>') {
    const { container } = render(<TipTapEditor content={content} onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());
    return container;
  }

  function imageFile(name = 'ok.jpg') {
    return new File(['x'], name, { type: 'image/jpeg' });
  }

  it('disables the Insert image button while an upload is in flight (AC 4)', async () => {
    // Without this, a second activation reopens the picker mid-upload and
    // starts a concurrent request — so "one multipart request" would not hold.
    let release: (v: typeof uploaded) => void = () => {};
    vi.spyOn(forumService, 'uploadPostImage').mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      })
    );
    await mount();

    const button = screen.getByRole('button', { name: 'Insert image' });
    expect(button).not.toBeDisabled();

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [imageFile()] },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));

    const uploading = await screen.findByRole('button', { name: 'Uploading image…' });
    expect(uploading).toBeDisabled();

    release(uploaded);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Insert image' })).toBeEnabled());
  });

  it('reuses ONE idempotency key for a given file selection', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue(uploaded);
    await mount();

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [imageFile('a.jpg')] },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [imageFile('b.jpg')] },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(2));

    const firstKey = uploadSpy.mock.calls[0][2];
    const secondKey = uploadSpy.mock.calls[1][2];
    expect(firstKey).toBeTruthy();
    // A DIFFERENT selection must not share a key, or the backend would replay
    // the first image's response and the second upload would silently vanish.
    expect(secondKey).not.toBe(firstKey);
  });

  it('routes a pasted image through the same validation gate', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue(uploaded);
    const container = await mount();
    const editorEl = container.querySelector('.ProseMirror') as HTMLElement;

    fireEvent.paste(editorEl, {
      clipboardData: {
        files: [imageFile('pasted.jpg')],
        items: [],
        types: ['Files'],
        // ProseMirror reads text/plain + text/html before consulting
        // handlePaste; without getData it throws before we are called.
        getData: () => '',
      },
    });

    // Same alt prompt as the toolbar path — not a second upload path.
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1));
  });

  it('rejects a pasted non-image by the same client-side rules', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage');
    const container = await mount();
    const editorEl = container.querySelector('.ProseMirror') as HTMLElement;

    fireEvent.paste(editorEl, {
      clipboardData: {
        files: [new File(['x'], 'doc.pdf', { type: 'application/pdf' })],
        items: [],
        types: ['Files'],
        getData: () => '',
      },
    });

    // Not an image at all, so it is not even offered to the prompt — and
    // crucially never uploaded.
    await waitFor(() => expect(uploadSpy).not.toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Skip' })).not.toBeInTheDocument();
  });

  it('routes a dropped image through the same validation gate', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue(uploaded);
    const container = await mount();
    const editorEl = container.querySelector('.ProseMirror') as HTMLElement;

    fireEvent.drop(editorEl, {
      dataTransfer: {
        files: [imageFile('dropped.jpg')],
        items: [],
        types: ['Files'],
        // ProseMirror reads the drag payload as text before consulting
        // handleDrop, exactly as it does for paste.
        getData: () => '',
      },
    });

    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1));
  });

  it('rejects an oversized dropped image before uploading', async () => {
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage');
    const container = await mount();
    const editorEl = container.querySelector('.ProseMirror') as HTMLElement;

    const big = imageFile('huge.jpg');
    Object.defineProperty(big, 'size', { value: 11 * 1024 * 1024 });
    fireEvent.drop(editorEl, {
      dataTransfer: { files: [big], items: [], types: ['Files'], getData: () => '' },
    });

    expect(await screen.findByText(/too large/i)).toBeInTheDocument();
    expect(uploadSpy).not.toHaveBeenCalled();
  });

  it('lets the author re-author alt text after insert, with no re-upload', async () => {
    // The whole point of the ImageBlock migration: alt is per-usage, so fixing
    // it is an attribute update rather than a second file upload.
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue(uploaded);
    const container = await mount();

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [imageFile()] },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(container.querySelector('img[data-image-id]')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: 'Edit image alt text' }));
    const input = await screen.findByLabelText(/describe this image/i);
    await userEvent.type(input, 'A monstera leaf');
    await userEvent.click(screen.getByRole('button', { name: 'Save alt text' }));

    await waitFor(() =>
      expect(container.querySelector('img[data-image-id]')?.getAttribute('alt')).toBe(
        'A monstera leaf'
      )
    );
    // No second upload — that is the improvement being pinned.
    expect(uploadSpy).toHaveBeenCalledTimes(1);
  });
});

// --- todo 357 review round 1: the four bugs that review measured ------------

describe('TipTapEditor image upload — review fixes', () => {
  const uploaded = {
    id: 1,
    url: 'https://cdn.example/x.jpg',
    alt: '',
    decorative: false,
    width: 10,
    height: 10,
  };

  async function mount(content = '<p>hello there</p><p>second para</p>') {
    const { container } = render(<TipTapEditor content={content} onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());
    return container;
  }

  const imageFile = (name = 'ok.jpg') => new File(['x'], name, { type: 'image/jpeg' });

  it('keeps the alt-text button usable in a document that is not just the image', async () => {
    // The regression: gating on editor.isActive('image') left this button
    // permanently disabled, because ProseMirror only makes a NodeSelection
    // after an insert when the image IS the whole document.
    vi.spyOn(forumService, 'uploadPostImage').mockResolvedValue(uploaded);
    const container = await mount();

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [imageFile()] },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(container.querySelector('img[data-image-id]')).toBeInTheDocument());

    const button = screen.getByRole('button', { name: 'Edit image alt text' });
    expect(button).toBeEnabled();
    await userEvent.click(button);
    await userEvent.type(await screen.findByLabelText(/describe this image/i), 'A monstera leaf');
    await userEvent.click(screen.getByRole('button', { name: 'Save alt text' }));

    await waitFor(() =>
      expect(container.querySelector('img[data-image-id]')?.getAttribute('alt')).toBe(
        'A monstera leaf'
      )
    );
  });

  it('refuses a second image while one is still uploading (AC 4, via paste too)', async () => {
    // The toolbar button's `disabled` did not cover paste/drop, and a boolean
    // flag was cleared by whichever upload settled first.
    let release: (v: typeof uploaded) => void = () => {};
    const uploadSpy = vi.spyOn(forumService, 'uploadPostImage').mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      })
    );
    const container = await mount();
    const editorEl = container.querySelector('.ProseMirror') as HTMLElement;

    fireEvent.change(screen.getByTestId('forum-image-input'), {
      target: { files: [imageFile('first.jpg')] },
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1));

    // Paste a second one while the first is still in flight.
    fireEvent.paste(editorEl, {
      clipboardData: {
        files: [imageFile('second.jpg')],
        items: [],
        types: ['Files'],
        getData: () => '',
      },
    });

    expect(await screen.findByText(/wait for the current image/i)).toBeInTheDocument();
    expect(uploadSpy).toHaveBeenCalledTimes(1);
    // No prompt for the refused file either.
    expect(screen.queryByRole('button', { name: 'Skip' })).not.toBeInTheDocument();

    release(uploaded);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Insert image' })).toBeEnabled());
  });

  it('reuses the SAME idempotency key when the same file is retried after a failure', async () => {
    // A fresh key per attempt is exactly what makes the server store a
    // duplicate row and orphan a file — the thing M36 exists to prevent.
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    const uploadSpy = vi
      .spyOn(forumService, 'uploadPostImage')
      .mockRejectedValueOnce(new Error('network flake'))
      .mockResolvedValueOnce(uploaded);
    await mount();

    const file = imageFile('retry-me.jpg');
    fireEvent.change(screen.getByTestId('forum-image-input'), { target: { files: [file] } });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(screen.getByText('network flake')).toBeInTheDocument());

    // Re-pick the SAME file.
    fireEvent.change(screen.getByTestId('forum-image-input'), { target: { files: [file] } });
    await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(2));

    expect(uploadSpy.mock.calls[1][2]).toBe(uploadSpy.mock.calls[0][2]);
  });

  it('refuses to guess which image to edit when the document holds several', async () => {
    // The old code ran updateAttributes('image', ...) against the LIVE
    // selection at Save time, so it would happily rewrite whichever image the
    // user had clicked while the prompt — still showing the first one's
    // preview — was open. Ambiguity is now refused instead of guessed at.
    vi.spyOn(forumService, 'uploadPostImage')
      .mockResolvedValueOnce({ ...uploaded, id: 11, url: 'https://cdn.example/a.jpg' })
      .mockResolvedValueOnce({ ...uploaded, id: 22, url: 'https://cdn.example/b.jpg' });
    const container = await mount('<p>intro</p>');

    for (const name of ['a.jpg', 'b.jpg']) {
      fireEvent.change(screen.getByTestId('forum-image-input'), {
        target: { files: [imageFile(name)] },
      });
      await userEvent.click(await screen.findByRole('button', { name: 'Skip' }));
      await waitFor(() =>
        expect(screen.getByRole('button', { name: 'Insert image' })).toBeEnabled()
      );
    }
    await waitFor(() => expect(container.querySelectorAll('img[data-image-id]')).toHaveLength(2));

    await userEvent.click(screen.getByRole('button', { name: 'Edit image alt text' }));

    expect(await screen.findByText(/select an image first/i)).toBeInTheDocument();
    // And nothing was silently rewritten.
    const alts = [...container.querySelectorAll('img[data-image-id]')].map((i) =>
      i.getAttribute('alt')
    );
    expect(alts).toEqual(['', '']);
  });

  it('tells the author to select an image when none is resolvable', async () => {
    const container = await mount('<p>only text here</p>');
    expect(container.querySelector('img[data-image-id]')).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: 'Edit image alt text' }));

    // A message, not a permanently-disabled button.
    expect(await screen.findByText(/select an image first/i)).toBeInTheDocument();
  });
});

describe('TipTapEditor alt preview src safety', () => {
  it('refuses a non-http(s)/blob src on the edit preview (CodeQL js/xss-through-dom)', async () => {
    // A user can put arbitrary markup in the document by pasting, so the src
    // read back off a node is attacker-influenced. React does not sanitize it.
    const { container } = render(
      <TipTapEditor
        content='<img src="javascript:alert(1)" data-image-id="5" alt="x">'
        onChange={vi.fn()}
      />
    );
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: 'Edit image alt text' }));

    const preview = await screen.findByLabelText(/describe this image/i);
    expect(preview).toBeInTheDocument();
    // The preview <img> is the one with an empty alt next to the label.
    const previewImg = container.querySelector('img.h-14');
    expect(previewImg).not.toBeNull();
    // Blanked -> React omits the attribute entirely. The property that matters
    // is that the hostile scheme never reaches the DOM.
    const src = previewImg?.getAttribute('src') ?? '';
    expect(src).not.toContain('javascript:');
    expect(src).toBe('');
  });
});
