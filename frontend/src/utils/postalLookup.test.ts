import { afterEach, describe, expect, it, vi } from 'vitest';
import { lookupProviderPostalCode, type PostalCandidate } from '@/api/auth';
import {
  memberPostalLocation, normalizePostalCountry, postalLookupMessage, startPostalLookup,
  type PostalLookupResult,
} from './postalLookup';

vi.mock('@/api/auth', () => ({ lookupProviderPostalCode: vi.fn() }));
const candidate: PostalCandidate = {
  country: 'United States', country_code: 'US', state_province: 'TX',
  city: ' Austin ', postal_code: '78701', display_name: 'Austin, Texas',
};

afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe('shared postal source contract', () => {
  it.each([
    [' us ', 'Other', 'United States'],
    ['', ' us ', 'United States'],
    ['invalid', ' united states ', 'United States'],
    ['invalid', ' Unknown country ', 'Unknown country'],
    [' ca ', 'United States', 'Canada'],
  ])('normalizes country code %s and name %s', (country_code, country, expected) => {
    expect(normalizePostalCountry({ ...candidate, country_code, country })).toBe(expected);
  });

  it('retains member-only state abbreviation normalization', () => {
    expect(memberPostalLocation(candidate)).toEqual({
      country: 'United States', state_province: 'Texas', city: 'Austin',
    });
  });

  it('trims queries, debounces and does not request short pincodes', async () => {
    vi.useFakeTimers();
    vi.mocked(lookupProviderPostalCode).mockResolvedValue({ status: 'match', candidates: [candidate] });
    const onLoading = vi.fn();
    const onResult = vi.fn();
    startPostalLookup(' 123 ', { onLoading, onResult });
    const cancel = startPostalLookup(' 78701 ', { onLoading, onResult });
    await vi.advanceTimersByTimeAsync(549);
    expect(lookupProviderPostalCode).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(lookupProviderPostalCode).toHaveBeenCalledWith('78701', expect.any(AbortSignal));
    expect(onLoading).toHaveBeenCalledTimes(1);
    expect(onResult).toHaveBeenCalledWith({ status: 'match', candidates: [candidate] });
    cancel();
  });

  it('cancels a debounce before loading or contacting the source', async () => {
    vi.useFakeTimers();
    const onLoading = vi.fn();
    const onResult = vi.fn();
    const cancel = startPostalLookup('78701', { onLoading, onResult });
    cancel();
    await vi.advanceTimersByTimeAsync(550);
    expect(onLoading).not.toHaveBeenCalled();
    expect(onResult).not.toHaveBeenCalled();
    expect(lookupProviderPostalCode).not.toHaveBeenCalled();
  });

  it.each(['resolve', 'reject'])('independently cancels requests despite late source %s', async (outcome) => {
    vi.useFakeTimers();
    let resolve!: (result: PostalLookupResult) => void;
    let reject!: (error: Error) => void;
    vi.mocked(lookupProviderPostalCode)
      .mockImplementationOnce(() => new Promise((res, rej) => { resolve = res; reject = rej; }))
      .mockResolvedValueOnce({ status: 'match', candidates: [candidate] });
    const first = vi.fn();
    const second = vi.fn();
    const cancelFirst = startPostalLookup('11111', { onResult: first });
    startPostalLookup('22222', { onResult: second });
    await vi.advanceTimersByTimeAsync(550);
    cancelFirst();
    expect(vi.mocked(lookupProviderPostalCode).mock.calls[0][1]?.aborted).toBe(true);
    expect(vi.mocked(lookupProviderPostalCode).mock.calls[1][1]?.aborted).toBe(false);
    if (outcome === 'resolve') resolve({ status: 'match', candidates: [candidate] });
    else reject(new Error('late failure'));
    await vi.advanceTimersByTimeAsync(0);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  it.each(['no_match', 'unavailable'] as const)('discards source candidates when status is %s for every form', async (status) => {
    vi.useFakeTimers();
    vi.mocked(lookupProviderPostalCode).mockResolvedValue({ status, candidates: [candidate] });
    const onResult = vi.fn();
    startPostalLookup('78701', { onResult });
    await vi.advanceTimersByTimeAsync(550);
    const result = onResult.mock.calls[0][0] as PostalLookupResult;
    expect(result).toEqual({ status, candidates: [] });
    for (const form of ['member', 'provider', 'invitation'] as const) {
      expect(postalLookupMessage(result, form)).toContain('manually');
      expect(postalLookupMessage(result, form)).not.toContain('Choose');
    }
  });

  it('represents a source failure as unavailable for all forms', async () => {
    vi.useFakeTimers();
    vi.mocked(lookupProviderPostalCode).mockRejectedValue(new Error('offline'));
    const onResult = vi.fn();
    startPostalLookup('78701', { onResult });
    await vi.advanceTimersByTimeAsync(550);
    const result = onResult.mock.calls[0][0] as PostalLookupResult;
    expect(result).toEqual({ status: 'unavailable', candidates: [] });
    for (const form of ['member', 'provider', 'invitation'] as const) {
      expect(postalLookupMessage(result, form)).toContain('unavailable');
    }
  });
});