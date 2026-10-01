import { describe, it, expect } from 'vitest';
import { AxiosError, CanceledError, type InternalAxiosRequestConfig } from 'axios';
import { NETWORK_ERROR_MESSAGE, httpErrorMessage, toHttpError } from './httpError';

const config = { headers: {} } as InternalAxiosRequestConfig;

function withResponse(status: number, data: unknown): AxiosError {
  return new AxiosError(
    `Request failed with status code ${status}`,
    AxiosError.ERR_BAD_REQUEST,
    config,
    {},
    { data, status, statusText: '', headers: {}, config }
  );
}

describe('httpErrorMessage', () => {
  it.each([
    ['a flattened message', { message: 'Invalid first name' }, 'Invalid first name'],
    ['a bare DRF detail', { detail: 'Not found.' }, 'Not found.'],
    ['the first field error', { first_name: ['Too long.'] }, 'first name: Too long.'],
    ['the status, for an empty JSON body', {}, 'Request failed (HTTP 500)'],
    ['the status, for a non-JSON body', '<html>oops</html>', 'Request failed (HTTP 500)'],
  ])('reads %s', (_label, body, expected) => {
    expect(httpErrorMessage(body, 500)).toBe(expected);
  });
});

describe('toHttpError', () => {
  it('turns an HTTP failure into the server message, keeping the axios error as cause', () => {
    const original = withResponse(400, { website: ['Enter a valid URL.'] });

    const translated = toHttpError(original) as Error;

    expect(translated).toBeInstanceOf(Error);
    expect(translated).not.toBeInstanceOf(AxiosError);
    expect(translated.message).toBe('website: Enter a valid URL.');
    expect(translated.cause).toBe(original);
  });

  // todo 434: axios's own text ("Network Error", "timeout of 30000ms
  // exceeded") reached the profile banner.
  it.each([
    ['a network error', new AxiosError('Network Error', AxiosError.ERR_NETWORK, config)],
    ['a timeout', new AxiosError('timeout of 30000ms exceeded', AxiosError.ECONNABORTED, config)],
    [
      'a clarified timeout',
      new AxiosError('timeout of 30000ms exceeded', AxiosError.ETIMEDOUT, config),
    ],
  ])('replaces the axios text of %s with a connection message', (_label, original) => {
    const translated = toHttpError(original) as Error;

    expect(translated.message).toBe(NETWORK_ERROR_MESSAGE);
    expect(translated.cause).toBe(original);
  });

  // todo 489: every response-less axios error used to read as a connection
  // problem, so a client bug (a bad URL, a bad option, an interceptor
  // rejection) told the user to check their wifi.
  it.each([
    ['an invalid URL', new AxiosError('Invalid URL', AxiosError.ERR_INVALID_URL, config)],
    [
      'a bad option value',
      new AxiosError('option timeout must be a number', AxiosError.ERR_BAD_OPTION_VALUE, config),
    ],
    ['an axios error with no code', new AxiosError('Rejected by an interceptor')],
  ])('returns %s unchanged, not as a connection problem', (_label, original) => {
    expect(toHttpError(original)).toBe(original);
  });

  it('returns a cancellation unchanged, so callers can still detect it', () => {
    const cancelled = new CanceledError(undefined, undefined, config);
    expect(toHttpError(cancelled)).toBe(cancelled);
  });

  it('returns a non-axios error unchanged', () => {
    const own = new Error('Could not load your profile.');
    expect(toHttpError(own)).toBe(own);
  });
});
