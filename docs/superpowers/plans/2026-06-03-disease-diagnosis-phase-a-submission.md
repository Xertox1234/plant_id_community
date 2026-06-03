# Disease Diagnosis Phase A (Submission Flow) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A logged-in user opens a new web `/diagnose` page, uploads a sick-plant photo + symptoms, and sees the AI disease diagnosis rendered — using the existing backend, plus one tiny backend change so its create response is usable.

**Architecture:** Web POSTs to the existing `POST /api/v1/plant-identification/disease-requests/` (which runs `diagnose_disease_from_request` synchronously), reads back `{request_id, status}`, then GETs `…/disease-requests/{uuid}/results/` and renders the results. The only backend change is exposing `request_id` + `status` (read-only) in the create response. No models, no migration. Save/track/reminders (Phase B) and async (Phase C) are out of scope.

**Tech Stack:** Django/DRF (backend), React 19 + TypeScript + Tailwind 4 + Vitest + react-router-dom (web). Cookie/CSRF auth.

**Spec:** `docs/superpowers/specs/2026-06-03-disease-diagnosis-phase-a-submission-design.md`
**Branch:** `feat/disease-diagnosis-phase-a-submission` (already created).

**Confirmed during planning:** `diagnose_disease_from_request` does **NOT** fabricate fake diseases. On no-results it creates one honest `PlantDiseaseResult` with `diagnosis_source="system_message"`, empty `suggested_disease_name`, `confidence_score=0.0`, and a "services unavailable — ask the community" `notes`. The results UI must render a `system_message` result as a message, not a disease card.

**Commands:** Backend from `backend/` with `source venv/bin/activate`. Web from `web/`. Commits: pre-commit runs flake8/kimi/markdownlint (web side runs eslint/prettier); if a linter reformats a file and aborts the commit, `git add -A` and re-run.

---

## Pre-flight

- [ ] **Step 0.1: Confirm branch + baselines green**

```bash
git branch --show-current   # feat/disease-diagnosis-phase-a-submission
cd backend && source venv/bin/activate && python manage.py test apps.plant_identification --keepdb 2>&1 | tail -2
cd ../web && npm run type-check && npm run test 2>&1 | tail -5
```

Expected: branch correct; backend `OK`; web type-check clean and vitest passing.

---

## Task 1: Backend — expose `request_id` + `status` in the create response

**Files:**

- Modify: `backend/apps/plant_identification/serializers.py` (`PlantDiseaseRequestCreateSerializer`, ~L209-225)
- Test: `backend/apps/plant_identification/test_api.py` (`TestDiseasesDiagnosisAPI`, add one test)

- [ ] **Step 1.1: Write the failing test**

Add to `class TestDiseasesDiagnosisAPI` in `test_api.py` (it already has `create_diseased_image`, `setUp`, and the `@patch` convention):

```python
    @pytest.mark.api
    @patch(
        "apps.plant_identification.services.disease_diagnosis_service.PlantDiseaseService.diagnose_disease_from_request"
    )
    def test_create_response_returns_request_id_and_status(self, mock_diagnose):
        """POST create must return request_id + status so the client can fetch results."""
        mock_diagnose.return_value = []
        self.client.force_authenticate(user=self.user)
        url = reverse("v1:plant_identification:disease-requests-list")
        data = {
            "symptoms_description": "Yellow leaves with black spots",
            "image_1": self.create_diseased_image(),
        }

        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("request_id", response.data)
        self.assertTrue(response.data["request_id"])  # non-empty UUID
        self.assertIn("status", response.data)
        # perform_create ran the (mocked, no-op) diagnosis; status is set by the service
        # path. With diagnose mocked to return [], the request stays whatever the view
        # left it — assert the field is present and a known value.
        self.assertIn(
            response.data["status"],
            ["pending", "processing", "diagnosed", "needs_help", "failed"],
        )
```

- [ ] **Step 1.2: Run it — expect FAIL**

```bash
cd backend && source venv/bin/activate
python manage.py test apps.plant_identification.test_api.TestDiseasesDiagnosisAPI.test_create_response_returns_request_id_and_status --keepdb 2>&1 | tail -5
```

Expected: FAIL — `KeyError`/`assertIn` on `request_id` (the create serializer doesn't expose it).

- [ ] **Step 1.3: Add the two read-only fields**

In `serializers.py`, edit `PlantDiseaseRequestCreateSerializer`:

```python
class PlantDiseaseRequestCreateSerializer(serializers.ModelSerializer):
    """Specialized serializer for creating disease diagnosis requests."""

    request_id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = PlantDiseaseRequest
        fields = [
            "request_id",
            "status",
            "plant_identification_request",
            "plant_species",
            "image_1",
            "image_2",
            "image_3",
            "symptoms_description",
            "plant_condition",
            "location",
            "recent_weather",
            "recent_care_changes",
        ]
```

(`validate` is unchanged.)

- [ ] **Step 1.4: Run it — expect PASS**

```bash
python manage.py test apps.plant_identification.test_api.TestDiseasesDiagnosisAPI.test_create_response_returns_request_id_and_status --keepdb 2>&1 | tail -3
```

Expected: `OK`.

- [ ] **Step 1.5: flake8 + full app suite + commit**

```bash
flake8 apps/plant_identification/serializers.py apps/plant_identification/test_api.py
python manage.py test apps.plant_identification --keepdb 2>&1 | tail -2   # expect OK
git add -A && git commit -m "feat(disease): expose request_id + status in create response"
```

---

## Task 2: Web — diagnosis result types (backend enum)

**Files:**

- Modify: `web/src/types/diagnosis.ts`

- [ ] **Step 2.1: Add the types + fix the stale status enum**

Add to `web/src/types/diagnosis.ts` (and within the file, change any `status` union that contains `'completed'` to the backend enum below):

```typescript
export type DiseaseRequestStatus =
  | 'pending'
  | 'processing'
  | 'diagnosed'
  | 'needs_help'
  | 'failed';

/** One AI diagnosis result — mirrors PlantDiseaseResultSerializer. */
export interface PlantDiseaseResult {
  id: number;
  uuid: string;
  request_id: string;
  suggested_disease_name: string;
  suggested_disease_type: string;
  confidence_score: number;
  confidence_percentage: number;
  diagnosis_source: string; // "api_plant_health" | "system_message" | ...
  severity_assessment: string;
  symptoms_identified: string;
  recommended_treatments: string;
  immediate_actions: string;
  notes: string;
  is_primary: boolean;
  display_name: string;
}

/** Response of GET /disease-requests/{uuid}/results/. */
export interface DiseaseDiagnosisResults {
  request_id: string;
  status: DiseaseRequestStatus;
  results: PlantDiseaseResult[];
}

/** Response of POST /disease-requests/ (create). */
export interface DiseaseDiagnosisCreated {
  request_id: string;
  status: DiseaseRequestStatus;
}
```

If a stale `DiagnosisResponse`/`DiagnosisRequest`/`Disease` interface exists with `status: ... 'completed' ...` and is unused, delete it (grep first: `grep -rn "DiagnosisResponse\|DiagnosisRequest\b\|'completed'" web/src` — only remove if no non-test importer).

- [ ] **Step 2.2: Type-check + commit**

```bash
cd web && npm run type-check 2>&1 | tail -3   # expect no errors
git add -A && git commit -m "feat(disease): web types for diagnosis results (backend status enum)"
```

---

## Task 3: Web — `diseaseService.ts`

**Files:**

- Create: `web/src/services/diseaseService.ts`
- Test: `web/src/services/diseaseService.test.ts`

- [ ] **Step 3.1: Write the failing test**

`web/src/services/diseaseService.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { diseaseService } from './diseaseService';
import { clearCsrfToken } from '../utils/csrf';

vi.mock('../utils/logger', () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));

describe('diseaseService', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let cookie = 'csrftoken=test-csrf-token';

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
    Object.defineProperty(document, 'cookie', {
      get: () => cookie,
      set: (v: string) => (cookie = v),
      configurable: true,
    });
    clearCsrfToken();
    document.head.querySelector('meta[name="csrf-token"]')?.remove();
    const meta = document.createElement('meta');
    meta.setAttribute('name', 'csrf-token');
    meta.setAttribute('content', 'test-csrf-token');
    document.head.appendChild(meta);
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearCsrfToken();
    document.head.querySelector('meta[name="csrf-token"]')?.remove();
    vi.restoreAllMocks();
  });

  it('submitDiagnosis POSTs multipart with CSRF and returns request_id + status', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ request_id: 'req-1', status: 'diagnosed' }),
    });
    const file = new File(['img'], 'leaf.jpg', { type: 'image/jpeg' });

    const res = await diseaseService.submitDiagnosis({
      image: file,
      symptoms_description: 'black spots',
    });

    expect(res).toEqual({ request_id: 'req-1', status: 'diagnosed' });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/plant-identification/disease-requests/');
    expect(opts.method).toBe('POST');
    expect(opts.credentials).toBe('include');
    expect(opts.headers['X-CSRFToken']).toBe('test-csrf-token');
    expect(opts.body).toBeInstanceOf(FormData);
  });

  it('getDiagnosisResults GETs with CSRF header and returns results', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ request_id: 'req-1', status: 'diagnosed', results: [] }),
    });

    const res = await diseaseService.getDiagnosisResults('req-1');

    expect(res.request_id).toBe('req-1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/plant-identification/disease-requests/req-1/results/');
    expect(opts.headers['X-CSRFToken']).toBe('test-csrf-token'); // CSRF on GET, like plantIdService.getHistory
    expect(opts.credentials).toBe('include');
  });

  it('submitDiagnosis throws a useful error on non-ok', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: 'At least one symptom image is required for disease diagnosis.' }),
    });
    const file = new File(['img'], 'leaf.jpg', { type: 'image/jpeg' });
    await expect(
      diseaseService.submitDiagnosis({ image: file, symptoms_description: '' })
    ).rejects.toThrow('At least one symptom image is required');
  });
});
```

- [ ] **Step 3.2: Run it — expect FAIL**

```bash
cd web && npx vitest run src/services/diseaseService.test.ts 2>&1 | tail -8
```

Expected: FAIL — cannot import `./diseaseService`.

- [ ] **Step 3.3: Implement `diseaseService.ts`**

`web/src/services/diseaseService.ts`:

```typescript
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
```

- [ ] **Step 3.4: Run it — expect PASS, then lint + commit**

```bash
npx vitest run src/services/diseaseService.test.ts 2>&1 | tail -4   # expect pass
npm run lint 2>&1 | tail -3
git add -A && git commit -m "feat(disease): diseaseService (submit + getResults, CSRF, v1)"
```

---

## Task 4: Web — `DiseaseResultsList` presentational component

> Named `DiseaseResultsList` (not `DiseaseDiagnosisResults`) to avoid colliding with the
> `DiseaseDiagnosisResults` *type* from Task 2.

**Files:**

- Create: `web/src/components/diagnosis/DiseaseResultsList.tsx`

- [ ] **Step 4.1: Implement the component**

`web/src/components/diagnosis/DiseaseResultsList.tsx`:

```tsx
import type { PlantDiseaseResult } from '@/types/diagnosis';

interface Props {
  results: PlantDiseaseResult[];
}

/**
 * Renders disease diagnosis results. A `system_message` result (honest "service
 * unavailable / ask the community" fallback) is rendered as a notice, not a disease card.
 */
export default function DiseaseResultsList({ results }: Props) {
  if (results.length === 0) {
    return (
      <p className="text-ink-2" role="status">
        No diagnosis was produced. Please try a clearer photo and a fuller symptom description.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((r) => {
        if (r.diagnosis_source === 'system_message') {
          return (
            <div
              key={r.id}
              role="status"
              className="bg-surface-3 border border-line rounded-lg p-4 text-ink-2"
            >
              {r.notes}
            </div>
          );
        }
        return (
          <div
            key={r.id}
            className={`bg-surface-2 border rounded-xl p-5 ${
              r.is_primary ? 'border-primary' : 'border-line'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-ink">
                {r.suggested_disease_name || r.display_name || 'Unknown condition'}
              </h3>
              <span className="text-sm font-medium text-ink-2">
                {r.confidence_percentage}% confidence
              </span>
            </div>
            {r.severity_assessment && (
              <p className="mt-1 text-sm text-ink-2">Severity: {r.severity_assessment}</p>
            )}
            {r.symptoms_identified && (
              <p className="mt-3 text-sm text-ink">
                <span className="font-medium">Symptoms: </span>
                {r.symptoms_identified}
              </p>
            )}
            {r.immediate_actions && (
              <p className="mt-2 text-sm text-ink">
                <span className="font-medium">Immediate actions: </span>
                {r.immediate_actions}
              </p>
            )}
            {r.recommended_treatments && (
              <p className="mt-2 text-sm text-ink">
                <span className="font-medium">Recommended treatments: </span>
                {r.recommended_treatments}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4.2: Type-check + lint + commit**

```bash
cd web && npm run type-check 2>&1 | tail -3 && npm run lint 2>&1 | tail -3
git add -A && git commit -m "feat(disease): DiseaseResultsList component"
```

---

## Task 5: Web — `DiseaseDiagnosePage`

**Files:**

- Create: `web/src/pages/diagnosis/DiseaseDiagnosePage.tsx`
- Test: `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx`

- [ ] **Step 5.1: Write the failing test**

`web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx`:

```tsx
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
          id: 1, uuid: 'u1', request_id: 'r1',
          suggested_disease_name: 'Black Spot', suggested_disease_type: 'fungal',
          confidence_score: 0.88, confidence_percentage: 88, diagnosis_source: 'api_plant_health',
          severity_assessment: 'moderate', symptoms_identified: 'black spots',
          recommended_treatments: 'fungicide', immediate_actions: 'remove affected leaves',
          notes: '', is_primary: true, display_name: 'Black Spot',
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
    vi.mocked(diseaseService.submitDiagnosis).mockResolvedValue({ request_id: 'r2', status: 'failed' });
    vi.mocked(diseaseService.getDiagnosisResults).mockResolvedValue({
      request_id: 'r2', status: 'failed', results: [],
    });

    render(<DiseaseDiagnosePage />);
    await userEvent.upload(screen.getByLabelText('upload'), new File(['i'], 'a.jpg', { type: 'image/jpeg' }));
    await userEvent.type(screen.getByLabelText(/symptoms/i), 'wilting');
    await userEvent.click(screen.getByRole('button', { name: /diagnose/i }));

    await waitFor(() =>
      expect(screen.getByText(/diagnosis unavailable/i)).toBeInTheDocument()
    );
  });

  it('disables submit until an image and symptoms are provided', async () => {
    render(<DiseaseDiagnosePage />);
    expect(screen.getByRole('button', { name: /diagnose/i })).toBeDisabled();
  });
});
```

- [ ] **Step 5.2: Run it — expect FAIL**

```bash
cd web && npx vitest run src/pages/diagnosis/DiseaseDiagnosePage.test.tsx 2>&1 | tail -6
```

Expected: FAIL — cannot import `./DiseaseDiagnosePage`.

- [ ] **Step 5.3: Implement the page**

`web/src/pages/diagnosis/DiseaseDiagnosePage.tsx`:

```tsx
import { useState } from 'react';
import { Stethoscope } from 'lucide-react';
import FileUpload from '../../components/PlantIdentification/FileUpload';
import DiseaseResultsList from '../../components/diagnosis/DiseaseResultsList';
import { diseaseService } from '../../services/diseaseService';
import type { DiseaseDiagnosisResults as Results } from '../../types/diagnosis';

export default function DiseaseDiagnosePage() {
  const [file, setFile] = useState<File | null>(null);
  const [symptoms, setSymptoms] = useState('');
  const [condition, setCondition] = useState('');
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = !!file && symptoms.trim().length > 0 && !loading;

  const handleSubmit = async () => {
    if (!file || !symptoms.trim()) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const created = await diseaseService.submitDiagnosis({
        image: file,
        symptoms_description: symptoms.trim(),
        plant_condition: condition || undefined,
        location: location || undefined,
      });
      const res = await diseaseService.getDiagnosisResults(created.request_id);
      if (res.status === 'failed') {
        setError('Diagnosis unavailable — please try again.');
      } else {
        setResults(res);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Diagnosis unavailable — please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-12 h-12 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center">
          <Stethoscope className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-ink">Diagnose a sick plant</h1>
          <p className="text-ink-2 mt-1">Upload a photo and describe the symptoms.</p>
        </div>
      </div>

      <div className="bg-surface-2 rounded-2xl shadow-sm border border-line p-8 space-y-6">
        <FileUpload onFileSelect={setFile} />

        <div>
          <label htmlFor="symptoms" className="block font-medium text-ink mb-2">
            Symptoms <span className="text-error">*</span>
          </label>
          <textarea
            id="symptoms"
            value={symptoms}
            onChange={(e) => setSymptoms(e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-line bg-surface p-3 text-ink"
            placeholder="e.g. Yellow leaves with black spots, spreading from the bottom up"
          />
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <input
            aria-label="Plant condition (optional)"
            value={condition}
            onChange={(e) => setCondition(e.target.value)}
            className="rounded-lg border border-line bg-surface p-3 text-ink"
            placeholder="Plant condition (optional)"
          />
          <input
            aria-label="Location (optional)"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="rounded-lg border border-line bg-surface p-3 text-ink"
            placeholder="Location (optional)"
          />
        </div>

        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="px-8 py-3 bg-clay text-on-clay rounded-lg font-medium hover:bg-clay/90 disabled:bg-surface-3 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Diagnosing…' : 'Diagnose'}
        </button>

        {error && (
          <div className="bg-error/10 border border-error/30 rounded-lg p-4" role="alert">
            <p className="text-sm text-error">{error}</p>
          </div>
        )}

        {results && (
          <div className="pt-4 border-t border-line">
            <h2 className="text-xl font-semibold text-ink mb-4">Diagnosis</h2>
            {results.status === 'needs_help' && (
              <p className="mb-4 text-sm text-ink-2" role="status">
                We couldn&apos;t confidently identify the issue. Consider posting in the
                community forum with your photo and symptoms.
              </p>
            )}
            <DiseaseResultsList results={results.results} />
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5.4: Run it — expect PASS, then type-check + lint + commit**

```bash
npx vitest run src/pages/diagnosis/DiseaseDiagnosePage.test.tsx 2>&1 | tail -4   # expect pass
npm run type-check 2>&1 | tail -3 && npm run lint 2>&1 | tail -3
git add -A && git commit -m "feat(disease): DiseaseDiagnosePage (upload + symptoms -> results)"
```

---

## Task 6: Web — route + nav

**Files:**

- Modify: `web/src/App.tsx`
- Modify: `web/src/components/layout/Header.tsx`

- [ ] **Step 6.1: Add the lazy import + protected route in `App.tsx`**

At the top, beside the other `lazy(...)` page imports:

```tsx
const DiseaseDiagnosePage = lazy(() => import('./pages/diagnosis/DiseaseDiagnosePage'));
```

Inside the **`ProtectedLayout` → `RootLayout`** block (the one already wrapping `/profile` and `/settings` — App.tsx:60-64), add:

```tsx
            <Route path="/diagnose" element={<DiseaseDiagnosePage />} />
```

so it reads:

```tsx
        <Route element={<ProtectedLayout />}>
          <Route element={<RootLayout />}>
            <Route path="/diagnose" element={<DiseaseDiagnosePage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
```

- [ ] **Step 6.2: Add the "Diagnose" nav link in `Header.tsx` (desktop AND mobile)**

In the **desktop** nav block (the `hidden md:flex` group, right after the `/identify` `NavLink`), add a sibling:

```tsx
            <NavLink
              to="/diagnose"
              className={({ isActive }) =>
                `font-medium transition-colors ${
                  isActive ? 'text-primary' : 'text-ink-2 hover:text-primary'
                }`
              }
            >
              Diagnose
            </NavLink>
```

In the **mobile** menu block (`md:hidden`, right after the `/identify` `NavLink`), add:

```tsx
            <NavLink
              to="/diagnose"
              onClick={closeMenu}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg font-medium transition-colors ${
                  isActive ? 'bg-primary/10 text-primary' : 'text-ink-2 hover:bg-surface'
                }`
              }
            >
              Diagnose
            </NavLink>
```

(Match the exact class strings the neighbouring `/identify` link uses — copy them if they differ from the above.)

- [ ] **Step 6.3: Type-check + lint + build + commit**

```bash
cd web && npm run type-check 2>&1 | tail -3 && npm run lint 2>&1 | tail -3 && npm run build 2>&1 | tail -5
git add -A && git commit -m "feat(disease): route /diagnose (protected, lazy) + nav links"
```

Expected: type-check/lint clean; production build succeeds.

---

## Task 7: Final verification + PR

- [ ] **Step 7.1: Full web + backend gates**

```bash
cd web && npm run type-check && npm run lint && npm run test 2>&1 | tail -6
cd ../backend && source venv/bin/activate && python manage.py test apps.plant_identification --keepdb 2>&1 | tail -2
python manage.py spectacular --file /tmp/schema.yml >/dev/null 2>&1 && echo "OpenAPI OK"
```

Expected: web type-check/lint clean, vitest green; backend `OK`; OpenAPI generates.

- [ ] **Step 7.2: Manual smoke (document the result in the PR)**

With backend (`:8000`) + web (`:5174`) + Redis running: log in, open `/diagnose`, upload a leaf photo, enter symptoms, Diagnose → a diagnosis (or honest "ask the community" message) renders. Note: the POST is synchronous, so expect a short wait while plant.health responds.

- [ ] **Step 7.3: Push + open PR**

```bash
git push -u origin feat/disease-diagnosis-phase-a-submission
gh pr create --base main --title "Revive disease diagnosis — Phase A (web submission flow)" --body-file <(cat <<'EOF'
Phase A of reviving the orphaned disease-diagnosis feature: a new protected `/diagnose` web page that uploads a photo + symptoms to the existing `POST /disease-requests/`, then renders the diagnosis from `…/results/`. The only backend change is exposing read-only `request_id` + `status` on the create response so the client can fetch results. No models, no migration.

Confirmed the disease service does NOT fabricate fake diseases (its fallback is an honest "ask the community" message). Phases B (save/track/reminders) and C (async) are deferred to their own specs.

Spec: docs/superpowers/specs/2026-06-03-disease-diagnosis-phase-a-submission-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)
```

---

## Notes for the executor

- **Backend test mock:** Task 1 patches `PlantDiseaseService.diagnose_disease_from_request` (the existing `TestDiseasesDiagnosisAPI` convention). That's correct here — the test verifies the serializer *response shape*, not diagnosis logic, so mocking the service method is the right level (no need to mock the plant.health client for this).
- **Design tokens:** use the semantic Tailwind tokens already in the repo (`text-ink`, `text-ink-2`, `bg-surface`/`-2`/`-3`, `border-line`, `bg-clay`/`text-on-clay`, `text-error`, `from-primary`/`to-secondary`) — see `IdentifyPage.tsx`. Don't introduce raw color classes.
- **Copy nav classes verbatim:** if the neighbouring `/identify` `NavLink` class strings differ from the snippets here, copy the real ones so the new link matches exactly.
- **Commit gate:** web commits run eslint/prettier; if prettier reformats on stage and aborts, `git add -A` and re-run. Backend commits hit flake8/kimi — these are additive feature commits so kimi shouldn't block; if it does, read the finding before bypassing.
