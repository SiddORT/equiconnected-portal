import type { EmailEntry } from '@/components/admin/MultiEmailField';
import type { PhoneEntry } from '@/components/admin/MultiPhoneField';
import { COUNTRY_CODES, DEFAULT_COUNTRY } from '@/utils/countryCodes';
import type { ProviderPortalEditableProfile } from '@/types';

function phoneEntryFromScalar(value: string): PhoneEntry {
  const normalized = value.trim();
  const country = normalized.startsWith('+')
    ? [...COUNTRY_CODES]
      .sort((a, b) => b.dialCode.length - a.dialCode.length)
      .find((candidate) => normalized.startsWith(candidate.dialCode))
    : undefined;

  return {
    country_code: country?.dialCode ?? DEFAULT_COUNTRY.dialCode,
    iso_code: country?.code ?? DEFAULT_COUNTRY.code,
    number: country ? normalized.slice(country.dialCode.length).trim() : normalized,
    is_primary: true,
  };
}

export function portalContactsFromProfile(profile: ProviderPortalEditableProfile): {
  phones: PhoneEntry[];
  emails: EmailEntry[];
} {
  const phones = profile.phones.length > 0
    ? profile.phones.map((phone) => ({ ...phone, is_primary: phone.is_primary ?? false }))
    : profile.phone?.trim()
      ? [phoneEntryFromScalar(profile.phone)]
      : [];
  const emails = profile.emails.length > 0
    ? profile.emails.map((email) => ({ ...email, is_primary: email.is_primary ?? false }))
    : profile.email?.trim()
      ? [{ email: profile.email.trim(), is_primary: true }]
      : [];

  return { phones, emails };
}

export function portalScalarContactsFromCollections(phones: PhoneEntry[], emails: EmailEntry[]) {
  const primaryPhone = phones.find((entry) => entry.is_primary) ?? phones[0];
  const primaryEmail = emails.find((entry) => entry.is_primary) ?? emails[0];

  return {
    phone: primaryPhone?.number.trim()
      ? `${primaryPhone.country_code} ${primaryPhone.number.trim()}`
      : null,
    email: primaryEmail?.email.trim() || null,
  };
}