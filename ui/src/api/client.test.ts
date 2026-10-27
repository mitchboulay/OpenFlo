import { http, HttpResponse, delay } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { ApiError, apiRequest } from './client';
import { shouldRetry } from './queryClient';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function expectApiError(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.catch((caught: unknown) => caught);
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

describe('apiRequest', () => {
  it('sends JSON with same-origin credentials and returns the parsed body', async () => {
    let seen: { method: string; contentType: string | null; credentials: string; body: unknown } | undefined;
    server.use(
      http.post('*/api/v1/homes', async ({ request }) => {
        seen = {
          method: request.method,
          contentType: request.headers.get('content-type'),
          credentials: request.credentials,
          body: await request.json(),
        };
        return HttpResponse.json({ id: 'h1', name: 'Cabin' }, { status: 201 });
      }),
    );
    const home = await apiRequest<{ id: string; name: string }>('/api/v1/homes', {
      method: 'POST',
      body: { name: 'Cabin' },
    });
    expect(home).toEqual({ id: 'h1', name: 'Cabin' });
    expect(seen).toEqual({ method: 'POST', contentType: 'application/json', credentials: 'same-origin', body: { name: 'Cabin' } });
  });

  it('returns undefined for an empty success body (204)', async () => {
    server.use(http.delete('*/api/v1/homes/h1', () => new HttpResponse(null, { status: 204 })));
    await expect(apiRequest('/api/v1/homes/h1', { method: 'DELETE' })).resolves.toBeUndefined();
  });

  it('maps the v1 error shape {code, message, detail}', async () => {
    server.use(
      http.get('*/api/v1/devices/x', () =>
        HttpResponse.json({ code: 'DEVICE_NOT_FOUND', message: 'No such device.', detail: { id: 'x' } }, { status: 404 }),
      ),
    );
    const error = await expectApiError(apiRequest('/api/v1/devices/x'));
    expect(error).toMatchObject({ status: 404, code: 'DEVICE_NOT_FOUND', message: 'No such device.', detail: { id: 'x' } });
  });

  it('maps the legacy {detail: string} shape', async () => {
    server.use(http.get('*/api/v1/homes', () => HttpResponse.json({ detail: 'Bad Gateway' }, { status: 502 })));
    const error = await expectApiError(apiRequest('/api/v1/homes'));
    expect(error).toMatchObject({ status: 502, code: 'HTTP_ERROR', message: 'Bad Gateway' });
  });

  it('keeps structured legacy detail (FastAPI validation errors)', async () => {
    const detail = [{ loc: ['body', 'name'], msg: 'Field required' }];
    server.use(http.post('*/api/v1/homes', () => HttpResponse.json({ detail }, { status: 422 })));
    const error = await expectApiError(apiRequest('/api/v1/homes', { method: 'POST', body: {} }));
    expect(error).toMatchObject({ status: 422, code: 'HTTP_ERROR', detail });
  });

  it('maps a non-JSON error body to the status text', async () => {
    server.use(http.get('*/api/v1/x', () => new HttpResponse('Bad Gateway', { status: 502, statusText: 'Bad Gateway' })));
    const error = await expectApiError(apiRequest('/api/v1/x'));
    expect(error).toMatchObject({ status: 502, code: 'HTTP_ERROR', message: 'Bad Gateway' });
  });

  it('rejects an unreadable success body', async () => {
    server.use(http.get('*/api/v1/x', () => new HttpResponse('<html>', { status: 200 })));
    const error = await expectApiError(apiRequest('/api/v1/x'));
    expect(error.code).toBe('INVALID_RESPONSE');
  });

  it('maps a network failure', async () => {
    server.use(http.get('*/api/v1/x', () => HttpResponse.error()));
    const error = await expectApiError(apiRequest('/api/v1/x'));
    expect(error).toMatchObject({ status: 0, code: 'NETWORK_ERROR' });
  });

  it('maps a timeout', async () => {
    server.use(
      http.get('*/api/v1/slow', async () => {
        await delay('infinite');
        return HttpResponse.json({});
      }),
    );
    const error = await expectApiError(apiRequest('/api/v1/slow', { timeoutMs: 20 }));
    expect(error).toMatchObject({ status: 0, code: 'TIMEOUT' });
  });

  it('passes caller cancellation through untouched', async () => {
    server.use(
      http.get('*/api/v1/slow', async () => {
        await delay('infinite');
        return HttpResponse.json({});
      }),
    );
    const controller = new AbortController();
    const pending = apiRequest('/api/v1/slow', { signal: controller.signal });
    controller.abort();
    const error = await pending.catch((caught: unknown) => caught);
    expect(error).not.toBeInstanceOf(ApiError);
    expect((error as Error).name).toBe('AbortError');
  });
});

describe('shouldRetry', () => {
  it('retries network errors and 5xx, never 4xx, at most twice', () => {
    expect(shouldRetry(0, new ApiError(0, 'NETWORK_ERROR', 'x'))).toBe(true);
    expect(shouldRetry(1, new ApiError(503, 'DB_BUSY', 'x'))).toBe(true);
    expect(shouldRetry(0, new ApiError(404, 'NOT_FOUND', 'x'))).toBe(false);
    expect(shouldRetry(2, new ApiError(503, 'DB_BUSY', 'x'))).toBe(false);
  });
});
