import { useEffect, useRef, useState } from 'react';
import type { PostalCandidate } from '@/api/auth';
import { FormField } from '@/components/ui/FormField';
import { Input } from '@/components/ui/Input';
import { PhoneInput } from '@/components/ui/PhoneInput';
import type { DraftLocation, InvitationDraftPayload, InvitationDraftProvider, VisitStability } from '@/types';
import { COUNTRY_CODES, DEFAULT_COUNTRY } from '@/utils/countryCodes';
import { normalizePostalCountry, postalLookupMessage, startPostalLookup } from '@/utils/postalLookup';
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
  if (locations.length === 0) return [emptyInvitationAddress()];
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
  if (addresses.length > 1) throw new Error('Choose one saved address before continuing.');
  const filled = addresses.filter((address) =>
    Object.entries(address).some(([key, field]) => key !== 'key' && Boolean(field.trim()))
  ).filter((address) => address.address_line_1.trim() && address.city.trim());
  if (filled.length === 0) return undefined;
  return filled.map((address) => ({
    name: address.name.trim() || null,
    address_line_1: address.address_line_1.trim(),
    address_line_2: address.address_line_2.trim() || null,
    city: address.city.trim(),
    state_province: address.state_province.trim() || null,
    country: address.country.trim() || null,
    postal_code: address.postal_code.trim() || null,
    is_primary: true,
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
  const addressLookups = useRef(new Map<string, { postalCode: string; cancel: () => void }>());
  // Keep legacy choices available if the invitee changes their mind before saving.
  const legacyAddresses = useRef(value.length > 1 ? value : []);
  const postalSignature = value.map((address) => `${address.key}:${address.postal_code.trim()}`).join('|');

  useEffect(() => {
    const currentPostalCodes = new Map(value.map((address) => [address.key, address.postal_code.trim()]));
    for (const [key, request] of addressLookups.current) {
      if (currentPostalCodes.get(key) === request.postalCode) continue;
      request.cancel();
      addressLookups.current.delete(key);
      if (!currentPostalCodes.has(key)) requestedPostalCodes.current.delete(key);
      setLookup((current) => ({
        ...current,
        [key]: { candidates: [], message: '', loading: false },
      }));
    }

    for (const address of value) {
      const postalCode = address.postal_code.trim();
      if (postalCode.length < 4) continue;
      const lastPostalCode = requestedPostalCodes.current.get(address.key);
      if (lastPostalCode === postalCode) continue;
      requestedPostalCodes.current.set(address.key, postalCode);
      setLookup((current) => ({
        ...current,
        [address.key]: { candidates: [], message: '', loading: false },
      }));
      const cancel = startPostalLookup(postalCode, {
        onLoading: () => {
          setLookup((current) => ({
            ...current,
            [address.key]: { candidates: [], message: '', loading: true },
          }));
        },
        onResult: (result) => {
          addressLookups.current.delete(address.key);
          setLookup((current) => ({
            ...current,
            [address.key]: {
              candidates: result.candidates,
              message: postalLookupMessage(result, 'invitation'),
              loading: false,
            },
          }));
        },
      });
      addressLookups.current.set(address.key, { postalCode, cancel });
    }
    // Existing postal values are restored from a saved invitation and should
    // not trigger a lookup until the invitee edits the field.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postalSignature]);

  useEffect(() => () => {
    for (const [key, request] of addressLookups.current) {
      request.cancel();
      if (requestedPostalCodes.current.get(key) === request.postalCode) {
        requestedPostalCodes.current.delete(key);
      }
    }
    addressLookups.current.clear();
  }, []);

  function clearAddressLookup(key: string) {
    addressLookups.current.get(key)?.cancel();
    addressLookups.current.delete(key);
    setLookup((current) => ({
      ...current,
      [key]: { candidates: [], message: '', loading: false },
    }));
  }

  function update(index: number, patch: Partial<InvitationAddress>) {
    const address = value[index];
    const locationFields: (keyof InvitationAddress)[] = [
      'postal_code', 'country', 'state_province', 'city', 'address_line_1', 'address_line_2',
    ];
    if (locationFields.some((field) => Object.prototype.hasOwnProperty.call(patch, field))) {
      clearAddressLookup(address.key);
      if (Object.prototype.hasOwnProperty.call(patch, 'postal_code')) {
        requestedPostalCodes.current.delete(address.key);
      }
    }
    onChange(value.map((current, i) => i === index ? { ...current, ...patch } : current));
  }

  function selectCandidate(index: number, candidate: PostalCandidate) {
    const address = value[index];
    const selectedPostalCode = candidate.postal_code || address.postal_code;
    update(index, {
      postal_code: selectedPostalCode,
      country: normalizePostalCountry(candidate),
      state_province: candidate.state_province || '',
      city: candidate.city,
    });
    requestedPostalCodes.current.set(address.key, selectedPostalCode.trim());
    setLookup((current) => ({
      ...current,
      [address.key]: { candidates: [], message: 'selected', loading: false },
    }));
  }

  return (
    <section className={styles.section} aria-label="Practice addresses">
      <h3 className={styles.sectionTitle}>Practice addresses</h3>
      {legacyAddresses.current.length > 1 && (
        <div className={styles.legacyChoices} role="group" aria-label="Choose an address to keep">
          <p className={styles.hint}>This invitation has multiple saved addresses. Choose the one to keep before saving or submitting. The others will be removed from this invitation.</p>
          {legacyAddresses.current.map((address, index) => (
            <button type="button" className={styles.candidate} key={address.key} disabled={disabled}
              aria-pressed={value.length === 1 && value[0].key === address.key}
              onClick={() => onChange([address])}>
              Keep {address.name.trim() || `Address ${index + 1}`} — {address.address_line_1}, {address.city}
            </button>
          ))}
          {errors.address_choice && <p role="alert" className={styles.error}>{errors.address_choice}</p>}
        </div>
      )}
      {value.length <= 1 && (
      <>
      <p className={styles.hint}>Choose a postal-code match or enter location details manually.</p>
      {value.slice(0, 1).map((address, index) => {
        const addressLookup = lookup[address.key];
        const postalId = `invitation-postal-${address.key}`;
        const postalFeedback = addressLookup?.loading ||
          (addressLookup?.message && addressLookup.message !== 'selected');
        return (
          <fieldset className={styles.addressCard} key={address.key}>
            <legend>Practice address</legend>
            <div className={styles.firstRow}>
              <Input label="Location name" placeholder="e.g. Main clinic" value={address.name}
                onChange={(event) => update(index, { name: event.target.value })}
                error={errors[`address_${index}_name`]} disabled={disabled} />
              <div className={styles.postalField}>
                <Input label="Postal / ZIP code" id={postalId} autoComplete="postal-code" value={address.postal_code}
                  aria-describedby={[
                    errors[`address_${index}_postal_code`] ? `${postalId}-error` : '',
                    postalFeedback ? `${postalId}-lookup` : '',
                  ].filter(Boolean).join(' ') || undefined}
                  onChange={(event) => update(index, { postal_code: event.target.value })}
                  error={errors[`address_${index}_postal_code`]} disabled={disabled} />
                {addressLookup?.loading && <p id={`${postalId}-lookup`} className={styles.hint} role="status">Looking up postal code…</p>}
                {addressLookup?.message && addressLookup.message !== 'selected' && (
                  <p id={`${postalId}-lookup`} className={styles.hint} role="status">{addressLookup.message}</p>
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
                    onClick={() => {
                      clearAddressLookup(address.key);
                      setLookup((current) => ({
                        ...current,
                        [address.key]: { candidates: [], message: 'Enter location details manually.', loading: false },
                      }));
                    }} disabled={disabled}>
                    Enter location manually
                  </button>
                </div>
              )}
              </div>
            </div>
            <div className={styles.placeRow}>
              <Input label="Country" value={address.country}
                onChange={(event) => update(index, { country: event.target.value })} disabled={disabled} />
              <Input label="State / province" value={address.state_province}
                onChange={(event) => update(index, { state_province: event.target.value })} disabled={disabled} />
              <Input label="City" value={address.city} onChange={(event) => update(index, { city: event.target.value })}
                error={errors[`address_${index}_city`]} disabled={disabled} />
            </div>
            <Input label="Address line 1" value={address.address_line_1}
              onChange={(event) => update(index, { address_line_1: event.target.value })}
              error={errors[`address_${index}_address_line_1`]} disabled={disabled} />
            <Input label="Address line 2" value={address.address_line_2}
              onChange={(event) => update(index, { address_line_2: event.target.value })} disabled={disabled} />
          </fieldset>
        );
      })}
      </>
      )}
    </section>
  );
}