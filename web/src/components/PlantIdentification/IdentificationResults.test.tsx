import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import IdentificationResults from './IdentificationResults';
import type { PlantIdentificationResult } from '@/types';

const RESULTS: PlantIdentificationResult = {
  plant_name: 'Swiss cheese plant',
  confidence: 0.82,
  source: 'plant_id',
  suggestions: [
    {
      plant_name: 'Swiss cheese plant',
      scientific_name: 'Monstera deliciosa',
      probability: 0.82,
      confidence: 0.82,
      source: 'plant_id',
    },
    {
      plant_name: 'Heartleaf philodendron',
      scientific_name: 'Philodendron hederaceum',
      probability: 0.11,
      confidence: 0.11,
      source: 'plant_id',
    },
  ],
};

describe('IdentificationResults', () => {
  it('renders each suggestion with a confidence pill, not a Chip button', () => {
    render(<IdentificationResults results={RESULTS} loading={false} error={null} />);

    expect(screen.getByText('Swiss cheese plant')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getByText('11%')).toBeInTheDocument();

    // The confidence readout is a static value — must not be a button.
    expect(screen.queryByRole('button', { name: /82%/ })).not.toBeInTheDocument();
  });

  it('renders disease suggestions with a match-percentage pill', () => {
    const withDisease: PlantIdentificationResult = {
      ...RESULTS,
      disease_suggestions: [{ name: 'Leaf spot', probability: 0.6, description: 'Fungal.' }],
    };
    render(<IdentificationResults results={withDisease} loading={false} error={null} />);

    expect(screen.getByText('Leaf spot')).toBeInTheDocument();
    expect(screen.getByText('60%')).toBeInTheDocument();
  });

  it('shows the save-to-collection action per suggestion when onSavePlant is provided', () => {
    render(
      <IdentificationResults
        results={RESULTS}
        loading={false}
        error={null}
        onSavePlant={vi.fn()}
        savedPlants={new Map()}
        savingPlant={null}
      />
    );
    expect(screen.getAllByRole('button', { name: /save .* to collection/i })).toHaveLength(2);
  });
});
