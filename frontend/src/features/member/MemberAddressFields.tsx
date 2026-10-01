import { useEffect, useRef, useState } from 'react';
import { Country, State } from 'country-state-city';
import { lookupProviderPostalCode, type PostalCandidate } from '@/api/auth';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { getStateOptions } from '@/utils/geography';
import styles from './MemberAddressFields.module.css';

export interface MemberAddressValue {
  postal_code?: string | null;
  country?: string | null;
  state_province?: string | null;
  city?: string | null;
  address?: string | null;
  address_line_2?: string | null;
}

function candidateLocation(candidate: PostalCandidate) {
  const country = Country.getCountryByCode(candidate.country_code?.toUpperCase() ?? '')?.name
    ?? Country.getAllCountries().find((item) =>
      item.name.toLowerCase() === candidate.country.trim().toLowerCase()
      || item.isoCode.toLowerCase() === candidate.country.trim().toLowerCase())?.name
    ?? candidate.country.trim();
  const states = getStateOptions(country);
  const state = candidate.state_province.trim();
  const countryCode = Country.getAllCountries().find((item) => item.name === country)?.isoCode;
  return {
    country,
    state_province: (countryCode && State.getStateByCodeAndCountry(state.toUpperCase(), countryCode)?.name)
      || states.find((item) => item.value.toLowerCase() === state.toLowerCase())?.value || state,
    city: candidate.city.trim(),
  };
}

/** Lookup starts only after a member edits the pincode, never on profile load. */
export function MemberAddressFields({
  value, onChange, section,
}: {
  value: MemberAddressValue;
  onChange: (patch: Partial<MemberAddressValue>) => void;
  section: 'personal' | 'stable';
}) {
  const [message, setMessage] = useState('');
  const [candidates, setCandidates] = useState<PostalCandidate[]>([]);
  const [selected, setSelected] = useState('');
  const request = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const postal = useRef(value.postal_code ?? '');
  const changeRef = useRef(onChange);
  changeRef.current = onChange;
  const postalId = `${section}-postal-code`;
  const statusId = `${postalId}-status`;

  function cancel() {
    request.current += 1;
    controller.current?.abort();
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }

  useEffect(() => {
    if (postal.current !== (value.postal_code ?? '')) {
      postal.current = value.postal_code ?? '';
      cancel();
      setMessage('');
      setCandidates([]);
      setSelected('');
    }
  }, [value.postal_code]);

  useEffect(() => () => {
    request.current += 1;
    controller.current?.abort();
    if (timer.current) clearTimeout(timer.current);
  }, []);

  function editLocation(patch: Partial<MemberAddressValue>) {
    cancel();
    setCandidates([]);
    setSelected('');
    setMessage('Enter or correct location details manually.');
    onChange(patch);
  }

  function editPostal(next: string) {
    cancel();
    postal.current = next;
    onChange({ postal_code: next });
    setCandidates([]);
    setSelected('');
    setMessage('');
    if (next.trim().length < 4) return;
    const version = request.current;
    const abortController = new AbortController();
    controller.current = abortController;
    setMessage('Looking up postal code…');
    timer.current = setTimeout(async () => {
      try {
        const result = await lookupProviderPostalCode(next.trim(), abortController.signal);
        if (abortController.signal.aborted || version !== request.current) return;
        const matches = result.status === 'match' ? result.candidates : [];
        if (matches.length === 1) {
          const location = candidateLocation(matches[0]);
          const complete = location.country && location.city
            && (location.state_province || getStateOptions(location.country).length === 0);
          if (complete) {
            changeRef.current(location);
            setMessage('Location details filled. You can correct them manually.');
            return;
          }
        }
        setCandidates(matches);
        setMessage(matches.length
          ? 'Choose a matching place to fill location details, or enter them manually.'
          : result.status === 'unavailable'
            ? 'Postal lookup is unavailable. Enter location details manually.'
            : 'No complete matching place found. Enter location details manually.');
      } catch {
        if (abortController.signal.aborted || version !== request.current) return;
        setMessage('Postal lookup is unavailable. Enter location details manually.');
      }
    }, 550);
  }

  return (
    <div className={styles.address}>
      <Input id={postalId} label="Pincode / Postal code" required autoComplete="postal-code"
        value={value.postal_code ?? ''} onChange={(event) => editPostal(event.target.value)}
        aria-describedby={statusId} />
      <p id={statusId} className={styles.hint} role="status">
        {message || 'Enter a pincode to find matching places, or enter location details manually.'}
      </p>
      {candidates.length > 0 && (
        <FormField label={`Matching place for ${section} location`} htmlFor={`${section}-postal-place`}>
          <select id={`${section}-postal-place`} className={styles.select} value={selected}
            onChange={(event) => {
              const index = event.target.value;
              setSelected(index);
              if (!index) return;
              cancel();
              onChange(candidateLocation(candidates[Number(index) - 1]));
              setMessage('Matching place selected. You can correct location details manually.');
            }}>
            <option value="">Choose a matching place</option>
            {candidates.map((candidate, index) => (
              <option key={index} value={String(index + 1)}>
                {candidate.display_name || [candidate.city, candidate.state_province, candidate.country].filter(Boolean).join(', ')}
              </option>
            ))}
          </select>
        </FormField>
      )}
      <div className={styles.location}>
        <Input label="Country" required autoComplete="country-name" value={value.country ?? ''}
          onChange={(event) => editLocation({ country: event.target.value })} />
        <Input label="State / Province" required={getStateOptions(value.country ?? '').length > 0}
          autoComplete="address-level1" value={value.state_province ?? ''}
          onChange={(event) => editLocation({ state_province: event.target.value })} />
        <Input label="City" required autoComplete="address-level2" value={value.city ?? ''}
          onChange={(event) => editLocation({ city: event.target.value })} />
      </div>
      <Input label="Address line 1" required autoComplete="address-line1" value={value.address ?? ''}
        onChange={(event) => onChange({ address: event.target.value })} />
      <Input label="Address line 2" autoComplete="address-line2" hint="Optional"
        value={value.address_line_2 ?? ''}
        onChange={(event) => onChange({ address_line_2: event.target.value })} />
    </div>
  );
}