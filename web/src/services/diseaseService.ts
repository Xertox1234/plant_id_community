/**
 * Disease Diagnosis Service
 *
 * Submits a sick-plant photo + symptoms to the existing disease-requests API and
 * reads back the diagnosis. Cookie/CSRF auth, versioned /api/v1/ URLs (mirrors
 * plantIdService). Phase A: single image, synchronous POST -> GET results.
 */

import { getCsrfToken } from '../utils/csrf';
import type { DiseaseDiagnosisCreated, DiseaseDiagnosisResults } from '../types/diagnosis';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_VERSION = 'v1';
const BASE = `${API_BASE_URL}/api/${API_VERSION}/plant-identification/disease-requests`;

export interface SubmitDiagnosisInput {
  image: File;
  symptoms_description: string;
  plant_condition?: string;
  location?: string;
}

function extractErrorMessage(data: unknown): string | undefined {
  if (data === null || typeof data !== 'object') return undefined;
  const d = data as Record<string, unknown>;
  for (const k of ['message', 'detail', 'error', 'non_field_errors']) {
    const v = d[k];
    if (typeof v === 'string' && v) return v;
    if (Array.isArray(v) && typeof v[0] === 'string') return v[0];
  }
  return undefined;
}

async function submitDiagnosis(input: SubmitDiagnosisInput): Promise<DiseaseDiagnosisCreated> {
  const form = new FormData();
  form.append('image_1', input.image);
  form.append('symptoms_description', input.symptoms_description);
  if (input.plant_condition) form.append('plant_condition', input.plant_condition);
  if (input.location) form.append('location', input.location);

  const csrfToken = await getCsrfToken();
  const response = await fetch(`${BASE}/`, {
    method: 'POST',
    credentials: 'include',
    headers: { ...(csrfToken && { 'X-CSRFToken': csrfToken }) },
    body: form,
  });
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    throw new Error(extractErrorMessage(data) || 'Failed to submit diagnosis. Please try again.');
  }
  return response.json();
}

async function getDiagnosisResults(requestId: string): Promise<DiseaseDiagnosisResults> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(`${BASE}/${requestId}/results/`, {
    credentials: 'include',
    headers: { ...(csrfToken && { 'X-CSRFToken': csrfToken }) },
  });
  if (!response.ok) {
    throw new Error('Failed to load diagnosis results.');
  }
  return response.json();
}

export const diseaseService = { submitDiagnosis, getDiagnosisResults };
