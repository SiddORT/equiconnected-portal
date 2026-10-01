import { useEffect, useRef, useState } from 'react';
import type { PostalCandidate } from '@/api/auth';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { getStateOptions } from '@/utils/geography';
import { memberPostalLocation, postalLookupMessage, startPostalLookup } from '@/utils/postalLookup';
import styles from './MemberAddressFields.module.css';

export interface MemberAddressValue {
  postal_code?: string | null;
  country?: string | null;
  state_province?: string | null;
  city?: string | null;
  address?: string | null;
  address_line_2?: string | null;
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
  const cancelLookup = useRef<(() => void) | null>(null);
  const postal = useRef(value.postal_code ?? '');
  const changeRef = useRef(onChange);
  changeRef.current = onChange;
  const postalId = `${section}-postal-code`;
  const statusId = `${postalId}-status`;

  function cancel() {
    cancelLookup.current?.();
    cancelLookup.current = null;
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

  useEffect(() => () => cancelLookup.current?.(), []);

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
    setMessage('Looking up postal code…');
    cancelLookup.current = startPostalLookup(next, {
      onResult: (result) => {
        const matches = result.candidates;
        if (matches.length === 1) {
          const location = memberPostalLocation(matches[0]);
          const complete = location.country && location.city
            && (location.state_province || getStateOptions(location.country).length === 0);
          if (complete) {
            changeRef.current(location);
            setMessage('Location details filled. You can correct them manually.');
            return;
          }
        }
        setCandidates(matches);
        setMessage(postalLookupMessage(result, 'member'));
      },
    });
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
              onChange(memberPostalLocation(candidates[Number(index) - 1]));
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