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
      set: (v: string) => {
        cookie = v;
      },
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
      json: async () => ({
        message: 'At least one symptom image is required for disease diagnosis.',
      }),
    });
    const file = new File(['img'], 'leaf.jpg', { type: 'image/jpeg' });
    await expect(
      diseaseService.submitDiagnosis({ image: file, symptoms_description: '' })
    ).rejects.toThrow('At least one symptom image is required');
  });
});
