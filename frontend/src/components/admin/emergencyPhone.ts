import { COUNTRY_CODES, DEFAULT_COUNTRY } from '@/utils/countryCodes';

/** Match the invitation emergency-phone convention, including compact prefixes. */
export function emergencyPhoneFromNumber(value: string | null | undefined) {
  const number = value?.trim() ?? '';
  const country = number.startsWith('+')
    ? COUNTRY_CODES.filter((candidate) => number.startsWith(candidate.dialCode))
      .sort((a, b) => b.dialCode.length - a.dialCode.length)[0]
    : undefined;
  return {
    countryCode: (country ?? DEFAULT_COUNTRY).dialCode,
    isoCode: (country ?? DEFAULT_COUNTRY).code,
    number: country ? number.slice(country.dialCode.length).trim() : number,
  };
}

export function completeEmergencyNumber(phone: ReturnType<typeof emergencyPhoneFromNumber>) {
  const local = phone.number.trim();
  // Retain unrecognized historical international prefixes rather than adding another.
  return local ? (local.startsWith('+') ? local : `${phone.countryCode} ${local}`) : null;
}