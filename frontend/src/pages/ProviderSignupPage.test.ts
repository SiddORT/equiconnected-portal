import { describe, expect, it } from 'vitest';
import type { ProviderRegistrationRequest } from '@/types';
import { validateProviderSignup } from './ProviderSignupPage';

const validApplication: ProviderRegistrationRequest = {
  first_name: 'Amina',
  last_name: 'Veterinarian',
  email: 'amina@example.com',
  mobile_number: '50 123 4567',
  country: 'United States',
  state_province: 'California',
  city: 'Los Angeles',
  password: 'HorseCare2026',
  password_confirmation: 'HorseCare2026',
  role: 'PROVIDER',
  provider_type: 'CLINIC',
  provider_name: 'Amina Equine Clinic',
  visit_stability: 'STABLE_VISIT',
  accept_terms: true,
  accept_privacy: true,
};

describe('provider registration validation', () => {
  it('requires the listing essentials and a complete location', () => {
    const errors = validateProviderSignup({
      ...validApplication,
      provider_name: '',
      state_province: '',
    });
    expect(errors.provider_name).toBe('This field is required');
    expect(errors.state_province).toBe('Select a state or province');
  });

  it('accepts a valid provider application with one selected provider type', () => {
    expect(validateProviderSignup(validApplication)).toEqual({});
  });
});