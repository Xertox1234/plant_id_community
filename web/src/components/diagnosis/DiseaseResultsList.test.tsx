import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DiseaseResultsList from './DiseaseResultsList';
import type { PlantDiseaseResult } from '@/types/diagnosis';

const RESULT: PlantDiseaseResult = {
  id: 1,
  uuid: 'u1',
  request_id: 'r1',
  suggested_disease_name: 'Black Spot',
  suggested_disease_type: 'fungal',
  confidence_score: 0.88,
  confidence_percentage: 88,
  diagnosis_source: 'api_plant_health',
  severity_assessment: 'moderate',
  symptoms_identified: 'black spots',
  recommended_treatments: 'fungicide',
  immediate_actions: 'remove affected leaves',
  notes: '',
  is_primary: true,
  display_name: 'Black Spot',
};

describe('DiseaseResultsList', () => {
  it('renders a result with a match-percentage pill, not a Chip button', () => {
    render(<DiseaseResultsList results={[RESULT]} />);

    expect(screen.getByText('Black Spot')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
    expect(screen.getByLabelText('88% confidence')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /88%/ })).not.toBeInTheDocument();
    expect(screen.getByText(/black spots/)).toBeInTheDocument();
  });

  it('renders a system_message result as a status notice, not a disease card', () => {
    const notice: PlantDiseaseResult = {
      ...RESULT,
      diagnosis_source: 'system_message',
      notes: 'Service unavailable — please try again.',
    };
    render(<DiseaseResultsList results={[notice]} />);

    expect(screen.getByRole('status')).toHaveTextContent('Service unavailable');
    expect(screen.queryByText('88%')).not.toBeInTheDocument();
  });

  it('shows the empty-results message when there are no results', () => {
    render(<DiseaseResultsList results={[]} />);
    expect(screen.getByRole('status')).toHaveTextContent('No diagnosis was produced');
  });
});
