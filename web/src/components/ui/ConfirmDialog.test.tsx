import { describe, it, expect, vi } from 'vitest';
import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ConfirmDialog from './ConfirmDialog';

const baseProps = {
  title: 'Delete this post?',
  message: 'This cannot be undone.',
  onConfirm: () => {},
  onCancel: () => {},
};

describe('ConfirmDialog', () => {
  it('renders nothing when closed', () => {
    render(<ConfirmDialog open={false} {...baseProps} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders an accessible modal dialog when open', () => {
    render(<ConfirmDialog open {...baseProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveTextContent('Delete this post?');
    expect(dialog).toHaveTextContent('This cannot be undone.');
  });

  it('calls onConfirm from the confirm button', async () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog open {...baseProps} confirmLabel="Delete" onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel from the cancel button and on Escape', async () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open {...baseProps} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);

    await userEvent.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it('focuses the confirm button on open and returns focus to the trigger on close', async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Open</button>
          <ConfirmDialog
            open={open}
            title="Delete?"
            message="Sure?"
            confirmLabel="Delete"
            onConfirm={() => setOpen(false)}
            onCancel={() => setOpen(false)}
          />
        </>
      );
    }
    render(<Harness />);
    const trigger = screen.getByRole('button', { name: 'Open' });
    trigger.focus();

    await userEvent.click(trigger);
    // Focus moves into the dialog (confirm button), not left on the trigger.
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveFocus();

    await userEvent.keyboard('{Escape}');
    // ...and returns to the trigger when the dialog closes (WCAG 2.4.3).
    expect(trigger).toHaveFocus();
  });
});
