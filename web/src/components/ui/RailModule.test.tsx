import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Users } from 'lucide-react';
import RailModule from './RailModule';

describe('RailModule', () => {
  it('renders a titled section with children', () => {
    render(
      <RailModule icon={<Users aria-hidden="true" />} title="Experts online">
        <p>Iris Delgado</p>
      </RailModule>
    );
    expect(screen.getByRole('heading', { name: 'Experts online' })).toBeInTheDocument();
    expect(screen.getByText('Iris Delgado')).toBeInTheDocument();
  });
});
