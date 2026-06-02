// web/src/components/ui/Eyebrow.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Eyebrow from './Eyebrow';

describe('Eyebrow', () => {
  it('renders uppercase muted text', () => {
    render(<Eyebrow>Plant Identification</Eyebrow>);
    const el = screen.getByText('Plant Identification');
    expect(el).toHaveClass('uppercase');
    expect(el).toHaveClass('text-ink-3');
  });
});
