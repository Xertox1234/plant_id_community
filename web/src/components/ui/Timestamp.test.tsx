import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Timestamp from './Timestamp';

describe('Timestamp', () => {
  it('renders a <time> with datetime, a relative label, and an accessible absolute date', () => {
    const iso = new Date(Date.now() - 1000 * 60 * 30).toISOString(); // 30 min ago
    const { container } = render(<Timestamp iso={iso} prefix="Posted" />);

    const time = container.querySelector('time');
    expect(time).not.toBeNull();
    // Machine-readable datetime is the exact ISO string.
    expect(time).toHaveAttribute('dateTime', iso);
    // Visible text is the relative form (accessible on touch/SR via aria-label).
    expect(time).toHaveTextContent(/ago/i);
    // Absolute date is reachable by SR/touch, prefixed, not hover-only.
    const absolute = new Date(iso).toLocaleString();
    expect(time).toHaveAttribute('aria-label', `Posted ${absolute}`);
    expect(time).toHaveAttribute('title', absolute);
  });

  it('falls back to plain "recently" text for an unparseable date, with no <time>', () => {
    const { container } = render(<Timestamp iso="not-a-date" />);
    expect(container.querySelector('time')).toBeNull();
    expect(screen.getByText('recently')).toBeInTheDocument();
  });
});
