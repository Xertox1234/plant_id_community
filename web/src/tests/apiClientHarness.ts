/**
 * Drive the REAL shared `apiClient` (utils/httpClient.ts) in service tests,
 * so its interceptors — CSRF header on mutating requests, the stale-CSRF
 * refresh-and-retry — are exercised rather than mocked away (todo 407 item 9).
 *
 * Two layers, because they prove different things:
 *
 * - `installAdapter()` swaps axios's transport for a mock. Both interceptors
 *   run around it, so it sees the final config (url, method, CSRF header,
 *   serialized body) and can answer with any status. It does NOT see what
 *   reaches the wire: axios's xhr adapter strips `Content-Type` from a
 *   bodyless request itself, after the adapter boundary.
 * - `captureXhrHeaders()` keeps the real xhr adapter and records the headers
 *   it hands `XMLHttpRequest`, with `send` stubbed so nothing hits the network.
 *   Use it for the on-the-wire header contract.
 *
 * Callers must `vi.mock('../utils/csrf', ...)` themselves (vi.mock is hoisted
 * per test file) with BOTH `getCsrfToken` and `clearCsrfToken`.
 */
import { vi, type Mock } from 'vitest';
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import apiClient from '../utils/httpClient';

const realAdapter = apiClient.defaults.adapter;

export type AdapterMock = Mock<(config: InternalAxiosRequestConfig) => Promise<AxiosResponse>>;

/** Replace apiClient's transport with a mock; undo with `restoreAdapter()`. */
export function installAdapter(): AdapterMock {
  const adapter: AdapterMock = vi.fn();
  apiClient.defaults.adapter = adapter;
  return adapter;
}

export function restoreAdapter(): void {
  apiClient.defaults.adapter = realAdapter;
}

/** A settled response, as an adapter would resolve it. */
export function ok(config: InternalAxiosRequestConfig, data: unknown, status = 200): AxiosResponse {
  return { data, status, statusText: 'OK', headers: {}, config };
}

/** A non-2xx failure, as axios's own `settle()` would reject it. */
export function httpError(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown
): AxiosError {
  return new AxiosError(
    `Request failed with status code ${status}`,
    AxiosError.ERR_BAD_REQUEST,
    config,
    {},
    { data, status, statusText: '', headers: {}, config }
  );
}

/**
 * The backend's real 403 envelope for a CSRF failure
 * (apps/users/authentication.py raises `PermissionDenied("CSRF Failed: …")`,
 * apps/core/exceptions.py flattens it) — the text apiClient's retry keys on.
 */
export const CSRF_FAILED_BODY = {
  error: true,
  message: 'CSRF Failed: CSRF token missing or incorrect.',
  code: 'permission_denied',
  status_code: 403,
};

/** The URL axios will actually request (baseURL applied only when relative). */
export function fullUrl(config: InternalAxiosRequestConfig): string {
  return apiClient.getUri(config);
}

/**
 * Record the header names the real xhr adapter sets, lower-cased. `send` is
 * stubbed, so the request promise never settles — fire it with `void`.
 */
export function captureXhrHeaders(): () => string[] {
  vi.spyOn(XMLHttpRequest.prototype, 'send').mockImplementation(() => {});
  const setHeader = vi.spyOn(XMLHttpRequest.prototype, 'setRequestHeader');
  return () => setHeader.mock.calls.map(([name]) => name.toLowerCase());
}
