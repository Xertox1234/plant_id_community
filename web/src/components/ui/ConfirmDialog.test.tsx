import { describe, it, expect, vi } from 'vitest';
import { useState } from 'react';
import { act, render, screen } from '@testing-library/react';
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

  // --- focus trap + once-per-open restore target (todo 396) ------------------

  function Harness({ onCancelSpy }: { onCancelSpy?: () => void }) {
    const [open, setOpen] = useState(false);
    const [ticks, setTicks] = useState(0);
    return (
      <>
        <button onClick={() => setOpen(true)}>Open</button>
        <button onClick={() => setTicks((t) => t + 1)}>Outside</button>
        {/* A parent re-render while the dialog is open. The inline onCancel
            gets a new identity each time, exactly as real callers pass it. */}
        <span data-testid="ticks">{ticks}</span>
        <ConfirmDialog
          open={open}
          title="Delete?"
          message="Sure?"
          confirmLabel="Delete"
          onConfirm={() => setOpen(false)}
          onCancel={() => {
            onCancelSpy?.();
            setOpen(false);
          }}
        />
        {open && <button onClick={() => setTicks((t) => t + 1)}>Rerender parent</button>}
      </>
    );
  }

  it('Tab from the last control wraps to the first instead of leaving the dialog', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Open' }));
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveFocus();

    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
  });

  it('Shift+Tab from the first control wraps to the last', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Open' }));
    screen.getByRole('button', { name: 'Cancel' }).focus();

    await userEvent.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveFocus();
  });

  it('Tab with focus outside the dialog (e.g. on <body>) pulls it back inside', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Open' }));
    (document.activeElement as HTMLElement).blur();
    expect(document.body).toHaveFocus();

    await userEvent.tab();
    // Not the page's first tabbable (the Open trigger behind the modal).
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
  });

  it('a parent re-render while open neither moves focus nor loses the trigger', async () => {
    const onCancelSpy = vi.fn();
    render(<Harness onCancelSpy={onCancelSpy} />);
    const trigger = screen.getByRole('button', { name: 'Open' });
    trigger.focus();
    await userEvent.click(trigger);

    const cancel = screen.getByRole('button', { name: 'Cancel' });
    cancel.focus();
    // Re-render the parent without moving focus: a new onCancel identity.
    act(() => {
      screen.getByRole('button', { name: 'Rerender parent' }).click();
    });
    expect(screen.getByTestId('ticks')).toHaveTextContent('1');
    // Focus stays where the user put it (not yanked back to Delete)...
    expect(cancel).toHaveFocus();

    await userEvent.keyboard('{Escape}');
    // ...Escape reaches the LATEST onCancel...
    expect(onCancelSpy).toHaveBeenCalledTimes(1);
    // ...and focus goes back to the original trigger, not to something that
    // was inside the dialog when the re-render happened.
    expect(trigger).toHaveFocus();
  });
});
