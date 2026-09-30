import { useEffect, useRef, useState } from 'react';
import { Country } from 'country-state-city';
import { lookupProviderPostalCode, type PostalCandidate } from '@/api/auth';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { PhoneInput } from '@/components/ui/PhoneInput';
import type { DraftLocation, InvitationDraftPayload, InvitationDraftProvider, VisitStability } from '@/types';
import { COUNTRY_CODES, DEFAULT_COUNTRY } from '@/utils/countryCodes';
import styles from './InvitationProfileFields.module.css';

export interface InvitationServiceValues {
  visit_stability: VisitStability | '';
  maximum_working_radius_km: string;
  emergency_services_available: boolean;
  emergency_country_code: string;
  emergency_iso_code: string;
  emergency_local_number: string;
}

export interface InvitationAddress {
  key: string;
  name: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state_province: string;
  country: string;
  postal_code: string;
}

export interface InvitationServiceErrors {
  maximum_working_radius_km?: string;
  emergency_contact_number?: string;
}

export interface InvitationServiceFieldsProps {
  value: InvitationServiceValues;
  onChange: (value: InvitationServiceValues) => void;
  errors?: InvitationServiceErrors;
  disabled?: boolean;
}

export interface InvitationAddressesProps {
  value: InvitationAddress[];
  onChange: (value: InvitationAddress[]) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
}

export function emptyInvitationAddress(key = 'address-0'): InvitationAddress {
  return {
    key,
    name: '',
    address_line_1: '',
    address_line_2: '',
    city: '',
    state_province: '',
    country: '',
    postal_code: '',
  };
}

export function invitationAddressesFromDraft(locations: DraftLocation[]): InvitationAddress[] {
  return locations.map((location, index) => ({
    key: `address-${index}`,
    name: location.name ?? '',
    address_line_1: location.address_line_1 ?? '',
    address_line_2: location.address_line_2 ?? '',
    city: location.city ?? '',
    state_province: location.state_province ?? '',
    country: location.country ?? '',
    postal_code: location.postal_code ?? '',
  }));
}

function parseEmergencyNumber(value: string | null | undefined) {
  const normalized = value?.trim() ?? '';
  if (normalized.startsWith('+')) {
    const country = COUNTRY_CODES
      .filter((candidate) => normalized.startsWith(candidate.dialCode))
      .sort((a, b) => b.dialCode.length - a.dialCode.length)[0];
    if (country) {
      return {
        emergency_country_code: country.dialCode,
        emergency_iso_code: country.code,
        emergency_local_number: normalized.slice(country.dialCode.length).trim(),
      };
    }
  }
  return {
    emergency_country_code: DEFAULT_COUNTRY.dialCode,
    emergency_iso_code: DEFAULT_COUNTRY.code,
    emergency_local_number: normalized,
  };
}

export function invitationServiceValuesFromDraft(provider: InvitationDraftProvider): InvitationServiceValues {
  return {
    visit_stability: provider.visit_stability ?? '',
    maximum_working_radius_km: provider.maximum_working_radius_km != null
      ? String(provider.maximum_working_radius_km) : '',
    emergency_services_available: provider.emergency_services_available ?? false,
    ...parseEmergencyNumber(provider.emergency_contact_number),
  };
}

export function invitationServicePayload(value: InvitationServiceValues): Pick<
  InvitationDraftPayload,
  'visit_stability' | 'maximum_working_radius_km' | 'emergency_services_available' | 'emergency_contact_number'
> {
  return {
    visit_stability: value.visit_stability || undefined,
    maximum_working_radius_km: value.visit_stability === 'STABLE_VISIT' &&
      value.maximum_working_radius_km.trim() &&
      Number.isFinite(Number(value.maximum_working_radius_km)) &&
      Number(value.maximum_working_radius_km) > 0
      ? Number(value.maximum_working_radius_km) : null,
    emergency_services_available: value.emergency_services_available,
    emergency_contact_number: value.emergency_services_available && value.emergency_local_number.trim()
      ? `${value.emergency_country_code} ${value.emergency_local_number.trim()}`
      : null,
  };
}

export function validateInvitationServices(value: InvitationServiceValues): InvitationServiceErrors {
  const errors: InvitationServiceErrors = {};
  if (value.visit_stability === 'STABLE_VISIT' &&
    (!value.maximum_working_radius_km.trim() ||
      !Number.isFinite(Number(value.maximum_working_radius_km)) ||
      Number(value.maximum_working_radius_km) <= 0)) {
    errors.maximum_working_radius_km = 'Enter a finite radius greater than 0 km.';
  }
  const localDigits = value.emergency_local_number.replace(/\D/g, '');
  const dialCodeIsValid = COUNTRY_CODES.some((country) => country.dialCode === value.emergency_country_code);
  if (value.emergency_services_available &&
    (!dialCodeIsValid || !/^[\d\s().-]+$/.test(value.emergency_local_number.trim()) ||
      localDigits.length < 6 || localDigits.length > 15)) {
    errors.emergency_contact_number = 'Enter a valid emergency number with 6–15 digits.';
  }
  return errors;
}

export function invitationLocationsPayload(addresses: InvitationAddress[]): DraftLocation[] | undefined {
  const filled = addresses.filter((address) =>
    Object.entries(address).some(([key, field]) => key !== 'key' && Boolean(field.trim()))
  ).filter((address) => address.address_line_1.trim() && address.city.trim());
  if (filled.length === 0) return undefined;
  return filled.map((address, index) => ({
    name: address.name.trim() || null,
    address_line_1: address.address_line_1.trim(),
    address_line_2: address.address_line_2.trim() || null,
    city: address.city.trim(),
    state_province: address.state_province.trim() || null,
    country: address.country.trim() || null,
    postal_code: address.postal_code.trim() || null,
    is_primary: index === 0,
  }));
}

export function InvitationServiceFields({
  value,
  onChange,
  errors = {},
  disabled = false,
}: InvitationServiceFieldsProps) {
  const stable = value.visit_stability === 'STABLE_VISIT';
  return (
    <section className={styles.section} aria-label="Visit and emergency services">
      <h3 className={styles.sectionTitle}>Visit and emergency services</h3>
      <div className={styles.serviceRow}>
        <label className={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={stable}
            disabled={disabled}
            onChange={(event) => onChange({
              ...value,
              visit_stability: event.target.checked ? 'STABLE_VISIT' : 'NOT_STABLE_VISIT',
              maximum_working_radius_km: event.target.checked ? value.maximum_working_radius_km : '',
            })}
          />
          <span>Offers stable visits</span>
        </label>
        {stable && (
          <Input
            label="Maximum working radius (km)"
            type="number"
            min={0.01}
            step="any"
            value={value.maximum_working_radius_km}
            onChange={(event) => onChange({ ...value, maximum_working_radius_km: event.target.value })}
            error={errors.maximum_working_radius_km}
            required
            disabled={disabled}
          />
        )}
      </div>
      <div className={styles.serviceRow}>
        <label className={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={value.emergency_services_available}
            disabled={disabled}
            onChange={(event) => onChange({
              ...value,
              emergency_services_available: event.target.checked,
              ...(event.target.checked ? {} : { emergency_local_number: '' }),
            })}
          />
          <span>Emergency services available</span>
        </label>
        {value.emergency_services_available && (
          <FormField label="Emergency contact number" required>
            <PhoneInput
              countryCode={value.emergency_country_code}
              isoCode={value.emergency_iso_code}
              number={value.emergency_local_number}
              onCountryChange={(countryCode, isoCode) =>
                onChange({ ...value, emergency_country_code: countryCode, emergency_iso_code: isoCode })}
              onNumberChange={(number) => onChange({ ...value, emergency_local_number: number })}
              error={errors.emergency_contact_number}
              disabled={disabled}
              ariaLabel="Emergency contact number"
            />
          </FormField>
        )}
      </div>
    </section>
  );
}

interface AddressLookupState {
  candidates: PostalCandidate[];
  message: string;
  loading: boolean;
}

export function InvitationAddresses({
  value,
  onChange,
  errors = {},
  disabled = false,
}: InvitationAddressesProps) {
  const [lookup, setLookup] = useState<Record<string, AddressLookupState>>({});
  const requestedPostalCodes = useRef(new Map(
    value.map((address) => [address.key, address.postal_code.trim()])
  ));
  const postalSignature = value.map((address) => `${address.key}:${address.postal_code.trim()}`).join('|');

  useEffect(() => {
    const timers: number[] = [];
    const controllers: AbortController[] = [];
    for (const address of value) {
      const postalCode = address.postal_code.trim();
      if (postalCode.length < 4) continue;
      const lastPostalCode = requestedPostalCodes.current.get(address.key);
      if (lastPostalCode === postalCode) continue;
      requestedPostalCodes.current.set(address.key, postalCode);
      const controller = new AbortController();
      controllers.push(controller);
      const timer = window.setTimeout(async () => {
        setLookup((current) => ({
          ...current,
          [address.key]: { candidates: [], message: '', loading: true },
        }));
        try {
          const result = await lookupProviderPostalCode(postalCode, controller.signal);
          if (controller.signal.aborted) return;
          setLookup((current) => ({
            ...current,
            [address.key]: {
              candidates: result.candidates,
              message: result.status === 'no_match'
                ? 'No matching place found. You can enter the address manually.'
                : result.status === 'unavailable'
                  ? 'Postal lookup is unavailable. You can enter the address manually.'
                  : 'Choose a matching place or enter the address manually.',
              loading: false,
            },
          }));
        } catch {
          if (!controller.signal.aborted) {
            setLookup((current) => ({
              ...current,
              [address.key]: {
                candidates: [],
                message: 'Postal lookup is unavailable. You can enter the address manually.',
                loading: false,
              },
            }));
          }
        }
      }, 550);
      timers.push(timer);
    }
    return () => {
      timers.forEach(window.clearTimeout);
      controllers.forEach((controller) => controller.abort());
    };
    // Existing postal values are restored from a saved invitation and should
    // not trigger a lookup until the invitee edits the field.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postalSignature]);

  function update(index: number, patch: Partial<InvitationAddress>) {
    onChange(value.map((address, i) => i === index ? { ...address, ...patch } : address));
  }

  function selectCandidate(index: number, candidate: PostalCandidate) {
    const address = value[index];
    const selectedPostalCode = candidate.postal_code || address.postal_code;
    requestedPostalCodes.current.set(address.key, selectedPostalCode.trim());
    update(index, {
      postal_code: selectedPostalCode,
      country: Country.getCountryByCode(candidate.country_code?.toUpperCase() ?? '')?.name ?? candidate.country,
      state_province: candidate.state_province || '',
      city: candidate.city,
    });
    setLookup((current) => ({
      ...current,
      [address.key]: { candidates: [], message: 'selected', loading: false },
    }));
  }

  return (
    <section className={styles.section} aria-label="Practice addresses">
      <h3 className={styles.sectionTitle}>Practice addresses</h3>
      <p className={styles.hint}>Add named locations where patients can visit you. Choose a postal-code match or enter location details manually.</p>
      {value.map((address, index) => {
        const addressLookup = lookup[address.key];
        return (
          <fieldset className={styles.addressCard} key={address.key}>
            <legend>{address.name.trim() || `Address ${index + 1}`}</legend>
            <Input label="Location name" placeholder="e.g. Main clinic" value={address.name}
              onChange={(event) => update(index, { name: event.target.value })}
              error={errors[`address_${index}_name`]} disabled={disabled} />
            <Input label="Address line 1" value={address.address_line_1}
              onChange={(event) => update(index, { address_line_1: event.target.value })}
              error={errors[`address_${index}_address_line_1`]} disabled={disabled} />
            <Input label="Address line 2" value={address.address_line_2}
              onChange={(event) => update(index, { address_line_2: event.target.value })} disabled={disabled} />
            <Input label="Postal / ZIP code" autoComplete="postal-code" value={address.postal_code}
              onChange={(event) => {
                update(index, { postal_code: event.target.value });
                requestedPostalCodes.current.delete(address.key);
                setLookup((current) => ({ ...current, [address.key]: { candidates: [], message: '', loading: false } }));
              }}
              error={errors[`address_${index}_postal_code`]} disabled={disabled} />
            {addressLookup?.loading && <p className={styles.hint} role="status">Looking up postal code…</p>}
            {addressLookup?.message && addressLookup.message !== 'selected' && (
              <p className={styles.hint} role="status">{addressLookup.message}</p>
            )}
            {!!addressLookup?.candidates.length && (
              <div className={styles.candidates} aria-label={`Postal matches for address ${index + 1}`}>
                {addressLookup.candidates.map((candidate, candidateIndex) => (
                  <button className={styles.candidate} type="button" key={`${candidate.postal_code}-${candidate.city}-${candidateIndex}`}
                    onClick={() => selectCandidate(index, candidate)} disabled={disabled}>
                    {candidate.display_name}
                  </button>
                ))}
                <button className={styles.manualButton} type="button"
                  onClick={() => setLookup((current) => ({
                    ...current,
                    [address.key]: { candidates: [], message: 'Enter location details manually.', loading: false },
                  }))} disabled={disabled}>
                  Enter location manually
                </button>
              </div>
            )}
            <Input label="City" value={address.city} onChange={(event) => update(index, { city: event.target.value })}
              error={errors[`address_${index}_city`]} disabled={disabled} />
            <Input label="State / province" value={address.state_province}
              onChange={(event) => update(index, { state_province: event.target.value })} disabled={disabled} />
            <Input label="Country" value={address.country}
              onChange={(event) => update(index, { country: event.target.value })} disabled={disabled} />
            {value.length > 1 && (
              <button className={styles.removeButton} type="button" disabled={disabled}
                onClick={() => onChange(value.filter((_, i) => i !== index))}>
                Remove address
              </button>
            )}
          </fieldset>
        );
      })}
      <button className={styles.addButton} type="button" disabled={disabled}
        onClick={() => onChange([...value, emptyInvitationAddress(`address-${Date.now()}-${value.length}`)])}>
        + Add address
      </button>
    </section>
  );
}