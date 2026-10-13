import { describe, expect, it } from 'vitest';
import { DEFAULT_COUNTRY, findByDialCode, findByIsoCode } from './countryCodes';
import { emptyPhoneEntry } from '@/components/admin/MultiPhoneField';

describe('phone country defaults', () => {
  it('uses UAE for the shared default and each new phone entry', () => {
    expect(DEFAULT_COUNTRY.code).toBe('AE');
    expect(DEFAULT_COUNTRY.dialCode).toBe('+971');
    expect(emptyPhoneEntry()).toMatchObject({ country_code: '+971', iso_code: 'AE' });
  });

  it('keeps saved and selected country codes available', () => {
    expect(findByDialCode('+1')?.code).toBe('US');
    expect(findByIsoCode('CA')?.dialCode).toBe('+1');
    expect(findByDialCode('+44')?.code).toBe('GB');
  });
});
