import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FileUpload from './FileUpload';

/**
 * jsdom implements neither `URL.createObjectURL` nor `revokeObjectURL` (no
 * blob URL store), so selecting a file would throw on preview. Same stub as
 * `TipTapEditor.test.tsx` (web/src/components/forum/TipTapEditor.test.tsx) —
 * copy it exactly, don't invent a different one.
 */
beforeAll(() => {
  const url = URL as unknown as Record<string, unknown>;
  url.createObjectURL = vi.fn(() => 'blob:preview-mock');
  url.revokeObjectURL = vi.fn();
});

describe('FileUpload', () => {
  it('shows the drop-zone prompt when idle', () => {
    render(<FileUpload onFileSelect={vi.fn()} />);
    expect(screen.getByText('Drop your plant photo here')).toBeInTheDocument();
    expect(screen.getByLabelText(/upload plant image/i)).toBeInTheDocument();
  });

  it('applies the drag-active treatment on dragenter and clears it on dragleave', () => {
    render(<FileUpload onFileSelect={vi.fn()} />);
    // The dashed drop-zone is the input's ancestor with the border classes.
    const dropZone = screen.getByLabelText(/upload plant image/i).closest('div')!;

    fireEvent.dragEnter(dropZone);
    expect(dropZone).toHaveClass('border-primary');

    fireEvent.dragLeave(dropZone);
    expect(dropZone).not.toHaveClass('border-primary');
  });

  it('shows a preview and a remove button after a file is selected', () => {
    const onFileSelect = vi.fn();
    render(<FileUpload onFileSelect={onFileSelect} />);

    const file = new File(['x'], 'plant.jpg', { type: 'image/jpeg' });
    const input = screen.getByLabelText(/upload plant image/i);
    fireEvent.change(input, { target: { files: [file] } });

    expect(screen.getByRole('button', { name: /remove image/i })).toBeInTheDocument();
    expect(onFileSelect).toHaveBeenCalledWith(file);
  });
});
