import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DiseaseDiagnosePage from './DiseaseDiagnosePage';
import { diseaseService } from '../../services/diseaseService';

vi.mock('../../services/diseaseService');
// FileUpload renders an <input type=file>; we drive it directly.
vi.mock('../../components/PlantIdentification/FileUpload', () => ({
  default: ({ onFileSelect }: { onFileSelect: (f: File | null) => void }) => (
    <input
      type="file"
      aria-label="upload"
      onChange={(e) => onFileSelect(e.target.files?.[0] ?? null)}
    />
  ),
}));

describe('DiseaseDiagnosePage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('submits and renders a diagnosis result', async () => {
    vi.mocked(diseaseService.submitDiagnosis).mockResolvedValue({
      request_id: 'r1',
      status: 'diagnosed',
    });
    vi.mocked(diseaseService.getDiagnosisResults).mockResolvedValue({
      request_id: 'r1',
      status: 'diagnosed',
      results: [
        {
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
        },
      ],
    });

    render(<DiseaseDiagnosePage />);
    const file = new File(['img'], 'leaf.jpg', { type: 'image/jpeg' });
    await userEvent.upload(screen.getByLabelText('upload'), file);
    await userEvent.type(screen.getByLabelText(/symptoms/i), 'black spots on leaves');
    await userEvent.click(screen.getByRole('button', { name: /diagnose/i }));

    await waitFor(() => expect(screen.getByText('Black Spot')).toBeInTheDocument());
    expect(screen.getByText(/88% confidence/)).toBeInTheDocument();
  });

  it('shows an error when status is failed', async () => {
    vi.mocked(diseaseService.submitDiagnosis).mockResolvedValue({
      request_id: 'r2',
      status: 'failed',
    });
    vi.mocked(diseaseService.getDiagnosisResults).mockResolvedValue({
      request_id: 'r2',
      status: 'failed',
      results: [],
    });

    render(<DiseaseDiagnosePage />);
    await userEvent.upload(
      screen.getByLabelText('upload'),
      new File(['i'], 'a.jpg', { type: 'image/jpeg' })
    );
    await userEvent.type(screen.getByLabelText(/symptoms/i), 'wilting');
    await userEvent.click(screen.getByRole('button', { name: /diagnose/i }));

    await waitFor(() => expect(screen.getByText(/diagnosis unavailable/i)).toBeInTheDocument());
  });

  it('disables submit until an image and symptoms are provided', () => {
    render(<DiseaseDiagnosePage />);
    expect(screen.getByRole('button', { name: /diagnose/i })).toBeDisabled();
  });
});
