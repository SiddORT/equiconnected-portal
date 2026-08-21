import { describe, expect, it } from 'vitest';
import type { RegistrationRequest } from '@/types';
import { validateSignup } from './SignupPage';

const validRegistration: RegistrationRequest = {
  first_name: 'Amina',
  last_name: 'Rider',
  email: 'amina@example.com',
  mobile_number: '50 123 4567',
  country: 'United States',
  state_province: 'California',
  city: 'Los Angeles',
  password: 'HorseCare2026',
  password_confirmation: 'HorseCare2026',
  role: 'HORSE_OWNER',
  accept_terms: true,
  accept_privacy: true,
};

describe('signup location validation', () => {
  it('requires a state or province when the selected country provides one', () => {
    expect(validateSignup({ ...validRegistration, state_province: '' }).state_province).toBe(
      'Select a state or province'
    );
  });

  it('accepts a coherent country, state, and city selection', () => {
    expect(validateSignup(validRegistration)).toEqual({});
  });
});