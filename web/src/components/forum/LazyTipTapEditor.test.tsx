import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const editorModule = () => ({
  default: ({ placeholder }: { placeholder?: string }) => <textarea aria-label={placeholder} />,
});

/** A fresh module each time: the loaded editor is cached at module level. */
async function freshEditor() {
  vi.resetModules();
  return (await import('./LazyTipTapEditor')).default;
}

describe('LazyTipTapEditor (audit F110)', () => {
  beforeEach(() => {
    vi.doMock('./TipTapEditor', editorModule);
  });

  it('holds the space with an announced placeholder, then shows the editor', async () => {
    const Editor = await freshEditor();
    render(<Editor placeholder="Write a reply..." />);
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Loading editor…');
    expect(status.parentElement).toHaveClass('min-h-[15.25rem]', 'sm:min-h-[21.5rem]');
    expect(await screen.findByLabelText('Write a reply...')).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('a remount after loading shows the editor at once', async () => {
    const Editor = await freshEditor();
    const { rerender } = render(<Editor key="1" placeholder="a" />);
    await screen.findByLabelText('a');
    rerender(<Editor key="2" placeholder="b" />);
    expect(screen.getByLabelText('b')).toBeInTheDocument();
  });

  it('a failed download says so and can be retried', async () => {
    vi.doMock('./TipTapEditor', () => {
      throw new Error('chunk gone');
    });
    const Editor = await freshEditor();
    render(<Editor placeholder="a" />);
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
    vi.resetModules();
    vi.doMock('./TipTapEditor', editorModule);
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByLabelText('a')).toBeInTheDocument();
  });
});
