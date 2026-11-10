import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ConsentCheckbox from './ConsentCheckbox';

describe('ConsentCheckbox', () => {
  it('is unticked by default and labelled with the exact copy', () => {
    render(<ConsentCheckbox checked={false} onChange={vi.fn()} />);
    const box = screen.getByRole('checkbox', {
      name: 'I am 14 or older, and I have read and accept the Privacy Policy and Terms of Service.',
    });
    expect(box).not.toBeChecked();
  });

  it('links to /privacy and /terms in a new tab', () => {
    render(<ConsentCheckbox checked={false} onChange={vi.fn()} />);
    for (const [name, href] of [
      ['Privacy Policy', '/privacy'],
      ['Terms of Service', '/terms'],
    ]) {
      const link = screen.getByRole('link', { name });
      expect(link).toHaveAttribute('href', href);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
    }
  });

  it('reports the new value when the box is clicked', () => {
    const onChange = vi.fn();
    render(<ConsentCheckbox checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('toggles when the label text (outside the links) is clicked', async () => {
    const onChange = vi.fn();
    render(<ConsentCheckbox checked={false} onChange={onChange} />);
    await userEvent.click(screen.getByText(/I am 14 or older/));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('toggles from the keyboard with Space', async () => {
    const onChange = vi.fn();
    render(<ConsentCheckbox checked={false} onChange={onChange} />);
    await userEvent.tab();
    expect(screen.getByRole('checkbox')).toHaveFocus();
    await userEvent.keyboard(' ');
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('does not toggle the box when a link inside the label is clicked', async () => {
    const onChange = vi.fn();
    render(<ConsentCheckbox checked={false} onChange={onChange} />);
    // Stop the jsdom navigation a click on an anchor would otherwise attempt.
    const privacy = screen.getByRole('link', { name: 'Privacy Policy' });
    privacy.addEventListener('click', (e) => e.preventDefault());
    await userEvent.click(privacy);
    await userEvent.click(screen.getByRole('link', { name: 'Terms of Service' }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
