import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Leaf } from 'lucide-react';
import StatCard from './StatCard';

describe('StatCard', () => {
  it('renders value, label, sublabel and progress', () => {
    render(
      <StatCard
        icon={<Leaf aria-hidden="true" />}
        value={34}
        label="Identifications"
        sublabel="16 to your Botanist badge"
        tone="sage"
        progress={{ value: 34, max: 50 }}
      />
    );
    expect(screen.getByText('34')).toBeInTheDocument();
    expect(screen.getByText('Identifications')).toBeInTheDocument();
    expect(screen.getByText('16 to your Botanist badge')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Identifications' })).toBeInTheDocument();
  });
});
