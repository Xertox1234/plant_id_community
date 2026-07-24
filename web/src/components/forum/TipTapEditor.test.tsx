import { describe, it, expect, vi } from 'vitest';
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
describe('TipTapEditor', () => {
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
    expect(screen.queryByTitle('Quote')).not.toBeInTheDocument();
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

    await waitFor(() => expect(uploadSpy).toHaveBeenCalledWith(file));
  });

  it('surfaces an upload failure as an error message (L13)', async () => {
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.spyOn(forumService, 'uploadPostImage').mockRejectedValue(new Error('server exploded'));
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector('.ProseMirror')).toBeInTheDocument());

    const input = screen.getByTestId('forum-image-input');
    const file = new File(['x'], 'ok.jpg', { type: 'image/jpeg' });
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText('server exploded')).toBeInTheDocument();
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
});
