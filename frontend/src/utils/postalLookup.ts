import { Country, State } from 'country-state-city';
import { lookupProviderPostalCode, type PostalCandidate } from '@/api/auth';
import { getStateOptions } from '@/utils/geography';

export type PostalLookupResult = Awaited<ReturnType<typeof lookupProviderPostalCode>>;
export const POSTAL_LOOKUP_DELAY = 550;

export function normalizePostalCountry(candidate: PostalCandidate): string {
  const text = candidate.country.trim();
  return Country.getCountryByCode(candidate.country_code?.trim().toUpperCase() ?? '')?.name
    ?? Country.getAllCountries().find((country) =>
      country.name.toLowerCase() === text.toLowerCase()
      || country.isoCode.toLowerCase() === text.toLowerCase())?.name
    ?? text;
}

/** Members use canonical state names; provider forms retain source state text. */
export function memberPostalLocation(candidate: PostalCandidate) {
  const country = normalizePostalCountry(candidate);
  const state = candidate.state_province.trim();
  const code = Country.getAllCountries().find((item) => item.name === country)?.isoCode;
  return {
    country,
    state_province: (code && State.getStateByCodeAndCountry(state.toUpperCase(), code)?.name)
      || getStateOptions(country).find((item) => item.value.toLowerCase() === state.toLowerCase())?.value
      || state,
    city: candidate.city.trim(),
  };
}

export function postalLookupMessage(result: PostalLookupResult, form: 'member' | 'provider' | 'invitation') {
  if (form === 'member') {
    return result.candidates.length
      ? 'Choose a matching place to fill location details, or enter them manually.'
      : result.status === 'unavailable'
        ? 'Postal lookup is unavailable. Enter location details manually.'
        : 'No complete matching place found. Enter location details manually.';
  }
  if (form === 'invitation') {
    return result.status === 'no_match'
      ? 'No matching place found. You can enter the address manually.'
      : result.status === 'unavailable'
        ? 'Postal lookup is unavailable. You can enter the address manually.'
        : 'Choose a matching place or enter the address manually.';
  }
  return result.status === 'no_match'
    ? 'No matching place found. Enter the location manually.'
    : result.status === 'unavailable'
      ? 'Lookup is unavailable. Enter the location manually.'
      : 'Choose a place below to fill your location.';
}

/**
 * One independent, debounced request. Cancellation suppresses callbacks even
 * when the postal source ignores AbortSignal or resolves after cancellation.
 * Callers own selection policy and decide when saved values permit lookup.
 */
export function startPostalLookup(
  postalCode: string,
  callbacks: { onLoading?: () => void; onResult: (result: PostalLookupResult) => void },
): () => void {
  const query = postalCode.trim();
  if (query.length < 4) return () => {};
  const controller = new AbortController();
  const timer = setTimeout(async () => {
    if (controller.signal.aborted) return;
    callbacks.onLoading?.();
    let result: PostalLookupResult;
    try {
      const response = await lookupProviderPostalCode(query, controller.signal);
      // Status, not stray source data, determines whether places are selectable.
      result = { ...response, candidates: response.status === 'match' ? response.candidates : [] };
    } catch {
      result = { status: 'unavailable', candidates: [] };
    }
    if (!controller.signal.aborted) callbacks.onResult(result);
  }, POSTAL_LOOKUP_DELAY);
  return () => {
    controller.abort();
    clearTimeout(timer);
  };
}