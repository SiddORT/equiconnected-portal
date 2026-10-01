// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { getAccessToken } = vi.hoisted(() => ({
  getAccessToken: vi.fn(),
}));

vi.mock('@/api/client', () => ({ getAccessToken }));

import { recordMemberContactClick } from './contactTracking';

const request = vi.fn();
const getRandomValues = vi.fn((values: Uint8Array) => values);
const FIXED_TIMESTAMP = 0x0123456789ab;

describe('member contact click tracking', () => {
  beforeEach(() => {
    request.mockReset();
    vi.stubGlobal('fetch', request);
    let randomByte = 0;
    getRandomValues.mockReset().mockImplementation((values) => {
      values.fill(randomByte);
      randomByte += 1;
      return values;
    });
    vi.stubGlobal('crypto', { getRandomValues } as unknown as Crypto);
    vi.spyOn(Date, 'now').mockReturnValue(FIXED_TIMESTAMP);
    getAccessToken.mockReset().mockReturnValue('member-access-token');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it.each(['phone', 'email', 'website'] as const)(
    'sends only the %s action and a fresh activation key',
    (action) => {
      request.mockResolvedValue({ ok: true, status: 204 });

      recordMemberContactClick('provider-1', action);

      expect(request).toHaveBeenCalledTimes(1);
      const [url, options] = request.mock.calls[0];
      expect(url).toBe('/api/v1/member/providers/provider-1/contact-click');
      expect(options).toMatchObject({
        method: 'POST',
        headers: {
          Authorization: 'Bearer member-access-token',
          'Content-Type': 'application/json',
        },
        keepalive: true,
        credentials: 'omit',
      });
      const payload = JSON.parse(options.body as string);
      expect(Object.keys(payload).sort()).toEqual(['action', 'event_key']);
      expect(payload.action).toBe(action);
      expect(payload.event_key).toBe('01234567-89ab-7000-8000-000000000000');
      expect(getRandomValues).toHaveBeenCalledTimes(1);
      expect(getRandomValues.mock.calls[0][0]).toBeInstanceOf(Uint8Array);
    },
  );

  it('uses a distinct UUIDv7 for each actual activation', () => {
    request.mockResolvedValue({ ok: true, status: 204 });

    recordMemberContactClick('provider-1', 'phone');
    recordMemberContactClick('provider-1', 'phone');

    const firstPayload = JSON.parse(request.mock.calls[0][1].body as string);
    const secondPayload = JSON.parse(request.mock.calls[1][1].body as string);
    expect(firstPayload.event_key).toBe('01234567-89ab-7000-8000-000000000000');
    expect(secondPayload.event_key).toBe('01234567-89ab-7101-8101-010101010101');
    expect(firstPayload.event_key).not.toBe(secondPayload.event_key);
  });

  it('retries a transient response once with the same event key and payload', async () => {
    request
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValueOnce({ ok: true, status: 204 });

    recordMemberContactClick('provider-1', 'email');

    await vi.waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    expect(request.mock.calls[0][0]).toBe(request.mock.calls[1][0]);
    expect(request.mock.calls[0][1].body).toBe(request.mock.calls[1][1].body);
    expect(request.mock.calls[1][1].headers.Authorization).toBe('Bearer member-access-token');
  });

  it('does not retry an expired session or attempt a token refresh', async () => {
    request.mockResolvedValue({ ok: false, status: 401 });

    recordMemberContactClick('provider-1', 'website');

    await vi.waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    expect(request.mock.calls[0][0]).toBe('/api/v1/member/providers/provider-1/contact-click');
    expect(getAccessToken).toHaveBeenCalledTimes(1);
    expect(request.mock.calls.some(([url]) => String(url).includes('/auth/refresh'))).toBe(false);
  });

  it('does not send a request when no access token is available', () => {
    getAccessToken.mockReturnValue(null);

    recordMemberContactClick('provider-1', 'phone');

    expect(request).not.toHaveBeenCalled();
  });

  it('does not track when cryptographically secure randomness is unavailable', () => {
    vi.stubGlobal('crypto', undefined);

    recordMemberContactClick('provider-1', 'phone');

    expect(request).not.toHaveBeenCalled();
    expect(getAccessToken).not.toHaveBeenCalled();
  });
});