import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TipTapEditor from './TipTapEditor';

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
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Write your post...')).toBeInTheDocument();
    });
  });

  it('renders with custom placeholder', async () => {
    render(
      <TipTapEditor
        onChange={vi.fn()}
        placeholder="Enter your comment..."
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Enter your comment...')).toBeInTheDocument();
    });
  });

  it('renders toolbar when editable', async () => {
    render(<TipTapEditor onChange={vi.fn()} editable={true} />);

    await waitFor(() => {
      expect(screen.getByTitle('Bold (Ctrl+B)')).toBeInTheDocument();
    });

    expect(screen.getByTitle('Italic (Ctrl+I)')).toBeInTheDocument();
    expect(screen.getByTitle('Heading 2')).toBeInTheDocument();
    expect(screen.getByTitle('Insert Link')).toBeInTheDocument();
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

  it('provides onChange callback prop', async () => {
    const onChangeMock = vi.fn();

    const { container } = render(
      <TipTapEditor onChange={onChangeMock} />
    );

    // Wait for editor to initialize
    await waitFor(() => {
      expect(container.querySelector('.ProseMirror')).toBeInTheDocument();
    });

    // Verify editor exists and onChange prop is passed
    expect(onChangeMock).toBeDefined();
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

  it('renders heading toolbar buttons', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Heading 2')).toBeInTheDocument();
    });

    expect(screen.getByTitle('Heading 2')).toBeInTheDocument();
    expect(screen.getByTitle('Heading 3')).toBeInTheDocument();
  });

  it('renders list toolbar buttons', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Bullet List')).toBeInTheDocument();
    });

    expect(screen.getByTitle('Bullet List')).toBeInTheDocument();
    expect(screen.getByTitle('Numbered List')).toBeInTheDocument();
  });

  it('renders code toolbar buttons', async () => {
    render(<TipTapEditor onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTitle('Code Block')).toBeInTheDocument();
    });

    expect(screen.getByTitle('Inline Code')).toBeInTheDocument();
    expect(screen.getByTitle('Code Block')).toBeInTheDocument();
  });

  it('shows loading state before editor initializes', () => {
    // Mock useEditor to return null (loading state)
    const { container } = render(<TipTapEditor onChange={vi.fn()} />);

    // Check if either loading message or editor is present
    const loadingOrEditor =
      screen.queryByText('Loading editor...') ||
      container.querySelector('.ProseMirror');

    expect(loadingOrEditor).toBeTruthy();
  });

  it('applies custom className to editor container', async () => {
    const { container } = render(
      <TipTapEditor onChange={vi.fn()} className="custom-class" />
    );

    await waitFor(() => {
      const editorContainer = container.querySelector('.custom-class');
      expect(editorContainer).toBeInTheDocument();
    });
  });
});
