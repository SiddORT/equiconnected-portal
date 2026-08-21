import { describe, expect, it } from 'vitest';
import { calculateProfileCompletion } from './profileCompletion';
import type { MemberProfile } from '@/types';
import { getCountryOptions, getStateOptions } from '@/utils/geography';

const completePersonal: MemberProfile = {
  first_name: 'Amina',
  last_name: 'Rider',
  email: 'amina@example.com',
  mobile_number: '+1 555 123 4567',
  address: '12 Oak Lane',
  country: 'United States',
  state_province: 'Texas',
  city: 'Austin',
  postal_code: '78701',
  roles: ['horse_owner'],
  stable_profile: null,
  horses: [{
    id: 'horse-1',
    name: 'Juniper',
    sex: 'MARE',
    registered_name: null,
    breed: null,
    date_of_birth: null,
    color: null,
    primary_discipline: null,
    registration_number: null,
    microchip_number: null,
    description: null,
    photo_reference: null,
    updated_at: '',
  }],
};

describe('calculateProfileCompletion', () => {
  it('counts only applicable roles and ignores optional horse details', () => {
    const completion = calculateProfileCompletion(completePersonal);

    expect(completion.percentage).toBe(100);
    expect(completion.isComplete).toBe(true);
    expect(completion.sections).toHaveLength(2);
    expect(completion.sections.find((section) => section.id === 'horses')?.complete).toBe(true);
  });

  it('does not require a state for countries without state choices', () => {
    const countryWithoutStates = getCountryOptions()
      .find((country) => getStateOptions(country.value).length === 0);
    expect(countryWithoutStates).toBeTruthy();
    const profile = {
      ...completePersonal,
      country: countryWithoutStates!.value,
      state_province: null,
    };
    const completion = calculateProfileCompletion(profile);

    expect(completion.sections[0].missing).not.toContain('Choose your state or province.');
    expect(completion.sections[0].complete).toBe(true);
  });

  it('does not require a stable state for countries without state choices', () => {
    const countryWithoutStates = getCountryOptions()
      .find((country) => getStateOptions(country.value).length === 0);
    expect(countryWithoutStates).toBeTruthy();
    const completion = calculateProfileCompletion({
      ...completePersonal,
      roles: ['stable_manager'],
      horses: [],
      stable_profile: {
        id: 'stable-1',
        name: 'Oak Valley Stables',
        description: null,
        address: '14 Oak Lane',
        country: countryWithoutStates!.value,
        state_province: null,
        city: 'Central',
        postal_code: '1000',
        contact_name: 'Amina Rider',
        contact_phone: '+1 555 123 4567',
        contact_email: 'amina@example.com',
        updated_at: '',
      },
    });

    const stable = completion.sections.find((section) => section.id === 'stable')!;
    expect(stable.missing).not.toContain('Choose the stable state or province.');
    expect(stable.complete).toBe(true);
  });

  it('returns the first role-relevant missing action and excludes non-applicable sections', () => {
    const completion = calculateProfileCompletion({
      ...completePersonal,
      first_name: null,
      address: null,
      stable_profile: null,
      roles: ['stable_manager'],
      horses: [],
    });

    expect(completion.nextSection).toBe('personal');
    expect(completion.nextAction).toBe('Add your first name.');
    expect(completion.sections.map((section) => section.id)).toEqual(['personal', 'stable']);
    expect(completion.percentage).toBeLessThan(100);
  });
});