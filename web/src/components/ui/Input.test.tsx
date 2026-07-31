import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Input from './Input';

/**
 * Input — the app's shared form primitive, and the widest-reach site of the
 * M26 live-region migration (audit 2026-07-11, todo 278).
 *
 * The property under test is not "an error renders" — it is that the error
 * text changes *inside a node that was already there*. MDN is explicit that a
 * live region must exist in the DOM before its content changes; the
 * conditional-mount pattern this replaced (`{error && <p role="alert">}`) is
 * generally not announced at all.
 */
describe('Input', () => {
  it('renders the label and wires it to the control', () => {
    render(<Input name="email" label="Email address" />);

    expect(screen.getByLabelText(/email address/i)).toBe(screen.getByRole('textbox'));
  });

  it('marks the control invalid and describes it by the error node', () => {
    render(<Input name="email" label="Email address" error="Email is required" />);

    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'email-error');
    expect(document.getElementById('email-error')).toHaveTextContent('Email is required');
  });

  it('leaves the live region mounted and empty before any error (audit M26)', () => {
    render(<Input name="email" label="Email address" />);

    const region = document.getElementById('email-error');
    expect(region).toBeInTheDocument();
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveTextContent('');
    // Empty means invisible, not absent — sr-only is out of the layout.
    expect(region).toHaveClass('sr-only');
    // Nothing to describe yet, so the control points at nothing.
    expect(screen.getByRole('textbox')).not.toHaveAttribute('aria-describedby');
  });

  it('swaps the error text inside the SAME node instead of remounting it', () => {
    const { rerender } = render(<Input name="email" label="Email address" />);

    const region = document.getElementById('email-error');

    rerender(<Input name="email" label="Email address" error="Email is required" />);
    // Same DOM node, new text — this identity check is the whole point: a
    // remounted region announces nothing.
    expect(document.getElementById('email-error')).toBe(region);
    expect(region).toHaveTextContent('Email is required');
    expect(region).not.toHaveClass('sr-only');

    rerender(<Input name="email" label="Email address" error="Email is not valid" />);
    expect(document.getElementById('email-error')).toBe(region);
    expect(region).toHaveTextContent('Email is not valid');

    rerender(<Input name="email" label="Email address" />);
    expect(document.getElementById('email-error')).toBe(region);
    expect(region).toHaveTextContent('');
  });

  it('does not use role="alert" — the anti-pattern this replaced', () => {
    render(<Input name="email" label="Email address" error="Email is required" />);

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
