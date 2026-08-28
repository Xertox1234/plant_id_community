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
    expect(screen.getByText('60%').closest('span')).toHaveTextContent('60% match');
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

  it('renders without crashing for a probability-only suggestion — the real API shape (todo 313)', () => {
    // Real `suggestions[]` items only ever carry `probability`, never
    // `confidence`. The onSavePlant path (unconditionally invoked during
    // render via getPlantKey) crashed on exactly this shape before the fix.
    const realShapeResults: PlantIdentificationResult = {
      plant_name: 'Monstera deliciosa',
      confidence: 0.99,
      source: 'plant_id',
      suggestions: [
        {
          plant_name: 'Monstera deliciosa',
          scientific_name: 'Monstera deliciosa',
          probability: 0.99,
          source: 'plant_id',
        },
      ],
    };

    expect(() =>
      render(
        <IdentificationResults
          results={realShapeResults}
          loading={false}
          error={null}
          onSavePlant={vi.fn()}
          savedPlants={new Map()}
          savingPlant={null}
        />
      )
    ).not.toThrow();
    expect(
      screen.getByRole('button', { name: /save monstera deliciosa to collection/i })
    ).toBeInTheDocument();
  });

  it('renders 0%, not NaN%, for a suggestion with neither probability nor confidence', () => {
    const noConfidenceResults: PlantIdentificationResult = {
      plant_name: 'Monstera deliciosa',
      confidence: 0.99,
      source: 'plant_id',
      suggestions: [{ plant_name: 'Monstera deliciosa', source: 'plant_id' }],
    };
    render(<IdentificationResults results={noConfidenceResults} loading={false} error={null} />);
    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.queryByText(/nan/i)).not.toBeInTheDocument();
  });
});
