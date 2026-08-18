/**
 * Country dial-code data for the phone country-code picker.
 * Common countries first, then the rest sorted alphabetically.
 */

export interface CountryCode {
  code: string;      // ISO 3166-1 alpha-2
  dialCode: string;  // e.g. "+1"
  flag: string;      // flag emoji
  name: string;
}

/** Countries pinned to the top of the picker, in this order. */
const COMMON: CountryCode[] = [
  { code: 'US', dialCode: '+1', flag: '🇺🇸', name: 'United States' },
  { code: 'GB', dialCode: '+44', flag: '🇬🇧', name: 'United Kingdom' },
  { code: 'CA', dialCode: '+1', flag: '🇨🇦', name: 'Canada' },
  { code: 'AU', dialCode: '+61', flag: '🇦🇺', name: 'Australia' },
  { code: 'IN', dialCode: '+91', flag: '🇮🇳', name: 'India' },
  { code: 'PK', dialCode: '+92', flag: '🇵🇰', name: 'Pakistan' },
  { code: 'DE', dialCode: '+49', flag: '🇩🇪', name: 'Germany' },
  { code: 'FR', dialCode: '+33', flag: '🇫🇷', name: 'France' },
  { code: 'ES', dialCode: '+34', flag: '🇪🇸', name: 'Spain' },
  { code: 'IT', dialCode: '+39', flag: '🇮🇹', name: 'Italy' },
  { code: 'AE', dialCode: '+971', flag: '🇦🇪', name: 'United Arab Emirates' },
  { code: 'SA', dialCode: '+966', flag: '🇸🇦', name: 'Saudi Arabia' },
];

const REST: CountryCode[] = [
  { code: 'AF', dialCode: '+93', flag: '🇦🇫', name: 'Afghanistan' },
  { code: 'AL', dialCode: '+355', flag: '🇦🇱', name: 'Albania' },
  { code: 'DZ', dialCode: '+213', flag: '🇩🇿', name: 'Algeria' },
  { code: 'AR', dialCode: '+54', flag: '🇦🇷', name: 'Argentina' },
  { code: 'AM', dialCode: '+374', flag: '🇦🇲', name: 'Armenia' },
  { code: 'AT', dialCode: '+43', flag: '🇦🇹', name: 'Austria' },
  { code: 'AZ', dialCode: '+994', flag: '🇦🇿', name: 'Azerbaijan' },
  { code: 'BH', dialCode: '+973', flag: '🇧🇭', name: 'Bahrain' },
  { code: 'BD', dialCode: '+880', flag: '🇧🇩', name: 'Bangladesh' },
  { code: 'BY', dialCode: '+375', flag: '🇧🇾', name: 'Belarus' },
  { code: 'BE', dialCode: '+32', flag: '🇧🇪', name: 'Belgium' },
  { code: 'BO', dialCode: '+591', flag: '🇧🇴', name: 'Bolivia' },
  { code: 'BA', dialCode: '+387', flag: '🇧🇦', name: 'Bosnia and Herzegovina' },
  { code: 'BR', dialCode: '+55', flag: '🇧🇷', name: 'Brazil' },
  { code: 'BG', dialCode: '+359', flag: '🇧🇬', name: 'Bulgaria' },
  { code: 'KH', dialCode: '+855', flag: '🇰🇭', name: 'Cambodia' },
  { code: 'CM', dialCode: '+237', flag: '🇨🇲', name: 'Cameroon' },
  { code: 'CL', dialCode: '+56', flag: '🇨🇱', name: 'Chile' },
  { code: 'CN', dialCode: '+86', flag: '🇨🇳', name: 'China' },
  { code: 'CO', dialCode: '+57', flag: '🇨🇴', name: 'Colombia' },
  { code: 'CR', dialCode: '+506', flag: '🇨🇷', name: 'Costa Rica' },
  { code: 'HR', dialCode: '+385', flag: '🇭🇷', name: 'Croatia' },
  { code: 'CU', dialCode: '+53', flag: '🇨🇺', name: 'Cuba' },
  { code: 'CY', dialCode: '+357', flag: '🇨🇾', name: 'Cyprus' },
  { code: 'CZ', dialCode: '+420', flag: '🇨🇿', name: 'Czechia' },
  { code: 'DK', dialCode: '+45', flag: '🇩🇰', name: 'Denmark' },
  { code: 'DO', dialCode: '+1', flag: '🇩🇴', name: 'Dominican Republic' },
  { code: 'EC', dialCode: '+593', flag: '🇪🇨', name: 'Ecuador' },
  { code: 'EG', dialCode: '+20', flag: '🇪🇬', name: 'Egypt' },
  { code: 'SV', dialCode: '+503', flag: '🇸🇻', name: 'El Salvador' },
  { code: 'EE', dialCode: '+372', flag: '🇪🇪', name: 'Estonia' },
  { code: 'ET', dialCode: '+251', flag: '🇪🇹', name: 'Ethiopia' },
  { code: 'FI', dialCode: '+358', flag: '🇫🇮', name: 'Finland' },
  { code: 'GE', dialCode: '+995', flag: '🇬🇪', name: 'Georgia' },
  { code: 'GH', dialCode: '+233', flag: '🇬🇭', name: 'Ghana' },
  { code: 'GR', dialCode: '+30', flag: '🇬🇷', name: 'Greece' },
  { code: 'GT', dialCode: '+502', flag: '🇬🇹', name: 'Guatemala' },
  { code: 'HN', dialCode: '+504', flag: '🇭🇳', name: 'Honduras' },
  { code: 'HK', dialCode: '+852', flag: '🇭🇰', name: 'Hong Kong' },
  { code: 'HU', dialCode: '+36', flag: '🇭🇺', name: 'Hungary' },
  { code: 'IS', dialCode: '+354', flag: '🇮🇸', name: 'Iceland' },
  { code: 'ID', dialCode: '+62', flag: '🇮🇩', name: 'Indonesia' },
  { code: 'IR', dialCode: '+98', flag: '🇮🇷', name: 'Iran' },
  { code: 'IQ', dialCode: '+964', flag: '🇮🇶', name: 'Iraq' },
  { code: 'IE', dialCode: '+353', flag: '🇮🇪', name: 'Ireland' },
  { code: 'IL', dialCode: '+972', flag: '🇮🇱', name: 'Israel' },
  { code: 'JM', dialCode: '+1', flag: '🇯🇲', name: 'Jamaica' },
  { code: 'JP', dialCode: '+81', flag: '🇯🇵', name: 'Japan' },
  { code: 'JO', dialCode: '+962', flag: '🇯🇴', name: 'Jordan' },
  { code: 'KZ', dialCode: '+7', flag: '🇰🇿', name: 'Kazakhstan' },
  { code: 'KE', dialCode: '+254', flag: '🇰🇪', name: 'Kenya' },
  { code: 'KW', dialCode: '+965', flag: '🇰🇼', name: 'Kuwait' },
  { code: 'LV', dialCode: '+371', flag: '🇱🇻', name: 'Latvia' },
  { code: 'LB', dialCode: '+961', flag: '🇱🇧', name: 'Lebanon' },
  { code: 'LY', dialCode: '+218', flag: '🇱🇾', name: 'Libya' },
  { code: 'LT', dialCode: '+370', flag: '🇱🇹', name: 'Lithuania' },
  { code: 'LU', dialCode: '+352', flag: '🇱🇺', name: 'Luxembourg' },
  { code: 'MY', dialCode: '+60', flag: '🇲🇾', name: 'Malaysia' },
  { code: 'MV', dialCode: '+960', flag: '🇲🇻', name: 'Maldives' },
  { code: 'MT', dialCode: '+356', flag: '🇲🇹', name: 'Malta' },
  { code: 'MX', dialCode: '+52', flag: '🇲🇽', name: 'Mexico' },
  { code: 'MD', dialCode: '+373', flag: '🇲🇩', name: 'Moldova' },
  { code: 'MC', dialCode: '+377', flag: '🇲🇨', name: 'Monaco' },
  { code: 'MN', dialCode: '+976', flag: '🇲🇳', name: 'Mongolia' },
  { code: 'ME', dialCode: '+382', flag: '🇲🇪', name: 'Montenegro' },
  { code: 'MA', dialCode: '+212', flag: '🇲🇦', name: 'Morocco' },
  { code: 'MM', dialCode: '+95', flag: '🇲🇲', name: 'Myanmar' },
  { code: 'NP', dialCode: '+977', flag: '🇳🇵', name: 'Nepal' },
  { code: 'NL', dialCode: '+31', flag: '🇳🇱', name: 'Netherlands' },
  { code: 'NZ', dialCode: '+64', flag: '🇳🇿', name: 'New Zealand' },
  { code: 'NI', dialCode: '+505', flag: '🇳🇮', name: 'Nicaragua' },
  { code: 'NG', dialCode: '+234', flag: '🇳🇬', name: 'Nigeria' },
  { code: 'MK', dialCode: '+389', flag: '🇲🇰', name: 'North Macedonia' },
  { code: 'NO', dialCode: '+47', flag: '🇳🇴', name: 'Norway' },
  { code: 'OM', dialCode: '+968', flag: '🇴🇲', name: 'Oman' },
  { code: 'PA', dialCode: '+507', flag: '🇵🇦', name: 'Panama' },
  { code: 'PY', dialCode: '+595', flag: '🇵🇾', name: 'Paraguay' },
  { code: 'PE', dialCode: '+51', flag: '🇵🇪', name: 'Peru' },
  { code: 'PH', dialCode: '+63', flag: '🇵🇭', name: 'Philippines' },
  { code: 'PL', dialCode: '+48', flag: '🇵🇱', name: 'Poland' },
  { code: 'PT', dialCode: '+351', flag: '🇵🇹', name: 'Portugal' },
  { code: 'QA', dialCode: '+974', flag: '🇶🇦', name: 'Qatar' },
  { code: 'RO', dialCode: '+40', flag: '🇷🇴', name: 'Romania' },
  { code: 'RU', dialCode: '+7', flag: '🇷🇺', name: 'Russia' },
  { code: 'RS', dialCode: '+381', flag: '🇷🇸', name: 'Serbia' },
  { code: 'SG', dialCode: '+65', flag: '🇸🇬', name: 'Singapore' },
  { code: 'SK', dialCode: '+421', flag: '🇸🇰', name: 'Slovakia' },
  { code: 'SI', dialCode: '+386', flag: '🇸🇮', name: 'Slovenia' },
  { code: 'ZA', dialCode: '+27', flag: '🇿🇦', name: 'South Africa' },
  { code: 'KR', dialCode: '+82', flag: '🇰🇷', name: 'South Korea' },
  { code: 'LK', dialCode: '+94', flag: '🇱🇰', name: 'Sri Lanka' },
  { code: 'SD', dialCode: '+249', flag: '🇸🇩', name: 'Sudan' },
  { code: 'SE', dialCode: '+46', flag: '🇸🇪', name: 'Sweden' },
  { code: 'CH', dialCode: '+41', flag: '🇨🇭', name: 'Switzerland' },
  { code: 'SY', dialCode: '+963', flag: '🇸🇾', name: 'Syria' },
  { code: 'TW', dialCode: '+886', flag: '🇹🇼', name: 'Taiwan' },
  { code: 'TZ', dialCode: '+255', flag: '🇹🇿', name: 'Tanzania' },
  { code: 'TH', dialCode: '+66', flag: '🇹🇭', name: 'Thailand' },
  { code: 'TN', dialCode: '+216', flag: '🇹🇳', name: 'Tunisia' },
  { code: 'TR', dialCode: '+90', flag: '🇹🇷', name: 'Turkey' },
  { code: 'UG', dialCode: '+256', flag: '🇺🇬', name: 'Uganda' },
  { code: 'UA', dialCode: '+380', flag: '🇺🇦', name: 'Ukraine' },
  { code: 'UY', dialCode: '+598', flag: '🇺🇾', name: 'Uruguay' },
  { code: 'UZ', dialCode: '+998', flag: '🇺🇿', name: 'Uzbekistan' },
  { code: 'VE', dialCode: '+58', flag: '🇻🇪', name: 'Venezuela' },
  { code: 'VN', dialCode: '+84', flag: '🇻🇳', name: 'Vietnam' },
  { code: 'YE', dialCode: '+967', flag: '🇾🇪', name: 'Yemen' },
  { code: 'ZW', dialCode: '+263', flag: '🇿🇼', name: 'Zimbabwe' },
];

export const COUNTRY_CODES: CountryCode[] = [...COMMON, ...REST];

export const DEFAULT_COUNTRY = COMMON[0];

/** Find the first country entry matching a dial code (e.g. "+44"). */
export function findByDialCode(dialCode: string): CountryCode | undefined {
  return COUNTRY_CODES.find((c) => c.dialCode === dialCode);
}

/** Find a country entry by its ISO 3166-1 alpha-2 code (e.g. "CA"). */
export function findByIsoCode(isoCode: string): CountryCode | undefined {
  return COUNTRY_CODES.find((c) => c.code === isoCode);
}
